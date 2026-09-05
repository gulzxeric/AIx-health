import asyncio
import io
import logging
from uuid import UUID

from app.config import settings
from app.core.minio_client import minio_client

logger = logging.getLogger(__name__)


async def upload_photo(
    patient_id: UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str = "image/jpeg",
) -> str:
    """上传照片到 MinIO，返回 object_url

    路径: {patient_id}/{filename}

    Args:
        patient_id: 患者 ID
        file_bytes: 文件字节数据
        filename: 文件名（如 "photo.jpg"）
        content_type: 图片 MIME 类型，如 image/png

    Returns:
        MinIO 对象 URL
    """
    bucket = settings.MINIO_BUCKET_MEMORIES
    object_name = f"{patient_id}/{filename}"

    await asyncio.to_thread(
        minio_client.put_object,
        bucket,
        object_name,
        io.BytesIO(file_bytes),
        len(file_bytes),
        content_type=content_type,
    )

    object_url = f"/{bucket}/{object_name}"
    logger.info("照片已上传到 MinIO: %s", object_url)
    return object_url


async def upload_audio(
    patient_id: UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str = "audio/webm",
) -> str:
    """上传音频到 MinIO，返回 object_url

    路径: {patient_id}/audio/{filename}
    """
    bucket = settings.MINIO_BUCKET_VOICE
    object_name = f"{patient_id}/audio/{filename}"

    await asyncio.to_thread(
        minio_client.put_object,
        bucket,
        object_name,
        io.BytesIO(file_bytes),
        len(file_bytes),
        content_type=content_type,
    )
    object_url = f"/{bucket}/{object_name}"
    logger.info("音频已上传到 MinIO: %s", object_url)
    return object_url


async def get_presigned_url(object_url: str, expires: int = 3600) -> str:
    """获取签名 URL（临时访问）

    Args:
        object_url: 对象 URL，格式为 "/bucket/object_name"
        expires: 过期时间（秒），默认 3600

    Returns:
        签名的临时访问 URL
    """
    # 移除开头的 "/"，按 "/" 分离 bucket 和 object_name
    path = object_url.lstrip("/")
    bucket, object_name = path.split("/", 1)

    presigned_url = await asyncio.to_thread(
        minio_client.presigned_get_object,
        bucket,
        object_name,
        expires=expires,
    )

    return presigned_url
