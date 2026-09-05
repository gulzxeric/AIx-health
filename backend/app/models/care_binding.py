import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CareBinding(Base):
    __tablename__ = "care_bindings"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        sa.String(10), default="member"
    )
    consent_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        UniqueConstraint("patient_id", "caregiver_id"),
    )
