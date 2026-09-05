# Fix 分支设计：图片+文字描述 & 语音系统落地

| 文档属性 | 详细信息 |
| :--- | :--- |
| **分支** | `fix/photo-caption-voice` |
| **更新日期** | 2026-09-05 |
| **定位** | 修复家属端「上传图片不能带文字描述」+ 将 ASR/TTS/声音克隆从占位落地为真实可用的语音系统 |
| **产品** | AIx-health 数字记忆相框（FastAPI + 原生 JS 双端） |

---

## 1. 背景与问题

### 1.1 问题 1：上传图片不能同时上传文字描述

家属端 **caregiver-app**（唯一在迭代/上线的 UI，另一套 `frontend/index.html` 豪华版为假上传演示，本轮不动）对话流中：

- 点 📷 选图后 **立即**以 `raw_text: '（照片描述）'` 提交（`caregiver-app/js/main.js` `handlePhotoSelected`），输入框里已输入的文字被无视；
- 后端 `POST /memories` 本就支持 `raw_text + photo_url(data URL)` 同传（`backend/app/api/v1/memories.py`），`raw_text` 为空或占位时由视觉模型 `describe_image` 自动生成描述 —— 链路后端完整，缺的是前端组合发送交互。

目标交互（已确认）：**微信式组合发送** —— 选图后不自动发送，弹出 composer（缩略图 + 描述输入框），确认后图片与描述作为一条记忆一起提交。

### 1.2 问题 2：声音系统仍为占位

三处占位：`backend/app/core/asr_service.py`、`tts_service.py`、`voice_clone.py`。相关前端全部为模拟：

- 家属端 🎤 按住录音是假定时器，松手随机选一句罐头文本（`caregiver-app/js/main.js` `startRecording/stopRecording`）；
- 患者端 CHAT 是自说自话模拟循环（`patient-app/js/main.js` `simulateChat/chatLoop`），无麦克风、无音频播放；
- `personas.py` 上传语音样本后调 `trigger_voice_clone` 恒返回 `False`；
- `upload_audio`（`minio_service.py:48`）直接传 `bytes` 给 `minio.put_object`，与 `upload_photo` 曾修复的报错同因（未包 `BytesIO`），实际会抛错。

### 1.3 已确认选型

| 项 | 选择 |
| :--- | :--- |
| ASR | **SenseVoice**（funasr `SenseVoiceSmall`），HTTP 旁路 `ASR_ENDPOINT=http://localhost:8200` |
| TTS/克隆 | **GPT-SoVITS**（官方仓库独立安装，不 vendoring），HTTP 旁路 `TTS_ENDPOINT=http://localhost:8300` |
| 克隆深度 | **参考音频即克隆（MVP）**：上传 3~10s 干净人声即作为音色参考，不做每角色微调训练 |
| 部署环境 | 本机 NVIDIA GPU，后端与模型服务同机 |
| 患者端克隆触发 | **照片亲人对话时用克隆**：患者端把当前照片 `photo_id` 带给 `/chat/message`，照片有人物标注且该人物已克隆 → 以该人物身份 + 克隆音色回复 |

---

## 2. 范围

### 2.1 本轮包含

1. caregiver-app「图片 + 文字描述」组合发送。
2. `voice-services/` ASR 微服务（SenseVoice）。
3. GPT-SoVITS 集成适配 + 后端 ASR/TTS/声音克隆占位转真 + 默认音色。
4. `POST /api/v1/audio/transcribe` 共用转写接口。
5. 家属端真实语音录记忆（按住说话 → 转写 → 提交记忆）。
6. 患者端语音对话闭环（VAD 监听 → 录音转写 → 对话 → TTS 播报 → 照片亲人克隆音）。
7. 打通 `minio_service.upload_audio` 的 `BytesIO` 缺陷、`.env.example` 缺键崩溃、config 默认值等配套修复。
8. README / voice-services 启动文档。

### 2.2 不在本轮

- `frontend/index.html`（豪华版）的假上传改造。
- 每角色 GPT-SoVITS 真微调训练流水线。
- 患者端眼动/注视触发、舒缓语音播报、离线降级细节。
- 相册/人物库 UI（caregiver-app 中尚不存在照片集页面）。

---

## 3. 详细设计

### 3.1 A. 家属端「图片 + 文字描述」组合发送

#### 交互流程

