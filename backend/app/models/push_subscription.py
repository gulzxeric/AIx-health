import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID, sa.ForeignKey("caregivers.id"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )
    p256dh_key: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )
    auth_key: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
