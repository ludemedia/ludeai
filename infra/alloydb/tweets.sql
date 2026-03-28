CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tweets (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  text            TEXT NOT NULL,
  embed_text      TEXT NOT NULL,           -- text + "[图片: <gemini description>]" for embedding
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
