from typing import Any

from pydantic import BaseModel, Field


class SourceFetchResultDTO(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    received_count: int = 0
    failed_pages: int = 0
    pages_fetched: int = 0
    total_available: int = 0
