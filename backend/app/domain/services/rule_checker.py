import re

from app.domain.services.placeholders import is_missing
from app.domain.services.vacancy_signals import (
    EDUCATION_AMBIGUITY,
    GENERIC_TITLES,
    SCHEDULE_DETAIL,
    schedule_has_details,
)
from app.schemas.issue import IssueDTO, IssueTopic
from app.schemas.vacancy import NormalizedVacancyDTO


class RuleChecker:
    """Programmatic checks that run before the AI analysis."""

    _VAGUE_SCHEDULE = ("гибк", "сменн", "по графику", "свободный график", "график обсуждается")
    _VAGUE_SALARY = (
        "по договоренности",
        "по договорённости",
        "по результатам собеседования",
        "обсуждается",
        "по итогам",
    )
    _VAGUE_DUTIES = (
        "разные задачи",
        "по указанию руководителя",
        "и другие обязанности",
        "прочие обязанности",
        "по необходимости",
        "поручени",
        "различные задачи",
    )
    _GENERIC_TITLES = GENERIC_TITLES
    _EXPERIENCE_YEARS = re.compile(r"(\d+)\s*(?:год|года|лет)", re.IGNORECASE)
    _FOLLOW_UP_LOCATION = re.compile(
        r"уточня\w+ (?:при|на) собеседовани|адрес уточня|формат работы уточня",
        re.IGNORECASE,
    )
    _SOFT_SKILLS = re.compile(
        r"коммуникабельн|стрессоустойчив|ответственн|исполнительн|активн|внимательн|трудолюбив|обучаем|"
        r"целеустремлен|инициативн|пунктуальн|вежлив|дисциплинирован",
        re.IGNORECASE,
    )
    _DUTY_MARKERS = re.compile(
        r"обязанн|функци|должностн|выполня|осуществля|обеспечива|консультир|проводить|заниматься|работа\s+с",
        re.IGNORECASE,
    )
    _REMOTE = re.compile(r"удал[её]нн|дистанционн|на дому", re.IGNORECASE)
    _ON_SITE = re.compile(r"на территории|в офисе|офис", re.IGNORECASE)
    _PART_TIME = re.compile(r"подработ|частичн\w* занят|неполн\w* (день|занят)|совместительств", re.IGNORECASE)

    def check(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        issues: list[IssueDTO] = []
        issues.extend(self._check_title(vacancy))
        issues.extend(self._check_duties(vacancy))
        issues.extend(self._check_requirements(vacancy))
        issues.extend(self._check_salary(vacancy))
        issues.extend(self._check_schedule(vacancy))
        issues.extend(self._check_location(vacancy))
        issues.extend(self._check_employment(vacancy))
        issues.extend(self._check_contradictions(vacancy))
        return self._deduplicate(issues)

    def _is_missing(self, value: str | None) -> bool:
        return is_missing(value)

    def _check_title(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        if self._is_missing(vacancy.title):
            return [
                self._issue(
                    IssueTopic.TITLE,
                    "title",
                    vacancy.title or "",
                    "Не указано название должности.",
                    "Указать конкретное название должности так, как она называется в штатном расписании.",
                ),
            ]
        if len(vacancy.title.strip()) < 3:
            return [
                self._issue(
                    IssueTopic.TITLE,
                    "title",
                    vacancy.title,
                    "Название должности нечитаемо.",
                    "Указать полное название должности.",
                ),
            ]
        words = vacancy.title.strip().lower().strip(".").split()
        if len(words) == 1 and words[0] in self._GENERIC_TITLES:
            return [
                self._issue(
                    IssueTopic.TITLE,
                    "job-name",
                    vacancy.title,
                    "Название должности слишком общее и не отражает профессиональную специализацию.",
                    "Указать название должности с направлением деятельности, "
                    "например «специалист по документообороту».",
                ),
            ]
        return []

    def _check_duties(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        duties = vacancy.duties or ""
        description = f"{vacancy.description or ''} {vacancy.qualification or ''}"
        if self._is_missing(duties):
            if self._DUTY_MARKERS.search(description) and len(vacancy.description.strip()) >= 40:
                return []
            return [
                self._issue(
                    IssueTopic.DUTIES,
                    "duties",
                    "" if self._is_missing(duties) else duties,
                    "В вакансии не раскрыты обязанности.",
                    "Перечислить ключевые обязанности: что именно сотрудник будет делать ежедневно.",
                ),
            ]
        stripped = duties.strip().lower().strip(" .")
        too_short = len(duties.strip()) < 25
        vague_phrase = stripped in self._VAGUE_DUTIES or (
            len(duties.strip()) < 90 and any(marker in stripped for marker in self._VAGUE_DUTIES)
        )
        if too_short or vague_phrase:
            return [
                self._issue(
                    IssueTopic.DUTIES,
                    "duties",
                    duties,
                    "Обязанности описаны слишком общо.",
                    "Раскрыть конкретные задачи, инструменты и ожидаемый результат работы.",
                ),
            ]
        return []

    def _check_requirements(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        requirements = vacancy.requirements or ""
        structured = any(
            not self._is_missing(value) for value in (vacancy.experience, vacancy.education, vacancy.qualification)
        )
        if self._is_missing(requirements):
            if structured or vacancy.skills:
                return []
            return [
                self._issue(
                    IssueTopic.REQUIREMENTS,
                    "requirements",
                    "",
                    "Не указаны требования к кандидату.",
                    "Указать образование, опыт работы и обязательные профессиональные навыки.",
                ),
            ]
        ambiguous = EDUCATION_AMBIGUITY.search(
            " ".join(filter(None, [requirements, vacancy.qualification, vacancy.education])),
        )
        if ambiguous:
            return [
                self._issue(
                    IssueTopic.REQUIREMENTS,
                    "requirements",
                    ambiguous.group(0),
                    "Уровень образования указан неоднозначно: приведены два варианта.",
                    "Указать один требуемый уровень образования либо пояснить, от чего он зависит.",
                ),
            ]
        if len(requirements.strip()) < 10:
            return [
                self._issue(
                    IssueTopic.REQUIREMENTS,
                    "requirements",
                    requirements,
                    "Требования указаны без конкретики.",
                    "Перечислить конкретные требования: образование, опыт, навыки и допуски.",
                ),
            ]
        if (
            not structured
            and len(vacancy.skills) == 0
            and self._SOFT_SKILLS.fullmatch(
                requirements.strip().lower().strip(" ."),
            )
        ):
            return [
                self._issue(
                    IssueTopic.REQUIREMENTS,
                    "requirements",
                    requirements,
                    "Требования ограничены общими характеристиками.",
                    "Добавить профессиональные требования: образование, опыт, навыки и знания.",
                ),
            ]
        return []

    def _check_salary(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        salary = vacancy.salary
        text = (salary.text or "").strip()
        if salary.has_amounts:
            if salary.to_amount is None and salary.from_amount is not None:
                return [
                    self._issue(
                        IssueTopic.SALARY,
                        "salary_min, salary_max",
                        f"salary_min: {salary.from_amount}, salary_max: 0",
                        "Не указана максимальная граница оплаты труда.",
                        "Указать верхнюю границу заработной платы либо пояснить, от чего зависит итоговая сумма.",
                    ),
                ]
            if salary.from_amount is None and salary.to_amount is not None:
                return [
                    self._issue(
                        IssueTopic.SALARY,
                        "salary_min, salary_max",
                        f"salary_min: 0, salary_max: {salary.to_amount}",
                        "Не указана минимальная граница оплаты труда.",
                        "Указать нижнюю границу заработной платы либо пояснить, от чего зависит итоговая сумма.",
                    ),
                ]
            return []
        if not text or self._is_missing(text):
            return [
                self._issue(
                    IssueTopic.SALARY,
                    "salary_min, salary_max",
                    "",
                    "В вакансии отсутствуют сведения об оплате: "
                    "нулевые значения не позволяют определить размер вознаграждения.",
                    "Указать минимальную и максимальную заработную плату в рублях либо явно обозначить, "
                    "что размер оплаты обсуждается на собеседовании.",
                ),
            ]
        if re.search(r"\d", text):
            return []
        lowered = text.lower()
        vague = any(marker in lowered for marker in self._VAGUE_SALARY)
        return [
            self._issue(
                IssueTopic.SALARY,
                "salary",
                text,
                "Условия оплаты указаны без конкретной суммы." if vague else "В описании оплаты нет числовых значений.",
                "Указать конкретную сумму или диапазон заработной платы, а также от чего зависит доход.",
            ),
        ]

    def _check_schedule(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        schedule = vacancy.schedule or ""
        if self._is_missing(schedule):
            if schedule_has_details(vacancy):
                return []
            return [
                self._issue(
                    IssueTopic.SCHEDULE,
                    "schedule",
                    "",
                    "Не указан график работы.",
                    "Указать рабочие дни, время начала и окончания работы, продолжительность смен.",
                ),
            ]
        lowered = schedule.lower()
        if any(marker in lowered for marker in self._VAGUE_SCHEDULE) and not schedule_has_details(vacancy):
            return [
                self._issue(
                    IssueTopic.SCHEDULE,
                    "schedule",
                    schedule,
                    "Не указаны конкретные условия расписания.",
                    "Уточнить рабочие дни, время начала и окончания работы, продолжительность смен.",
                ),
            ]
        return []

    def _check_location(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        address = vacancy.address or ""
        work_place = vacancy.work_place_type or ""
        if self._is_missing(address) and self._is_missing(work_place):
            return [
                self._issue(
                    IssueTopic.LOCATION,
                    "address",
                    "",
                    "Не указано место работы.",
                    "Указать населённый пункт и адрес рабочего места либо формат работы (удалённо, разъездной).",
                ),
            ]
        if not self._is_missing(address) and len(address.strip()) < 8 and self._is_missing(work_place):
            return [
                self._issue(
                    IssueTopic.LOCATION,
                    "address",
                    address,
                    "Адрес рабочего места указан не полностью.",
                    "Уточнить населённый пункт, улицу и дом либо указать формат работы.",
                ),
            ]
        return []

    def _check_employment(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        employment = vacancy.employment_type or ""
        if self._is_missing(employment):
            return [
                self._issue(
                    IssueTopic.EMPLOYMENT,
                    "employment",
                    "",
                    "Не указан тип занятости.",
                    "Указать тип занятости: полная, частичная, проектная или стажировка.",
                ),
            ]
        if len(employment.strip()) < 4:
            return [
                self._issue(
                    IssueTopic.EMPLOYMENT,
                    "employment",
                    employment,
                    "Тип занятости указан неоднозначно.",
                    "Указать тип занятости полностью, например «полная занятость».",
                ),
            ]
        return []

    def _check_contradictions(self, vacancy: NormalizedVacancyDTO) -> list[IssueDTO]:
        issues: list[IssueDTO] = []
        salary = vacancy.salary
        if salary.from_amount is not None and salary.to_amount is not None and salary.from_amount > salary.to_amount:
            issues.append(
                self._issue(
                    IssueTopic.CONTRADICTION,
                    "salary",
                    f"от {salary.from_amount} / до {salary.to_amount}",
                    "Нижняя граница оплаты больше верхней.",
                    "Исправить диапазон оплаты: нижняя граница не может превышать верхнюю.",
                ),
            )

        description = vacancy.description or ""
        work_place = vacancy.work_place_type or ""
        remote_text = " ".join(filter(None, [description, vacancy.duties]))
        on_site_text = " ".join(filter(None, [work_place, vacancy.qualification, vacancy.requirements]))
        remote_match = self._REMOTE.search(remote_text)
        on_site_match = self._ON_SITE.search(on_site_text)
        if remote_match and on_site_match:
            issues.append(
                self._issue(
                    IssueTopic.CONTRADICTION,
                    "work_place_type, requirement.qualification",
                    f"{self._quote(remote_text, remote_match)} / {self._quote(on_site_text, on_site_match)}",
                    "Формат работы в описании противоречит требованию о присутствии в офисе.",
                    "Согласовать формат работы: указать либо работу в офисе, либо удалённую работу.",
                ),
            )

        experience = (vacancy.experience or "").strip()
        if experience.lower() in {"без опыта", "0 лет опыта"}:
            requirement_text = " ".join(filter(None, [vacancy.requirements, vacancy.qualification]))
            match = self._EXPERIENCE_YEARS.search(requirement_text)
            if match and int(match.group(1)) > 0:
                issues.append(
                    self._issue(
                        IssueTopic.CONTRADICTION,
                        "requirement.experience, requirement.qualification",
                        f"experience: 0 / {self._quote(requirement_text, match)}",
                        "Структурированное значение опыта противоречит тексту требований.",
                        "Согласовать требования к опыту и указать единое значение.",
                    ),
                )

        schedule = (vacancy.schedule or "").strip()
        if "гибк" in schedule.lower():
            fixed_text = " ".join(filter(None, [vacancy.qualification, vacancy.requirements, vacancy.description]))
            fixed_match = SCHEDULE_DETAIL.search(fixed_text)
            if fixed_match and re.search(r"пятидневн|ежедневн|фиксирован", fixed_text, re.IGNORECASE):
                issues.append(
                    self._issue(
                        IssueTopic.CONTRADICTION,
                        "schedule, requirement.qualification",
                        f"schedule: {schedule} / {self._quote(fixed_text, fixed_match)}",
                        "Гибкий график противоречит фиксированному режиму работы в тексте вакансии.",
                        "Уточнить, является ли график фиксированным или гибким, "
                        "и описать допустимые часы начала и окончания.",
                    ),
                )

        address = (vacancy.address or "").strip()
        follow_up = self._FOLLOW_UP_LOCATION.search(f"{vacancy.qualification or ''} {vacancy.requirements or ''}")
        if address and follow_up and len(address) < 20:
            issues.append(
                self._issue(
                    IssueTopic.LOCATION,
                    "addresses.address, requirement.qualification",
                    f"{address} / {vacancy.qualification}",
                    "Адрес и формат работы указаны не полностью.",
                    "Указать фактический формат работы (офисный, удалённый или гибридный) и точный адрес.",
                ),
            )

        part_time_match = self._PART_TIME.search(description)
        employment = vacancy.employment_type or ""
        if part_time_match and employment and "полн" in employment.lower() and "неполн" not in employment.lower():
            issues.append(
                self._issue(
                    IssueTopic.CONTRADICTION,
                    "employment",
                    f"{employment} / {self._quote(description, part_time_match)}",
                    "Тип занятости противоречит тексту описания.",
                    "Уточнить тип занятости: полная или частичная занятость.",
                ),
            )
        return issues

    def _quote(self, text: str, match: re.Match[str]) -> str:
        start = max(0, text.rfind(".", 0, match.start()) + 1)
        end = text.find(".", match.end())
        if end == -1:
            end = min(len(text), match.end() + 120)
        return text[start:end].strip()[:300]

    def _issue(
        self,
        topic: IssueTopic,
        source_field: str,
        quote: str,
        problem: str,
        recommendation: str,
    ) -> IssueDTO:
        return IssueDTO(
            topic=topic,
            source_field=source_field,
            quote=quote,
            problem=problem,
            recommendation=recommendation,
        )

    def _deduplicate(self, issues: list[IssueDTO]) -> list[IssueDTO]:
        seen: set[tuple[str, str]] = set()
        unique: list[IssueDTO] = []
        for issue in issues:
            key = (str(issue.topic), issue.problem.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(issue)
        return unique
