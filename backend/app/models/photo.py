import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id"), nullable=False
    )
    object_url: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    persona_name: Mapped[str | None] = mapped_column(
        sa.String(100), nullable=True
    )
    persona_relation: Mapped[str | None] = mapped_column(
        sa.String(50), nullable=True
    )
    face_embedding: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        Index("idx_photos_patient", "patient_id"),
    )
