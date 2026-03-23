CREATE TABLE IF NOT EXISTS twitter_profiles (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  twitter_id        TEXT UNIQUE NOT NULL,
  username          TEXT NOT NULL,
  display_name      TEXT,
  bio               TEXT,
  location          TEXT,
  followers         INT,
  following         INT,
  tweet_count       INT,
  profile_image_url TEXT,
  twitter_url       TEXT,
  verified          BOOLEAN DEFAULT FALSE,
  account_created_at TIMESTAMPTZ,
  added_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_twitter_profiles_username ON twitter_profiles (username);
