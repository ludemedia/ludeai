"""
Download tweet images to GCS and generate descriptions via Gemini Vision.
"""
import os
import logging
import httpx
from google.cloud import storage
from vertexai.generative_models import GenerativeModel, Part

log = logging.getLogger(__name__)

GCS_BUCKET = os.environ.get("GCS_MEDIA_BUCKET", "ludeai-media")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "cobalt-mantis-491817-p2")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

DESCRIPTION_PROMPT = (
    "Describe this image in 1-2 sentences in both Chinese and English. "
    "Focus on who/what is shown, the setting, and any visible text. "
    "Format: Chinese description. English description."
)


def _get_gcs_client():
    return storage.Client(project=GCP_PROJECT)


def upload_to_gcs(image_bytes: bytes, gcs_path: str) -> str:
    """Upload image bytes to GCS. Returns gs:// URI."""
    client = _get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    return f"gs://{GCS_BUCKET}/{gcs_path}"


def describe_image(image_bytes: bytes) -> str:
    """Use Gemini Vision to describe an image. Returns text description."""
    model = GenerativeModel("gemini-2.0-flash")
    image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
    response = model.generate_content([DESCRIPTION_PROMPT, image_part])
    return response.text.strip()


async def process_tweet_media(tweet: dict) -> dict:
    """
    For a single tweet:
    - Download photos from Twitter CDN
    - Upload to GCS
    - Generate Gemini Vision descriptions
    - Update tweet dict with media info and embed_text

    Returns the tweet dict with added 'embed_text' and updated 'media'.
    """
    descriptions = []
    processed_media = []

    for idx, media in enumerate(tweet.get("media", [])):
        if media["type"] != "photo" or not media.get("url"):
            # Video/GIF: keep metadata only, no download
            processed_media.append({
                **media,
                "gcs_path": None,
                "description": None,
            })
            continue

        try:
            # Download image
            async with httpx.AsyncClient() as client:
                resp = await client.get(media["url"], timeout=30)
                resp.raise_for_status()
                image_bytes = resp.content

            # Upload to GCS
            gcs_path = f"tweets/{tweet['id']}/{idx}.jpg"
            gcs_uri = upload_to_gcs(image_bytes, gcs_path)

            # Generate description
            description = describe_image(image_bytes)
            descriptions.append(description)

            processed_media.append({
                **media,
                "gcs_path": gcs_uri,
                "description": description,
            })

            log.info(f"  media {idx}: uploaded + described ({len(description)} chars)")

        except Exception as e:
            log.warning(f"  media {idx} failed: {e}")
            processed_media.append({
                **media,
                "gcs_path": None,
                "description": None,
            })

    # Build embed_text: original text + image descriptions
    embed_text = tweet["text"]
    if descriptions:
        for desc in descriptions:
            embed_text += f"\n[图片: {desc}]"

    tweet["media"] = processed_media
    tweet["embed_text"] = embed_text
    tweet["has_media"] = len(processed_media) > 0

    return tweet
