# Database Architecture

## Overview

Two-layer data strategy:
- **AlloyDB** — operational database, real-time semantic search via pgvector
- **BigQuery** — analytics warehouse, full-history vector search, long-term storage

---

## AlloyDB Schema

### `accounts`
Tracks which Twitter accounts to monitor.

```sql
CREATE TABLE accounts (
  id            TEXT PRIMARY KEY,          -- Twitter user_id
  username      TEXT NOT NULL UNIQUE,      -- @handle (without @)
  display_name  TEXT,
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  active        BOOLEAN DEFAULT TRUE
);
```

### `tweets`
Core table. One row per tweet. The `embedding` is generated from the tweet text
**plus any image descriptions** produced by Gemini Vision, so image content is
fully searchable without a separate multimodal model.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tweets (
  id              TEXT PRIMARY KEY,        -- Twitter tweet_id
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  text            TEXT NOT NULL,           -- original tweet text
  embed_text      TEXT NOT NULL,           -- text + image descriptions (used for embedding)
  url             TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL,
  likes           INT DEFAULT 0,
  retweets        INT DEFAULT 0,
  replies         INT DEFAULT 0,
  is_retweet      BOOLEAN DEFAULT FALSE,
  is_reply        BOOLEAN DEFAULT FALSE,
  has_media       BOOLEAN DEFAULT FALSE,
  embedding       vector(768),             -- Vertex AI text-embedding-004 on embed_text
  ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic search index (cosine similarity, HNSW)
CREATE INDEX idx_tweets_embedding
  ON tweets USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Filtering indexes
CREATE INDEX idx_tweets_account    ON tweets (account_id);
CREATE INDEX idx_tweets_created_at ON tweets (created_at DESC);
CREATE INDEX idx_tweets_has_media  ON tweets (has_media) WHERE has_media = TRUE;
```

### `tweet_media`
One row per media attachment. Images are downloaded to GCS for permanent
storage (Twitter URLs expire). Gemini Vision generates a text description
for each image, which is appended to `tweets.embed_text` before embedding.

```sql
CREATE TABLE tweet_media (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tweet_id     TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
  media_key    TEXT NOT NULL,              -- Twitter media_key
  type         TEXT NOT NULL,              -- photo | video | animated_gif
  original_url TEXT,                       -- Twitter CDN URL (may expire)
  gcs_path     TEXT,                       -- gs://ludeai-media/tweets/{tweet_id}/{idx}.jpg
  description  TEXT,                       -- Gemini Vision caption (photos only)
  width        INT,
  height       INT,
  ingested_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tweet_media_tweet_id ON tweet_media (tweet_id);
```

### `ingestion_runs`
Audit log for each ingestion job execution.

```sql
CREATE TABLE ingestion_runs (
  id              SERIAL PRIMARY KEY,
  account_id      TEXT REFERENCES accounts(id),
  started_at      TIMESTAMPTZ DEFAULT NOW(),
  finished_at     TIMESTAMPTZ,
  tweets_fetched  INT DEFAULT 0,
  tweets_new      INT DEFAULT 0,
  media_downloaded INT DEFAULT 0,
  status          TEXT DEFAULT 'running',  -- running | success | error
  error_message   TEXT
);
```

---

## Media Handling Strategy

```
Ingestion Job — for each tweet with photos:
  │
  ├─ 1. Download image from Twitter CDN
  ├─ 2. Upload to GCS  →  gs://ludeai-media/tweets/{tweet_id}/{idx}.jpg
  ├─ 3. Call Gemini Vision  →  description text
  ├─ 4. Append to tweet text:
  │       embed_text = tweet.text
  │                  + "\n[图片: <gemini description>]"
  └─ 5. Embed embed_text  →  store in tweets.embedding

Video / GIF:
  - Store original_url only (no GCS download)
  - No Gemini description (skip)
  - embed_text = tweet.text only
```

**GCS bucket:** `ludeai-media`
**Path convention:** `tweets/{tweet_id}/{0,1,2,...}.jpg`

---

## AlloyDB — Key Queries

### Semantic Search
```sql
SELECT
  t.id, t.text, t.url, t.created_at, t.has_media,
  a.username,
  1 - (t.embedding <=> $1::vector) AS score
FROM tweets t
JOIN accounts a ON a.id = t.account_id
WHERE t.embedding IS NOT NULL
  AND ($2::text IS NULL OR a.username = $2)
ORDER BY t.embedding <=> $1::vector
LIMIT $3;
```

### Fetch media for a tweet
```sql
SELECT type, gcs_path, description
FROM tweet_media
WHERE tweet_id = $1
ORDER BY ingested_at;
```

---

## BigQuery Schema

**Dataset:** `twitter_archive`

### `tweets` table

| Column | Type | Description |
|---|---|---|
| `id` | STRING | Twitter tweet_id |
| `account_id` | STRING | Twitter user_id |
| `username` | STRING | @handle |
| `text` | STRING | Original tweet text |
| `embed_text` | STRING | Text + image descriptions |
| `url` | STRING | Link to tweet |
| `created_at` | TIMESTAMP | When tweeted |
| `likes` | INT64 | Like count at ingestion time |
| `retweets` | INT64 | Retweet count |
| `replies` | INT64 | Reply count |
| `is_retweet` | BOOL | |
| `is_reply` | BOOL | |
| `has_media` | BOOL | |
| `embedding` | ARRAY\<FLOAT64\> | 768-dim embedding of embed_text |
| `ingested_at` | TIMESTAMP | When stored |

**Partitioned by:** `created_at` (monthly)
**Clustered by:** `username`

### `tweet_media` table

| Column | Type | Description |
|---|---|---|
| `id` | STRING | UUID |
| `tweet_id` | STRING | |
| `type` | STRING | photo / video / animated_gif |
| `gcs_path` | STRING | GCS URI |
| `description` | STRING | Gemini Vision caption |

### BigQuery Vector Search (ad-hoc)
```sql
SELECT
  base.id, base.text, base.username, base.url, base.created_at,
  distance
FROM VECTOR_SEARCH(
  TABLE twitter_archive.tweets,
  'embedding',
  (SELECT embedding FROM twitter_archive.tweets WHERE id = 'SEED_TWEET_ID'),
  top_k => 20,
  distance_type => 'COSINE'
);
```

---

## Data Flow Summary

```
Ingestion Job
  │
  ├─▶ GCS                         (raw image files)
  ├─▶ AlloyDB.tweets + tweet_media (upsert, real-time search)
  └─▶ BigQuery.tweets + tweet_media (streaming insert, analytics)
```

AlloyDB is the **source of truth** for the search API.
BigQuery is for **analytics, backfill, and historical queries**.
GCS is the **permanent media store**.
