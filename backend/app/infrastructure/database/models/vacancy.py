import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.types import JSONType, TimestampType


class VacancyModel(Base):
    __tablename__ = "vacancies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_data: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    raw_data: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow, onupdate=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
