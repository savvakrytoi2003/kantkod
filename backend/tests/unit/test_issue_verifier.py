from app.domain.services.issue_merger import IssueVerifier
from app.schemas.issue import IssueDTO, IssueTopic
from app.schemas.vacancy import NormalizedVacancyDTO


def make_vacancy(**overrides: object) -> NormalizedVacancyDTO:
    data: dict[str, object] = {
        "external_id": "1",
        "title": "Заведующий производством",
        "description": "",
        "duties": "Контролировать качество блюд.",
        "requirements": "Опыт от года.",
        "salary": {"from_amount": 31000, "to_amount": 31000, "currency": "руб.", "text": "от 31000"},
        "schedule": "Полный рабочий день",
        "employment_type": "Полная занятость",
        "work_place_type": None,
        "address": "г. Советск, ул. Талаха, 18",
        "region_name": "Калининградская область",
        "company_name": "ООО Балтсервис",
    }
    data.update(overrides)
    return NormalizedVacancyDTO.model_validate(data)


def make_issue(topic: IssueTopic, problem: str, quote: str = "") -> IssueDTO:
    return IssueDTO(
        topic=topic,
        source_field=str(topic),
        quote=quote,
        problem=problem,
        recommendation="Уточнить сведения.",
    )


def test_false_missing_issue_is_dropped() -> None:
    issue = make_issue(IssueTopic.EMPLOYMENT, "Не указан тип занятости.")

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_real_missing_issue_is_kept() -> None:
    issue = make_issue(IssueTopic.EMPLOYMENT, "Не указан тип занятости.")

    assert IssueVerifier().verify([issue], make_vacancy(employment_type=None)) == [issue]


def test_quoted_issue_is_kept() -> None:
    issue = make_issue(IssueTopic.SCHEDULE, "График описан неполно.", quote="Полный рабочий день")

    assert IssueVerifier().verify([issue], make_vacancy()) == [issue]


def test_contradiction_requires_both_values() -> None:
    without_quote = make_issue(IssueTopic.CONTRADICTION, "Противоречие в графике.")
    with_both = make_issue(
        IssueTopic.CONTRADICTION,
        "Противоречие в графике.",
        quote="Полный рабочий день / Полная занятость",
    )

    verified = IssueVerifier().verify([without_quote, with_both], make_vacancy())

    assert verified == [with_both]


def test_quote_absent_from_vacancy_is_dropped() -> None:
    issue = make_issue(IssueTopic.OTHER, "Не указано образование.", quote="Не указано")

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_placeholder_employment_issue_is_kept() -> None:
    issue = make_issue(IssueTopic.EMPLOYMENT, "Не указан тип занятости.")

    assert IssueVerifier().verify([issue], make_vacancy(employment_type="любой")) == [issue]


def test_ai_location_issue_dropped_for_complete_address() -> None:
    issue = make_issue(
        IssueTopic.LOCATION,
        "Не указаны детали о доступности или транспорте.",
        quote="г. Советск, ул. Талаха, 18",
    )

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_ai_employment_issue_dropped_for_filled_field() -> None:
    issue = make_issue(
        IssueTopic.EMPLOYMENT,
        "Неясный тип занятости, так как указано только «полная занятость».",
        quote="Полная занятость",
    )

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_ai_salary_issue_dropped_for_amounts() -> None:
    issue = make_issue(
        IssueTopic.SALARY,
        "Неясные условия оплаты.",
        quote="salary_min: 31000, salary_max: 31000",
    )

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_ai_salary_issue_kept_when_only_one_bound() -> None:
    issue = make_issue(
        IssueTopic.SALARY,
        "Не указана максимальная граница оплаты.",
        quote="salary_min: 31000, salary_max: 0",
    )
    vacancy = make_vacancy(salary={"from_amount": 31000, "to_amount": None})

    assert IssueVerifier().verify([issue], vacancy) == [issue]


def test_ai_schedule_issue_dropped_when_details_in_qualification() -> None:
    issue = make_issue(
        IssueTopic.SCHEDULE,
        "Неясный график работы.",
        quote="Полный рабочий день",
    )
    vacancy = make_vacancy(qualification="График работы 5/2, с 09:00 до 18:00.")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_ai_schedule_issue_kept_when_no_details() -> None:
    issue = make_issue(
        IssueTopic.SCHEDULE,
        "Неясный график работы.",
        quote="Полный рабочий день",
    )
    vacancy = make_vacancy(qualification=None, requirements="")

    assert IssueVerifier().verify([issue], vacancy) == [issue]


