import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Caregiver(Base):
    __tablename__ = "caregivers"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    phone: Mapped[str] = mapped_column(
        sa.String(20), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        sa.String(100), nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
    )
