import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.clock import utcnow
from app.infrastructure.database.types import TimestampType


class VacancyIssueModel(Base):
    __tablename__ = "vacancy_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vacancy_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(nullable=False)
    source_field: Mapped[str] = mapped_column(nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow)
