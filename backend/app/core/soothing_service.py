import uuid
from datetime import datetime, time, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.patient_config import PatientConfig


async def get_soothing_config(patient_id: uuid.UUID, db) -> dict:
    """获取患者的舒缓配置

    从 patient_configs 表中读取舒缓配置（存储在 JSON 字段或独立字段）。
    若无配置则返回默认值。
    """
    stmt = select(PatientConfig).where(PatientConfig.patient_id == patient_id)
    result = await db.execute(stmt)
    cfg = result.scalar_one_or_none()

    # 从 patient_configs 的 extra 或 soothing_config 字段读取
    # 目前 patient_configs 尚无专门舒缓字段，先返回默认值
    soothing = (cfg.soothing_config or {}) if hasattr(cfg, "soothing_config") and cfg.soothing_config else {}

    return {
        "patient_id": patient_id,
        "sunset_start": soothing.get("sunset_start", "17:00"),
        "sunset_end": soothing.get("sunset_end", "19:30"),
        "auto_soothing": soothing.get("auto_soothing", True),
    }


async def update_soothing_config(patient_id: uuid.UUID, config: dict, db) -> dict:
    """更新患者的舒缓配置"""
    stmt = select(PatientConfig).where(PatientConfig.patient_id == patient_id)
    result = await db.execute(stmt)
    cfg = result.scalar_one_or_none()

    if cfg is None:
        raise ValueError(f"患者配置不存在: {patient_id}")

    # 更新 soothing_config 字段
    soothing = cfg.soothing_config or {} if hasattr(cfg, "soothing_config") else {}
    soothing.update({
        "sunset_start": config.get("sunset_start", soothing.get("sunset_start", "17:00")),
        "sunset_end": config.get("sunset_end", soothing.get("sunset_end", "19:30")),
        "auto_soothing": config.get("auto_soothing", soothing.get("auto_soothing", True)),
    })
    cfg.soothing_config = soothing
    await db.commit()

    return {
        "patient_id": patient_id,
        "sunset_start": soothing["sunset_start"],
        "sunset_end": soothing["sunset_end"],
        "auto_soothing": soothing["auto_soothing"],
    }


async def check_sunset_window(patient_id: uuid.UUID, db) -> dict:
    """检查当前是否在日落时间窗口内

    从患者配置读取日落窗口时间，对比当前服务器时间。
    返回: {in_window, window_start, window_end, remaining_minutes}
    """
    config = await get_soothing_config(patient_id, db)
    sunset_start_str = config["sunset_start"]
    sunset_end_str = config["sunset_end"]

    now = datetime.now(timezone.utc)

    # 将日落时间解析为 time 对象
    try:
        start_parts = sunset_start_str.split(":")
        end_parts = sunset_end_str.split(":")
        sunset_start = time(int(start_parts[0]), int(start_parts[1]))
        sunset_end = time(int(end_parts[0]), int(end_parts[1]))
    except (ValueError, IndexError):
        return {
            "in_window": False,
            "window_start": sunset_start_str,
            "window_end": sunset_end_str,
            "remaining_minutes": 0,
        }

    current_time = now.time()

    in_window = sunset_start <= current_time <= sunset_end

    remaining_minutes = 0
    if in_window:
        # 计算到窗口结束的剩余分钟
        end_dt = now.replace(
            hour=sunset_end.hour,
            minute=sunset_end.minute,
            second=0,
            microsecond=0,
        )
        diff = (end_dt - now).total_seconds()
        remaining_minutes = max(0, int(diff // 60))
    else:
        remaining_minutes = 0

    return {
        "in_window": in_window,
        "window_start": sunset_start_str,
        "window_end": sunset_end_str,
        "remaining_minutes": remaining_minutes,
    }


async def detect_negative_signal(patient_id: uuid.UUID, db) -> dict:
    """检测负面信号

    输入：最近对话 session 的声学/眼动数据。
    检测规则（占位，后续完善）：
    - 声学情绪分析（语速、音量、停顿模式）
    - 眼动模式（回避注视、频繁眨眼）

    返回: {has_negative, signals, confidence}
    """
    from app.models.chat_session import ChatSession

    # 获取最近结束的 3 个 session
    stmt = (
        select(ChatSession)
        .where(
            ChatSession.patient_id == patient_id,
            ChatSession.status == "ended",
        )
        .order_by(ChatSession.ended_at.desc())
        .limit(3)
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())

    if not sessions:
        return {
            "has_negative": False,
            "signals": [],
            "confidence": 0.0,
        }

    signals = []
    signal_count = 0

    for s in sessions:
        gaze = s.gaze_data or {}
        acoustic = s.acoustic_data or {}

        # 占位规则 1: 频繁眨眼（检测 blink_rate 是否过高）
        blink_rate = gaze.get("blink_rate", 0)
        if isinstance(blink_rate, (int, float)) and blink_rate > 20:
            signals.append({
                "type": "high_blink_rate",
                "value": blink_rate,
                "session_id": str(s.id),
                "description": "眨眼频率过高，可能存在紧张或疲劳",
            })
            signal_count += 1

        # 占位规则 2: 回避注视（注视时长过短）
        avg_fixation = gaze.get("avg_fixation_ms", 0)
        if isinstance(avg_fixation, (int, float)) and 0 < avg_fixation < 500:
            signals.append({
                "type": "low_fixation",
                "value": avg_fixation,
                "session_id": str(s.id),
                "description": "注视时长过短，可能存在回避注视模式",
            })
            signal_count += 1

        # 占位规则 3: 声学停顿过长（可能为负面情绪）
        avg_pause = acoustic.get("avg_pause_ms", 0)
        if isinstance(avg_pause, (int, float)) and avg_pause > 5000:
            signals.append({
                "type": "prolonged_pause",
                "value": avg_pause,
                "session_id": str(s.id),
                "description": "声学停顿时间过长，可能存在情绪低落",
            })
            signal_count += 1

    # 置信度：基于检测到的信号数量（最多 3 个 session * 3 规则 = 9）
    max_signals = len(sessions) * 3
    confidence = min(1.0, signal_count / max(1, max_signals))

    return {
        "has_negative": signal_count > 0,
        "signals": signals,
        "confidence": round(confidence, 2),
    }


async def auto_trigger_soothing(patient_id: uuid.UUID, db) -> dict:
    """自动触发舒缓模式

    条件：
    1. 当前在日落时间窗口内（17:00-19:30）
    2. 自动舒缓配置已启用
    3. 负面信号检测阳性

    返回: {triggered, in_window, has_negative_signal, reason}
    """
    # 1. 获取舒缓配置
    config = await get_soothing_config(patient_id, db)
    if not config["auto_soothing"]:
        return {
            "triggered": False,
            "in_window": False,
            "has_negative_signal": False,
            "reason": "自动舒缓已关闭",
        }

    # 2. 检查日落窗口
    window_info = await check_sunset_window(patient_id, db)
    if not window_info["in_window"]:
        return {
            "triggered": False,
            "in_window": False,
            "has_negative_signal": False,
            "reason": f"不在日落窗口内（{config['sunset_start']}-{config['sunset_end']}）",
        }

    # 3. 检测负面信号
    negative_info = await detect_negative_signal(patient_id, db)
    if not negative_info["has_negative"]:
        return {
            "triggered": False,
            "in_window": True,
            "has_negative_signal": False,
            "reason": "未检测到负面信号",
        }

    return {
        "triggered": True,
        "in_window": True,
        "has_negative_signal": True,
        "reason": "日落窗口内检测到负面信号，触发舒缓模式",
    }
