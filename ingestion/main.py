"""
Cloud Run Job — Tweet Ingestion

Fetch tweets for a user within a time range, process media,
generate embeddings, and store in AlloyDB.

Usage (CLI):
    python main.py --username ludewb --since 2024-01-01 --until 2024-06-01
    python main.py --username ludewb --since 2024-01-01
    python main.py --username ludewb   # fetches recent tweets (last 7 days)

Environment variables:
    TWITTER_BEARER_TOKEN  — Twitter API v2 bearer token
    GCS_MEDIA_BUCKET      — GCS bucket for media (default: ludeai-media)
    GCP_PROJECT           — GCP project ID
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from twitter_client import fetch_tweets
from media import process_tweet_media
from embedder import embed_tweets
from db import ensure_account, upsert_tweets, log_run, close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ingestion")


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest tweets for a user")
    parser.add_argument("--username", required=True, help="Twitter @handle (without @)")
    parser.add_argument("--since", type=str, default=None,
                        help="Start date (YYYY-MM-DD). Default: 7 days ago")
    parser.add_argument("--until", type=str, default=None,
                        help="End date (YYYY-MM-DD). Default: now")
    parser.add_argument("--skip-media", action="store_true",
                        help="Skip media download and Gemini Vision")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Skip embedding generation")
    return parser.parse_args()


async def run():
    args = parse_args()

    # Parse dates
    since = (
        datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if args.since
        else datetime.now(timezone.utc) - timedelta(days=7)
    )
    until = (
        datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if args.until
        else datetime.now(timezone.utc)
    )

    log.info(f"Ingesting @{args.username} from {since.date()} to {until.date()}")

    # 1. Fetch tweets from Twitter API
    log.info("Step 1/4: Fetching tweets from Twitter API...")
    tweets = fetch_tweets(args.username, since=since, until=until)
    if not tweets:
        log.info("No tweets found in this range. Done.")
        return

    log.info(f"Fetched {len(tweets)} tweets")

    # Ensure account exists in DB
    account_id = tweets[0]["account_id"]
    await ensure_account(account_id, args.username)
    run_id = await log_run(account_id, status="running")

    try:
        # 2. Process media (download to GCS + Gemini Vision)
        media_count = 0
        if not args.skip_media:
            log.info("Step 2/4: Processing media (GCS + Gemini Vision)...")
            for i, tweet in enumerate(tweets):
                if tweet.get("media"):
                    tweets[i] = await process_tweet_media(tweet)
                    media_count += sum(
                        1 for m in tweets[i]["media"] if m.get("gcs_path")
                    )
                else:
                    tweet["embed_text"] = tweet["text"]
                    tweet["has_media"] = False
            log.info(f"Processed {media_count} media files")
        else:
            log.info("Step 2/4: Skipping media processing")
            for tweet in tweets:
                tweet["embed_text"] = tweet["text"]
                tweet["has_media"] = bool(tweet.get("media"))

        # 3. Generate embeddings
        if not args.skip_embed:
            log.info("Step 3/4: Generating embeddings...")
            tweets = embed_tweets(tweets)
            log.info("Embeddings done")
        else:
            log.info("Step 3/4: Skipping embedding")
            for tweet in tweets:
                tweet["embedding"] = None

        # 4. Write to AlloyDB
        log.info("Step 4/4: Writing to AlloyDB...")
        new_count = await upsert_tweets(tweets)

        await log_run(
            run_id, status="success",
            tweets_fetched=len(tweets), tweets_new=new_count,
            media_downloaded=media_count,
        )

        log.info(f"Done! {len(tweets)} tweets ({new_count} new), {media_count} media files")

    except Exception as e:
        log.error(f"Ingestion failed: {e}", exc_info=True)
        await log_run(run_id, status="error", error_message=str(e))
        raise
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
