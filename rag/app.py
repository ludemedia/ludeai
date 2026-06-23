"""
网页 UI：广东军区会议 / 514录音 RAG 问答（Gradio）。

复用 chat.py 的检索逻辑，用 Qwen（mlx-lm）流式生成答案，并展示引用来源。

启动：
    python rag/app.py            # 浏览器打开 http://127.0.0.1:7860
"""
import gradio as gr
from sentence_transformers import SentenceTransformer
from mlx_lm import load, stream_generate

from chat import load_index, retrieve, build_prompt, SYSTEM_PROMPT, GEN_MODEL, INDEX_DIR

if not (INDEX_DIR / "embeddings.npy").exists():
    raise SystemExit("索引不存在，请先运行：python rag/build_index.py")

print("加载索引与模型 …")
VECS, CHUNKS, META = load_index()
EMBEDDER = SentenceTransformer(META["embed_model"])
MODEL, TOK = load(GEN_MODEL)
print("就绪。")


def sources_md(hits):
    rows = [
        f"**[{n}]** `{s:.2f}` {h['source'][:60]} （句 {h['line_start']}–{h['line_end']}）"
        for n, (h, s) in enumerate(hits, 1)
    ]
    return "### 引用来源\n" + "\n\n".join(rows)


def respond(message, history):
    hits = retrieve(message, EMBEDDER, VECS, CHUNKS)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_prompt(message, hits)},
    ]
    prompt = TOK.apply_chat_template(messages, add_generation_prompt=True)
    answer = ""
    for resp in stream_generate(MODEL, TOK, prompt=prompt, max_tokens=800):
        answer += resp.text
        yield answer
    yield answer + "\n\n---\n" + sources_md(hits)


demo = gr.ChatInterface(
    fn=respond,
    title="路德社资料 RAG 问答 — 广东军区会议 / 514录音 / 093417",
    description="基于 34 篇转写的本地检索增强问答。检索：bge-small-zh；生成：Qwen2.5-7B（mlx，仅依据资料作答并标注引用）。",
    examples=[
        "广东省军区那场战前动员会议提到要装备什么武器系统？",
        "参加这次广东省军区秘密会议的都有哪些人？",
        "514录音里习近平说的“战略决胜”是什么意思？",
        "093417 核潜艇事故是怎么回事？死了多少人？",
    ],
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
