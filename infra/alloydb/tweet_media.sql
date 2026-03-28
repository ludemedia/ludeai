CREATE TABLE IF NOT EXISTS tweet_media (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tweet_id     TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
  media_key    TEXT NOT NULL,
  type         TEXT NOT NULL,              -- photo | video | animated_gif
  original_url TEXT,                       -- Twitter CDN URL (may expire)
  gcs_path     TEXT,                       -- gs://ludeai-media/tweets/{tweet_id}/{idx}.jpg
  description  TEXT,                       -- Gemini Vision caption (photos only)
  width        INT,
  height       INT,
  ingested_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tweet_media_tweet_id ON tweet_media (tweet_id);