1. 用户点 📷 → `photoInput.click()`。
2. 选择文件后，`handlePhotoSelected` **不再立即发送**：用 `FileReader` 读 data URL 存入 `AppState.pendingPhoto = { dataUrl }`，并渲染 composer。
3. Composer（位于输入区上方）：图片缩略图、描述输入框（placeholder「补充这张照片的描述（可留空）」）、✕ 取消按钮。
4. 用户在 composer 输入描述后按 ➤（复用 `#btnSend`）或回车 → 提交；描述留空 → 提交占位 `（照片描述）`（触发后端视觉自动描述，行为与现状一致）。
5. 发送成功后追加照片气泡 + 记忆卡片（沿用现状渲染），清空 composer 与待发图。

#### 行为边界

- Composer 打开期间，`#chatInput` 不可见/被替换，避免两个输入框歧义；✕ 取消即恢复普通输入并丢弃待发图。
- 纯文本发送路径（无图）逻辑不变。
- 内存中始终只有一张待发照片（再次选图覆盖上一张），符合后端单 `photo_url` 语义。

#### 涉及文件

| 文件 | 改动 |
| :--- | :--- |
| `caregiver-app/index.html` | 输入区新增 composer 容器标记（默认隐藏） |
| `caregiver-app/js/main.js` | `AppState` 增 `pendingPhoto`；抽 `submitMemoryEntry({text, photo})`；改 `handlePhotoSelected` 为进 composer；新增 composer 的 描述输入/✕/回车 处理；`sendTextMessage` 改为复用 `submitMemoryEntry` |
| `caregiver-app/css/caregiver.css` | composer 面板样式（缩略图、输入框、取消按钮） |
| 后端 | 无改动（`POST /memories` 已支持） |

#### 关键代码现状锚点

- `caregiver-app/js/main.js:432-474` `handlePhotoSelected`（当前直接提交处）。
- `caregiver-app/js/main.js:332-383` `sendTextMessage`。
- `caregiver-app/index.html:50-55` 输入区；`index.html:143` `#photoInput`。

---

### 3.2 B. 语音模型服务（新增 `voice-services/`）

仓库根新增 `voice-services/`（与 `backend/`、`caregiver-app/` 平级），包含两个模型的**旁路服务**与安装文档。后端通过已预留的 `ASR_ENDPOINT=:8200` / `TTS_ENDPOINT=:8300` 走 HTTP 调用，模型与主后端进程隔离。

```
voice-services/
├── asr_server.py            # FastAPI :8200，funasr SenseVoiceSmall
├── audio_utils.py           # ffmpeg 归一化/转码封装（webm->wav16k / wav24k mono）
├── requirements-asr.txt     # funasr、torch 等（独立 venv）
└── README.md                # ASR 服务 + GPT-SoVITS 安装/启动/模型下载/ffmpeg 依赖

voice-runtime/               # 运行时目录（默认在仓库根，见 3.2.3，可 .gitignore）
└── refs/
    ├── default.wav          # 默认老街坊/强叔参考音（用户放置，3~10s 干净中文）
    └── default.prompt.txt   # 其转写文本（可选，也可用 DEFAULT_VOICE_REF_TEXT 配置）
```

#### 3.2.1 ASR 服务（`asr_server.py`）

- 框架：FastAPI + uvicorn，端口 8200（可用环境变量 `ASR_PORT` 覆盖）。
- 模型：`funasr` 的 `AutoModel(model="iic/SenseVoiceSmall", trust_remote_code=True, vad_model="fsmn-vad", ...)`，首次启动从 ModelScope 下载；**懒加载**（首次请求时才初始化，避免启动即占显存/卡住）。
- 端点：
  - `POST /asr`（multipart：`file` 音频、可选 `language=zh|en|auto`）→ `{"text": str, "language": str, "duration": float}`。
  - `GET /health` → `{"status":"ok"}`。
- 预处理：入参音频（浏览器录音为 `audio/webm;codecs=opus`）先经 `audio_utils.py` 用 ffmpeg 转 **wav 16k mono** 再喂模型；ffmpeg 缺失时返回 503 及明确提示。
- 并发：模型调用放入线程池（`asyncio.to_thread` / 简单 asyncio.Semaphore 限 1），避免重叠推理。

#### 3.2.2 GPT-SoVITS（官方仓库独立安装，只做适配）

