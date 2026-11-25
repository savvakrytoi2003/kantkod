import uuid
from datetime import datetime

from sqlalchemy import Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.types import TimestampType


class ReportRunModel(Base):
    __tablename__ = "report_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    vacancies_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
