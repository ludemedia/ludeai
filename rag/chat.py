"""
Local RAG chat over the 514录音 / 广东军区会议 transcripts.

Retrieval: cosine similarity over the embeddings built by build_index.py.
Generation: Qwen (mlx-lm, Apple-Silicon accelerated) answers using only the
retrieved transcript context, with sources cited.

Usage:
    python rag/build_index.py        # once, to build the index
    python rag/chat.py               # interactive chat
    python rag/chat.py -q "广东省军区会议提到要装备什么武器系统？"   # single question
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from mlx_lm import load, generate

INDEX_DIR = Path(__file__).resolve().parent / "index"
GEN_MODEL = "mlx-community/Qwen2.5-7B-Instruct-4bit"
TOP_K = 5

SYSTEM_PROMPT = (
    "你是一个严谨的中文资料问答助手。下面会给你若干段从路德社节目转写中检索到的资料片段。"
    "请只依据这些资料回答用户的问题，用简体中文作答。"
    "如果资料中没有相关信息，就直接说“资料中没有提到”，不要编造。"
    "回答时可以引用片段编号（如 [1][2]）作为依据。"
)


def load_index():
    vecs = np.load(INDEX_DIR / "embeddings.npy")
    chunks = [json.loads(l) for l in (INDEX_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    meta = json.loads((INDEX_DIR / "meta.json").read_text(encoding="utf-8"))
    return vecs, chunks, meta


def retrieve(query, embedder, vecs, chunks, k=TOP_K):
    q = embedder.encode([query], normalize_embeddings=True)[0].astype(np.float32)
    scores = vecs @ q
    idx = np.argsort(-scores)[:k]
    return [(chunks[i], float(scores[i])) for i in idx]


def build_prompt(query, hits):
    ctx = "\n\n".join(
        f"[{n}]（来源：{h['source']}）\n{h['text']}"
        for n, (h, _) in enumerate(hits, 1)
    )
    return f"以下是检索到的资料片段：\n\n{ctx}\n\n问题：{query}\n\n请依据上述资料回答："


def answer(query, embedder, model, tok, vecs, chunks):
    hits = retrieve(query, embedder, vecs, chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_prompt(query, hits)},
    ]
    prompt = tok.apply_chat_template(messages, add_generation_prompt=True)
    out = generate(model, tok, prompt=prompt, max_tokens=800, verbose=False)
    return out, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--question", help="ask one question and exit")
    args = ap.parse_args()

    if not (INDEX_DIR / "embeddings.npy").exists():
        raise SystemExit("Index not found. Run: python rag/build_index.py")

    vecs, chunks, meta = load_index()
    print(f"加载索引：{meta['n_chunks']} 个片段 | 向量模型 {meta['embed_model']}")
    embedder = SentenceTransformer(meta["embed_model"])
    print(f"加载生成模型 {GEN_MODEL} …")
    model, tok = load(GEN_MODEL)

    def ask(q):
        out, hits = answer(q, embedder, model, tok, vecs, chunks)
        print("\n" + out.strip() + "\n")
        print("— 引用来源 —")
        for n, (h, s) in enumerate(hits, 1):
            print(f"  [{n}] {s:.2f}  {h['source'][:48]}  (句 {h['line_start']}–{h['line_end']})")

    if args.question:
        ask(args.question)
        return

    print("\n输入问题开始问答（输入 q 退出）：")
    while True:
        try:
            q = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"q", "quit", "exit"}:
            break
        if q:
            ask(q)


if __name__ == "__main__":
    main()
