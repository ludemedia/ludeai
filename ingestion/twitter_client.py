"""
Fetch tweets for a user within a time range using Twitter API v2.
"""
import os
import logging
from datetime import datetime
from typing import Optional
import tweepy

log = logging.getLogger(__name__)

TWEET_FIELDS = [
    "id", "text", "created_at", "public_metrics",
    "referenced_tweets", "attachments", "author_id",
]
MEDIA_FIELDS = ["media_key", "type", "url", "preview_image_url", "width", "height"]
EXPANSIONS = ["attachments.media_keys"]
MAX_RESULTS_PER_PAGE = 100


def get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=os.environ["TWITTER_BEARER_TOKEN"],
        wait_on_rate_limit=True,
    )


def fetch_tweets(
    username: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """
    Fetch all tweets for a user between `since` and `until`.
    Returns a list of dicts ready for DB insertion.
    """
    client = get_client()

    # resolve username → user_id
    user_resp = client.get_user(username=username, user_fields=["id"])
    if not user_resp.data:
        raise ValueError(f"User @{username} not found")
    user_id = user_resp.data.id

    all_tweets = []
    media_map = {}  # media_key → media object
    next_token = None

    while True:
        resp = client.get_users_tweets(
            id=user_id,
            start_time=since.isoformat() + "Z" if since else None,
            end_time=until.isoformat() + "Z" if until else None,
            tweet_fields=TWEET_FIELDS,
            media_fields=MEDIA_FIELDS,
            expansions=EXPANSIONS,
            max_results=MAX_RESULTS_PER_PAGE,
            pagination_token=next_token,
        )

        # collect media from includes
        if resp.includes and "media" in resp.includes:
            for m in resp.includes["media"]:
                media_map[m.media_key] = {
                    "media_key": m.media_key,
                    "type": m.type,
                    "url": getattr(m, "url", None) or getattr(m, "preview_image_url", None),
                    "width": getattr(m, "width", None),
                    "height": getattr(m, "height", None),
                }

        if not resp.data:
            break

        for tweet in resp.data:
            metrics = tweet.public_metrics or {}
            ref_tweets = tweet.referenced_tweets or []
            is_retweet = any(r.type == "retweeted" for r in ref_tweets)
            is_reply = any(r.type == "replied_to" for r in ref_tweets)

            # collect media attachments
            tweet_media = []
            if tweet.attachments and "media_keys" in tweet.attachments:
                for mk in tweet.attachments["media_keys"]:
                    if mk in media_map:
                        tweet_media.append(media_map[mk])

            all_tweets.append({
                "id": str(tweet.id),
                "account_id": str(user_id),
                "username": username,
                "text": tweet.text,
                "url": f"https://x.com/{username}/status/{tweet.id}",
                "created_at": tweet.created_at,
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "is_retweet": is_retweet,
                "is_reply": is_reply,
                "media": tweet_media,
            })

        log.info(f"Fetched {len(all_tweets)} tweets so far for @{username}")

        next_token = resp.meta.get("next_token") if resp.meta else None
        if not next_token:
            break

    log.info(f"Total: {len(all_tweets)} tweets for @{username}")
    return all_tweets