def test_ai_requirements_issue_dropped_when_requirements_specific() -> None:
    issue = make_issue(
        IssueTopic.REQUIREMENTS,
        "Формулировка требований слишком общая.",
        quote="Высшее образование",
    )
    vacancy = make_vacancy(requirements="Высшее образование, опыт работы от 1 года, знание 1С.")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_ai_requirements_issue_kept_when_requirements_vague() -> None:
    issue = make_issue(
        IssueTopic.REQUIREMENTS,
        "Формулировка требований слишком общая.",
        quote="аккуратность, ответственность",
    )
    vacancy = make_vacancy(requirements="аккуратность, ответственность")

    assert IssueVerifier().verify([issue], vacancy) == [issue]


def test_ai_title_issue_dropped_for_specific_title() -> None:
    issue = make_issue(
        IssueTopic.TITLE,
        "Название должности слишком общее.",
        quote="Заведующий производством",
    )

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_ai_title_issue_kept_for_generic_title() -> None:
    issue = make_issue(IssueTopic.TITLE, "Название должности слишком общее.", quote="Специалист")

    assert IssueVerifier().verify([issue], make_vacancy(title="Специалист")) == [issue]


def test_ai_duties_issue_dropped_for_detailed_duties() -> None:
    duties = (
        "Организация работы склада, приём и размещение товара, контроль остатков, "
        "проведение инвентаризации, оформление документов, обучение персонала, "
        "обеспечение безопасности и порядка на складе."
    )
    issue = make_issue(IssueTopic.DUTIES, "Обязанности слишком общие.", quote="Организация работы склада")

    assert IssueVerifier().verify([issue], make_vacancy(duties=duties)) == []


def test_other_issue_is_retopiced_by_source_field() -> None:
    issue = make_issue(IssueTopic.OTHER, "Требования слишком общие.", quote="Высшее образование")
    issue = issue.model_copy(update={"source_field": "DEMO-1.qualification"})

    verified = IssueVerifier().verify([issue], make_vacancy(requirements="Высшее образование, опыт работы"))

    assert verified == []


def test_ambiguous_education_issue_is_kept() -> None:
    requirements = "высшее или среднее экономическое образование"
    issue = make_issue(IssueTopic.REQUIREMENTS, "Уровень образования указан неоднозначно.", quote=requirements)

    assert IssueVerifier().verify([issue], make_vacancy(requirements=requirements)) == [issue]


def test_contradiction_with_placeholder_part_is_dropped() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "Опыт и образование противоречат друг другу.",
        quote="1 год опыта / Требования не предъявляются",
    )
    vacancy = make_vacancy(
        experience="1 год опыта",
        education="Требования не предъявляются",
    )

    assert IssueVerifier().verify([issue], vacancy) == []


def test_formatting_complaint_is_dropped() -> None:
    issue = make_issue(
        IssueTopic.DUTIES,
        "Обязанности перечислены слитно без разделителей.",
        quote="Организация работы склада",
    )

    assert IssueVerifier().verify([issue], make_vacancy()) == []


def test_experience_contradiction_is_compatible_when_experience_exceeds_requirement() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "Опыт не соответствует требованиям.",
        quote="3 года опыта / не менее одного года",
    )
    vacancy = make_vacancy(experience="3 года опыта")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_experience_contradiction_is_kept_when_experience_is_lower() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "Опыт не соответствует требованиям.",
        quote="1 год опыта / не менее 3 лет",
    )
    vacancy = make_vacancy(experience="1 год опыта", requirements="Опыт работы не менее 3 лет.")

    assert IssueVerifier().verify([issue], vacancy) == [issue]


def test_experience_contradiction_with_months_is_compatible() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "Опыт не соответствует требованиям.",
        quote="1 год опыта / опыт работы от 6 мес.",
    )
    vacancy = make_vacancy(experience="1 год опыта")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_preference_is_not_a_contradiction() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "Образование противоречит требованиям.",
        quote="Общее образование / профильное образование будет преимуществом",
    )
    vacancy = make_vacancy(education="Общее образование")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_full_day_and_shift_schedule_is_not_a_contradiction() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "График противоречит описанию.",
        quote="Полный рабочий день / Рабочее время 8 часов, сменный график",
    )
    vacancy = make_vacancy(qualification="Рабочее время 8 часов, сменный график")

    assert IssueVerifier().verify([issue], vacancy) == []


def test_full_day_and_part_time_is_a_contradiction() -> None:
    issue = make_issue(
        IssueTopic.CONTRADICTION,
        "График противоречит описанию.",
        quote="Полный рабочий день / возможен неполный рабочий день",
    )
    vacancy = make_vacancy(qualification="Возможен неполный рабочий день.")

    assert IssueVerifier().verify([issue], vacancy) == [issue]


def test_field_mismatch_complaint_is_dropped() -> None:
    issue = make_issue(
        IssueTopic.REQUIREMENTS,
        "В поле qualification вместо квалификационных требований указаны условия работы и льготы.",
        quote="график работы 07.00-16.00, 5/2; выплаты заработной платы",
    )
    vacancy = make_vacancy(qualification="график работы 07.00-16.00, 5/2; выплаты заработной платы")

    assert IssueVerifier().verify([issue], vacancy) == []