- 不在本仓库安装 GPT-SoVITS。`voice-services/README.md` 给出步骤：克隆 `RVC-Boss/GPT-SoVITS` → 按官方装依赖并下载预训练模型（`GPT_SoVITS/pretrained_models/*`）→ 以 **API v2** 启动并指向 `:8300`：
  ```bash
  python api_v2.py -a 127.0.0.1 -p 8300 -c GPT_SoVITS/configs/tts_infer.yaml
  ```
- 适配层集中在一个模块（`backend/app/core/gpt_sovits.py`），**对接官方 `api_v2.py` 的 `POST /tts` JSON 契约**（已核对官方源码）：
  | 字段 | 取值 |
  | :--- | :--- |
  | `text` | 待合成文本 |
  | `text_lang` | `zh` / `en`（语言映射见 3.3.4） |
  | `ref_audio_path` | GPT-SoVITS 进程可读的**绝对路径**（本机共享目录 `voice-runtime/refs/...`） |
  | `prompt_text` | 参考音频的转写文本（默认音/克隆 cfg 提供） |
  | `prompt_lang` | `zh` / `en`（必填） |
  | `speed_factor` | `0.85`（适老化慢速） |
  | `text_split_method` | `cut5` |
  | `media_type` | `wav` |
  | `streaming_mode` | `False` |
  - 成功：HTTP 200 返回 wav 字节流；失败：HTTP 400 JSON `{"message": ..., "Exception": ...}`。
  - `ref_audio_path` 要求 GPT-SoVITS 服务进程与后端同机、可读同一本地目录；后端在调用前把参考音频确保存在于 `voice-runtime/refs/`（见 3.2.3）。

#### 3.2.3 参考音频落盘目录 `voice-runtime/`

后端与 GPT-SoVITS 服务同机，克隆/默认音色所需参考音频放本地目录（**不进 MinIO 也可，样本仍存 MinIO 留档**）：

- 目录：仓库根 `voice-runtime/refs/`；默认由 `config.py` 相对仓库根解析，可用环境变量 `VOICE_RUNTIME_DIR` 覆盖为绝对路径。
- `default.wav`：默认老街坊/强叔参考音（用户放置）+ `default.prompt.txt`（其文本，由 ASR 生成或手写）。
- `{persona_id}.wav` + `{persona_id}.prompt.txt`：人物库克隆音参考。

---

### 3.3 C. 后端占位模块转真与新增接口

#### 3.3.1 配置（`backend/app/config.py`、`backend/.env.example`、根 `.env.example`）

- 给 `ASR_ENDPOINT`、`TTS_ENDPOINT` 提供默认值 `http://localhost:8200` / `http://localhost:8300`（修：现无默认且 `.env.example` 缺键，用示例文件会直接崩 `Settings()`）。
- 新增配置项：
  - `ASR_TIMEOUT` / `TTS_TIMEOUT`（默认 30s）
  - `VOICE_RUNTIME_DIR`（默认：仓库根 `voice-runtime`，相对仓库根解析）
  - `DEFAULT_VOICE_REF`（默认音参考路径）、`DEFAULT_VOICE_REF_TEXT`（其转写文本，可空）
  - `TTS_DEFAULT_SPEED` = `0.85`
- 同步修正 `backend/.env.example` 与根 `.env.example`，补 ASR/TTS 及上述键，避免新用户直接复现崩溃。

#### 3.3.2 `asr_service.py`（转真）

```text
speech_to_text(audio_bytes, language="zh-CN") -> str
```
改为：`httpx` 以 multipart POST `{ASR_ENDPOINT}/asr`；超时/连接失败/非 2xx → 记 error 并抛 `ASRError`（业务侧决定是否降级）。调用前音频已由前端或上游归一为可解码格式；服务端仍做 ffmpeg 兜底转码。

#### 3.3.3 `tts_service.py`（转真）

```text
synthesize_speech(text, language, patient_id, voice="default",
                  ref_audio_url=None, ref_text=None) -> str | None
```
- 解析音色：
  - `voice="default"` → `DEFAULT_VOICE_REF` + `DEFAULT_VOICE_REF_TEXT`；
  - `voice="persona"` 时由调用方传 `ref_audio_url`（MinIO 对象）/ `ref_text`（`voice_clone_cfg.prompt_text`）。
