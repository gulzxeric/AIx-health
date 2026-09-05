import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(
        sa.Date, nullable=False
    )
    vitality_index: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True
    )
    vitality_trend_pct: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True
    )
    baseline_status: Mapped[str] = mapped_column(
        sa.String(20), default="ready"
    )
    baseline_days_remaining: Mapped[int] = mapped_column(
        sa.Integer, default=0
    )
    top_topics: Mapped[list] = mapped_column(
        JSON, default=[], nullable=False
    )
    advice_text: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (
        UniqueConstraint("patient_id", "date"),
    )