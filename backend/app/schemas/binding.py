from uuid import UUID

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    device_code: str = Field(..., min_length=6, max_length=6, description="6位设备码")


class ScanResponse(BaseModel):
    patient_id: UUID
    device_code: str
    is_new: bool
    role: str
    patient_name: str | None = None


class CompleteConfigRequest(BaseModel):
    patient_id: UUID
    era: str = Field(..., description='年代，如 "1980s"')
    region: dict = Field(default_factory=dict, description='地区 JSON，如 {"country":"CN","province":"广东","city":"广州"}')
    language: str = Field(default="zh-CN", description="语言代码")
    persona_name: str = Field(default="强叔", description="常驻角色名")


class CompleteConfigResponse(BaseModel):
    success: bool
    patient_id: UUID
    config: dict


class ConsentSignRequest(BaseModel):
    patient_id: UUID
    caregiver_name: str = Field(..., min_length=1, max_length=100, description="家属姓名")
    caregiver_phone: str = Field(..., min_length=11, max_length=20, description="家属手机号")


class ConsentSignResponse(BaseModel):
    id: UUID
    signed_at: str
    consent_version: str
