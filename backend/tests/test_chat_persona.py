import uuid
from types import SimpleNamespace

import app.api.v1.chat as chat_mod
from app.core.chat_engine import ChatEngine
from app.schemas.chat import ChatMessageRequest


class _FakeExec:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _SeqDB:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, stmt):
        return _FakeExec(self.results.pop(0))

    async def commit(self):
        pass


def _config():
    return SimpleNamespace(
        persona_name="强叔", era="1980s", language="zh-CN",
        region={"city": "广州"},
    )


def test_build_prompt_persona_mode():
    eng = ChatEngine()
    msgs = eng.build_prompt(
        _config(), [], "无照片", "你在吗",
        photo_persona={"persona_name": "阿珍", "persona_relation": "老伴"},
    )
    assert "阿珍" in msgs[0]["content"]
    assert "老伴" in msgs[0]["content"]


def test_build_prompt_default_mode():
    eng = ChatEngine()
    msgs = eng.build_prompt(_config(), [], "无照片", "你在吗")
    assert "强叔" in msgs[0]["content"]
    assert "阿珍" not in msgs[0]["content"]


def test_chat_message_request_accepts_photo_id():
    req = ChatMessageRequest(
        session_id=uuid.uuid4(), asr_text="hi",
        photo_id=uuid.uuid4(),
    )
    assert req.photo_id is not None


async def test_chat_message_cloned_voice(monkeypatch):
    session = SimpleNamespace(
        id=uuid.uuid4(), patient_id=uuid.uuid4(), message_count=0,
    )
    persona_row = SimpleNamespace(
        id=uuid.uuid4(), voice_cloned=True,
        voice_sample_url="/voice/x/audio/a.webm",
        voice_clone_cfg={"prompt_text": "你好，我是阿珍"},
    )
    db = _SeqDB([session, persona_row])

    reply = {
        "reply_text": "我是阿珍，我记得你",
        "persona": "阿珍",
        "persona_id": persona_row.id,
        "voice_source": "cloned",
    }

    async def fake_reply(**kwargs):
        assert kwargs.get("photo_id") is not None
        return reply

    captured = {}

    async def fake_tts(text, language, patient_id, voice="default",
                       persona_id=None, ref_audio_url=None, ref_text=None):
        captured.update(voice=voice, ref_text=ref_text)
        return "http://audio/1.wav" if voice == "persona" else "http://audio/0.wav"

    monkeypatch.setattr(chat_mod.chat_engine, "generate_reply", fake_reply)
    monkeypatch.setattr(chat_mod, "synthesize_speech", fake_tts)

    req = ChatMessageRequest(
        session_id=session.id, asr_text="阿珍你在吗",
        photo_id=uuid.uuid4(),
    )
    resp = await chat_mod.chat_message(req, db=db)

    assert resp.voice_source == "cloned"
    assert resp.persona == "阿珍"
    assert captured["voice"] == "persona"
    assert captured["ref_text"] == "你好，我是阿珍"
    assert resp.reply_audio_url == "http://audio/1.wav"


async def test_chat_message_default_voice(monkeypatch):
    session = SimpleNamespace(
        id=uuid.uuid4(), patient_id=uuid.uuid4(), message_count=0,
    )
    db = _SeqDB([session])

    async def fake_reply(**kwargs):
        return {
            "reply_text": "今天厂里排休呢",
            "persona": "强叔",
            "persona_id": None,
            "voice_source": "default",
        }

    captured = {}

    async def fake_tts(text, language, patient_id, voice="default",
                       persona_id=None, ref_audio_url=None, ref_text=None):
        captured.update(voice=voice)
        return None

    monkeypatch.setattr(chat_mod.chat_engine, "generate_reply", fake_reply)
    monkeypatch.setattr(chat_mod, "synthesize_speech", fake_tts)

    req = ChatMessageRequest(session_id=session.id, asr_text="我要去上班")
    resp = await chat_mod.chat_message(req, db=db)

    assert resp.voice_source == "default"
    assert captured["voice"] == "default"
    assert resp.reply_audio_url is None
