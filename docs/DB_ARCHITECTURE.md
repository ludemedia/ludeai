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
Core table. One row per tweet, includes pgvector embedding column.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tweets (
  id            TEXT PRIMARY KEY,          -- Twitter tweet_id
  account_id    TEXT NOT NULL REFERENCES accounts(id),
  text          TEXT NOT NULL,
  url           TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL,
  likes         INT DEFAULT 0,
  retweets      INT DEFAULT 0,
  replies       INT DEFAULT 0,
  is_retweet    BOOLEAN DEFAULT FALSE,
  is_reply      BOOLEAN DEFAULT FALSE,
  embedding     vector(768),               -- Vertex AI text-embedding-004
  ingested_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic search index (cosine similarity, HNSW)
CREATE INDEX idx_tweets_embedding
  ON tweets USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Filtering indexes
CREATE INDEX idx_tweets_account    ON tweets (account_id);
CREATE INDEX idx_tweets_created_at ON tweets (created_at DESC);
```

### `ingestion_runs`
Audit log for each ingestion job execution.

```sql
CREATE TABLE ingestion_runs (
  id            SERIAL PRIMARY KEY,
  account_id    TEXT REFERENCES accounts(id),
  started_at    TIMESTAMPTZ DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  tweets_fetched  INT DEFAULT 0,
  tweets_new      INT DEFAULT 0,
  status        TEXT DEFAULT 'running',    -- running | success | error
  error_message TEXT
);
```

---

## AlloyDB — Key Queries

### Semantic Search
```sql
SELECT
  t.id, t.text, t.url, t.created_at,
  a.username,
  1 - (t.embedding <=> $1::vector) AS score
FROM tweets t
JOIN accounts a ON a.id = t.account_id
WHERE t.embedding IS NOT NULL
  AND ($2::text IS NULL OR a.username = $2)   -- optional account filter
ORDER BY t.embedding <=> $1::vector
LIMIT $3;
```

### Latest tweets per account
```sql
SELECT * FROM tweets
WHERE account_id = $1
ORDER BY created_at DESC
LIMIT 50;
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
| `text` | STRING | Tweet text |
| `url` | STRING | Link to tweet |
| `created_at` | TIMESTAMP | When tweeted |
| `likes` | INT64 | Like count at ingestion time |
| `retweets` | INT64 | Retweet count |
| `replies` | INT64 | Reply count |
| `is_retweet` | BOOL | |
| `is_reply` | BOOL | |
| `embedding` | ARRAY\<FLOAT64\> | 768-dim embedding |
| `ingested_at` | TIMESTAMP | When stored |

**Partitioned by:** `created_at` (monthly)
**Clustered by:** `username`

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
  ├─▶ AlloyDB.tweets          (upsert, real-time search)
  └─▶ BigQuery.tweets         (streaming insert, analytics)
```

AlloyDB is the **source of truth** for the search API.
BigQuery is for **analytics, backfill, and historical queries**.
