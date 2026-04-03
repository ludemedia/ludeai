"""
AlloyDB read/write operations via google-cloud-alloydb-connector.
"""
import os
import logging
import asyncpg
from google.cloud.alloydb.connector import AsyncConnector

log = logging.getLogger(__name__)

INSTANCE_URI = os.environ.get(
    "ALLOYDB_INSTANCE",
    "projects/cobalt-mantis-491817-p2/locations/us-central1/clusters/ludeai-cluster/instances/ludeai-primary",
)
DB_USER = os.environ.get("DB_USER", "satoshi@ludemedia.org")
DB_NAME = os.environ.get("DB_NAME", "postgres")

_connector: AsyncConnector | None = None
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _connector, _pool
    if _pool is not None:
        return _pool

    _connector = AsyncConnector()

    async def getconn():
        return await _connector.connect(
            INSTANCE_URI,
            "asyncpg",
            user=DB_USER,
            db=DB_NAME,
            enable_iam_auth=True,
        )

    _pool = await asyncpg.create_pool(dsn=None, connect=getconn, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _connector, _pool
    if _pool:
        await _pool.close()
        _pool = None
    if _connector:
        await _connector.close()
        _connector = None


async def ensure_account(account_id: str, username: str):
    """Insert account if not exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO accounts (id, username)
            VALUES ($1, $2)
            ON CONFLICT (id) DO NOTHING
            """,
            account_id, username,
        )


async def upsert_tweets(tweets: list[dict]) -> int:
    """Upsert tweets + media into AlloyDB. Returns count of new tweets."""
    pool = await get_pool()
    new_count = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            for t in tweets:
                result = await conn.execute(
                    """
                    INSERT INTO tweets (
                        id, account_id, text, embed_text, url, created_at,
                        likes, retweets, replies,
                        is_retweet, is_reply, has_media, embedding
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::vector
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        likes     = EXCLUDED.likes,
                        retweets  = EXCLUDED.retweets,
                        replies   = EXCLUDED.replies
                    """,
                    t["id"], t["account_id"], t["text"], t["embed_text"],
                    t["url"], t["created_at"],
                    t["likes"], t["retweets"], t["replies"],
                    t["is_retweet"], t["is_reply"], t.get("has_media", False),
                    str(t["embedding"]) if t.get("embedding") else None,
                )

                if "INSERT" in result:
                    new_count += 1

                # Insert media rows
                for media in t.get("media", []):
                    await conn.execute(
                        """
                        INSERT INTO tweet_media (
                            tweet_id, media_key, type, original_url,
                            gcs_path, description, width, height
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        ON CONFLICT DO NOTHING
                        """,
                        t["id"], media["media_key"], media["type"],
                        media.get("url"), media.get("gcs_path"),
                        media.get("description"),
                        media.get("width"), media.get("height"),
                    )

    log.info(f"Upserted {len(tweets)} tweets ({new_count} new)")
    return new_count


async def log_run(account_id: str, status: str, tweets_fetched: int = 0,
                  tweets_new: int = 0, media_downloaded: int = 0,
                  error_message: str = None) -> int:
    """Insert or update an ingestion run log entry."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status == "running":
            row = await conn.fetchrow(
                """
                INSERT INTO ingestion_runs (account_id, status)
                VALUES ($1, $2)
                RETURNING id
                """,
                account_id, status,
            )
            return row["id"]
        else:
            await conn.execute(
                """
                UPDATE ingestion_runs
                SET status = $2, finished_at = NOW(),
                    tweets_fetched = $3, tweets_new = $4,
                    media_downloaded = $5, error_message = $6
                WHERE id = $1
                """,
                account_id, status,
                tweets_fetched, tweets_new, media_downloaded, error_message,
            )
            return account_id
