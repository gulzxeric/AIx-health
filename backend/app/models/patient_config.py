import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PatientConfig(Base):
    __tablename__ = "patient_configs"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        sa.ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    era: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )
    region: Mapped[dict] = mapped_column(
        JSON, default={}, nullable=False
    )
    language: Mapped[str] = mapped_column(
        sa.String(5), default="zh-CN"
    )
    timezone: Mapped[str] = mapped_column(
        sa.String(50), default="Asia/Shanghai"
    )
    persona_name: Mapped[str] = mapped_column(
        sa.String(50), default="强叔"
    )
    privacy_consent: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
