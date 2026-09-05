import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session_factory
from app.models.patient import Patient

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def daily_brief_job():
    """每日简报批处理（23:00 执行）

    1. 查询所有活跃患者
    2. 对每个患者生成简报
    3. 活力指数 < 40 触发推送（占位）
    """
    logger.info("每日简报批处理开始")

    from app.core.brief_generator import generate_brief

    async with async_session_factory() as db:
        stmt = select(Patient).where(Patient.status == "active")
        result = await db.execute(stmt)
        patients = list(result.scalars().all())

    if not patients:
        logger.info("没有活跃患者，跳过简报生成")
        return

    for patient in patients:
        try:
            brief = await generate_brief(patient.id)
            vitality_index = brief.get("vitality_index")

            logger.info(
                "患者 %s 简报已生成: vitality_index=%s",
                patient.id,
                vitality_index,
            )

            # 活力指数 < 40 触发推送（占位，Phase 7 实现）
            if vitality_index is not None and vitality_index < 40:
                logger.info(
                    "患者 %s 活力指数 %d < 40，待触发推送通知",
                    patient.id,
                    vitality_index,
                )
                # TODO: Phase 7 — 调用推送服务通知所有绑定家属

        except Exception as e:
            logger.error(
                "患者 %s 简报生成失败: %s",
                patient.id,
                e,
                exc_info=True,
            )

    logger.info("每日简报批处理完成")


def setup_scheduler(app):
    """配置定时任务

    在 FastAPI 应用启动时注册定时任务。
    """
    # 每日 23:00 执行简报批处理
    scheduler.add_job(
        daily_brief_job,
        "cron",
        hour=23,
        minute=0,
        id="daily_brief",
        name="每日简报生成",
        replace_existing=True,
    )

    # 启动调度器
    scheduler.start()
    logger.info("定时调度器已启动，任务已注册")
