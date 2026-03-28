CREATE TABLE IF NOT EXISTS accounts (
  id            TEXT PRIMARY KEY,          -- Twitter user_id
  username      TEXT NOT NULL UNIQUE,
  display_name  TEXT,
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  active        BOOLEAN DEFAULT TRUE
);
