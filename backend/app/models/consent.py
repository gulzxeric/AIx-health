import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id"), nullable=False
    )
    consent_version: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False
    )
    signed_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
