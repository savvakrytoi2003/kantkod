import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.types import TimestampType


class VacancyAnalysisModel(Base):
    __tablename__ = "vacancy_analyses"
    __table_args__ = (Index("ix_vacancy_analyses_vacancy_hash", "vacancy_id", "content_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
