# 📄 AI Resume Analyzer — 智能简历分析系统

基于 AI 的智能简历分析系统，支持 PDF 简历上传解析、关键信息提取、岗位需求匹配评分。

## 🏗 系统架构

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│   Frontend       │────▶│   Backend (FastAPI)   │────▶│  LLM API     │
│   GitHub Pages   │     │   Alibaba Cloud FC    │     │  Claude/Tongyi│
│   HTML/CSS/JS    │◀────│   Python 3.10         │◀────│              │
└─────────────────┘     └──────────┬───────────┘     └──────────────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │  Redis Cache │
                            │  (Optional)  │
                            └──────────────┘
```

## ✨ 功能特性

- **📥 PDF 上传解析**: 支持多页 PDF，PyMuPDF 提取 + 文本清洗
- **🤖 AI 信息提取**: 自动提取姓名、电话、邮箱、技能、教育背景、项目经历等
- **🎯 岗位匹配评分**: 基础关键词匹配 + AI 智能评分双模式
- **⚡ 缓存机制**: 可选 Redis 缓存，避免重复计算
- **📱 响应式前端**: 纯 HTML/CSS/JS，拖拽上传，移动端适配

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- (可选) Redis 服务

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 LLM API Key

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

### 3. 前端设置

```bash
cd frontend

# 开发时修改 js/api.js 中的 API_BASE 指向本地后端
# const API_BASE = "http://127.0.0.1:8000/api/v1";

# 直接用浏览器打开 index.html，或使用简单 HTTP 服务
python -m http.server 3000
```

### 4. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商 (`claude` / `tongyi`) | `claude` |
| `CLAUDE_API_KEY` | Anthropic API 密钥 | - |
| `CLAUDE_MODEL` | Claude 模型 | `claude-sonnet-4-20250514` |
| `TONGYI_API_KEY` | 通义千问 API 密钥 | - |
| `TONGYI_MODEL` | 通义千问模型 | `qwen-plus` |
| `REDIS_URL` | Redis 连接 URL（可选） | - |
| `CORS_ORIGINS` | CORS 允许来源 | `*` |
| `MAX_FILE_SIZE_MB` | 上传文件大小限制 | `10` |

## 📡 API 端点

所有端点前缀: `/api/v1`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/resume/upload` | 上传 PDF 简历 |
| `POST` | `/resume/extract` | 提取关键信息 |
| `POST` | `/jd/extract-keywords` | 提取 JD 关键词 |
| `POST` | `/resume/score` | 简历评分匹配 |
| `POST` | `/resume/analyze` | 一键分析（上传+提取+评分) |
| `GET` | `/resume/{resume_id}` | 查询缓存结果 |

详细 API 文档: [docs/API.md](docs/API.md)

## 🚢 部署

### 后端 → 阿里云函数计算 FC

```bash
# 1. 安装 Serverless Devs
npm install -g @serverless-devs/s

# 2. 配置阿里云凭证
s config add

# 3. 部署
cd backend
s deploy
```

### 前端 → GitHub Pages

1. 修改 `frontend/js/api.js` 中的 `API_BASE` 为已部署的后端 URL
2. Push 代码到 GitHub 仓库
3. GitHub Actions 自动部署到 Pages（需要仓库 Settings > Pages 启用）

## 📁 项目结构

```
resume-analyzer/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 配置管理
│   │   ├── fc_handler.py       # FC 适配器 (Mangum)
│   │   ├── api/routes.py       # API 路由
│   │   ├── models/             # Pydantic 数据模型
│   │   ├── services/           # 核心服务
│   │   │   ├── pdf_parser.py   # PDF 解析
│   │   │   ├── text_cleaner.py # 文本清洗
│   │   │   ├── llm_service.py  # LLM 抽象层
│   │   │   ├── extractor.py    # 信息提取
│   │   │   ├── scorer.py       # 评分匹配
│   │   │   └── cache_service.py# 缓存服务
│   │   └── utils/helpers.py    # 工具函数
│   ├── requirements.txt
│   ├── Dockerfile
│   └── s.yaml                  # FC 部署配置
├── frontend/                   # 前端
│   ├── index.html
│   ├── css/style.css
│   ├── js/api.js               # API 客户端
│   ├── js/components.js        # UI 组件
│   └── js/app.js               # 应用逻辑
├── .github/workflows/          # CI/CD
└── docs/API.md                 # API 文档
```

## 🔧 技术栈

- **后端**: Python, FastAPI, PyMuPDF, httpx, Anthropic/DashScope API
- **前端**: Vanilla HTML/CSS/JavaScript
- **部署**: Alibaba Cloud FC (Mangum), GitHub Pages
- **缓存**: Redis (可选)

## 📝 License

MIT
