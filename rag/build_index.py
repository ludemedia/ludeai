"""
Build a local RAG index over the 514录音 / 广东军区会议 transcripts.

Reads the per-sentence .txt transcripts, groups consecutive sentences into
overlapping chunks, embeds them with a Chinese embedding model, and saves the
vectors + metadata to rag/index/.

Usage:
    python rag/build_index.py [--src data/transcripts/514_093417] \
                              [--embed-model BAAI/bge-small-zh-v1.5]
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "transcripts" / "514_093417"
INDEX_DIR = Path(__file__).resolve().parent / "index"
DEFAULT_EMBED = "BAAI/bge-small-zh-v1.5"

CHUNK_CHARS = 450      # target characters per chunk
OVERLAP_SENTS = 1      # sentences of overlap between consecutive chunks


def title_of(path: Path) -> str:
    """Human-readable source label: the video title without the [id] / suffix."""
    return re.sub(r"\s*\[[A-Za-z0-9_-]+\]$", "", path.stem)


def chunk_file(path: Path) -> list[dict]:
    """Group a per-sentence transcript into overlapping character-bounded chunks."""
    sents = [s.strip() for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    chunks, i = [], 0
    while i < len(sents):
        buf, j = [], i
        while j < len(sents) and sum(len(s) for s in buf) < CHUNK_CHARS:
            buf.append(sents[j])
            j += 1
        chunks.append({
            "text": "".join(buf),
            "source": title_of(path),
            "line_start": i + 1,
            "line_end": j,
        })
        if j >= len(sents):
            break
        i = j - OVERLAP_SENTS  # step back for overlap
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--embed-model", default=DEFAULT_EMBED)
    args = ap.parse_args()

    src = Path(args.src)
    files = sorted(src.glob("*.txt"))
    if not files:
        raise SystemExit(f"No transcripts found in {src}")

    all_chunks: list[dict] = []
    for f in files:
        all_chunks.extend(chunk_file(f))
    print(f"{len(files)} transcripts → {len(all_chunks)} chunks")

    print(f"Embedding with {args.embed_model} …")
    model = SentenceTransformer(args.embed_model)
    vecs = model.encode(
        [c["text"] for c in all_chunks],
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype(np.float32)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", vecs)
    (INDEX_DIR / "chunks.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in all_chunks), encoding="utf-8")
    (INDEX_DIR / "meta.json").write_text(
        json.dumps({"embed_model": args.embed_model, "dim": int(vecs.shape[1]),
                    "n_chunks": len(all_chunks), "src": str(src)}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"✅ Saved index to {INDEX_DIR} ({vecs.shape[0]} × {vecs.shape[1]})")


if __name__ == "__main__":
    main()
