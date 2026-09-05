import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        sa.String(20), default="active"
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    message_count: Mapped[int] = mapped_column(
        sa.Integer, default=0
    )
    gaze_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    acoustic_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
