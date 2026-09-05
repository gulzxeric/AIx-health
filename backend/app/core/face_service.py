import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def detect_faces(image_bytes: bytes) -> list:
    """检测照片中的人脸，返回 face_embedding 列表

    当前返回空列表（占位），后续接入 InsightFace。

    Args:
        image_bytes: 照片文件字节数据

    Returns:
        face_embedding 列表，每个元素为一个 512 维向量
    """
    logger.info("人脸检测被调用 (占位模式): image_size=%d bytes", len(image_bytes))
    return []


async def compare_faces(
    face_embedding: list,
    patient_id: UUID,
    db: AsyncSession,
) -> list:
    """与患者人物库中所有人脸比对，返回匹配结果

    当前返回空列表（占位），后续接入余弦相似度比对。

    Args:
        face_embedding: 待比对的 512 维人脸特征向量
        patient_id: 患者 ID
        db: 数据库会话

    Returns:
        匹配的人物列表，每项包含 {persona_id, name, relation, similarity}
    """
    logger.info("人脸比对被调用 (占位模式): patient_id=%s", patient_id)
    return []
