from contextlib import asynccontextmanager

from minio import Minio

from app.config import settings


def create_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )


minio_client: Minio = create_minio_client()


async def ensure_buckets() -> None:
    """Ensure all required MinIO buckets exist on startup."""
    buckets = [
        settings.MINIO_BUCKET_MEMORIES,
        settings.MINIO_BUCKET_VOICE,
        settings.MINIO_BUCKET_AVATARS,
        settings.MINIO_BUCKET_ASSETS,
    ]
    for bucket_name in buckets:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)


@asynccontextmanager
async def get_minio_client():
    """Dependency provider for MinIO client."""
    yield minio_client
