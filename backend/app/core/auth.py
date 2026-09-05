"""JWT 鉴权工具"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer_scheme = HTTPBearer()


def create_jwt_token(caregiver_id: UUID) -> str:
    """创建家属端 JWT Token（有效期 30 天）"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {
        "sub": str(caregiver_id),
        "type": "caregiver",
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """验证 JWT Token，返回 payload"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_caregiver(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UUID:
    """依赖项：从请求头提取 JWT 并返回家属 ID"""
    payload = verify_jwt_token(credentials.credentials)
    if payload.get("type") != "caregiver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅限家属端访问",
        )
    return UUID(payload["sub"])


def create_device_token(patient_id: UUID) -> str:
    """创建设备 Token（持久有效）"""
    payload = {
        "sub": str(patient_id),
        "type": "device",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_patient(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UUID:
    """依赖项：从请求头提取设备 Token 并返回患者 ID"""
    payload = verify_jwt_token(credentials.credentials)
    if payload.get("type") != "device":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅限患者端访问",
        )
    return UUID(payload["sub"])
