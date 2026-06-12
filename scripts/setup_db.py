"""
One-time script: create all AlloyDB tables.

Usage:
    python scripts/setup_db.py

Requires:
    pip install "google-cloud-alloydb-connector[asyncpg]" asyncpg
    gcloud auth application-default login
"""
import asyncio
import os
import asyncpg
from google.cloud.alloydb.connector import AsyncConnector

INSTANCE_URI = "projects/cobalt-mantis-491817-p2/locations/us-central1/clusters/ludeai-cluster/instances/ludeai-primary"
DB_USER      = "satoshi@ludemedia.org"
DB_NAME      = "postgres"

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

-- accounts
CREATE TABLE IF NOT EXISTS accounts (
  id            TEXT PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  display_name  TEXT,
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  active        BOOLEAN DEFAULT TRUE
);

-- tweets
CREATE TABLE IF NOT EXISTS tweets (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  text            TEXT NOT NULL,
  embed_text      TEXT NOT NULL,
  url             TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL,
  likes           INT DEFAULT 0,
  retweets        INT DEFAULT 0,
  replies         INT DEFAULT 0,
  is_retweet      BOOLEAN DEFAULT FALSE,
  is_reply        BOOLEAN DEFAULT FALSE,
  has_media       BOOLEAN DEFAULT FALSE,
  embedding       vector(768),
  ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tweets_embedding
  ON tweets USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_tweets_account    ON tweets (account_id);
CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_has_media  ON tweets (has_media) WHERE has_media = TRUE;

-- tweet_media
CREATE TABLE IF NOT EXISTS tweet_media (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tweet_id     TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
  media_key    TEXT NOT NULL,
  type         TEXT NOT NULL,
  original_url TEXT,
  gcs_path     TEXT,
  description  TEXT,
  width        INT,
  height       INT,
  ingested_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tweet_media_tweet_id ON tweet_media (tweet_id);

-- twitter_profiles
CREATE TABLE IF NOT EXISTS twitter_profiles (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  twitter_id         TEXT UNIQUE NOT NULL,
  username           TEXT NOT NULL,
  display_name       TEXT,
  bio                TEXT,
  location           TEXT,
  followers          INT,
  following          INT,
  tweet_count        INT,
  profile_image_url  TEXT,
  twitter_url        TEXT,
  verified           BOOLEAN DEFAULT FALSE,
  account_created_at TIMESTAMPTZ,
  added_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_twitter_profiles_username ON twitter_profiles (username);

-- ingestion_runs
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id               SERIAL PRIMARY KEY,
  account_id       TEXT REFERENCES accounts(id),
  started_at       TIMESTAMPTZ DEFAULT NOW(),
  finished_at      TIMESTAMPTZ,
  tweets_fetched   INT DEFAULT 0,
  tweets_new       INT DEFAULT 0,
  media_downloaded INT DEFAULT 0,
  status           TEXT DEFAULT 'running',
  error_message    TEXT
);
"""


async def main():
    # If ALLOYDB_PROXY=1 (local dev with Auth Proxy running on localhost:5432),
    # connect directly via asyncpg. Otherwise use the AlloyDB Connector.
    use_proxy = os.environ.get("ALLOYDB_PROXY", "0") == "1"

    if use_proxy:
        print("Connecting via AlloyDB Auth Proxy (localhost:5432)...")
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=5432,
            user="postgres",
            password=os.environ.get("ALLOYDB_PASSWORD", "LudeAI2026!Secure"),
            database=DB_NAME,
            timeout=30,
            ssl=False,
        )
        connector = None
    else:
        print("Connecting via AlloyDB Connector (direct)...")
        connector = AsyncConnector()
        conn = await connector.connect(
            INSTANCE_URI,
            "asyncpg",
            user=DB_USER,
            db=DB_NAME,
            enable_iam_auth=True,
        )

    await conn.execute(SCHEMA)
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    print("Tables created:")
    for t in tables:
        print(f"  ✓ {t['tablename']}")

    await conn.close()
    if connector:
        await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
