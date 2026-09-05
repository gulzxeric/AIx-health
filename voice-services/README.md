# voice-services 语音服务

AIx-health 的旁路语音模型服务。后端（:8000）通过 HTTP 调用，二者可独立启停。

| 服务 | 端口 | 说明 |
| :--- | :--- | :--- |
| ASR（SenseVoice） | 8200 | 本目录 `asr_server.py` |
| TTS（GPT-SoVITS） | 8300 | 官方仓库 `api_v2.py`，独立安装 |

## 0. 前置依赖

- Python 3.10+（建议 3.11）
- **ffmpeg**（必须，音频归一化）：Windows `winget install Gyan.FFmpeg`，装后在终端 `ffmpeg -version` 验证
- NVIDIA GPU（可选，ASR 用 `ASR_DEVICE=cuda` 加速）

## 1. ASR 服务（SenseVoice）

```bash
cd voice-services
python -m venv .venv
.venv\Scripts\pip install -r requirements-asr.txt
# GPU 加速：set ASR_DEVICE=cuda
.venv\Scripts\python asr_server.py          # 默认 127.0.0.1:8200
```

- 首次请求会从 ModelScope 自动下载 SenseVoiceSmall（约 1GB），请耐心等待。
- 验证：`curl http://127.0.0.1:8200/health`

## 2. GPT-SoVITS 服务（:8300）

在**本目录之外**（如 `../GPT-SoVITS`）克隆官方仓库并安装：

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS
# 按官方 README 安装依赖并下载预训练模型到 GPT_SoVITS/pretrained_models/
python api_v2.py -a 127.0.0.1 -p 8300 -c GPT_SoVITS/configs/tts_infer.yaml
```

验证：服务起来后，后端 `/chat/message` 的 TTS 会在有请求时自动调用。

## 3. 默认音色（必配一次）

GPT-SoVITS 是参考音频合成，**任何语音都需要参考音**。默认老街坊/强叔音：

1. 准备一段 3~10s 干净中文人声 wav（音色越接近目标越好）；
2. 放到仓库根 `voice-runtime/refs/default.wav`；
3. 把这段话的**文字内容**写入 `voice-runtime/refs/default.prompt.txt`（一行即可），
   或在 `backend/.env` 配 `DEFAULT_VOICE_REF` / `DEFAULT_VOICE_REF_TEXT`。

> 未配置时对话仍可用（纯文字回复，`reply_audio_url=null`）。

## 4. 人物库克隆音（参考音频即克隆）

`PUT /personas/{id}/voice` 上传 3~10s 样本即可，后端自动：转码 -> ASR 转写 ->
校验 -> 缓存到 `voice-runtime/refs/{persona_id}.wav` -> `voice_cloned=true`。
患者端轮播到该人物照片并对话时，自动用其克隆音色回复。

## 5. 启动顺序

postgres/minio（docker-compose.dev.yml）→ ASR(:8200) → GPT-SoVITS(:8300) → backend(:8000) → 前端
