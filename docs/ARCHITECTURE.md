# Twitter Archive & Semantic Search — Architecture

## Overview

Archive tweets from multiple Twitter accounts and provide a clean semantic search frontend, hosted on GCP.

---

## Stack

| Layer | Technology |
|---|---|
| Tweet Ingestion | Twitter API v2 + Cloud Scheduler + Cloud Run Job |
| Raw Storage | Firestore (tweets + metadata) |
| Embeddings | Vertex AI Text Embeddings (`text-embedding-004`) |
| Vector Search | Vertex AI Vector Search |
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
  - Store raw tweet in Firestore
  - Generate embedding via Vertex AI
  - Upsert embedding into Vertex AI Vector Search
     │
     ├──▶ Firestore
     │      tweets/{tweet_id}: { text, author, created_at, url, ... }
     │
     └──▶ Vertex AI Vector Search Index
            { id: tweet_id, embedding: [...] }

User
  │
  ▼
Next.js Frontend (Firebase Hosting)
  - Single search bar
  - Calls Backend API
     │
     ▼
Cloud Run — Search API (FastAPI)
  1. Embed the query via Vertex AI
  2. Query Vector Search → top-K tweet IDs
  3. Fetch tweet docs from Firestore by IDs
  4. Return results to frontend
```

---

## Components

### 1. Ingestion Service (`/ingestion`)
- Cloud Run Job, triggered by Cloud Scheduler
- Twitter API v2: fetch timeline for each account, handle pagination & deduplication
- Calls Vertex AI Embeddings API to embed each tweet's text
- Writes to Firestore + upserts to Vector Search index

### 2. Search API (`/api`)
- FastAPI on Cloud Run, public HTTPS endpoint
- `POST /search` — accepts `{ query: string, limit: int }`
- Embeds query → Vector Search ANN query → Firestore batch get → return tweets

### 3. Frontend (`/web`)
- Next.js, minimal UI: search bar + results list
- Shows tweet text, author, date, link to original tweet
- Deployed to Firebase Hosting

---

## GCP Services Used

- **Cloud Run** — ingestion job + search API
- **Cloud Scheduler** — periodic ingestion trigger
- **Firestore** — tweet document store
- **Vertex AI Embeddings** — `text-embedding-004`
- **Vertex AI Vector Search** — ANN index for semantic search
- **Firebase Hosting** — frontend hosting
- **Secret Manager** — Twitter API keys

---

## Repo Structure

```
ludeai/
├── ingestion/        # Cloud Run Job: fetch tweets + embed + store
├── api/              # Cloud Run: FastAPI search endpoint
├── web/              # Next.js frontend
├── infra/            # Terraform for GCP resources
└── ARCHITECTURE.md
```

---

## Open Questions

- How many Twitter accounts to track?
- Full historical backfill needed, or from now forward?
- Twitter API tier (Free / Basic / Pro) — affects rate limits & archive access
