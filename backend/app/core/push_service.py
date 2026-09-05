import json
import logging
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

# VAPID 密钥缓存（避免每次推送都重新生成）
_vapid_private_key: str | None = None
_vapid_public_key: str | None = None


def generate_vapid_keys() -> dict:
    """生成 VAPID 密钥对

    使用 pywebpush 的内置工具生成 P-256 EC 密钥对。
    若 pywebpush 未安装，回退使用 cryptography 手动生成。
    """
    try:
        from pywebpush import _VapidIdentifier

        private_key, public_key = _VapidIdentifier._gen_keyinfo()
        return {
            "private_key": private_key.decode("utf-8") if isinstance(private_key, bytes) else str(private_key),
            "public_key": public_key.decode("utf-8") if isinstance(public_key, bytes) else str(public_key),
        }
    except ImportError:
        logger.warning("pywebpush 未安装，使用 cryptography 生成 VAPID 密钥")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return {
            "private_key": private_pem,
            "public_key": public_pem,
        }


def ensure_vapid_keys():
    """确保 VAPID 密钥已配置

    若 settings 中密钥为空，则自动生成并写入 settings 对象。
    注意：运行时生成的密钥仅内存有效，重启后需重新生成或持久化。
    """
    global _vapid_private_key, _vapid_public_key

    if settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY:
        _vapid_private_key = settings.VAPID_PRIVATE_KEY
        _vapid_public_key = settings.VAPID_PUBLIC_KEY
        return

    if _vapid_private_key and _vapid_public_key:
        return

    # 首次启动时生成
    keys = generate_vapid_keys()
    _vapid_private_key = keys["private_key"]
    _vapid_public_key = keys["public_key"]

    # 回写到 settings 对象（仅运行时持久，不更改 .env 文件）
    object.__setattr__(settings, "VAPID_PRIVATE_KEY", _vapid_private_key)
    object.__setattr__(settings, "VAPID_PUBLIC_KEY", _vapid_public_key)

    logger.info("VAPID 密钥已自动生成（运行时）")


async def send_push_notification(
    subscription: PushSubscription,
    title: str,
    body: str,
    tag: str | None = None,
) -> bool:
    """发送 Web Push 推送通知

    使用 VAPID 协议，通过 pywebpush 或 httpx 发送推送请求。

    Args:
        subscription: 推送订阅模型实例
        title: 推送标题
        body: 推送内容
        tag: 可选推送标签（用于通知去重）

    Returns:
        bool: 是否发送成功
    """
    ensure_vapid_keys()

    # 构建推送 payload（JSON 格式，符合 Web Push 规范）
    payload = json.dumps({
        "title": title,
        "body": body,
        "tag": tag or "default",
    })

    # 构建订阅信息字典
    sub_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh_key,
            "auth": subscription.auth_key,
        },
    }

    try:
        # 优先使用 pywebpush 库
        from pywebpush import webpush, WebPushException

        response = webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=_vapid_private_key,
            vapid_claims={
                "sub": f"mailto:{settings.VAPID_CONTACT}",
            },
        )
        logger.info(
            "推送发送成功: caregiver=%s, status=%s",
            subscription.caregiver_id,
            response.status_code,
        )
        return True

    except ImportError:
        # 回退：使用 httpx 手动实现 Web Push
        logger.debug("pywebpush 不可用，使用 httpx 发送 Web Push")
        return await _send_via_httpx(sub_info, payload)

    except WebPushException as e:
        if e.response and e.response.status_code == 410:
            # 410 Gone — 订阅已过期，应清理
            logger.warning(
                "推送订阅已过期（410），将清理: subscription=%s, caregiver=%s",
                subscription.id,
                subscription.caregiver_id,
            )
            await _remove_subscription(subscription.id)
        elif e.response and e.response.status_code == 429:
            logger.warning(
                "推送频率限制（429），稍后重试: caregiver=%s",
                subscription.caregiver_id,
            )
        else:
            logger.error(
                "推送发送失败: caregiver=%s, error=%s",
                subscription.caregiver_id,
                e,
            )
        return False

    except Exception as e:
        logger.error(
            "推送发送异常: caregiver=%s, error=%s",
            subscription.caregiver_id,
            e,
            exc_info=True,
        )
        return False


