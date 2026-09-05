# AIX Health（数字记忆相框）

面向阿尔茨海默病（AD）患者的**数字记忆相框系统**。患者端为拟物化数字相框，家属端为手机 PWA 应用，通过共享后端实现记忆资产实时同步与认知干预闭环。

---

## 系统架构

```
┌──────────────────┐       ┌──────────────────┐
│   患者端 (相框)   │       │  家属端 (手机 PWA)│
│  patient-app/    │       │  caregiver-app/  │
│  HTML+CSS+JS     │       │  HTML+CSS+JS     │
└───────┬──────────┘       └───────┬──────────┘
        │                          │
        │     ┌────────────┐      │
        └─────┤  FastAPI   ├──────┘
              │  后端 API   │
              │ :8000       │
              ├────────────┤
              │ PostgreSQL │
              │ MinIO      │
              │ LLM API    │
              └────────────┘
```

| 模块 | 目录 | 说明 |
|:---|:---|:---|
| **家属端** | `caregiver-app/` | 微信风格对话交互，记忆录入与管理 |
| **患者端** | `patient-app/` | 四状态数字相框（绑定/轮播/对话/舒缓） |
| **家属端（豪华版）** | `frontend/` | 拟物化家属端实现 |
| **后端** | `backend/` | FastAPI + PostgreSQL + MinIO + LLM |

---

## 快速开始（纯前端演示）

**无需任何后端依赖**，直接打开 HTML 文件即可体验完整交互：

```bash
# 克隆项目
git clone https://github.com/gulzxeric/AIx-health.git
cd AIx-health

# 用浏览器直接打开以下文件即可（或用 Live Server 启动）
# - 家属端：caregiver-app/index.html
# - 患者端：patient-app/index.html
```

前端默认使用 **Mock API** 模拟数据，无需数据库或 LLM 服务。

---

## 演示全流程（5 分钟上手）

### 1. 打开患者端
打开 `patient-app/index.html`，看到 **COLD_START** 界面，显示设备码 `ABC123` 和二维码。

### 2. 打开家属端
打开 `caregiver-app/index.html`，主界面模拟已绑定状态，显示患者"张伯伯"和在线状态。

### 3. 录入记忆
在对话流 Tab 输入文字并发送，例如：
- *"我爸以前在广州造船厂上班，每天下班都带我去江边看船"*
- *"阿珍是我老伴，我们是在厂里认识的，她唱歌特别好听"*

系统"正在分析记忆..." → 弹出**记忆卡片**，展示 LLM 抽取的实体（年代、地点、事件、喜好、可信度）。

### 4. 查看记忆库与简报
- 切换到 🗂️ 记忆库 Tab → 按标签筛选查看所有记忆
- 切换到 📊 每日简报 Tab → 活力指数、高共鸣话题、沟通建议

### 5. 体验患者端状态切换
在患者端浏览器控制台（F12）输入：

```js
// 配置就绪 → 进入轮播待机
window.__debug.stateMachine.transition('config_ready')

// 触发对话模式
window.__debug.triggerChat()

// 触发舒缓模式
window.__debug.triggerSoothing()
```

患者端状态机：`COLD_START → STANDBY → CHAT → SOOTHING`

---

## 后端启动

```bash
cd backend

# 环境变量
cp .env.example .env
# 编辑 .env 中数据库和 LLM 配置

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

**依赖说明**：

| 服务 | 必需？ | 说明 |
|:---|:---|:---|
| PostgreSQL | ✅ | 主数据库 |
| LLM API | ❌ | 实体抽取+对话，无则降级 |
| MinIO | ❌ | 照片/语音存储 |
| ASR/TTS | ❌ | 语音识别/合成，演示用模拟数据 |

---

## 真实后端模式

前端默认使用 Mock 数据，`api.js` 在 `mock-api.js` 之后加载，自动覆盖为真实后端调用。

**只需**：
1. 启动后端（`:8000`）
2. 数据库中插入测试患者（ID: `58b203df-5424-4f53-b155-82b34f840213`，设备码 `ABC123`）
3. 刷新前端页面

---

## 项目结构

```
AIX-health/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # 16 个路由模块（绑定/同意/记忆/对话/照片/简报/舒缓...）
│   │   ├── core/            # 核心服务（LLM引擎/人脸比对/TTS/推送/调度...）
│   │   ├── models/          # 14 个 SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 数据模式
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 异步数据库引擎
│   │   └── main.py          # 应用入口
│   ├── alembic/             # 数据库迁移
│   └── requirements.txt
├── caregiver-app/            # 家属端 PWA
│   ├── index.html
│   ├── manifest.json / sw.js
│   ├── css/caregiver.css
│   └── js/ (mock-api.js / api.js / main.js)
├── patient-app/              # 患者端相框
│   ├── index.html
│   ├── css/patient.css
│   └── js/ (mock-api.js / api.js / main.js / state-machine.js / ...)
├── frontend/                 # 家属端豪华版
├── PRD/                      # 产品需求文档
└── docs/                     # 详细文档
```

---

## 技术栈

| 层 | 技术 |
|:---|:---|
| 前端 | 原生 HTML/CSS/JS + PWA（无框架） |
| 后端 | FastAPI (Python) + SQLAlchemy (async) |
| 数据库 | PostgreSQL + Alembic |
| 对象存储 | MinIO（S3 兼容） |
| LLM | OpenAI 兼容 API（可替换） |
| ASR/TTS | 预留接口（FunASR / Coqui TTS） |
| 推送 | Web Push (VAPID) |
| 调度 | APScheduler |

---

> 详细文档见 [docs/项目使用指南.md](docs/%E9%A1%B9%E7%9B%AE%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97.md)（含 API 路由总表、常见问题、各模块详细说明）。
