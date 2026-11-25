import re
from typing import Any

from app.domain.services.placeholders import is_missing
from app.schemas.vacancy import NormalizedVacancyDTO, SalaryDTO


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return "; ".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _optional(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _to_amount(value: Any) -> int | None:
    """Zero and negative values mean "not specified" in the source payload."""
    amount = _to_int(value)
    if amount is None or amount <= 0:
        return None
    return amount


def _to_skills(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [_text(item).strip() for item in value]
    else:
        text = _text(value)
        items = [part.strip() for part in re.split(r"[;,]", text)] if text else []
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _to_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [_text(item).strip() for item in value]
    else:
        text = _text(value).strip()
        items = [text] if text else []
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _join_non_missing(*values: Any) -> str | None:
    """Склеивает уникальные непустые значения, отбрасывая заглушки «нет», «не указано»."""
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value).strip()
        if not text or is_missing(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return "; ".join(parts) or None


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        return _optional(value.get("name")) or _optional(value.get("title"))
    return _optional(value)


def _address(value: Any) -> str | None:
    """Поддерживает строку, dict и список адресов из разных версий API."""
    if isinstance(value, dict):
        return _address(value.get("address") or value.get("addresses"))
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = (
                    _optional(item.get("location"))
                    or _optional(item.get("address"))
                    or _optional(item.get("fullAddress"))
                )
            else:
                text = _optional(item)
            if text and text not in parts:
                parts.append(text)
        return "; ".join(parts) or None
    return _optional(value)


def _work_place_kind(value: Any) -> str | None:
    """Преобразует объект workPlaceType в читаемый текст (квоты, спец. места, инвалиды)."""
    if isinstance(value, str):
        return _optional(value)
    if not isinstance(value, dict):
        return None
    parts: list[str] = []
    if value.get("workPlaceQuota"):
        parts.append("квотируемое рабочее место")
    if value.get("workPlaceSpecial"):
        parts.append("специальное рабочее место")
    if value.get("workPlaceForeign"):
        parts.append("иностранная рабочая сила")
    group = _optional(value.get("workPlaceDisabilityGroup"))
    if group:
        parts.append(f"рабочее место для инвалидов: {group}")
    return "; ".join(parts) or None


def _experience(value: Any) -> str | None:
    years = _to_int(value)
    if years is None:
        return _optional(value)
    if years <= 0:
        return "без опыта"
    if 11 <= years % 100 <= 14:
        word = "лет"
    elif years % 10 == 1:
        word = "год"
    elif 2 <= years % 10 <= 4:
        word = "года"
    else:
        word = "лет"
    return f"{years} {word} опыта"


def _salary(vacancy: dict[str, Any]) -> SalaryDTO:
    raw = vacancy.get("salary")
    if isinstance(raw, dict):
        text = _optional(raw.get("text"))
        from_raw = raw.get("from_amount", raw.get("from", raw.get("min")))
        to_raw = raw.get("to_amount", raw.get("to", raw.get("max")))
        currency = _optional(raw.get("currency"))
    else:
        text = _optional(raw)
        from_raw = vacancy.get("salary_min")
        to_raw = vacancy.get("salary_max")
        currency = None
    return SalaryDTO(
        from_amount=_to_amount(from_raw),
        to_amount=_to_amount(to_raw),
        currency=currency or _optional(vacancy.get("currency")),
        text=text,
    )


class VacancyNormalizer:
    """Maps the source vacancy payload to the internal normalized representation."""

    def normalize(self, item: dict[str, Any]) -> NormalizedVacancyDTO | None:
        vacancy = item.get("vacancy") if isinstance(item.get("vacancy"), dict) else item
        if not isinstance(vacancy, dict):
            return None

        external_id = _optional(vacancy.get("id")) or _optional(vacancy.get("vacancy_id"))
        if not external_id:
            return None

        company = vacancy.get("company")
        region = vacancy.get("region")
        requirement = vacancy.get("requirement") if isinstance(vacancy.get("requirement"), dict) else {}

        company_code = _optional(company.get("companycode")) if isinstance(company, dict) else None
        source_url = _optional(vacancy.get("vac_url")) or _optional(vacancy.get("source_url"))
        if not source_url and company_code:
            source_url = f"https://trudvsem.ru/vacancy/card/{company_code}/{external_id}"

        work_place_type = _optional(vacancy.get("work_place_type"))
        if not work_place_type and isinstance(vacancy.get("workPlaceType"), str):
            work_place_type = _optional(vacancy.get("workPlaceType"))

        return NormalizedVacancyDTO(
            external_id=external_id,
            title=_join_non_missing(
                vacancy.get("job-name"),
                vacancy.get("job_name"),
                vacancy.get("title"),
            )
            or "",
            description=_text(vacancy.get("description")),
            duties=_text(vacancy.get("duty")),
            requirements=_text(vacancy.get("requirements")),
            source_url=source_url,
            salary=_salary(vacancy),
            schedule=_optional(vacancy.get("schedule")) or _optional(vacancy.get("work-schedule")),
            shift=_to_text_list(vacancy.get("shift")),
            employment_type=_optional(vacancy.get("employment")) or _optional(vacancy.get("employment_type")),
            work_place_type=work_place_type,
            work_place_kind=_work_place_kind(vacancy.get("workPlaceType")),
            address=_address(vacancy.get("addresses")),
            region_code=_optional(region.get("region_code")) if isinstance(region, dict) else None,
            region_name=_name(region),
            company_name=_name(company),
            company_code=company_code,
            experience=_experience(requirement.get("experience")),
            education=_join_non_missing(requirement.get("education"), vacancy.get("education")),
            qualification=_join_non_missing(
                requirement.get("qualification"),
                vacancy.get("qualification"),
            ),
            skills=_to_skills(vacancy.get("skills")),
            published_at=_optional(vacancy.get("creation-date")) or _optional(vacancy.get("creation_date")),
            modified_at=_optional(vacancy.get("date_modify")) or _optional(vacancy.get("date_modified")),
        )
