import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SoothingEvent(Base):
    """舒缓事件记录"""
    __tablename__ = "soothing_events"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("patients.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        sa.String(50), nullable=False,
        comment="事件类型: settled_20min | time_window_end | negative_signal",
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID, nullable=True,
        comment="关联的对话 session ID",
    )
    metadata: Mapped[dict] = mapped_column(
        JSON, default={}, nullable=False,
        comment="附带元数据",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        comment="记录时间",
    )

    def __repr__(self) -> str:
        return (
            f"<SoothingEvent id={self.id} patient_id={self.patient_id} "
            f"event_type={self.event_type}>"
        )