async def _send_via_httpx(sub_info: dict, payload: str) -> bool:
    """使用 httpx 模拟 Web Push 发送（降级方案）"""
    import base64

    import httpx
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    endpoint = sub_info["endpoint"]

    try:
        # 使用 HTTP POST 发送
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "Content-Encoding": "aes128gcm",
                    "TTL": "86400",  # 24 小时
                },
                timeout=10.0,
            )

            if response.status_code in (200, 201, 204):
                logger.info(
                    "推送发送成功（httpx）: endpoint=%s, status=%s",
                    endpoint[:50],
                    response.status_code,
                )
                return True
            else:
                logger.warning(
                    "推送发送失败（httpx）: endpoint=%s, status=%s, body=%s",
                    endpoint[:50],
                    response.status_code,
                    response.text[:200],
                )
                return False

    except Exception as e:
        logger.error(
            "推送发送异常（httpx）: endpoint=%s, error=%s",
            endpoint[:50],
            e,
        )
        return False


async def _remove_subscription(subscription_id: UUID):
    """清理过期的推送订阅"""
    try:
        async with async_session_factory() as db:
            stmt = select(PushSubscription).where(PushSubscription.id == subscription_id)
            result = await db.execute(stmt)
            sub = result.scalar_one_or_none()
            if sub:
                await db.delete(sub)
                await db.commit()
                logger.info("已清理过期订阅: %s", subscription_id)
    except Exception as e:
        logger.error("清理过期订阅失败: %s, error=%s", subscription_id, e)


async def broadcast_to_patient(
    patient_id: UUID,
    title: str,
    body: str,
    db=None,
    tag: str | None = None,
) -> int:
    """向某患者所有绑定的家属发送推送

    查询所有关联的 push_subscriptions，逐个发送。
    发送失败不阻断主流程。

    Args:
        patient_id: 患者 ID
        title: 推送标题
        body: 推送内容
        db: 可选数据库 session（不传则内部创建）
        tag: 可选推送标签

    Returns:
        int: 成功发送数
    """
    from app.models.care_binding import CareBinding

    async def _do_broadcast(session):
        # 查询该患者所有绑定的家属
        stmt = (
            select(CareBinding)
            .where(CareBinding.patient_id == patient_id)
        )
        result = await session.execute(stmt)
        bindings = list(result.scalars().all())

        if not bindings:
            logger.info("患者 %s 无绑定家属，跳过推送", patient_id)
            return 0

        caregiver_ids = [b.caregiver_id for b in bindings]

        # 查询所有家属的推送订阅
        sub_stmt = (
            select(PushSubscription)
            .where(PushSubscription.caregiver_id.in_(caregiver_ids))
        )
        sub_result = await session.execute(sub_stmt)
        subscriptions = list(sub_result.scalars().all())

        if not subscriptions:
            logger.info("患者 %s 无推送订阅，跳过推送", patient_id)
            return 0

        success_count = 0
        for sub in subscriptions:
            ok = await send_push_notification(sub, title, body, tag)
            if ok:
                success_count += 1

        logger.info(
            "患者 %s 推送完成: 目标订阅 %d, 成功 %d",
            patient_id,
            len(subscriptions),
            success_count,
        )
        return success_count

    if db is not None:
        return await _do_broadcast(db)
    else:
        async with async_session_factory() session:
            return await _do_broadcast(session)


async def send_vitality_alert(
    patient_id: UUID,
    vitality_index: int,
    db=None,
) -> int:
    """发送活力指数预警推送

    当活力指数 < 40 时触发。

    Args:
        patient_id: 患者 ID
        vitality_index: 活力指数
        db: 可选数据库 session（不传则内部创建）

    Returns:
        int: 成功发送数
    """
    title = "需要关注"
    body = "今天老人的精神状态不太好，建议多陪陪他"
    tag = f"vitality-alert-{patient_id}-{vitality_index}"

    return await broadcast_to_patient(
        patient_id=patient_id,
        title=title,
        body=body,
        db=db,
        tag=tag,
    )
