CREATE TABLE IF NOT EXISTS ingestion_runs (
  id               SERIAL PRIMARY KEY,
  account_id       TEXT REFERENCES accounts(id),
  started_at       TIMESTAMPTZ DEFAULT NOW(),
  finished_at      TIMESTAMPTZ,
  tweets_fetched   INT DEFAULT 0,
  tweets_new       INT DEFAULT 0,
  media_downloaded INT DEFAULT 0,
  status           TEXT DEFAULT 'running',  -- running | success | error
  error_message    TEXT
);
