# 数字记忆相框 系统设计文档

| 文档属性 | 详细信息 |
| :--- | :--- |
| **产品名称** | 数字记忆相框 |
| **文档版本** | v1.0 |
| **更新日期** | 2026-09-05 |
| **文档定位** | 技术实现团队系统设计参考，覆盖后端正向设计、前端架构概览与双端联动契约 |
| **前置文档** | [家属端 PRD v1.1](../PRD/家属端PRD.md)、[患者端 PRD v1.4.0](../PRD/数字记忆相框（患者端）PRD（含前端拟物化与演示架构）.md) |
| **实现路线** | 按 Phase 0–7 分段推进，每段独立分支（`phase/N-*`），独立可验证 |

---

## 目录

1. [系统概述与架构总览](#1-系统概述与架构总览)
2. [全局数据模型](#2-全局数据模型)
3. [核心业务流程](#3-核心业务流程)
4. [后端详细设计](#4-后端详细设计)
5. [患者端前端架构概览](#5-患者端前端架构概览)
6. [家属端前端架构概览](#6-家属端前端架构概览)
7. [双端数据联动契约](#7-双端数据联动契约)
8. [隐私、安全与伦理](#8-隐私安全与伦理)
9. [部署与环境](#9-部署与环境)
10. [分段实现路线（Phase 计划）](#10-分段实现路线phase-计划)

---

## 1. 系统概述与架构总览

### 1.1 产品定位

数字记忆相框 是一款基于消费级硬件的无感多模态认知陪伴与神经生理筛查系统，面向轻中度阿尔茨海默病（AD）患者及其家庭照护者。

系统由**两个客户端**和**一个共享后端**构成：

| 端 | 载体 | 目标用户 | 核心职责 |
| :--- | :--- | :--- | :--- |
| **患者端**（数字记忆相框） | 浏览器全屏 Web（iPad / PC） | AD/MCI 患者 | 验证疗法对话、老照片轮播、眼动/声学采集、日落舒缓 |
| **家属端**（家属助手） | 手机 PWA | 家庭核心照护者 | 扫码绑定、微信式增量建档、记忆库管理、每日简报、异常预警 |
| **共享后端** | FastAPI 服务 | — | 数据存储、LLM 编排、ASR/TTS、人脸比对、简报批处理、推送 |

### 1.2 全局架构图

```
┌────────────────────────────────────────────────────────────────────────┐
│                          共享后端（FastAPI）                            │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ API路由层  │ │LLM 编排  │ │ASR/TTS   │ │人脸比对  │ │定时任务  │  │
│  │ (REST/SSE) │ │(实体抽取)│ │(语音处理) │ │(特征比对) │ │(简报计算)│  │
│  │            │ │(对话引擎)│ │(声音克隆) │ │          │ │(推送触发)│  │
│  └─────┬──────┘ └────┬─────┘ └────┬─────┘ └─────┬────┘ └─────┬────┘  │
│        │             │            │            │            │         │
│  ┌─────┴──────────────────────────────────────────────────────┴─────┐ │
│  │                        数据层                                      │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐    │ │
│  │  │ PostgreSQL   │  │     MinIO        │  │   LLM / ASR      │    │ │
│  │  │ + pgvector   │  │ 对象存储         │  │ 外部 API/本地模型│    │ │
│  │  │ 业务+向量数据 │  │ 照片/音频/视频   │  │                  │    │ │
│  │  └──────────────┘  └──────────────────┘  └──────────────────┘    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────┐   ┌─────────────────────────────┐
│  患者端（相框 Web）  │   │  家属端（手机 PWA）          │
│  全屏 Web App       │   │  PWA（可安装/推送）          │
│  MediaPipe(眼动)    │   │  WebRTC(录音)                │
│  Web Audio(声学)    │   │  相册/相机 API               │
│  COLD_START         │   │  微信式对话流                 │
│  STANDBY            │   │  记忆库浏览                   │
│  CHAT               │   │  每日简报                     │
│  SOOTHING           │   │  异常推送                     │
└─────────────────────┘   └─────────────────────────────┘
```

### 1.3 设计原则

1. **无感与零门槛（Zero-Friction）**：家属端模拟微信聊天交互；患者端全流程零文字输入、操作 ≤ 2 次点击。
2. **实时闭环（Real-time Sync）**：家属输入的增量记忆即时解析并同步至患者端，直接赋能数字人对话。
3. **可解释与去医学化（De-medicalized Insight）**：将眼动、声学等生理指标转化为直观的"认知活力指数"与沟通建议，避免晦涩术语。
4. **多人协作与合规优先（Shared & Consent-first）**：一患者可绑定多位家属共享记忆库与简报；采集人脸/语音必须以逐人知情同意为前提。

### 1.4 技术栈总览

| 层次 | 技术 | 说明 |
| :--- | :--- | :--- |
| **后端框架** | FastAPI (Python 3.11+) | REST API + SSE，异步优先 |
| **数据库** | PostgreSQL 16 + pgvector 0.7+ | 业务数据 + 向量嵌入 |
| **对象存储** | MinIO (S3-compatible) | 照片原件/语音样本/克隆音色/微动视频 |
| **ORM** | SQLAlchemy 2.0 (async) | — |
| **迁移** | Alembic | — |
| **配置** | pydantic-settings (.env) | — |
| **ASR** | 开源方案（如 FunASR / Whisper 本地部署） | 普通话/英语，准确率 ≥ 90% |
| **TTS** | 开源方案（如 Coqui TTS / GPT-SoVITS） | 语速 0.85x，支持零样本克隆 |
| **LLM** | OpenAI Next（deepseek-v4-flash） | 实体抽取 + 对话引擎 + 简报生成 |
| **人脸比对** | 开源方案（如 InsightFace） | 闭集 5-10 人，准确率 ≥ 95% |
| **患者端前端** | 纯前端 HTML/CSS/JS（或轻量框架） | 浏览器全屏 Web，MediaPipe FaceMesh + Web Audio |
| **家属端前端** | PWA（HTML/CSS/JS + Service Worker） | 手机浏览器可安装，Web Push API |
| **鉴权** | JWT + 手机号验证码 | 家属端登录；患者端靠设备 token |
| **部署** | 全本地手动启动（无容器） | — |

---

## 2. 全局数据模型

### 2.1 核心实体关系与数据流向图

```
                    ┌───────────────────────────────────────────────────┐
                    │                  共享后端                          │
                    │  ┌─────────────────────────────────────────┐     │
                    │  │             PostgreSQL                   │     │
                    │  │  ┌──────────┐    ┌──────────┐           │     │
                    │  │  │ Caregiver│◄──►│Patient   │           │     │
       ┌──────────┐ │  │  │ (家属)   │    │ (患者)   │           │     │
       │ 家属端   │ │  │  └────┬─────┘    └─────┬────┘           │     │
       │ (输入端) │─┼─┼───────┼────────────────┼─────────────────│     │
       └──────────┘ │  │       │                │                  │     │
          │①上传    │  │       ▼                ▼                  │     │
          │记忆/    │  │  ┌──────────┐   ┌──────────────┐         │     │
          │照片/    │  │  │ Consent  │   │PatientConfig │         │     │
          │语音样本 │  │  │(知情同意)│   │ (患者配置)   │         │     │
          ▼         │  │  └──────────┘   └──────────────┘         │     │
                   │  │                                              │     │
                   │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │     │
                   │  │  │ Memory   │  │  Photo   │  │ Persona  │  │     │
                   │  │  │ (记忆)   │  │ (照片)   │  │ (人物库) │  │     │
                   │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │     │
                   │  │       │              │              │        │     │
                   │  │       └──────────────┴──────────────┘        │     │
                   │  │              ▲                               │     │
                   │  │              │②患者端读取                    │     │
                   │  │  ┌──────────┐│                               │     │
                   │  │  │AssetPack ││                               │     │
                   │  │  │(资产包)  ││                               │     │
                   │  │  └──────────┘│                               │     │
                   │  └──────────────┼───────────────────────────────┘     │
                   │                 │                                     │
                   └─────────────────┼─────────────────────────────────────┘
                                     │ ②读取
                                     ▼
                              ┌──────────┐
                              │ 患者端   │
                              │ (消费端) │
                              └──────────┘

数据流向：
① 家属端 → 后端 POST：记忆/照片/语音样本/配置 → 写入 PostgreSQL + MinIO（云端存储）
② 患者端 → 后端 GET：从 PostgreSQL + MinIO 拉取记忆/照片/配置/资产包
③ 患者端 → 后端 POST：眼动/声学埋点 → 写入 PostgreSQL
④ 家属端 → 后端 GET：从 PostgreSQL 拉取简报/设备状态
```

### 2.2 表结构 DDL（核心 9 表）

#### 2.2.1 `patients` — 患者档案

```sql
CREATE TABLE patients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_code     VARCHAR(6) UNIQUE NOT NULL,   -- 6 位设备码
    display_name    VARCHAR(100),                  -- 患者显示名（家属设定，可选）
    status          VARCHAR(20) DEFAULT 'active',  -- active | disabled
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

#### 2.2.2 `caregivers` — 家属账号

```sql
CREATE TABLE caregivers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(20) UNIQUE NOT NULL,   -- 手机号
    name            VARCHAR(100) NOT NULL,          -- 家属姓名
    avatar_url      TEXT,                           -- 头像（可选）
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

#### 2.2.3 `care_bindings` — 家属-患者绑定关系

```sql
CREATE TABLE care_bindings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    caregiver_id    UUID NOT NULL REFERENCES caregivers(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL DEFAULT 'member',  -- admin | member
    consent_id      UUID,                                   -- 关联知情同意记录
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(patient_id, caregiver_id)
);
```

> 首位绑定该患者的家属自动获得 `admin` 角色，后续家属为 `member`。
> 管理员可修改配置、管理成员；成员可上传记忆/照片/语音样本、查看简报。

#### 2.2.4 `consents` — 知情同意记录

```sql
CREATE TABLE consents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caregiver_id    UUID NOT NULL REFERENCES caregivers(id),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    consent_version VARCHAR(20) NOT NULL,        -- 同意书版本号
    content_hash    VARCHAR(64) NOT NULL,        -- 当时签署内容的 SHA256
    signed_at       TIMESTAMPTZ DEFAULT now()
);
```

#### 2.2.5 `patient_configs` — 患者配置

```sql
CREATE TABLE patient_configs (
    patient_id      UUID PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    era             VARCHAR(20) NOT NULL,         -- e.g. "1980s", "1970s-1980s"
    region          JSONB NOT NULL DEFAULT '{}',  -- {"country":"CN","province":"广东","city":"广州"}
    language        VARCHAR(5) NOT NULL DEFAULT 'zh-CN',  -- zh-CN | en
    timezone        VARCHAR(50) DEFAULT 'Asia/Shanghai',
    persona_name    VARCHAR(50) DEFAULT '强叔',   -- 常驻角色名
    privacy_consent JSONB,                        -- {status, policy_version, confirmed_by, confirmed_at}
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

#### 2.2.6 `memories` — 记忆条目（含向量嵌入）

```sql
CREATE TABLE memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    caregiver_id    UUID NOT NULL REFERENCES caregivers(id),
    raw_text        TEXT NOT NULL,                 -- 原文（ASR 转写或直接输入的文本）
    photo_url       TEXT,                          -- 关联照片 URL（可选）
    entities        JSONB NOT NULL DEFAULT '{}',   -- {era, location[], event, preference[], photo_people[], confidence, missing[]}
    vector_embedding VECTOR(1536),                 -- 嵌入向量（维度取决于嵌入模型）
    sync_status     VARCHAR(20) DEFAULT 'synced',  -- synced | pending
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_memories_patient ON memories(patient_id);
CREATE INDEX idx_memories_entities ON memories USING GIN (entities);
CREATE INDEX idx_memories_vector ON memories USING ivfflat (vector_embedding vector_cosine_ops) WITH (lists = 100);
```

#### 2.2.7 `photos` — 照片记录

```sql
CREATE TABLE photos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    uploaded_by     UUID NOT NULL REFERENCES caregivers(id),
    object_url      TEXT NOT NULL,                 -- MinIO 对象 URL
    thumbnail_url   TEXT,                          -- 缩略图 URL
    persona_name    VARCHAR(100),                  -- 人物标注名（可选，如 "阿珍"）
    persona_relation VARCHAR(50),                  -- 关系标注（可选，如 "老伴"）
    face_embedding  VECTOR(512),                   -- 人脸特征向量（可选，由人脸比对模块填充）
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_photos_patient ON photos(patient_id);
CREATE INDEX idx_photos_face ON photos USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 50);
```

#### 2.2.8 `personas` — 人物库（含人脸特征 + 声音样本）

```sql
CREATE TABLE personas (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    name                VARCHAR(100) NOT NULL,       -- 人物称呼（如 "阿珍"、"父亲"）
    relation            VARCHAR(50),                 -- 关系（如 "老伴"、"工友"）
    face_embedding      VECTOR(512),                 -- 人脸特征向量
    sample_photo_url    TEXT,                        -- 参考照片 URL
    voice_sample_url    TEXT,                        -- 语音样本 URL（可选）
    voice_cloned        BOOLEAN DEFAULT FALSE,       -- 是否已克隆音色
    voice_clone_cfg     JSONB,                       -- 克隆音色配置（模型产出的配置数据）
    idle_video_url      TEXT,                        -- LivePortrait 微动视频 URL（可选）
    created_by          UUID REFERENCES caregivers(id),
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_personas_patient ON personas(patient_id);
CREATE INDEX idx_personas_face ON personas USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 20);
```

#### 2.2.9 `asset_packs` — 年代资产包

```sql
CREATE TABLE asset_packs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    era             VARCHAR(20) NOT NULL,
    region_key      VARCHAR(50),                     -- 地区标识，如 "CN-广东-广州"
    status          VARCHAR(20) DEFAULT 'generating', -- generating | ready | failed
    photo_urls      JSONB DEFAULT '[]',              -- 年代照片 URL 列表
    topic_library   JSONB DEFAULT '[]',              -- 话题库
    prompt_anchors  JSONB DEFAULT '[]',              -- Prompt 记忆锚点
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_asset_packs_patient ON asset_packs(patient_id);
```

### 2.3 MinIO 存储桶设计

| Bucket 名称 | 用途 | 目录结构 |
| :--- | :--- | :--- |
| `memories` | 老照片原件 + 缩略图 | `{patient_id}/{photo_id}_original.jpg` / `{patient_id}/{photo_id}_thumb.jpg` |
| `voice` | 语音样本 + 克隆音色 | `{patient_id}/samples/{persona_id}.wav` / `{patient_id}/cloned/{persona_id}.pth` |
| `avatars` | LivePortrait 微动视频 | `{patient_id}/{photo_id}_idle.mp4` |
| `asset-packs` | 年代资产包照片 | `public/{era}/{region_key}/{photo_name}.jpg` |

### 2.4 全局枚举与常量

```python
# 患者端状态机
PATIENT_STATES = ["COLD_START", "STANDBY", "CHAT", "SOOTHING"]

# 家属端角色
CAREGIVER_ROLES = ["admin", "member"]

# 同步状态
SYNC_STATUS = ["synced", "pending"]

# 资产包状态
ASSET_PACK_STATUS = ["generating", "ready", "failed"]

# 活力指数区间
VITALITY_LEVELS = {
    (80, 100): "活跃度高",
    (60, 79):  "反应平缓",
    (40, 59):  "需关注",
    (0, 39):   "建议关注变化",
}

# 印象标签类型
ENTITY_TYPES = ["era", "location", "event", "preference"]

# 语言支持
SUPPORTED_LANGUAGES = ["zh-CN", "en"]
```

---

## 3. 核心业务流程

### 3.1 全局业务流总图

```
┌─────────┐     ┌────────────┐     ┌──────────────┐     ┌─────────┐
│ 家属端  │     │  共享后端  │     │   患者端     │     │ 外部服务│
└────┬────┘     └─────┬──────┘     └──────┬───────┘     └────┬────┘
     │                │                   │                  │
     │ ① 扫码绑定请求  │                   │                  │
     │───────────────►│                   │                  │
     │                │ ② 查询设备码      │                  │
     │                │───► (PostgreSQL) ──│                  │
     │◄───────────────│ ③ 返回患者档案    │                  │
     │                │                   │                  │
     │ ④ 签署知情同意 │                   │                  │
     │───────────────►│ ⑤ 写入 consent    │                  │
     │                │───► (PostgreSQL) ──│                  │
     │                │                   │                  │
     │ ⑥ 首位家属?    │                   │                  │
     │◄───────────────│ 是→跳转初始化建档  │                  │
     │                │ 否→直接进入主界面  │                  │
     │                │                   │                  │
     │ ⑦ 提交年代+地区│                   │                  │
     │───────────────►│ ⑧ 生成资产包      │                  │
     │                │───► LLM 搜索 ──────│─────────────────►│
     │                │◄── 结构化物料 ─────│◄────────────────│
     │                │ ⑨ 写 asset_packs  │                  │
     │                │───► (pg/ MinIO) ───│                  │
     │                │                   │                  │
     │                │  ⑩ 配置下发       │                  │
     │                │──────────────────►│                  │
     │                │                   │ COLD_START→STANDBY│
     │                │                   │                  │
     │ ══════════════════════ 日常使用 ══════════════════════ │
     │                │                   │                  │
     │ ⑪ 语音/照片录入 │                   │                  │
     │───────────────►│ ⑫ ASR+LLM 抽取    │                  │
     │                │───► ASR/LLM ───────│─────────────────►│
     │◄───────────────│ ⑬ 返回记忆卡片    │                  │
     │                │                   │                  │
     │ ⑭ 同步记忆     │                   │                  │
     │                │──────────────────►│ ⑮ 对话引擎引用   │
     │                │                   │                  │
     │                │ ═══ 每日批处理 ═══ │                  │
     │                │ ⑯ 计算活力指数    │                  │
     │                │◄── 拉取埋点数据 ───│                  │
     │                │ ⑰ 生成简报        │                  │
     │◄───────────────│ ⑱ 推送异常预警    │                  │
     │                │                   │                  │
```

### 3.2 设备绑定与配置下发流程

参见 [3.2 节家属端 PRD](../PRD/家属端PRD.md#31-模块零扫码绑定与知情同意-f-f00-pre)，该流程涉及两端联动：

1. 患者端首次启动 → 显示 QR 码（含 6 位设备码）→ 进入 `COLD_START`
2. 家属端扫码 → `POST /api/v1/bindings/scan` → 后端匹配 `patients.device_code`
3. 后端判断该患者是否已有绑定：
   - 无绑定 → 标记该家属为 `admin`，返回 `new_patient`
   - 已有绑定 → 返回 `existing_patient`
4. 家属端展示知情同意书 → 家属签署 → `POST /api/v1/consents`
5. 若为首位家属：
   - 家属端引导填写 `era` + `language` + `region`
   - 后端触发资产包生成（异步 LLM 任务）
   - 资产包就绪后，后端写 `patient_configs` + `asset_packs`
6. 患者端轮询配置 → `GET /api/v1/patients/config` → 拉取配置 + 资产包 → 进入 `STANDBY`

### 3.3 增量记忆闭环流程

1. **家属端入口**：语音（5-10s）/ 文本 / 照片（1 张） → 可组合发送
2. **后端 Pipeline**：
   - Step 1：ASR 转文字（语音路径）
   - Step 2：照片上传至 MinIO + 生成缩略图
   - Step 3：LLM 多模态实体抽取（文本 + 可选照片）
   - Step 4：人脸特征比对（含照片时，与患者人物库比对）
   - Step 5：实体归一化与校验
   - Step 6：生成记忆卡片 → 返回前端
   - Step 7：确认后写入 `memories`（含向量嵌入）
   - Step 8：同步患者端（SSE 推送或患者端轮询）
3. **患者端消费**：对话引擎检索 `memories` 中的向量嵌入，按语义相似度引用

### 3.4 每日简报生成流程

1. **触发**：每日固定时间（如晚上 23:00）批处理任务
2. **输入**：患者端前一日采集的眼动/声学 session 数据
3. **计算**：
   - 活力指数：4 项指标 > 个体 7 天基线归一化 > 加权求和（注视 40% + 扫视 30% + 声学 30%）
   - 高共鸣话题：按注视时长 + 对话轮次 + 主动发声次数的综合排序
4. **LLM 生成**：基于高共鸣话题 + 关联记忆实体，实时生成验证疗法沟通建议
5. **推送判断**：活力指数 < 40 → 触发 PWA 推送通知所有绑定家属
6. **存储**：简报 JSON 存入 `daily_briefs` 表（见 4.7），家属端按日期查询

---

## 4. 后端详细设计

### 4.1 API 契约总览

#### 4.1.1 鉴权体系

| 鉴权方式 | 适用端 | 机制 |
| :--- | :--- | :--- |
| **JWT Bearer Token** | 家属端 | 手机号 + 验证码登录获得 JWT，有效期 30 天，Refresh Token 自动续期 |
| **Device Token** | 患者端 | 首次绑定后服务端下发一次性设备 token，持久有效直至解绑 |
| **内部服务调用** | 后端内部 | 无额外鉴权（本地环境） |

#### 4.1.2 API 路由一览

```
──────────────────────────────────────────────────────────────
# ── 设备绑定与配置 ──
POST   /api/v1/bindings/scan              # 扫码绑定
POST   /api/v1/bindings/complete          # 完成配置（仅admin）
GET    /api/v1/patients/config            # [设备Token] 患者端拉取配置
POST   /api/v1/patients/config            # [Admin] 更新患者配置

# ── 知情同意 ──
POST   /api/v1/consents                   # 签署知情同意
GET    /api/v1/consents/{patient_id}      # 查询已签署的同意记录

# ── 记忆管理 ──
POST   /api/v1/memories                   # [家属] 提交记忆（语音/文字/照片）
PUT    /api/v1/memories/{id}              # [家属] 编辑记忆实体
DELETE /api/v1/memories/{id}              # [家属] 删除记忆（硬删除）
GET    /api/v1/memories                   # [家属] 查询记忆（按患者+标签筛选）

# ── 照片管理 ──
POST   /api/v1/photos                     # [家属] 上传照片（含人物标注可选）
GET    /api/v1/photos                     # [家属/患者端] 查询照片列表

# ── 人物库 ──
POST   /api/v1/personas                   # [家属] 创建人物库条目（首次标注）
PUT    /api/v1/personas/{id}/voice        # [家属] 上传语音样本 + 触发克隆
GET    /api/v1/personas                   # [家属] 查询人物库

# ── 对话引擎（患者端调用）──
POST   /api/v1/chat/message               # [设备Token] 提交患者语音/ASR文本，返回数字人回复
POST   /api/v1/chat/session/start         # [设备Token] 开始对话 session
POST   /api/v1/chat/session/end           # [设备Token] 结束对话 session（上报埋点）

# ── 埋点上报（患者端调用）──
POST   /api/v1/biometrics/gaze            # [设备Token] 上报眼动数据
POST   /api/v1/biometrics/acoustic        # [设备Token] 上报声学数据
POST   /api/v1/biometrics/session         # [设备Token] 上报会话级汇总

# ── 每日简报 ──
GET    /api/v1/briefs/{date}              # [家属] 获取指定日期简报（最近 7 天）
GET    /api/v1/briefs/latest              # [家属] 获取最新简报

# ── 设备状态 ──
GET    /api/v1/devices/status             # [家属] 获取患者端在线状态
POST   /api/v1/devices/heartbeat          # [设备Token] 患者端心跳

# ── 系统 ──
GET    /health                            # 健康检查
```

### 4.2 LLM Pipeline 详细设计

**LLM 集成方式**：后端 FastAPI 通过 OpenAI 兼容 API 接口调用 `deepseek-v4-flash` 模型，由 `https://api.openai-next.com/v1` 代理。所有 LLM 调用（实体抽取、对话引擎、简报生成）统一走此通道，通过 `openai` Python SDK 或 httpx 直接请求。

```python
# 调用示例（伪代码）
import openai

client = openai.AsyncOpenAI(
    api_key="sk-...",
    base_url="https://api.openai-next.com/v1"
)
response = await client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[...],
    response_format={"type": "json_object"}  # 实体抽取场景
)
```

#### 4.2.1 实体抽取模块（记忆入库）

**输入**：家属端发送的文本（ASR 转写或直接输入） + 可选照片
**输出**：结构化 JSON（era, location[], event, preference[], photo, confidence, missing[]）

**Prompt 架构**：

```text
【System Prompt】（固定模板，参见 PRD 3.3.1 D 节）
你是"记忆实体抽取器"。从家属描述的老人生活片段（可能含一张老照片）中，
提取实体并输出 JSON：
...

【上下文】（由后端注入患者画像）
患者出生年代：{patient_era}（{era_desc} 成年）
患者语言：{language}

【User 输入】
原文：{raw_text}
{若有照片：含照片 URL，LLM 视觉分析参与抽取}
```

**降级策略**：

| 异常场景 | 处理 |
| :--- | :--- |
| LLM 超时/限流 | 指数退避重试 2 次 → 失败后暂存草稿 |
| 输出非 JSON | 重试 1 次（附加 "只输出 JSON" 纠正提示）→ 降级为原文入库 |
| 全空实体 | 返回 "未识别到记忆信息" 提示 |
| confidence < 0.6 | 标记 "待确认"，不自动确认 |

#### 4.2.2 对话引擎模块（患者端验证疗法对话）

**角色体系**（双层）：

| 角色 | 触发条件 | Prompt 策略 |
| :--- | :--- | :--- |
| **常驻角色「老街坊」** | 默认 | 固定角色设定（同龄街坊）+ 患者年代记忆锚点 + 当前轮播照片上下文 |
| **照片亲人模式** | 注视已标注照片 ≥ 5s / 开口说出人物名 | Prompt 切换为该人物身份（"我是阿珍"）+ 其记忆关联 + 克隆声音（如有） |

**核心对话规则**（硬编码到 System Prompt）：

1. **时空错位不纠错**：患者说 "我要去上班" → 回复 "今天厂里排休呢"（禁止出现 "退休/你不是/你记错了"）
2. **引用记忆**：从 `memories` 向量库检索 Top 3 相关记忆，自然穿插引用
3. **语言一致**：使用患者配置的语言（zh-CN / en）
4. **简洁回复**：普通话回复 ≤ 40 字，英语回复 ≤ 40 词

**对话 Session 流程**：

```
患者端 CHAT 状态
  │  老人开口 / 连续注视 ≥ 5s
  ▼
POST /api/v1/chat/session/start  → 返回 session_id
  │
  ▼
循环：
  1. ASR 采集老人语音 → 转文本
  2. POST /api/v1/chat/message { session_id, asr_text, photo_context }
  3. 后端：
     a. 检索相关记忆 (pgvector 余弦相似度)
     b. LLM 生成回复（含验证疗法约束）
     c. TTS 合成语音
     d. 返回 { reply_text, reply_audio_url, persona, voice_source }
  4. 患者端播报 TTS + 显示大字幕
  │
  ▼  老人静默 ≥ 90s
POST /api/v1/chat/session/end → 上报埋点汇总
```

#### 4.2.3 简报沟通建议生成模块（每日批处理）

**触发**：每日批处理任务，在处理完活力指数计算后调用。

**输入**：
- 当日 Top 3 高共鸣话题（话题名、注视时长、对话轮次）
- 各话题关联的记忆实体

**Prompt**：

```text
你是验证疗法沟通顾问，为家属提供今日与 AD 老人的沟通建议。

今日高共鸣话题：
1. {话题A} - 注视 {X}s, 对话 {Y} 轮
2. {话题B} - 注视 {X}s, 对话 {Y} 轮

沟通原则：
1. 顺应老人的时空（不纠错）
2. 基于高共鸣话题建议具体切入点
3. 每条建议给出「聊什么」+「避坑提醒」

输出 1-2 条建议，每条 ≤ 100 字。
```

### 4.3 ASR / TTS / 声音克隆

#### 4.3.1 ASR（自动语音识别）

| 属性 | 规格 |
| :--- | :--- |
| **语言** | 普通话 (zh-CN) / 英语 (en) |
| **输入** | WebM/Opus 音频（家属端）/ WAV（患者端） |
| **准确率要求** | ≥ 90% |
| **延迟要求** | ≤ 1.5s |
| **选型** | 开源方案（如 FunASR / Whisper 本地部署），FastAPI 旁路调用，可替换 |

**集成方式**：FastAPI 接收音频文件后上传至 MinIO，调用开源 ASR 服务（如 FunASR / Whisper）返回转写文本。

#### 4.3.2 TTS（文本转语音）

| 属性 | 规格 |
| :--- | :--- |
| **语速** | 0.85x（适老化慢速） |
| **音色** | 默认音色（按语言）+ 克隆音色（照片亲人模式命中时） |
| **延迟** | ≤ 2s（预合成 + 缓存） |
| **选型** | 开源方案（如 Coqui TTS / GPT-SoVITS），FastAPI 旁路调用，可替换 |

**缓存策略**：常用回复文本（如过渡语 "天快黑了……"）预合成缓存；个性化克隆音色在后台上传样本时预合成配置，对话时直接使用。

#### 4.3.3 声音克隆

| 属性 | 规格 |
| :--- | :--- |
| **方案** | 零样本克隆（OpenVoice v2 / CosyVoice 零样本模式） |
| **输入** | 数秒参考音频（家属端上传） |
| **算力** | CPU / 低配 GPU，走后端预合成 |
| **失败策略** | 静默回退默认音色，不阻断对话 |

**触发流程**：
1. 家属端上传语音样本 + 归属人名 → `POST /api/v1/personas/{id}/voice`
2. 后端异步执行克隆 → 生成音色配置缓存
3. 患者端照片亲人模式命中时 → 查 `persona.voice_cloned === true` → 使用克隆音色 TTS

### 4.4 人脸特征比对模块

| 属性 | 规格 |
| :--- | :--- |
| **方案** | 开源方案（如 InsightFace 本地部署） |
| **场景** | 闭集小样本（单患者人物库 5-10 人） |
| **准确率** | ≥ 95% |
| **流程** | 检测 → 特征提取(512维) → 余弦相似度比对 |

**工作流程**：

```
家属上传含照片记忆
  │
  ▼
检测照片中是否含人脸
  ├── 无人脸 → 跳过比对，photo_people: []
  │
  ▼  有人脸
提取 face_embedding (512维)
  │
  ▼
与该患者人物库(personas)中所有 face_embedding 做余弦相似度比对
  ├── 最高相似度 ≥ 阈值(如 0.7) → 匹配，填充 photo_people: ["阿珍"]
  ├── 最高相似度 < 阈值 → 标记 "未知人物"，家属可人工标注入库
  │
  ▼
首次标注 → POST /api/v1/personas → 写入人物库，供后续复用
```

### 4.5 每日简报批处理与活力指数算法

#### 4.5.1 活力指数计算

**输入指标**（来自患者端埋点）：

| 指标 | 定义 | 方向 | 权重 |
| :--- | :--- | :--- | :--- |
| 注视维持时长 | 单次交互中注视总时长均值 | 越长越活跃 | 40% |
| 扫视潜伏期 | 刺激呈现到首次扫视的延迟均值 | 越短越活跃 | 30% |
| 声学停顿延迟 | 对话中回答前的停顿时长均值 | 越短越活跃 | 30% |

**计算步骤**：

1. **基线归一化**：各指标对比患者自身近 7 天基线，映射为 0-100 子分
   - `子分 = min(100, (当前值 - 基线最小值) / (基线最大值 - 基线最小值) * 100)`
   - 注视时长类指标：当前值越大子分越高
   - 潜伏期类指标：当前值越小（越快）子分越高 → `子分 = min(100, (基线最大值 - 当前值) / (基线最大值 - 基线最小值) * 100)`

2. **加权求和**：
   ```
   活力指数 = 注视子分 × 0.4 + 扫视子分 × 0.3 + 声学子分 × 0.3
   ```

3. **趋势标注**：对比昨日指数 → `较昨日 ±X%`

4. **等级映射**：

| 指数区间 | 状态等级 | 展示文案 |
| :--- | :--- | :--- |
| 80-100 | 活跃度高 | "今天精神头很好" |
| 60-79 | 反应平缓 | "今天状态平稳" |
| 40-59 | 需关注 | "今天有点疲惫，多陪陪" |
| < 40 | 建议就医随访 | "建议本周关注状态变化" |

#### 4.5.2 高共鸣话题判定

**输入**：患者端单次交互会话数据

| 信号 | 高共鸣阈值 |
| :--- | :--- |
| 注视时长 | ≥ 30 秒 |
| 对话轮次 | ≥ 3 轮 |
| 主动发声 | ≥ 2 次 |

**判定规则**：满足**任一条**即标记为"高共鸣话题"。

**排序**（倒序取 Top 3）：
```
共鸣分 = 注视时长(秒) + 对话轮次 × 10 + 主动发声 × 5
```

#### 4.5.3 简报批处理定时任务

**触发**：每日 23:00（可通过配置调整，按患者时区计算）

**流程**：
1. 查询前一日（自然日，按患者时区）所有 session 数据
2. 计算活力指数
3. 计算高共鸣话题 Top 3
4. LLM 生成沟通建议
5. 组装简报 JSON → 写入 `daily_briefs` 表
6. 活力指数 < 40 → 触发推送任务

**`daily_briefs` 表**：

```sql
CREATE TABLE daily_briefs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    date            DATE NOT NULL,
    vitality_index  INTEGER,                     -- null 表示基线期
    vitality_trend_pct INTEGER,                  -- 较昨日变化百分比
    baseline_status VARCHAR(20) DEFAULT 'ready', -- collecting | ready
    baseline_days_remaining INTEGER DEFAULT 0,
    top_topics      JSONB DEFAULT '[]',          -- [{topic_name, gaze_duration, dialogue_turns}]
    advice_text     TEXT,                        -- LLM 生成沟通建议
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(patient_id, date)
);
```

### 4.6 PWA 推送服务

#### 4.6.1 推送架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  家属端 PWA  │     │ 后端推送服务  │     │ Web Push 网关    │
│  (Service    │◄────│  (FastAPI)   │────►│ (VAPID 协议)     │
│   Worker)    │     │  push events │     │ 第三方/自建      │
└──────────────┘     └──────────────┘     └──────────────────┘
```

#### 4.6.2 推送触发条件（MVP）

| 条件 | 推送范围 | 推送内容 |
| :--- | :--- | :--- |
| 活力指数 < 40 | 该患者所有已绑定家属 | "今天老人的精神状态不太好，建议多陪陪他" + 简报链接 |
| 长时间无交互 | MVP 暂不实现 | — |

#### 4.6.3 VAPID 密钥管理

- 后端生成 VAPID 公私钥对
- 家属端 PWA 首次授权时，将 PushSubscription 上传至后端
- 推送时后端用 VAPID 私钥签发请求

**表结构**（推送订阅存储）：

```sql
CREATE TABLE push_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caregiver_id    UUID NOT NULL REFERENCES caregivers(id),
    endpoint        TEXT NOT NULL,
    p256dh_key      TEXT NOT NULL,
    auth_key        TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 4.7 定时任务一览

| 任务 | 周期 | 职责 |
| :--- | :--- | :--- |
| 每日简报生成 | 每日 23:00 | 计算活力指数 + 高共鸣话题 + LLM 建议 |
| 异常推送 | 简报生成后 | 活力指数 < 40 → 推送 |
| 资产包重试 | 每 10 分钟 | 对 `status=failed` 的资产包重试生成（最多 3 次） |
| 会话清理 | 每日 04:00 | 清理超过 30 天的完整对话日志（保留聚合指标） |

### 4.8 存储选型映射

```
┌─────────────────────┬──────────────────┬──────────────────────────┐
│       数据           │     存储位置     │      说明                │
├─────────────────────┼──────────────────┼──────────────────────────┤
│ 业务结构化数据      │ PostgreSQL       │ 患者/家属/绑定/配置/简报 │
│ 记忆向量嵌入        │ pgvector(Postgre)│ 对话引擎语义检索        │
│ 人脸特征向量        │ pgvector(Postgre)│ 人脸比对                 │
│ 照片原件/缩略图     │ MinIO memories   │ 家属上传老照片           │
│ 语音样本/克隆音色   │ MinIO voice      │ 声音克隆素材与产物      │
│ 微动视频            │ MinIO avatars    │ LivePortrait 预生成      │
│ 年代资产包照片      │ MinIO asset-packs│ 初始化资产包             │
│ 原始录音（永久保存） │ MinIO voice      │ 家属端录音 / 患者端录音│
│ 推送订阅            │ PostgreSQL       │ PWA 推送端点             │
│ 患者端埋点数据      │ PostgreSQL        │ 眼动/声学 session 数据  │
└─────────────────────┴──────────────────┴──────────────────────────┘
```

---

## 5. 患者端前端架构概览

### 5.1 状态机

患者端为单屏多状态应用，4 个状态：

```
                  ┌─────────────────────────────────────┐
                  │            COLD_START                │
                  │  展示二维码 + 设备码，等待家属绑定    │
                  └──────────────┬──────────────────────┘
                                 │ 家属绑定 + 配置就绪
                                 ▼
                  ┌─────────────────────────────────────┐
                  │            STANDBY                   │
                  │  全屏照片轮播（10s/张，淡入淡出800ms）│
                  │  麦克风持续监听（默认）               │
                  │  眼动持续追踪                        │
                  └──────┬──────────────┬───────────────┘
                         │ 老人说话     │ 连续注视 ≥ 5s
                         │ 或           │
                         ▼              ▼
                  ┌─────────────────────────────────────┐
                  │            CHAT                      │
                  │  数字人对话（老街坊/照片亲人模式）    │
                  │  大字幕 + TTS 播报（0.85x）          │
                  │  眼动/声学采集                        │
                  │  静默 90s → 回 STANDBY               │
                  └──────┬──────────────────────────────┘
                         │ 17:00-19:30 + 负面信号触发
                         ▼
                  ┌─────────────────────────────────────┐
                  │          SOOTHING                    │
                  │  暖色滤镜渐变 + 40Hz 白噪音背景      │
                  │  倾听姿态（不主动提问）               │
                  │  20min 无信号 / 19:30 → 回 STANDBY   │
                  └─────────────────────────────────────┘
```

### 5.2 模块划分概览

| 模块 | 职责 | 关键技术 |
| :--- | :--- | :--- |
| **状态管理** | 状态机流转（COLD_START / STANDBY / CHAT / SOOTHING） | 单例状态机 |
| **眼动追踪** | 基于 MediaPipe FaceMesh 的虹膜定位与注视落点判定 | MediaPipe 468 关键点 |
| **声学采集** | 麦克风实时采集、音量检测、VAD | Web Audio API |
| **对话 UI** | 数字人形象（L1 插画）、大字幕、声波动画 | CSS 动画 / Canvas |
| **照片轮播** | Ken Burns 视效、淡入淡出切换 | CSS transitions |
| **拟物化外壳** | 胡桃木外框、斜切衬垫、物理五金点缀 | CSS 多层渐变 + box-shadow |
| **HUD 模式** | 评委调试面板（?hud=1 或 D 键） | 叠加层，右侧抽屉 |
| **离线降级** | LLM 不可达时回退本地话术库、照片缓存 | localStorage / Service Worker |

### 5.3 双重视口架构

| 模式 | 触发 | 展示内容 |
| :--- | :--- | :--- |
| **老人纯净模式** | 默认 | 全屏相框，无任何技术参数 |
| **评委 HUD 模式** | URL 参数 `?hud=1` / 快捷键 D | 主相框左移，右侧滑出半透明面板：注视点十字光斑、声学曲线、Prompt 意图、音色标识 |

### 5.4 与后端的交互接口

| 接口 | 方法 | 用途 |
| :--- | :--- | :--- |
| `/api/v1/patients/config` | GET | 拉取配置 + 资产包（轮询） |
| `/api/v1/photos` | GET | 拉取照片列表 |
| `/api/v1/chat/message` | POST | 对话消息 |
| `/api/v1/chat/session/*` | POST | 会话生命周期 |
| `/api/v1/biometrics/*` | POST | 埋点上报 |
| `/api/v1/devices/heartbeat` | POST | 心跳 |

---

## 6. 家属端前端架构概览

### 6.1 应用形态

- **载体**：手机 PWA（可安装、支持系统级推送）
- **前端技术**：纯前端 HTML/CSS/JS + Service Worker（或轻量框架如 React/Vue，待定）
- **离线能力**：Service Worker 缓存静态资源 + 最近简报数据

### 6.2 页面的Tab结构

```
┌─────────────────────────────────────────┐
│  底部三 Tab 导航                          │
│                                           │
│  Tab 1: 💬 对话流（增量建档）              │
│  ─────────────────────────────────        │
│  微信风格对话列表                          │
│  输入区：语音(按住) / 文本 / 照片          │
│  实时反馈：记忆提取卡片                    │
│                                           │
│  Tab 2: 🗂️ 记忆库                        │
│  ─────────────────────────────────        │
│  标签筛选（地点/事件/喜好/年代）           │
│  卡片列表 + 编辑/删除入口                 │
│                                           │
│  Tab 3: 📊 每日简报                       │
│  ─────────────────────────────────        │
│  活力指数卡片                             │
│  高共鸣话题 Top 3                         │
│  沟通建议                                 │
│  日期选择（最近 7 天）                    │
└─────────────────────────────────────────┘
```

### 6.3 状态栏

顶部固定状态栏：患者相框在线状态 + 最近同步时间

### 6.4 核心交互模块

| 模块 | 职责 | 关键技术 |
| :--- | :--- | :--- |
| **扫码绑定** | 调用摄像头扫码 + 知情同意签署 | 浏览器扫码 API / Camera |
| **语音录入** | MediaRecorder 采集 5-10s 音频 | WebRTC MediaRecorder (opus/webm) |
| **照片上传** | 相册选取或相机拍摄 | File API / Camera API |
| **记忆流** | 显示对话列表 + 实体卡片 | 虚拟滚动 / DOM 动态渲染 |
| **推送接收** | Service Worker 接收 Web Push | Push API + Notification API |
| **离线缓存** | 静态资源 + 简报数据缓存 | Cache API / IndexedDB |

### 6.5 与后端的交互接口

| 接口 | 方法 | 用途 |
| :--- | :--- | :--- |
| `/api/v1/bindings/*` | POST | 扫码绑定 |
| `/api/v1/consents` | POST | 签署知情同意 |
| `/api/v1/memories` | POST/GET/PUT/DELETE | 记忆管理 |
| `/api/v1/photos` | POST/GET | 照片上传/查询 |
| `/api/v1/personas` | POST/GET | 人物库管理 |
| `/api/v1/briefs/*` | GET | 简报查看 |
| `/api/v1/devices/status` | GET | 设备状态 |

---

## 7. 双端数据联动契约

### 7.1 记忆同步（家属 → 患者）

```
触发：家属编辑或确认记忆卡片
  │
  ▼
后端：写入 memories 表（含向量嵌入）
  │
  ▼
患者端在线时：
  ┌── 方式 A：SSE 推送（后端主动通知患者端有新记忆）
  └── 方式 B：患者端轮询（每 30s 查询 memories 更新）

患者端离线时：
  记忆正常入库，患者端上线后增量拉取（按 updated_at > 上次同步时间）
```

### 7.2 配置下发（家属 → 患者）

```
触发：首位家属完成初始化建档 / 管理员修改配置
  │
  ▼
后端：更新 patient_configs + 生成 asset_packs
  │
  ▼
患者端：轮询 GET /api/v1/patients/config
  返回 { config, asset_pack }
  │
  ▼
患者端：本地缓存至 localStorage，应用配置
```

### 7.3 指标回流（患者 → 家属）

```
患者端每轮对话/每个 session 结束后：
  │
  ▼
POST /api/v1/biometrics/session → 写入后端
  │
  ▼
每日 23:00 批处理：
  汇总 sessions → 计算活力指数 + 高共鸣话题 → 写入 daily_briefs
  │
  ▼
家属端：
  GET /api/v1/briefs/{date} → 获取简报展示
  PWA 推送（若活力指数 < 40）
```

### 7.4 异常事件通知（患者 → 家属）

```
SOOTHING 退出事件（settled_20min / time_window_end）：
  │
  ▼
POST /api/v1/devices/soothing-event → 写入后端
  │
  ▼
家属端在线：SSE 推送实时展示
家属端离线：下次打开时展示
```

---

## 8. 隐私、安全与伦理

### 8.1 知情同意流程

1. **每位家属绑定时单独签署**知情同意书，不因其他家属已同意而豁免
2. 同意书明确披露：
   - 采集内容：语音、文字、照片、人脸特征、眼动数据、声学数据
   - 用途：记忆资产、认知简报、数字人对话、声音克隆
   - 存储：原始录音永久保存，照片/特征加密存储
   - 人脸比对范围：仅限患者闭集人物库，不跨患者比对
   - 照片中非本人人物的授权：家属上传即代表担保已获得授权
3. 同意记录含：家属 ID、版本号、内容哈希、时间戳，可追溯

### 8.2 AI 身份披露策略

| 受众 | 策略 |
| :--- | :--- |
| **患者** | 数字人以"老街坊"或"亲人"身份对话，不主动披露 AI 身份（验证疗法临床要求） |
| **家属** | 绑定流程明确告知 "数字人由 AI 驱动"，提供完整对话记录可查 |
| **被追问时** | 不得撒谎（"我是陪你聊天的伙伴"），不得断言自己是人类 |

### 8.3 声音与影像克隆知情同意

- 上传他人语音样本/照片用于克隆时，家属必须勾选 "我已获得本人或其监护人的同意"
- 克隆音色仅用于该患者本人交互，不跨患者复用
- 家属删除语音样本/照片时，级联删除克隆音色与微动视频缓存

### 8.4 数据安全

| 措施 | 说明 |
| :--- | :--- |
| 全链路 HTTPS/TLS | 所有 API 通信加密 |
| 静态加密 | 数据库、对象存储启用加密 |
| 访问控制 | 设备 token 仅读所属患者数据；家属 token 仅操作关联患者 |
| 媒体访问 | 使用鉴权后的短期签名地址 |
| 免登录安全 | 长效 JWT Token，需评估安全存储与吊销机制 |

### 8.5 免责声明

本系统是陪伴与照护支持工具，**不是医疗器械**。不进行诊断、筛查判定或治疗建议。所有指标仅供日常参考，异常情况请咨询专业医师。

---

## 9. 部署与环境

### 9.1 本地开发环境

| 服务 | 安装方式 | 启动命令 | 默认端口 |
| :--- | :--- | :--- | :--- |
| PostgreSQL 16+ | 本地安装 | `pg_ctl start` | 5432 |
| pgvector | 在 PostgreSQL 中 `CREATE EXTENSION vector` | — | — |
| MinIO | 下载二进制 | `minio server ./data` | 9000 (API) / 9001 (Console) |
| FastAPI | pip install + uvicorn | `uvicorn app.main:app --reload` | 8000 |
| 患者端前端 | 静态文件服务器 | `python -m http.server` | 8080 |
| 家属端前端 | 静态文件服务器 | `python -m http.server` | 8081 |

### 9.2 环境配置（.env）

```bash
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/aixhealth

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_MEMORIES=memories
MINIO_BUCKET_VOICE=voice
MINIO_BUCKET_AVATARS=avatars
MINIO_BUCKET_ASSETS=asset-packs

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30

# LLM (OpenAI Next)
LLM_ENDPOINT=https://api.openai-next.com/v1
LLM_API_KEY=sk-LJUVK673m0fg9zTEC98eC0Ca16204d17990541FbBbA4Db83
LLM_MODEL=deepseek-v4-flash
LLM_PROVIDER=openai-next

# ASR (开源方案，如 FunASR / Whisper)
ASR_ENDPOINT=http://localhost:8200

# TTS (开源方案，如 Coqui TTS / GPT-SoVITS)
TTS_ENDPOINT=http://localhost:8300

# Web Push (VAPID)
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_CONTACT=admin@example.com

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 9.3 项目目录结构

```
aix-health/
├── PRD/                           # 产品需求文档
│   ├── 家属端PRD.md
│   └── 数字记忆相框（患者端）PRD（含前端拟物化与演示架构）.md
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-09-05-retinaecho-system-spec.md   # 本文档
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── schemas/             # Pydantic 模型
│   │   ├── api/v1/              # 路由
│   │   ├── core/                # 业务逻辑
│   │   └── utils/               # 工具
│   ├── alembic/                 # 数据库迁移
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env
├── patient-app/                  # 患者端前端（静态 Web）
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── assets/
├── caregiver-app/                # 家属端前端（PWA）
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js                     # Service Worker
│   ├── css/
│   └── js/
├── scripts/                      # 部署/启动脚本
│   ├── start-postgres.sh
│   ├── start-minio.sh
│   └── start-all.sh
└── README.md
```

---

## 10. 分段实现路线（Phase 计划）

整个系统按 8 个 Phase 分段实现，每段独立分支、独立可测。

| Phase | 分支名 | 内容 | 前置依赖 | 可验证标准 |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 0** | `phase/0-infrastructure` | FastAPI 骨架 + PostgreSQL 建库 + MinIO 部署 + Alembic 迁移 + 健康检查 | 无 | `curl /health` → 200，数据库 9 张表就绪，MinIO buckets 可见 |
| **Phase 1** | `phase/1-binding` | 设备绑定 API + 知情同意 API + 患者端轮询配置 + 冷启动资产包生成 | Phase 0 | 家属端扫码 → 患者端进入 STANDBY |
| **Phase 2** | `phase/2-memory-ingestion` | 增量记忆 API（语音/文本/照片）+ ASR 接入 + LLM 实体抽取 + 记忆入库（含向量） | Phase 1 | 家属发消息 → 返回记忆卡片 → 数据写入 pgvector |
| **Phase 3** | `phase/3-patient-chat` | 患者端 STANDBY 轮播 + CHAT 对话引擎（老街坊角色）+ TTS 接入 | Phase 1 | 患者端轮播 → 开口触发对话 → 数字人回复 |
| **Phase 4** | `phase/4-photo-persona` | 照片上传 + 人脸比对 + 人物库管理 + 照片亲人模式 + 声音克隆 | Phase 2 + Phase 3 | 注视照片 5s → 变身亲人角色 → 克隆声音 |
| **Phase 5** | `phase/5-daily-brief` | 埋点上报 API + 活力指数计算 + 简报生成批处理 + 简报查看 API | Phase 3 | 每日 23:00 生成简报 → 家属端可查看 |
| **Phase 6** | `phase/6-soothing` | 日落舒缓模式 + 负面信号检测 + 退出事件通知 | Phase 3 | 触发舒缓 → 暖色 + 白噪音 → 退出通知家属 |
| **Phase 7** | `phase/7-pwa-push` | PWA Service Worker + Web Push 订阅/推送 + 记忆库管理 Tab + 异常预警 | Phase 5 | 活力指数 < 40 → 所有家属收到推送通知 |

### Phase 间依赖关系

```
Phase 0 (基础设施)
  │
  ├── Phase 1 (绑定+配置)
  │     ├── Phase 2 (记忆入库)
  │     │     └── Phase 4 (照片亲人)
  │     └── Phase 3 (患者对话)
  │           ├── Phase 5 (每日简报)
  │           │     └── Phase 7 (PWA推送)
  │           └── Phase 6 (日落舒缓)
  │
  └── 所有 Phase 依赖 Phase 0
```

---

> **本文档为系统级统一设计文档。** 每个 Phase 启动前，会据此输出该 Phase 的详细设计（API 详细签名、具体算法伪代码、测试用例），在对应分支上实现。
