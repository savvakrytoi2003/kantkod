"""Общие признаки того, что поле вакансии действительно раскрыто.

Используются и правилами, и верификатором, чтобы не расходиться в оценках.
"""

from __future__ import annotations

import re

from app.domain.services.placeholders import is_missing
from app.schemas.vacancy import NormalizedVacancyDTO

GENERIC_TITLES = frozenset(
    {
        "специалист",
        "менеджер",
        "сотрудник",
        "рабочий",
        "помощник",
        "оператор",
        "консультант",
        "администратор",
    },
)

# Конкретные детали графика: время, дни, смены, часы, выходные.
SCHEDULE_DETAIL = re.compile(
    r"\d{1,2}[:.]\d{2}"  # 09:00, 9.00
    r"|\d+\s*(?:час|смен|дн|день|недел)"  # 8 часов, 2 смены
    r"|с\s*\d{1,2}\s*(?:до|по)"  # с 9 до 18
    r"|\d+\s*/\s*\d+"  # 5/2, 2/2
    r"|\b(?:пн|вт|ср|чт|пт|сб|вс)\b"  # сокращённые дни
    r"|(?:понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)"
    r"|(?:выходн|праздничн)"
    r"|(?:перв|втор|трет|четверт)[а-яё]*\s+смен"  # первая смена
    r"|(?:дневн|вечерн|ночн|утренн)[а-яё]*\s+смен",  # дневная смена
    re.IGNORECASE,
)

_PROFESSIONAL_MARKERS = re.compile(
    r"образован|опыт\s+работ|стаж|квалификац|специальн|навык|знани|умени|владени|"
    r"допуск|сертификат|курс|разряд|категори",
    re.IGNORECASE,
)

_DUTY_ACTION_MARKERS = re.compile(
    r"выполня|осуществля|обеспечива|консультир|проводить|заниматься|работа\s+с|продаж|обслужива|"
    r"подготовк|ведение|контроль|учет|учёт|оформлен|прием|приём|диагностик|ремонт|монтаж|уборк|"
    r"разработк|составлен|расчет|расчёт|анализ|регистрац|обработк|сборк|доставк|погрузк|разгрузк|"
    r"изготовлен|проверк|настройк|тестирован",
    re.IGNORECASE,
)

_ADDRESS_MARKERS = re.compile(
    r"(?:ул|улиц|просп|переул|бульвар|шоссе|дом|д\.|площад|наб|тупик|\d)",
    re.IGNORECASE,
)

EDUCATION_AMBIGUITY = re.compile(
    r"(?:высшее|среднее(?:\s+профессиональное)?|средне[- ]?специальное)"
    r".{0,40}(?:или|либо)"
    r".{0,40}(?:высшее|среднее(?:\s+профессиональное)?|средне[- ]?специальное)",
    re.IGNORECASE,
)


def schedule_context(vacancy: NormalizedVacancyDTO) -> str:
    return " ".join(
        filter(
            None,
            [
                vacancy.schedule,
                vacancy.qualification,
                vacancy.requirements,
                vacancy.description,
                vacancy.duties,
                " ".join(vacancy.shift),
            ],
        ),
    )


def schedule_has_details(vacancy: NormalizedVacancyDTO) -> bool:
    """График конкретен, если часы/дни/смены есть в любом текстовом поле вакансии."""
    return bool(SCHEDULE_DETAIL.search(schedule_context(vacancy)))


def salary_is_clear(vacancy: NormalizedVacancyDTO) -> bool:
    salary = vacancy.salary
    if salary.from_amount is not None and salary.to_amount is not None:
        return True
    return bool(re.search(r"\d", (salary.text or "")))


def location_is_clear(vacancy: NormalizedVacancyDTO) -> bool:
    if not is_missing(vacancy.work_place_type):
        return True
    address = (vacancy.address or "").strip()
    if is_missing(address) or len(address) < 12:
        return False
    return bool(_ADDRESS_MARKERS.search(address))


def requirements_are_specific(vacancy: NormalizedVacancyDTO) -> bool:
    requirements = (vacancy.requirements or "").strip()
    qualification = (vacancy.qualification or "").strip()
    education_text = " ".join(filter(None, [requirements, qualification, vacancy.education]))
    if EDUCATION_AMBIGUITY.search(education_text):
        return False
    if len(requirements) >= 30 and _PROFESSIONAL_MARKERS.search(requirements):
        return True
    if len(qualification) >= 30 and _PROFESSIONAL_MARKERS.search(qualification):
        return True
    if not is_missing(vacancy.education) and len(requirements) >= 30:
        return True
    return bool(vacancy.skills) and len(requirements) >= 30


def title_is_specific(vacancy: NormalizedVacancyDTO) -> bool:
    title = (vacancy.title or "").strip()
    if is_missing(title):
        return False
    lowered = title.lower().strip(" .")
    if lowered in GENERIC_TITLES:
        return False
    return len(title) >= 15 or len(title.split()) >= 2


def duties_are_specific(vacancy: NormalizedVacancyDTO) -> bool:
    duties = (vacancy.duties or "").strip()
    if len(duties) < 150:
        return False
    markers = {match.group(0).lower() for match in _DUTY_ACTION_MARKERS.finditer(duties)}
    return len(markers) >= 3
