import hashlib
import json

from app.schemas.vacancy import NormalizedVacancyDTO


class ContentHasher:
    """Computes a stable SHA-256 hash of normalized vacancy content."""

    def hash(self, vacancy: NormalizedVacancyDTO) -> str:
        payload = json.dumps(
            vacancy.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
