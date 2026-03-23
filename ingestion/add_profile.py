"""
CLI: add a Twitter profile to the database.

Usage:
    python add_profile.py https://twitter.com/elonmusk
    python add_profile.py https://x.com/elonmusk
    python add_profile.py elonmusk
"""
import sys
import re
import os
import asyncio
import asyncpg
import tweepy


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_username(input_str: str) -> str:
    """Extract username from a Twitter/X URL or return as-is."""
    match = re.search(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)", input_str)
    if match:
        return match.group(1)
    return input_str.lstrip("@")


def fetch_profile(username: str) -> dict:
    client = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"])
    resp = client.get_user(
        username=username,
        user_fields=[
            "id", "name", "description", "location",
            "public_metrics", "profile_image_url",
            "url", "verified", "created_at",
        ],
    )
    if not resp.data:
        raise ValueError(f"User '@{username}' not found")

    u = resp.data
    return {
        "twitter_id":          str(u.id),
        "username":            u.username,
        "display_name":        u.name,
        "bio":                 u.description,
        "location":            u.location,
        "followers":           u.public_metrics["followers_count"],
        "following":           u.public_metrics["following_count"],
        "tweet_count":         u.public_metrics["tweet_count"],
        "profile_image_url":   u.profile_image_url,
        "twitter_url":         f"https://x.com/{u.username}",
        "verified":            u.verified or False,
        "account_created_at":  u.created_at,
    }


async def upsert_profile(profile: dict):
    conn = await asyncpg.connect(os.environ["ALLOYDB_DSN"])
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO twitter_profiles (
                twitter_id, username, display_name, bio, location,
                followers, following, tweet_count, profile_image_url,
                twitter_url, verified, account_created_at
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12
            )
            ON CONFLICT (twitter_id) DO UPDATE SET
                username          = EXCLUDED.username,
                display_name      = EXCLUDED.display_name,
                bio               = EXCLUDED.bio,
                location          = EXCLUDED.location,
                followers         = EXCLUDED.followers,
                following         = EXCLUDED.following,
                tweet_count       = EXCLUDED.tweet_count,
                profile_image_url = EXCLUDED.profile_image_url,
                twitter_url       = EXCLUDED.twitter_url,
                verified          = EXCLUDED.verified,
                updated_at        = NOW()
            RETURNING id, username
            """,
            profile["twitter_id"], profile["username"], profile["display_name"],
            profile["bio"], profile["location"], profile["followers"],
            profile["following"], profile["tweet_count"], profile["profile_image_url"],
            profile["twitter_url"], profile["verified"], profile["account_created_at"],
        )
        return row
    finally:
        await conn.close()


# ── main ─────────────────────────────────────────────────────────────────────

async def main():
    if len(sys.argv) < 2:
        print("Usage: python add_profile.py <twitter_url_or_username>")
        sys.exit(1)

    username = parse_username(sys.argv[1])
    print(f"Fetching @{username} ...")

    profile = fetch_profile(username)
    print(f"  {profile['display_name']} · {profile['followers']:,} followers")

    row = await upsert_profile(profile)
    print(f"Saved  id={row['id']}  @{row['username']}")


if __name__ == "__main__":
    asyncio.run(main())
