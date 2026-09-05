import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BiometricRaw(Base):
    __tablename__ = "biometrics_raw"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID, sa.ForeignKey("chat_sessions.id"), nullable=True
    )
    data_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, comment="gaze | acoustic | session"
    )
    payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, default={}
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
