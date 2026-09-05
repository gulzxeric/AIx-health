"""设备绑定与配置业务逻辑"""
import random
import string
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_binding import CareBinding
from app.models.caregiver import Caregiver
from app.models.patient import Patient


def generate_device_code() -> str:
    """生成 6 位随机设备码（大写字母 + 数字）"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


async def find_patient_by_code(
    db: AsyncSession, device_code: str
) -> Patient | None:
    """根据设备码查找患者"""
    result = await db.execute(
        select(Patient).where(Patient.device_code == device_code)
    )
    return result.scalar_one_or_none()


async def check_binding_role(
    db: AsyncSession, patient_id: UUID, caregiver_id: UUID
) -> str | None:
    """检查家属在患者中的角色，返回 role 或 None（未绑定）"""
    result = await db.execute(
        select(CareBinding).where(
            CareBinding.patient_id == patient_id,
            CareBinding.caregiver_id == caregiver_id,
        )
    )
    binding = result.scalar_one_or_none()
    return binding.role if binding else None


async def get_binding_count(db: AsyncSession, patient_id: UUID) -> int:
    """查询某患者的绑定家属数量"""
    result = await db.execute(
        select(CareBinding).where(CareBinding.patient_id == patient_id)
    )
    return len(result.scalars().all())


async def find_caregiver_by_phone(
    db: AsyncSession, phone: str
) -> Caregiver | None:
    """根据手机号查找家属"""
    result = await db.execute(
        select(Caregiver).where(Caregiver.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_caregiver(db: AsyncSession, name: str, phone: str) -> Caregiver:
    """创建新家属账号"""
    caregiver = Caregiver(name=name, phone=phone)
    db.add(caregiver)
    await db.flush()
    return caregiver
