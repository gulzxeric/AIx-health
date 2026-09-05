import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona

logger = logging.getLogger(__name__)


async def detect_and_extract(image_bytes: bytes) -> list:
    """检测人脸并提取特征向量

    当前返回空列表（占位），后续接入 InsightFace。

    Args:
        image_bytes: 图片文件字节数据

    Returns:
        人脸列表，每项包含:
            bbox: [x1, y1, x2, y2] 人脸边界框
            embedding: [512维向量] 人脸特征向量
    """
    logger.info(
        "人脸检测被调用 (占位模式): image_size=%d bytes", len(image_bytes)
    )
    return []


async def match_persona(
    face_embedding: list,
    patient_id: UUID,
    db: AsyncSession,
    threshold: float = 0.7,
) -> list:
    """与患者人物库中所有人脸进行余弦相似度比对

    当前返回空列表（占位），后续接入余弦相似度计算。

    Args:
        face_embedding: 待比对的 512 维人脸特征向量
        patient_id: 患者 ID
        db: 数据库会话
        threshold: 相似度阈值，默认 0.7

    Returns:
        匹配的人物列表，按相似度降序，每项包含:
            persona_id: UUID
            name: str
            relation: str | None
            similarity: float
    """
    logger.info(
        "人脸比对被调用 (占位模式): patient_id=%s, threshold=%.2f",
        patient_id,
        threshold,
    )
    # 查询该患者的所有人物库条目
    stmt = select(Persona).where(Persona.patient_id == patient_id)
    result = await db.execute(stmt)
    personas = list(result.scalars().all())

    if not personas:
        logger.info("患者 %s 的人物库为空，跳过比对", patient_id)
        return []

    # 占位：后续对每个有 face_embedding 的 persona 计算余弦相似度
    matches = []
    for p in personas:
        if p.face_embedding is None:
            continue
        # TODO: 接入余弦相似度计算
        # similarity = cosine_similarity(face_embedding, p.face_embedding)
        # if similarity >= threshold:
        #     matches.append({...})
        pass

    return matches


async def auto_label_photo(
    patient_id: UUID,
    image_bytes: bytes,
    db: AsyncSession,
) -> dict:
    """自动标注照片中的人物

    1. 检测人脸
    2. 提取特征向量
    3. 与人物库比对
    4. 返回标注结果

    Args:
        patient_id: 患者 ID
        image_bytes: 图片文件字节数据
        db: 数据库会话

    Returns:
        标注结果:
            faces_detected: int      检测到的人脸数
            matches: list[dict]      匹配的人物列表
            labels: list[str]        标注的人物名称列表
    """
    logger.info("自动标注照片: patient_id=%s", patient_id)

    # 1. 检测人脸 + 提取特征
    faces = await detect_and_extract(image_bytes)

    if not faces:
        logger.info("未检测到人脸，跳过标注")
        return {"faces_detected": 0, "matches": [], "labels": []}

    # 2. 对每张人脸进行比对
    all_matches = []
    all_labels = []

    for face in faces:
        embedding = face.get("embedding", [])
        if not embedding:
            continue

        matches = await match_persona(embedding, patient_id, db)
        all_matches.extend(matches)

        if matches:
            # 取最高相似度的匹配
            best = matches[0]
            all_labels.append(best["name"])
        else:
            all_labels.append("未知人物")

    return {
        "faces_detected": len(faces),
        "matches": all_matches,
        "labels": all_labels,
    }
