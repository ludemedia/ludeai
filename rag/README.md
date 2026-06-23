# RAG 问答 — 广东军区会议 / 514录音

一个本地、离线的中文 RAG 问答原型，针对 [data/transcripts/514_093417/](../data/transcripts/514_093417/)
的 34 篇转写（514录音 / 广东省军区会议 / 093417 核潜艇）做检索增强问答。

- **检索**：`bge-small-zh-v1.5` 把转写切块后向量化，按余弦相似度取 Top-K。
- **生成**：**Qwen2.5-7B-Instruct**（mlx-lm，Apple Silicon GPU 加速），只依据检索到的
  片段作答，并标注引用编号与来源视频。全程本地运行，无需联网（模型首次会自动下载）。

## 用法

```bash
pip install -r rag/requirements.txt

python rag/build_index.py          # 构建索引（一次即可）→ rag/index/
python rag/chat.py                 # 进入交互问答
python rag/chat.py -q "广东省军区会议提到要装备什么武器系统？"   # 单问
```

## 结构

```
rag/
├── build_index.py   # 切块 + 向量化 → rag/index/{embeddings.npy, chunks.jsonl, meta.json}
├── chat.py          # 检索 + Qwen 生成 + 引用
├── index/           # 生成的索引（不入库）
└── requirements.txt
```

## 示例

> **问**：参加这次广东省军区秘密会议的都有哪些人？为什么说这个录音极度保密？
>
> **答**：参会的有广东省军区司令员、政委，省政法委副书记、副省长，公安厅厅长，
> 省委书记李希，省长……会议极度保密是因为内容涉及军事机密，参会人员不得带手机、
> 信号全屏蔽，连录音设备都无法使用。[1]
>
> 引用：[1]《中共深墙内幕 S2E14…广东省军区战前动员会议录音》

## 可调项

- `chat.py` 顶部 `GEN_MODEL`：换更大/更小的 Qwen（如 `Qwen2.5-14B-Instruct-4bit`）。
- `build_index.py` 的 `--embed-model`：换向量模型（如 `Qwen/Qwen3-Embedding-0.6B` 做到全 Qwen 栈）。
- `--src`：指向其它转写目录，即可对别的内容建库。
