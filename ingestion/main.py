"""
Cloud Run Job entry point.
Fetches tweets for all active accounts, generates embeddings,
writes to AlloyDB and BigQuery.
"""
import asyncio
import logging
from twitter_client import fetch_new_tweets
from embedder import embed_batch
from db import get_active_accounts, upsert_tweets, log_run

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def run():
    accounts = await get_active_accounts()
    log.info(f"Running ingestion for {len(accounts)} accounts")

    for account in accounts:
        run_id = await log_run(account["id"], status="running")
        try:
            tweets = await fetch_new_tweets(account)
            if tweets:
                tweets = await embed_batch(tweets)
                new_count = await upsert_tweets(tweets)
                log.info(f"@{account['username']}: {new_count} new tweets")
            await log_run(run_id, status="success", tweets_new=len(tweets))
        except Exception as e:
            log.error(f"@{account['username']} failed: {e}")
            await log_run(run_id, status="error", error_message=str(e))


if __name__ == "__main__":
    asyncio.run(run())
