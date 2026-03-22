# Twitter Archive & Semantic Search — Architecture

## Overview

Archive tweets from multiple Twitter accounts and provide a clean semantic search frontend, hosted on GCP.

---

## Stack

| Layer | Technology |
|---|---|
| Tweet Ingestion | Twitter API v2 + Cloud Scheduler + Cloud Run Job |
| Primary Database | AlloyDB (PostgreSQL + pgvector) |
| Analytics Warehouse | BigQuery |
| Embeddings | Vertex AI Text Embeddings (`text-embedding-004`) |
| Vector Search | AlloyDB pgvector (ANN) + BigQuery Vector Search |
| Backend API | Cloud Run (Python / FastAPI) |
| Frontend | Next.js → Firebase Hosting |

---

## Data Flow

```
Twitter API v2
     │
     ▼
Cloud Scheduler (cron, e.g. every 6h)
     │
     ▼
Cloud Run Job — Ingestion Service
  - Fetch new tweets for each tracked account
  - Deduplicate by tweet_id
  - Generate embedding via Vertex AI text-embedding-004
     │
     ├──▶ AlloyDB (primary store)
     │      table: tweets
     │        id, author, text, url, created_at,
     │        embedding vector(768)   ← pgvector column
     │
     └──▶ BigQuery (analytics + backup vector search)
            dataset: twitter_archive
            table: tweets  (streaming insert or batch load)
            VECTOR column on embedding for BQ Vector Search

User
  │
  ▼
Next.js Frontend (Firebase Hosting)
  - Single search bar
  - Calls Backend API
     │
     ▼
Cloud Run — Search API (FastAPI)
  1. Embed query via Vertex AI
  2. AlloyDB pgvector ANN query → top-K results
     (fallback: BigQuery VECTOR_SEARCH for analytics queries)
  3. Return tweets to frontend
```

---

## Database Design

### AlloyDB — Primary Operational DB

PostgreSQL-compatible, supports pgvector natively with HNSW/IVFFlat indexing.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tweets (
  id            TEXT PRIMARY KEY,
  author        TEXT NOT NULL,
  author_id     TEXT NOT NULL,
  text          TEXT NOT NULL,
  url           TEXT,
  created_at    TIMESTAMPTZ NOT NULL,
  embedding     vector(768),           -- Vertex AI text-embedding-004
  ingested_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON tweets USING hnsw (embedding vector_cosine_ops);
```

### BigQuery — Analytics & Backup

- Receives all tweets via streaming insert from the ingestion job
- Supports `VECTOR_SEARCH()` for ad-hoc semantic queries across full history
- Can run analytics: tweet volume by account, time series, etc.

---

## Components

### 1. Ingestion Service (`/ingestion`)
- Cloud Run Job, triggered by Cloud Scheduler
- Twitter API v2: fetch timeline per account, paginate, deduplicate
- Embed tweet text via Vertex AI Embeddings API
- Write to AlloyDB + BigQuery streaming insert

### 2. Search API (`/api`)
- FastAPI on Cloud Run, public HTTPS endpoint
- `POST /search` — `{ query: string, limit: int, author?: string }`
- Embed query → AlloyDB pgvector cosine similarity search → return tweets

### 3. Frontend (`/web`)
- Next.js, minimal UI: search bar + results list
- Filter by account (optional)
- Shows tweet text, author, date, link to original

---

## GCP Services Used

- **AlloyDB** — primary tweet store + pgvector semantic search
- **BigQuery** — analytics warehouse + Vector Search for historical queries
- **Vertex AI Embeddings** — `text-embedding-004` (768 dimensions)
- **Cloud Run** — ingestion job + search API
- **Cloud Scheduler** — periodic ingestion trigger
- **Firebase Hosting** — Next.js frontend
- **Secret Manager** — Twitter API keys, AlloyDB credentials

---

## Repo Structure

```
ludeai/
├── ingestion/              # Cloud Run Job: fetch → embed → write to AlloyDB + BQ
│   ├── main.py
│   ├── twitter_client.py
│   ├── embedder.py
│   ├── db.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── api/                    # Cloud Run: FastAPI search endpoint
│   ├── main.py
│   ├── search.py
│   ├── db.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── web/                    # Next.js frontend
│   ├── app/
│   ├── components/
│   ├── package.json
│   └── next.config.js
│
├── infra/                  # Terraform for all GCP resources
│   ├── alloydb/            # AlloyDB cluster, instance, schema
│   ├── bigquery/           # BQ dataset + table definitions
│   ├── cloudrun/           # Cloud Run service definitions
│   └── scheduler/          # Cloud Scheduler jobs
│
└── docs/
    ├── ARCHITECTURE.md
    └── DB_ARCHITECTURE.md
```

---

## Open Questions

- How many Twitter accounts to track?
- Full historical backfill needed, or from now forward?
- Twitter API tier (Free / Basic / Pro) — affects rate limits & archive access