- 流程：取参考音频 → （必要时 ffmpeg 转 wav24k mono 到 `voice-runtime/refs/`）→ 调 GPT-SoVITS `/tts`（语言映射：`zh-CN→zh`、`en→en`；`speed_factor=0.85`）→ 拿 wav 字节 → 上传 MinIO `{MINIO_BUCKET_VOICE}/{patient_id}/tts/{uuid}.wav` → 返回 **presigned URL**（`get_presigned_url`）。
- 任何失败 → 记 error，返回 `None`（调用方 `reply_audio_url=null`，对话不阻断）。
- 默认音未配置（无 `default.wav`）时，直接记 warning 返回 `None`。

#### 3.3.4 `voice_clone.py`（转真，参考音频即克隆）

```text
trigger_voice_clone(persona_id, voice_sample_url) -> bool
```
1. 经 `get_presigned_url` 下载样本 → ffmpeg 转 **wav 24k mono** → 存 `voice-runtime/refs/{persona_id}.wav`。
2. 调 ASR（`speech_to_text`）得到 `prompt_text`，并把语言映射为 GPT-SoVITS 语言码：患者配置/识别语言 `zh-CN → zh`、`en → en`，其他语言按 `zh` 处理（MVP 仅支持 zh/en）。
3. 校验时长 1s ≤ d ≤ 30s（样本过短/过长 → 记 cfg `{"error": ...}` 并返回 `False`，不设 `voice_cloned`）。
4. 写 `persona.voice_clone_cfg = {"prompt_text":..., "prompt_language":"zh"|"en", "ref_audio_path":..., "duration":..., "cloned_at":...}` 且 `persona.voice_cloned = True`，返回 `True`。

> 说明：所选 MVP 是「参考音频注册」，不产生新模型文件；`ref_audio_path` 仅记录便于排查，推理时按 `{persona_id}` 重新定位 `voice-runtime/refs/{persona_id}.wav`。

#### 3.3.5 新增转写接口（共用）

`backend/app/api/v1/audio.py`（新增，挂载到 `/api/v1`）：

```text
POST /api/v1/audio/transcribe
  multipart: file(音频), optional patient_id
  -> 200 {"text": str, "language": str}
  -> 503 {"detail": "ASR 服务不可用"}（服务端/ffmpeg 缺失）
```
内部：读字节 → `speech_to_text`。供家属端（录记忆）与患者端（语音对话）共用。

#### 3.3.6 `personas.py` 上传语音样本

- `PUT /personas/{persona_id}/voice`：上传后调用真实 `trigger_voice_clone`；成功后 `voice_cloned=True` 返回。
- `minio_service.upload_audio`：修复 `put_object` 传原始 `bytes` → 改为 `io.BytesIO(file_bytes)` 并传 `len(file_bytes)`（对齐 `upload_photo:34-41`）；`content_type` 由调用方按真实 mime 传入（默认 `audio/webm`）。

#### 3.3.7 `chat.py` + `chat_engine.py`（照片亲人克隆音）

- `schemas/chat.py` `ChatMessageRequest` 增可选字段 `photo_id: UUID | None = None`。
- `chat_engine.generate_reply(..., photo_id=None)`：
  1. 若 `photo_id` 提供，经 `check_photo_persona_mode` 查该照片人物（`persona_name`/`persona_relation`）；
  2. 命中人物 → LLM prompt 以**该人物身份**构建（如「你是阿珍，患者的…」）；返回 `persona=该人名`；
  3. 未命中 → 现状默认老街坊/`patient_config.persona_name`。
  返回字典增加 `persona_id: UUID | None` 与 `voice_source: "cloned" | "default"`（命中且该 Persona `voice_cloned` → `cloned`）。
- `chat.py` `chat_message`：
  1. `reply = generate_reply(...)`；
  2. TTS 音色选择：`voice_source=="cloned"` → 载入 Persona 的 `voice_clone_cfg`，以 `synthesize_speech(voice="persona", ref_audio_url=persona.voice_sample_url, ref_text=cfg.prompt_text, patient_id=session.patient_id)`；否则默认音色；
  3. 失败静默返回 `reply_audio_url=None`。
- 前端聊天角色名随之展示为照片人物名（阿珍等）。

#### 3.3.8 文件清单（后端）

