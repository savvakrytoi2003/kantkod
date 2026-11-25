import asyncio
import logging
from typing import Any

import httpx

from app.config.settings import Settings
from app.domain.errors import SourceApiError
from app.domain.services.source_payload_parser import SourcePayloadParser
from app.schemas.source import SourceFetchResultDTO

logger = logging.getLogger(__name__)


class TrudvsemClient:
    """HTTP client for the 'Work in Russia' open data API with pagination support."""

    _MAX_PAGE_SIZE = 100

    def __init__(self, settings: Settings, client: httpx.AsyncClient, parser: SourcePayloadParser) -> None:
        self._settings = settings
        self._client = client
        self._parser = parser

    async def fetch(self, max_vacancies: int | None = None) -> SourceFetchResultDTO:
        limit_total = max_vacancies or self._settings.source_max_vacancies
        page_size = max(1, min(self._settings.source_page_size, self._MAX_PAGE_SIZE))

        collected: dict[str, dict[str, Any]] = {}
        received = 0
        failed_pages = 0
        pages_fetched = 0
        total_available = 0
        offset = 0
        consecutive_failures = 0

        while len(collected) < limit_total:
            try:
                payload = await self._fetch_page(offset=offset, limit=page_size)
            except SourceApiError as exc:
                failed_pages += 1
                consecutive_failures += 1
                logger.warning("source page failed", extra={"offset": offset, "error": str(exc)})
                if pages_fetched == 0 and failed_pages >= 2:
                    raise
                if consecutive_failures > self._settings.source_max_retries:
                    break
                offset += page_size
                continue

            consecutive_failures = 0
            pages_fetched += 1
            total_available = max(total_available, self._parser.total(payload))
            items = self._parser.parse(payload)
            received += len(items)
            logger.info(
                "source page fetched",
                extra={"offset": offset, "page_items": len(items), "received": received},
            )

            if not items:
                break

            for item in items:
                external_id = self._external_id(item)
                if not external_id:
                    continue
                collected[external_id] = item
                if len(collected) >= limit_total:
                    break

            offset += page_size
            if total_available and offset >= total_available:
                break

        logger.info(
            "source fetch finished",
            extra={
                "received": received,
                "unique": len(collected),
                "pages": pages_fetched,
                "failed_pages": failed_pages,
            },
        )
        return SourceFetchResultDTO(
            items=list(collected.values()),
            received_count=received,
            failed_pages=failed_pages,
            pages_fetched=pages_fetched,
            total_available=total_available,
        )

    async def _fetch_page(self, offset: int, limit: int) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self._settings.source_max_retries + 1):
            try:
                response = await self._client.get(
                    self._settings.source_api_url,
                    params={"offset": offset, "limit": limit},
                    timeout=self._settings.source_timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "source request failed",
                    extra={"offset": offset, "attempt": attempt, "error": last_error},
                )
                await asyncio.sleep(min(2 ** (attempt - 1), 4))
                continue

            if not isinstance(payload, dict):
                raise SourceApiError("Source API returned unexpected payload")
            status = str(payload.get("status", "200"))
            if status not in {"200", "0"}:
                raise SourceApiError(f"Source API returned status {status}")
            return payload

        raise SourceApiError(f"Source API request failed: {last_error}")

    def _external_id(self, item: dict[str, Any]) -> str:
        vacancy = item.get("vacancy")
        if not isinstance(vacancy, dict):
            return ""
        value = vacancy.get("id") or vacancy.get("vacancy_id")
        return str(value).strip() if value else ""
