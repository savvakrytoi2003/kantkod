import re

from app.domain.services.placeholders import is_missing
from app.domain.services.vacancy_signals import (
    duties_are_specific,
    location_is_clear,
    requirements_are_specific,
    salary_is_clear,
    schedule_has_details,
    title_is_specific,
)
from app.schemas.issue import IssueDTO, IssueTopic
from app.schemas.vacancy import NormalizedVacancyDTO

_MISSING_QUOTE = re.compile(
    r"не указан|не указано|не указана|не указаны|отсутств|нет сведен|нет информац|"
    r"не заполнен|не предъявл|не содержится",
    re.IGNORECASE,
)
_FIELD_ONLY_QUOTE = re.compile(r"^[a-z_]+\s*:\s*$", re.IGNORECASE)
_FORMATTING_HINT = re.compile(
    r"слит\w*|без разделител|форматирован|опечат|орфограф|склеен|пропущен\w* пробел",
    re.IGNORECASE,
)
_PREFERENCE_HINT = re.compile(
    r"преимуществ|желательн|приветству|будет плюсом|не обязательн",
    re.IGNORECASE,
)
_FIELD_MISMATCH_HINT = re.compile(
    r"не в том поле|в поле qualification вместо|поле qualification содержит",
    re.IGNORECASE,
)
_DURATION = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(год|года|лет|мес(?:яц(?:а|ев)?)?)",
    re.IGNORECASE,
)
_FIELD_TOPICS: dict[str, IssueTopic] = {
    "job-name": IssueTopic.TITLE,
    "job_name": IssueTopic.TITLE,
    "title": IssueTopic.TITLE,
    "duty": IssueTopic.DUTIES,
    "duties": IssueTopic.DUTIES,
    "description": IssueTopic.DUTIES,
    "requirement": IssueTopic.REQUIREMENTS,
    "requirements": IssueTopic.REQUIREMENTS,
    "qualification": IssueTopic.REQUIREMENTS,
    "education": IssueTopic.REQUIREMENTS,
    "experience": IssueTopic.REQUIREMENTS,
    "salary": IssueTopic.SALARY,
    "salary_min": IssueTopic.SALARY,
    "salary_max": IssueTopic.SALARY,
    "currency": IssueTopic.SALARY,
    "schedule": IssueTopic.SCHEDULE,
    "shift": IssueTopic.SCHEDULE,
    "address": IssueTopic.LOCATION,
    "addresses": IssueTopic.LOCATION,
    "location": IssueTopic.LOCATION,
    "workplacetype": IssueTopic.LOCATION,
    "work_place_type": IssueTopic.LOCATION,
    "employment": IssueTopic.EMPLOYMENT,
    "employment_type": IssueTopic.EMPLOYMENT,
}


def retopic_issue(issue: IssueDTO) -> IssueDTO:
    """Уточняет тему «other» по полю, на которое ссылается замечание."""
    if issue.topic is not IssueTopic.OTHER:
        return issue
    for part in re.split(r"[,;]", issue.source_field or ""):
        suffix = part.strip().split(".")[-1].strip().lower().replace("-", "_")
        topic = _FIELD_TOPICS.get(suffix)
        if topic is not None:
            return issue.model_copy(update={"topic": topic})
    return issue


