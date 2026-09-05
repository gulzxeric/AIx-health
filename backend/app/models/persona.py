import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(
        sa.String(100), nullable=False
    )
    relation: Mapped[str | None] = mapped_column(
        sa.String(50), nullable=True
    )
    face_embedding: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    sample_photo_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    voice_sample_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    voice_cloned: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    voice_clone_cfg: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    idle_video_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        Index("idx_personas_patient", "patient_id"),
    )
