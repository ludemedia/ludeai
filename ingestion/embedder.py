"""
Generate embeddings via Vertex AI text-embedding-004.
"""
import os
import logging
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

log = logging.getLogger(__name__)

MODEL_ID = "text-embedding-004"
BATCH_SIZE = 250  # Vertex AI limit per request


def _get_model():
    return TextEmbeddingModel.from_pretrained(MODEL_ID)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts, returns list of 768-dim vectors."""
    model = _get_model()
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        inputs = [TextEmbeddingInput(text=t, task_type="RETRIEVAL_DOCUMENT") for t in batch]
        results = model.get_embeddings(inputs)
        all_embeddings.extend([r.values for r in results])
        log.info(f"Embedded {len(all_embeddings)}/{len(texts)} texts")

    return all_embeddings


def embed_tweets(tweets: list[dict]) -> list[dict]:
    """Add 'embedding' field to each tweet dict using embed_text."""
    texts = [t["embed_text"] for t in tweets]
    embeddings = embed_texts(texts)
    for tweet, emb in zip(tweets, embeddings):
        tweet["embedding"] = emb
    return tweets
