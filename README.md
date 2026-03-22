# ludeai — 路德社数据生态库

> 今天站在未来说历史 — [路德社 ludepress.com](https://ludepress.com)

路德社内容数据平台，统一归档、索引和检索路德社各类内容资产，包括推特、YouTube、知识图谱等。

---

## 当前模块

### Twitter 语义搜索
归档路德社相关 Twitter 账号的全部推文，支持语义搜索。

### 即将推出
- **YouTube 翻译归档** — 视频字幕提取、翻译、语义检索
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

## 目录结构

```
├── ingestion/    # 数据采集：抓取推文 → 生成 embedding → 存储
├── api/          # 搜索 API：FastAPI on Cloud Run
├── web/          # 前端：Next.js 搜索界面
├── infra/        # GCP 基础设施 Terraform
└── docs/         # 架构文档
```

## 文档

- [系统架构](docs/ARCHITECTURE.md)
- [数据库设计](docs/DB_ARCHITECTURE.md)