class IssueMerger:
    """Merges rule-based and AI findings and removes duplicates."""

    def merge(self, rule_issues: list[IssueDTO], ai_issues: list[IssueDTO]) -> list[IssueDTO]:
        merged: list[IssueDTO] = []
        seen: set[tuple[str, str]] = set()

        for issue in [retopic_issue(item) for item in [*rule_issues, *ai_issues]]:
            key = self._key(issue)
            if key in seen:
                continue
            if self._overlaps(issue, merged) or self._echoes_contradiction(issue, merged):
                continue
            seen.add(key)
            merged.append(issue)
        return merged

    def _overlaps(self, issue: IssueDTO, merged: list[IssueDTO]) -> bool:
        """Отбрасывает повтор, если та же цитата или её часть уже есть в принятых замечаниях."""
        parts = self._quote_parts(issue.quote)
        if not parts:
            return False
        for existing in merged:
            other = self._quote_parts(existing.quote)
            for part in parts:
                for candidate in other:
                    if part in candidate or candidate in part:
                        return True
        return False

    def _echoes_contradiction(self, issue: IssueDTO, merged: list[IssueDTO]) -> bool:
        """Замечание по тому же полю, что и найденное противоречие, только дублирует его."""
        if issue.topic is IssueTopic.CONTRADICTION:
            return False
        fields = self._fields(issue.source_field)
        if not fields:
            return False
        return any(
            existing.topic is IssueTopic.CONTRADICTION and fields & self._fields(existing.source_field)
            for existing in merged
        )

    def _fields(self, source_field: str) -> set[str]:
        parts = {part.strip().split(".")[-1].lower() for part in re.split(r"[,;]", source_field or "")}
        return {part for part in parts if part}

    def _quote_parts(self, quote: str) -> list[str]:
        parts = re.split(r"\s+/\s+|[|;]", quote or "")
        return [text for text in (self._normalize(part) for part in parts) if len(text) >= 12]

    def _key(self, issue: IssueDTO) -> tuple[str, str]:
        topic = str(issue.topic)
        raw_quote = (issue.quote or "").strip()
        # Пустая цитата, пояснение «не указано…» и цитата из одного имени поля
        # означают «сведения отсутствуют» — такое замечание одно на тему.
        if not raw_quote or _MISSING_QUOTE.search(raw_quote) or _FIELD_ONLY_QUOTE.fullmatch(raw_quote):
            return topic, "missing"
        quote = self._normalize(raw_quote)
        if quote:
            return topic, f"quote:{quote}"
        return topic, "missing"

    def _normalize(self, value: str) -> str:
        text = (value or "").lower().replace("ё", "е")
        text = re.sub(r"[«»\"'`.,;:!?()\[\]\u2026\u2014\u2013-]", " ", text)
        return re.sub(r"\s+", " ", text).strip()