| 文件 | 改动 |
| :--- | :--- |
| `backend/app/config.py` | 默认值 + 新增键（见 3.3.1） |
| `backend/app/core/asr_service.py` | httpx 调用 ASR 服务 |
| `backend/app/core/tts_service.py` | GPT-SoVITS 合成 + MinIO 上传 + presigned |
| `backend/app/core/voice_clone.py` | 下载→转码→ASR→校验→写 cfg/flag |
| `backend/app/core/gpt_sovits.py` | 新增：GPT-SoVITS HTTP 适配器（httpx） |
| `backend/app/core/audio_utils.py` | 新增：ffmpeg 转码封装（`voice-services/audio_utils.py` 若独立则可复用，避免重复） |
| `backend/app/api/v1/audio.py` | 新增 transcribe 路由，`main.py` 挂载 |
| `backend/app/api/v1/personas.py` | 真克隆触发接入 |
| `backend/app/api/v1/chat.py` | photo_id、克隆音选择、静默降级 |
| `backend/app/core/chat_engine.py` | 照片亲人 prompt 构建 + 返回 persona_id/voice_source |
| `backend/app/schemas/chat.py` | `photo_id` 字段 |
| `backend/app/core/minio_service.py` | upload_audio BytesIO 修复 + content_type |
| `backend/.env.example`、根 `.env.example` | 补键 |

> `voice-services/audio_utils.py` 与后端转码逻辑共享一份实现：优先将通用转码放 `voice-services/audio_utils.py`，后端按需 import 或在后端内置同逻辑副本；**以不引入跨目录 import 的部署负担为原则**，具体在实现计划中落定。

---

### 3.4 D. 前端语音

#### 3.4.1 家属端真实语音录记忆（caregiver-app）

- 保留「按住说话 → 松开发送」手势。
- `startRecording/stopRecording` 改造：`MediaRecorder`（`audio/webm;codecs=opus`）真实采集；不足 ~0.5s 视为误触取消；录音中 UI 走现有 recording 态。
- 松手 → blob → `MockAPI.transcribeAudio(blob)`（api.js 走 `POST /api/v1/audio/transcribe`）→ 文本 → 复用 `submitMemoryEntry({text})` → 追加气泡 + 记忆卡片。
- ASR 失败/无 mic → toast 提示并可回退当前模拟罐头话术（仅 mock 模式保留）。
- `api.js` / `mock-api.js`：新增 `transcribeAudio(blob)`（mock 返回固定句）。

#### 3.4.2 患者端语音对话闭环（patient-app）

新增 `patient-app/js/voice.js`（VAD/录音单例）：

- `getUserMedia` 常驻麦克风；`AnalyserNode` 音量均方根阈值检测说话开始/结束。
- **STANDBY**：监听中；VAD 检出说话 → `stateMachine.transition('speech_detected')` 进入 CHAT。
- **CHAT**：
  1. 用户说话 → 静音尾音 ~0.7s 判定切句 → `MediaRecorder` 产出该句 blob；
  2. `transcribeAudio(blob)` → 文本（空/过短则忽略）；
  3. 取轮播当前照片（`photoCarousel.getCurrentPhoto()`，仅当有 `persona_name` 才带）`photo_id` → `sendChatMessage({session_id, asr_text, photo_id})`；
  4. 展示 `result.reply_text` 大字幕、角色名（`#chat-persona-name`=阿珍等）、声波动画与 HUD voice_source；
  5. 若 `reply_audio_url` → 播放（新增 `<audio id="chat-audio">`）；**播放期间暂停 VAD 触发**（防自听回声），播完恢复监听。
  6. 无新语句超过 90s → `stateMachine.transition('silence_timeout')` 回 STANDBY。
- 状态机无需改动：`STANDBY --speech_detected--> CHAT` 与 `CHAT --silence_timeout--> STANDBY` 转移已存在（`state-machine.js` 转移表）。语音检测即调 `transition('speech_detected')`，空闲超时即调 `transition('silence_timeout')`。
- 麦克风/录音不可用（权限拒绝、非 https/localhost、无 MediaRecorder）→ 回退现有模拟循环，保证演示可用。
- `index.html`：CHAT 区加 `<audio>`；`js/api.js`/`js/mock-api.js` 增 `transcribeAudio`；api.js 的 `sendChatMessage` 允许 `photo_id`。
- 患者端加载照片的 `photo-carousel.js` 新增 `getCurrentPhoto()`：返回 `this._photos[this._currentIndex]`（含 `id`、`url`、`persona_name`）或 `null`；`persona_name` 取自照片对象（真实 GET /photos 已有该字段）。

