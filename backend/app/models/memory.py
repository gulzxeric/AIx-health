import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id"), nullable=False
    )
    raw_text: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )
    photo_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    entities: Mapped[dict] = mapped_column(
        JSON, default={}, nullable=False
    )
    vector_embedding: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    sync_status: Mapped[str] = mapped_column(
        sa.String(20), default="synced"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
    )

    __table_args__ = (
        Index("idx_memories_patient", "patient_id"),
    )
