# ludeai

Twitter archive and semantic search platform built on GCP.

Archive tweets from multiple accounts and search them semantically via a clean frontend.

## Stack

- **AlloyDB** — primary database with pgvector for semantic search
- **BigQuery** — analytics warehouse and historical vector search
- **Vertex AI** — text embeddings (`text-embedding-004`)
- **Cloud Run** — ingestion job + search API
- **Next.js** — frontend, deployed on Firebase Hosting

## Structure

```
├── ingestion/    # Cloud Run Job: fetch tweets → embed → store
├── api/          # Cloud Run Service: FastAPI search endpoint
├── web/          # Next.js frontend
├── infra/        # Terraform for all GCP resources
└── docs/         # Architecture docs
```

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Database Design](docs/DB_ARCHITECTURE.md)