#### 3.4.3 前端文件清单

| 文件 | 改动 |
| :--- | :--- |
| `caregiver-app/js/main.js` | 真实录音 + transcribe + `submitMemoryEntry` |
| `caregiver-app/js/api.js` / `mock-api.js` | 增 `transcribeAudio` |
| `patient-app/js/voice.js` | 新增 VAD/录音模块 |
| `patient-app/js/main.js` | CHAT 真闭环、空闲回退、照片上下文、暂停/恢复 VAD |
| `patient-app/js/photo-carousel.js` | 暴露 `getCurrentPhoto()` |
| `patient-app/index.html` | `<audio>` 元素 |
| `patient-app/js/api.js` / `mock-api.js` | 增 `transcribeAudio`、`photo_id` 透传 |

---

### 3.5 E. 文档与依赖

- `voice-services/README.md`：ASR 服务启停、funasr/ModelScope 下载、ffmpeg 依赖、GPT-SoVITS 官方仓库安装与 `:8300` 启动、默认音 `default.wav` 放置与 `default.prompt.txt` 生成方式。
- 根 `README.md`：补充语音落地段落（架构图、服务启动顺序：postgres/minio → asr(:8200) → gpt-sovits(:8300) → backend(:8000)）。
- `backend/requirements.txt`：仅增 `httpx`（若尚未有）等轻依赖；funasr/torch 只进 `voice-services/requirements-asr.txt`。

---

## 4. 错误处理与降级总表

| 场景 | 处理 |
| :--- | :--- |
| ASR 服务未启动/超时 | `/audio/transcribe` 返回 503；前端 toast「语音识别不可用」，可回退模拟 |
| ffmpeg 缺失 | ASR 服务 /asr 返回 503 与提示；克隆转码失败返回 False |
| GPT-SoVITS 未启动/超时 | `synthesize_speech` 记 error 返回 None → `reply_audio_url=null`，对话文字照常 |
| 默认音 `default.wav` 未配置 | TTS 记 warning 返回 None，不阻断 |
| 语音样本过短(<1s)/过长(>30s) | 克隆返回 False，`voice_clone_cfg.error` 记录原因，`voice_cloned` 保持 False |
| 照片无人物标注 / 人物未克隆 | 对话用默认老街坊身份与默认音色 |
| 患者端无 mic/权限拒绝/非 https | 回退现有模拟循环 |

---

## 5. 数据与接口变更小结

- 数据模型：无新增表。`personas.voice_clone_cfg`（JSONB，已有列）承载克隆注册信息。
- 接口：
  - 新增 `POST /api/v1/audio/transcribe`
  - 变更 `POST /api/v1/chat/message`（请求增可选 `photo_id`）
  - 变更 `PUT /personas/{id}/voice`（行为：真克隆）
- 外部服务：`ASR_ENDPOINT`(:8200)、`TTS_ENDPOINT`(:8300)。

## 6. 验证方式（人工 + 命令）

1. `python voice-services/asr_server.py` → `GET :8200/health`；curl 传一段中文 wav 验证文本。
2. 起 GPT-SoVITS（:8300）→ curl /tts 出 wav。
3. 起 backend → `POST /api/v1/audio/transcribe` 上传 webm 返回文本。
4. caregiver-app：先打字再选图/选图后补描述发送，验证记忆卡片文字=描述；选图不输描述仍走视觉识别。
5. caregiver-app 按住录音 → 记忆文字=识别结果。
6. 人物库上传语音样本（3~10s 中文）→ `voice_cloned=true` 且 `voice_clone_cfg.prompt_text` 非空。
7. patient-app：说话触发对话，得到克隆音/默认音播报与字幕；播放中无自触发循环；90s 空闲回 STANDBY。

## 7. 决策记录

| 决策 | 选择 | 原因 |
| :--- | :--- | :--- |
| 组合发送交互 | 微信式 composer 预览 | 用户确认 |
| 语音服务架构 | A 旁路 HTTP 微服务 | 进程隔离、GPU 同机、契合预留端口 |
| ASR | SenseVoice | 中文口语优化、自带标点 |
| TTS/克隆 | GPT-SoVITS 参考音频即克隆 | 用户确认 MVP，先打通闭环 |
| 克隆触发 | 照片亲人对话传 `photo_id` | 用户确认，最贴合真实叙事 |
