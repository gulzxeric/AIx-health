import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssetPack(Base):
    __tablename__ = "asset_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    era: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )
    region_key: Mapped[str | None] = mapped_column(
        sa.String(50), nullable=True
    )
    status: Mapped[str] = mapped_column(
        sa.String(20), default="generating"
    )
    photo_urls: Mapped[list] = mapped_column(
        JSON, default=[], nullable=False
    )
    topic_library: Mapped[list] = mapped_column(
        JSON, default=[], nullable=False
    )
    prompt_anchors: Mapped[list] = mapped_column(
        JSON, default=[], nullable=False
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        Index("idx_asset_packs_patient", "patient_id"),
    )