class IssueVerifier:
    """Проверяет замечания по данным вакансии.

    Отбрасывает замечания, которые противоречат самой вакансии: «не указан
    тип занятости» при заполненном поле, «неясная оплата» при указанной сумме,
    «неясный график» при наличии часов/смен, «неполный адрес» при полном адресе,
    «общие требования» при конкретных требованиях и т.п.
    """

    def verify(self, issues: list[IssueDTO], vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        haystack = self._haystack(vacancy)
        verified: list[IssueDTO] = []
        for item in issues:
            issue = retopic_issue(item)
            if self._is_supported(issue, vacancy, haystack):
                verified.append(issue)
        return verified

    def _haystack(self, vacancy: NormalizedVacancyDTO) -> str:
        values = [
            vacancy.title,
            vacancy.description,
            vacancy.duties,
            vacancy.requirements,
            vacancy.qualification or "",
            vacancy.education or "",
            vacancy.experience or "",
            vacancy.schedule or "",
            " ".join(vacancy.shift),
            vacancy.employment_type or "",
            vacancy.address or "",
            vacancy.work_place_type or "",
            vacancy.work_place_kind or "",
            vacancy.region_name or "",
            vacancy.salary.text or "",
            self._salary_amounts(vacancy),
            " ".join(vacancy.skills),
        ]
        return self._normalize(" ".join(values))

    def _topic_haystack(self, topic: IssueTopic, vacancy: NormalizedVacancyDTO) -> str:
        """Текст только тех полей, к которым относится тема замечания."""
        salary = vacancy.salary
        values: dict[IssueTopic, list[str | None]] = {
            IssueTopic.TITLE: [vacancy.title],
            IssueTopic.DUTIES: [vacancy.duties, vacancy.description],
            IssueTopic.REQUIREMENTS: [
                vacancy.requirements,
                vacancy.qualification,
                vacancy.education,
                vacancy.experience,
                " ".join(vacancy.skills),
            ],
            IssueTopic.SALARY: [salary.text, self._salary_amounts(vacancy), salary.currency],
            IssueTopic.SCHEDULE: [
                vacancy.schedule,
                vacancy.qualification,
                vacancy.requirements,
                vacancy.description,
                vacancy.duties,
                " ".join(vacancy.shift),
            ],
            IssueTopic.LOCATION: [
                vacancy.address,
                vacancy.work_place_type,
                vacancy.work_place_kind,
                vacancy.region_name,
            ],
            IssueTopic.EMPLOYMENT: [vacancy.employment_type],
        }
        return self._normalize(" ".join(filter(None, values.get(topic, []))))

    def _quote_supported(self, quote: str, haystack: str) -> bool:
        """Цитата должна встречаться в данных вакансии; структурные значения проверяются по частям."""
        normalized_quote = self._normalize(quote)
        if normalized_quote and normalized_quote in haystack:
            return True

        parts = re.split(r"\s+/\s+|[|;]|,\s*(?=[A-Za-z_]+\s*:)", quote)
        for part in parts:
            text = re.sub(r"^[A-Za-z_]+\s*:\s*", "", part.strip()).strip()
            if not text or text.isdigit():
                continue
            if self._normalize(text) not in haystack:
                return False
        # Цитата из одних структурных значений (salary_min: 0) проверять не по чему.
        return True

    def _is_supported(
        self,
        issue: IssueDTO,
        vacancy: NormalizedVacancyDTO,
        haystack: str,
    ) -> bool:
        quote = (issue.quote or "").strip()

        if issue.topic is IssueTopic.CONTRADICTION:
            parts = [part.strip() for part in re.split(r"\s+/\s+|[|;]", quote) if part.strip()]
            if len(parts) < 2:
                return False
            values = [re.sub(r"^[A-Za-z_]+\s*:\s*", "", part).strip() for part in parts]
            if any(is_missing(value) or _MISSING_QUOTE.search(value) for value in values):
                # «опыт 1 год / требования не предъявляются» — это не противоречие,
                # а незаполненное поле.
                return False
            if any(_PREFERENCE_HINT.search(value) for value in values):
                # «профильное образование будет преимуществом» — пожелание, а не конфликт.
                return False
            normalized = {self._normalize(value) for value in values}
            if len(normalized) < 2:
                return False
            if self._experience_contradiction_compatible(issue, vacancy):
                return False
            if self._schedule_contradiction_compatible(issue):
                return False
            return self._quote_supported(quote, haystack)

        if not self._semantically_valid(issue, vacancy):
            return False

        if issue.topic is IssueTopic.OTHER:
            return not quote or self._quote_supported(quote, haystack)

        if quote:
            # Пояснительная цитата вида «В вакансии не указано: тип занятости»
            # допустима, если соответствующее поле действительно пустое.
            if _MISSING_QUOTE.search(quote) and is_missing(self._source_value(issue.topic, vacancy)):
                return True
            if _FIELD_ONLY_QUOTE.fullmatch(quote):
                return is_missing(self._source_value(issue.topic, vacancy))
            topic_haystack = self._topic_haystack(issue.topic, vacancy)
            if self._quote_supported(quote, topic_haystack):
                return True
            return self._quote_supported(quote, haystack)

        return is_missing(self._source_value(issue.topic, vacancy))

    def _semantically_valid(self, issue: IssueDTO, vacancy: NormalizedVacancyDTO) -> bool:
        """Есть ли вообще повод для замечания, если смотреть на заполненность полей."""
        topic = issue.topic
        if topic is not IssueTopic.CONTRADICTION and _FORMATTING_HINT.search(issue.problem):
            # Опечатки, слитый текст и форматирование источника — не про ясность условий.
            return False
        if topic is not IssueTopic.CONTRADICTION and _FIELD_MISMATCH_HINT.search(issue.problem):
            # «В поле qualification вместо требований указаны льготы» — это не про ясность условий.
            return False
        if topic is IssueTopic.EMPLOYMENT:
            return is_missing(vacancy.employment_type)
        if topic is IssueTopic.SALARY:
            return not salary_is_clear(vacancy)
        if topic is IssueTopic.SCHEDULE:
            return not schedule_has_details(vacancy)
        if topic is IssueTopic.LOCATION:
            return not location_is_clear(vacancy)
        if topic is IssueTopic.REQUIREMENTS:
            return not requirements_are_specific(vacancy)
        if topic is IssueTopic.TITLE:
            return not title_is_specific(vacancy)
        if topic is IssueTopic.DUTIES:
            return not duties_are_specific(vacancy)
        return True

    def _source_value(self, topic: IssueTopic, vacancy: NormalizedVacancyDTO) -> str:
        salary = vacancy.salary
        values = {
            IssueTopic.TITLE: vacancy.title,
            IssueTopic.DUTIES: vacancy.duties or vacancy.description,
            IssueTopic.REQUIREMENTS: " ".join(
                filter(
                    None,
                    [
                        vacancy.requirements,
                        vacancy.qualification,
                        vacancy.education,
                        vacancy.experience,
                        " ".join(vacancy.skills),
                    ],
                ),
            ),
            IssueTopic.SALARY: salary.text or self._salary_amounts(vacancy),
            IssueTopic.SCHEDULE: " ".join(filter(None, [vacancy.schedule, " ".join(vacancy.shift)])),
            IssueTopic.LOCATION: " ".join(
                filter(None, [vacancy.address, vacancy.work_place_type, vacancy.work_place_kind]),
            ),
            IssueTopic.EMPLOYMENT: vacancy.employment_type,
        }
        return (values.get(topic) or "").strip()

    def _salary_amounts(self, vacancy: NormalizedVacancyDTO) -> str:
        salary = vacancy.salary
        parts = [
            f"от {salary.from_amount}" if salary.from_amount is not None else "",
            f"до {salary.to_amount}" if salary.to_amount is not None else "",
        ]
        return " ".join(part for part in parts if part)

    def _experience_contradiction_compatible(
        self,
        issue: IssueDTO,
        vacancy: NormalizedVacancyDTO,
    ) -> bool:
        """Опыт «3 года» и требование «не менее 1 года» — не противоречие."""
        text = f"{issue.source_field} {issue.quote}".lower()
        if "experience" not in text and "опыт" not in text and "стаж" not in text:
            return False
        structured = self._months(vacancy.experience or "")
        if structured is None:
            return False
        required = self._max_months(issue.quote or "")
        if required is None:
            return "без опыта" in (issue.quote or "").lower()
        return structured >= required

    def _months(self, value: str) -> int | None:
        text = value.lower()
        if "без опыта" in text:
            return 0
        match = _DURATION.search(text)
        if not match:
            return None
        amount = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        return round(amount * 12) if unit.startswith(("год", "лет")) else round(amount)

    def _max_months(self, value: str) -> int | None:
        text = value.lower()
        months: list[int] = []
        for match in _DURATION.finditer(text):
            amount = float(match.group(1).replace(",", "."))
            unit = match.group(2).lower()
            months.append(round(amount * 12) if unit.startswith(("год", "лет")) else round(amount))
        if "полгода" in text or "полугода" in text:
            months.append(6)
        if re.search(r"(?:не менее|от|минимум)\s+(?:одного|одной|1)\s+года", text):
            months.append(12)
        if "полтора года" in text or "полутора лет" in text:
            months.append(18)
        return max(months) if months else None

    def _schedule_contradiction_compatible(self, issue: IssueDTO) -> bool:
        """«Полный рабочий день» и сменный график/2-2 — совместимые условия."""
        text = f"{issue.source_field} {issue.quote}".lower()
        if "schedule" not in text and "график" not in text:
            return False
        combined = (issue.quote or "").lower()
        if "неполн" in combined or "частичн" in combined:
            return False
        full_day = "полный рабочий день" in combined
        shift_pattern = "смен" in combined or bool(re.search(r"\d+\s*/\s*\d+", combined)) or "час" in combined
        return full_day and shift_pattern

    def _normalize(self, value: str) -> str:
        text = (value or "").lower().replace("ё", "е")
        text = re.sub(r"[«»\"'`.,;:!?()\[\]\u2026\u2014\u2013-]", " ", text)
        return re.sub(r"\s+", " ", text).strip()
