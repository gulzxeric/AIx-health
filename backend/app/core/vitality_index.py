import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models.chat_session import ChatSession
from app.models.patient_config import PatientConfig


def map_vitality_level(index: int) -> tuple[str, str]:
    """映射等级和文案

    Returns:
        (等级名, 展示文案)
    """
    levels = [
        (80, 100, "活跃度高", "今天精神头很好"),
        (60, 79, "反应平缓", "今天状态平稳"),
        (40, 59, "需关注", "今天有点疲惫，多陪陪"),
        (0, 39, "建议关注变化", "建议本周关注状态变化"),
    ]
    for lo, hi, level, text in levels:
        if lo <= index <= hi:
            return level, text
    return "未知", ""


async def _get_patient_timezone(patient_id: uuid.UUID, db) -> str:
    """获取患者的时区配置"""
    stmt = select(PatientConfig).where(PatientConfig.patient_id == patient_id)
    result = await db.execute(stmt)
    cfg = result.scalar_one_or_none()
    if cfg and cfg.timezone:
        return cfg.timezone
    return "Asia/Shanghai"


async def _get_sessions_for_date(
    patient_id: uuid.UUID,
    target_date: date,
    db,
) -> list[ChatSession]:
    """获取指定日期的所有结束会话"""
    day_start = datetime(
        target_date.year, target_date.month, target_date.day,
        tzinfo=timezone.utc,
    )
    day_end = day_start + timedelta(days=1)

    stmt = (
        select(ChatSession)
        .where(
            ChatSession.patient_id == patient_id,
            ChatSession.status == "ended",
            ChatSession.started_at >= day_start,
            ChatSession.started_at < day_end,
        )
        .order_by(ChatSession.started_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _extract_metrics(sessions: list[ChatSession]) -> dict:
    """从 sessions 中提取注视/扫视/声学指标

    Returns:
        {
            "avg_fixation_ms": float | None,   # 注视维持时长均值
            "avg_saccade_ms": float | None,     # 扫视潜伏期均值
            "avg_pause_ms": float | None,       # 声学停顿延迟均值
        }
    """
    fixation_values = []
    saccade_values = []
    pause_values = []

    for s in sessions:
        gaze = s.gaze_data or {}
        acoustic = s.acoustic_data or {}

        f = gaze.get("avg_fixation_ms")
        if f is not None and f > 0:
            fixation_values.append(float(f))

        sc = gaze.get("avg_saccade_ms")
        if sc is not None and sc > 0:
            saccade_values.append(float(sc))

        p = acoustic.get("avg_pause_ms")
        if p is not None and p > 0:
            pause_values.append(float(p))

    return {
        "avg_fixation_ms": sum(fixation_values) / len(fixation_values) if fixation_values else None,
        "avg_saccade_ms": sum(saccade_values) / len(saccade_values) if saccade_values else None,
        "avg_pause_ms": sum(pause_values) / len(pause_values) if pause_values else None,
    }


def _normalize_fixation(current: float, baseline_min: float, baseline_max: float) -> float:
    """归一化注视时长指标（越长越活跃）

    子分 = min(100, (当前值 - 基线最小值) / (基线最大值 - 基线最小值) * 100)
    """
    if baseline_max <= baseline_min:
        return 50.0
    score = (current - baseline_min) / (baseline_max - baseline_min) * 100
    return min(100.0, max(0.0, score))


def _normalize_latency(current: float, baseline_min: float, baseline_max: float) -> float:
    """归一化潜伏期指标（越短越活跃）

    子分 = min(100, (基线最大值 - 当前值) / (基线最大值 - 基线最小值) * 100)
    """
    if baseline_max <= baseline_min:
        return 50.0
    score = (baseline_max - current) / (baseline_max - baseline_min) * 100
    return min(100.0, max(0.0, score))


async def calculate_vitality_index(
    patient_id: uuid.UUID,
    db,
) -> dict:
    """计算活力指数

    输入指标（来自埋点）：
    - 注视维持时长（均值）— 权重 40%
    - 扫视潜伏期（均值）— 权重 30%
    - 声学停顿延迟（均值）— 权重 30%

    计算步骤：
    1. 从 chat_sessions 表获取前一日所有 session 数据
    2. 提取注视/扫视/声学指标
    3. 基线归一化（对比近 7 天）
    4. 加权求和
    5. 趋势标注（较昨日变化）
    6. 等级映射

    Returns:
        {
            "vitality_index": int | None,        # None 表示基线期
            "vitality_trend_pct": int | None,    # 较昨日变化百分比
            "baseline_status": str,               # collecting | ready
            "baseline_days_remaining": int,       # 基线剩余天数
            "level": str,                         # 等级名
            "level_text": str,                    # 展示文案
        }
    """
    # 获取患者时区
    # 简化：使用 UTC 日期
    today = date.today()
    yesterday = today - timedelta(days=1)
    seven_days_ago = today - timedelta(days=7)

    # 1. 获取前一日 session 数据
    today_sessions = await _get_sessions_for_date(patient_id, yesterday, db)
    metrics_today = _extract_metrics(today_sessions)

    # 检查是否有今日数据
    has_data = any(v is not None for v in metrics_today.values())
    if not has_data:
        return {
            "vitality_index": None,
            "vitality_trend_pct": None,
            "baseline_status": "collecting",
            "baseline_days_remaining": 7,
            "level": "",
            "level_text": "暂无数据",
        }

    # 2. 获取近 7 天基线数据
    baseline_sessions = []
    for delta in range(1, 8):
        d = yesterday - timedelta(days=delta)
        sessions = await _get_sessions_for_date(patient_id, d, db)
        baseline_sessions.extend(sessions)

    baseline_metrics = _extract_metrics(baseline_sessions)

    # 检查基线是否就绪（至少需要 3 天的数据作为基线）
    baseline_ready = any(v is not None for v in baseline_metrics.values())

    if not baseline_ready:
        # 基线未就绪，返回空结果
        return {
            "vitality_index": None,
            "vitality_trend_pct": None,
            "baseline_status": "collecting",
            "baseline_days_remaining": 7,
            "level": "",
            "level_text": "正在收集基线数据",
        }

    # 3. 基线归一化
    # 注视维持时长（越大越好）
    fixation_score = 50.0
    if (
        metrics_today["avg_fixation_ms"] is not None
        and baseline_metrics["avg_fixation_ms"] is not None
    ):
        # 使用基线均值作为参考，设置范围 = 均值 +/- 标准差范围
        # 简化：使用基线值的 ±50% 作为范围
        base_val = baseline_metrics["avg_fixation_ms"]
        baseline_min = base_val * 0.5
        baseline_max = base_val * 1.5
        fixation_score = _normalize_fixation(
            metrics_today["avg_fixation_ms"],
            baseline_min,
            baseline_max,
        )

    # 扫视潜伏期（越小越好）
    saccade_score = 50.0
    if (
        metrics_today["avg_saccade_ms"] is not None
        and baseline_metrics["avg_saccade_ms"] is not None
    ):
        base_val = baseline_metrics["avg_saccade_ms"]
        baseline_min = base_val * 0.5
        baseline_max = base_val * 1.5
        saccade_score = _normalize_latency(
            metrics_today["avg_saccade_ms"],
            baseline_min,
            baseline_max,
        )

    # 声学停顿延迟（越小越好）
    pause_score = 50.0
    if (
        metrics_today["avg_pause_ms"] is not None
        and baseline_metrics["avg_pause_ms"] is not None
    ):
        base_val = baseline_metrics["avg_pause_ms"]
        baseline_min = base_val * 0.5
        baseline_max = base_val * 1.5
        pause_score = _normalize_latency(
            metrics_today["avg_pause_ms"],
            baseline_min,
            baseline_max,
        )

    # 4. 加权求和
    vitality_index = (
        fixation_score * 0.4
        + saccade_score * 0.3
        + pause_score * 0.3
    )
    vitality_index = round(vitality_index)

    # 5. 趋势标注（对比昨日）
    # 获取昨日的数据（前一天的自然日）
    day_before_yesterday = yesterday - timedelta(days=1)
    prev_sessions = await _get_sessions_for_date(patient_id, day_before_yesterday, db)
    prev_metrics = _extract_metrics(prev_sessions)

    trend_pct = None
    if prev_metrics["avg_fixation_ms"] is not None:
        # 计算昨日的近似活力指数
        prev_fixation_score = 50.0
        if baseline_metrics["avg_fixation_ms"] is not None:
            base_val = baseline_metrics["avg_fixation_ms"]
            baseline_min = base_val * 0.5
            baseline_max = base_val * 1.5
            prev_fixation_score = _normalize_fixation(
                prev_metrics["avg_fixation_ms"],
                baseline_min,
                baseline_max,
            )

        prev_saccade_score = 50.0
        if baseline_metrics["avg_saccade_ms"] is not None:
            base_val = baseline_metrics["avg_saccade_ms"]
            baseline_min = base_val * 0.5
            baseline_max = base_val * 1.5
            prev_saccade_score = _normalize_latency(
                prev_metrics["avg_saccade_ms"],
                baseline_min,
                baseline_max,
            )

        prev_pause_score = 50.0
        if baseline_metrics["avg_pause_ms"] is not None:
            base_val = baseline_metrics["avg_pause_ms"]
            baseline_min = base_val * 0.5
            baseline_max = base_val * 1.5
            prev_pause_score = _normalize_latency(
                prev_metrics["avg_pause_ms"],
                baseline_min,
                baseline_max,
            )

        prev_index = (
            prev_fixation_score * 0.4
            + prev_saccade_score * 0.3
            + prev_pause_score * 0.3
        )
        if prev_index > 0:
            trend_pct = round((vitality_index - prev_index) / prev_index * 100)
        else:
            trend_pct = 0

    # 6. 等级映射
    level, level_text = map_vitality_level(vitality_index)

    return {
        "vitality_index": vitality_index,
        "vitality_trend_pct": trend_pct,
        "baseline_status": "ready",
        "baseline_days_remaining": 0,
        "level": level,
        "level_text": level_text,
    }


async def get_top_topics(
    patient_id: uuid.UUID,
    db,
) -> list[dict]:
    """计算高共鸣话题 Top 3

    输入：患者端单次交互会话数据
    信号及阈值：
    - 注视时长 >= 30 秒
    - 对话轮次 >= 3 轮
    - 主动发声 >= 2 次

    判定：满足任一条即标记为"高共鸣话题"

    排序公式：共鸣分 = 注视时长(秒) + 对话轮次*10 + 主动发声*5
    返回 Top 3
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    sessions = await _get_sessions_for_date(patient_id, yesterday, db)

    topics = []
    for s in sessions:
        gaze = s.gaze_data or {}
        acoustic = s.acoustic_data or {}

        # 从埋点数据中提取话题信息
        gaze_events = gaze.get("gaze_events", [])
        acoustic_events = acoustic.get("acoustic_events", [])

        # 计算各指标
        gaze_duration_sec = gaze.get("avg_fixation_ms", 0) * (
            len(gaze_events) if gaze_events else 1
        ) / 1000.0 if gaze.get("avg_fixation_ms") else 0.0

        dialogue_turns = s.message_count or 0
        active_vocalizations = sum(
            1 for e in acoustic_events
            if isinstance(e, dict) and e.get("is_voice", False)
        )
        if not active_vocalizations and acoustic.get("voice_duration_ms", 0) > 0:
            # 如果找不到事件中的发声标记，使用 voice_duration 估算
            active_vocalizations = max(
                1, round(acoustic.get("voice_duration_ms", 0) / 5000)
            )

        # 判定是否为高共鸣话题
        is_high_resonance = (
            gaze_duration_sec >= 30
            or dialogue_turns >= 3
            or active_vocalizations >= 2
        )

        if not is_high_resonance:
            continue

        # 计算共鸣分
        resonance_score = gaze_duration_sec + dialogue_turns * 10 + active_vocalizations * 5

        topics.append({
            "topic_name": f"对话 #{s.id.hex[:8]}",
            "gaze_duration": round(gaze_duration_sec, 1),
            "dialogue_turns": dialogue_turns,
            "active_vocalizations": active_vocalizations,
            "resonance_score": resonance_score,
            "session_id": str(s.id),
        })

    # 按共鸣分排序，取 Top 3
    topics.sort(key=lambda t: t["resonance_score"], reverse=True)
    return topics[:3]
