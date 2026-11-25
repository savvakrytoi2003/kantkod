from typing import Any

from app.domain.errors import InvalidSourcePayloadError


class SourcePayloadParser:
    """Parses the raw payload of the source API (also used for local JSON files)."""

    def parse(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise InvalidSourcePayloadError("Payload must be a JSON object")

        results = payload.get("results")
        if results is None:
            raise InvalidSourcePayloadError("Payload has no 'results' section")

        if isinstance(results, dict):
            items = results.get("vacancies") or []
        else:
            raise InvalidSourcePayloadError("Payload 'results' section has unexpected type")

        if not isinstance(items, list):
            raise InvalidSourcePayloadError("Payload 'results.vacancies' must be a list")

        parsed: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("vacancy"), dict):
                parsed.append(item)
        return parsed

    def total(self, payload: dict[str, Any]) -> int:
        meta = payload.get("meta")
        if isinstance(meta, dict):
            total = meta.get("total")
            try:
                return int(total)
            except (TypeError, ValueError):
                return 0
        return 0
