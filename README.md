# ludeai — 路德社数据生态库

> 今天站在未来说历史 — [路德社 ludepress.com](https://ludepress.com)

路德社内容数据平台，统一归档、索引和检索路德社各类内容资产，包括推特、YouTube、知识图谱等。

---

## 当前模块

### Twitter 语义搜索
归档路德社相关 Twitter 账号的全部推文，支持语义搜索。

### YouTube 下载与转写
从 url_source 的频道清单批量下载 YouTube 视频，抽取音频并用 Whisper 转写为
简体中文文字（自动恢复标点、按句换行），为后续翻译与语义检索做准备。

### 即将推出
- **YouTube 翻译归档** — 字幕翻译、语义检索
- **知识图谱** — 人物、事件、组织关系图谱，支持关联查询
- **路德时评归档** — 路德社文章全文索引与搜索
- **播客归档** — 播客内容转文字、语义搜索

---

## 技术栈

- **AlloyDB** — 主数据库，pgvector 语义搜索
- **BigQuery** — 数据仓库，历史数据分析
- **Vertex AI** — 文本向量化（`text-embedding-004`）
- **Cloud Run** — 数据采集 Job + 搜索 API
- **Next.js** — 前端，Firebase Hosting 部署
- **yt-dlp** — YouTube 视频下载
- **mlx-whisper** — 语音转写（Apple Silicon 加速，`large-v3-turbo`）
- **FunASR ct-punc** — 中文标点恢复

## 目录结构

```
├── ingestion/    # 数据采集：抓取推文 → 生成 embedding → 存储
├── api/          # 搜索 API：FastAPI on Cloud Run
├── web/          # 前端：Next.js 搜索界面
├── infra/        # GCP 基础设施 Terraform
├── scripts/      # 数据库初始化 + YouTube 下载/转写脚本
├── data/         # 本地数据（不入库，仅保留少量样本，见下）
└── docs/         # 架构文档
```

---

## YouTube 下载与转写流程

### 程序文件（`scripts/`）

| 文件 | 作用 |
|---|---|
| [`download_youtube.py`](scripts/download_youtube.py) | 读取 `data/url_source/*.json` 频道清单，用 yt-dlp 下载视频到 `data/video_download/` |
| [`transcribe.py`](scripts/transcribe.py) | 抽音频 → Whisper 转写 → 标点恢复 → 按句换行，输出到 `data/transcripts/` |
| [`setup_db.py`](scripts/setup_db.py) | 初始化 AlloyDB 表结构（支持 `ALLOYDB_PROXY=1` 本地 Auth Proxy 直连） |

### 处理管线

```
data/url_source/<频道>.json   （phpMyAdmin 导出的 yt_videos 清单）
      │  download_youtube.py (yt-dlp)
      ▼
data/video_download/<频道>/<名>.mp4
      │  transcribe.py — ffmpeg 抽 16kHz 单声道音频
      ▼
data/audio/<频道>/<名>.wav
      │  mlx-whisper (large-v3-turbo, language=zh, condition_on_previous_text=False)
      │  → 去标点 → FunASR ct-punc 恢复标点 → 按 。！？ 断句
      ▼
data/transcripts/<频道>/<名>.txt   （简体中文，每句一行）
```

> **关于标点**：Whisper 对部分语速快、无停顿的音频不输出标点，因此不依赖其标点——
> 统一去除后用 FunASR ct-punc 重新恢复，保证所有文件分句一致。

### 运行

```bash
# 依赖（建议在 venv 内）
pip install -r scripts/requirements.txt
brew install ffmpeg            # 抽音频 / Whisper 加载所需

python scripts/download_youtube.py            # 各频道下载前 15 个视频
python scripts/transcribe.py                  # 抽音频 + 转写（可断点续跑）
```

---

## 已推送的数据样本

完整媒体资产（视频 / 音频 / 文字）体量大，**不纳入版本库**（见 [.gitignore](.gitignore)）。
仓库内仅保留两组样本，演示下载与转写效果：

| 频道 | 音频（mp3, 64kbps 单声道） | 文字（txt, 每句一行） |
|---|---|---|
| 路德社主頻道 | 《中共对美赤裸裸列出所谓合作清单…》 | 805 句 |
| 閆博士說 | 《Trump 下最严厉通牒…》 | 639 句 |

> 原始音频为 16kHz 单声道 wav（各约 180MB，超 GitHub 100MB 单文件上限），
> 样本已压成 mp3（约 42–48MB）便于入库。

---

## 文档

- [系统架构](docs/ARCHITECTURE.md)
- [数据库设计](docs/DB_ARCHITECTURE.md)
