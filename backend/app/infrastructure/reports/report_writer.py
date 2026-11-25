import logging
import os
from pathlib import Path

from app.config.settings import Settings
from app.schemas.report import ReportDTO

logger = logging.getLogger(__name__)


class ReportWriter:
    """Writes JSON reports and keeps the last successful report intact on failures."""

    _LATEST_NAME = "latest.json"

    def __init__(self, settings: Settings) -> None:
        self._directory = Path(settings.reports_dir)

    def latest_path(self) -> Path:
        return self._directory / self._LATEST_NAME

    def write(self, report: ReportDTO, filename: str | None = None) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        name = filename or f"report-{report.generated_at.strftime('%Y%m%dT%H%M%SZ')}.json"
        path = self._directory / name
        self.write_to(path, report)
        return path

    def write_latest(self, report: ReportDTO) -> Path:
        path = self.latest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write_to(path, report)
        return path

    def write_to(self, path: str | Path, report: ReportDTO) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, target)
        logger.info(
            "report written",
            extra={"path": str(target), "vacancies": len(report.vacancies), "issues": report.issues_count},
        )
        return target

    def read_latest(self) -> ReportDTO | None:
        return self.read(self.latest_path())

    def read(self, path: str | Path) -> ReportDTO | None:
        target = Path(path)
        if not target.exists():
            return None
        try:
            return ReportDTO.model_validate_json(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("report read failed", extra={"path": str(target), "error": str(exc)})
            return None
