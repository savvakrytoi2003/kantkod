from app.domain.services.rule_checker import RuleChecker
from app.schemas.issue import IssueTopic
from app.schemas.vacancy import NormalizedVacancyDTO, SalaryDTO


def _topics(vacancy: NormalizedVacancyDTO) -> set[IssueTopic]:
    return {issue.topic for issue in RuleChecker().check(vacancy)}


def test_empty_vacancy_reports_all_missing_fields():
    topics = _topics(NormalizedVacancyDTO(external_id="X-1"))

    assert {
        IssueTopic.TITLE,
        IssueTopic.DUTIES,
        IssueTopic.REQUIREMENTS,
        IssueTopic.SALARY,
        IssueTopic.SCHEDULE,
        IssueTopic.LOCATION,
        IssueTopic.EMPLOYMENT,
    } <= topics


def test_concrete_vacancy_has_no_issues():
    vacancy = NormalizedVacancyDTO(
        external_id="X-2",
        title="Специалист по документообороту",
        duties="Регистрация входящей корреспонденции и ведение электронного архива документов.",
        requirements="Среднее профессиональное образование, уверенное владение офисным пакетом.",
        education="Среднее профессиональное",
        experience="без опыта",
        salary=SalaryDTO(from_amount=45000, to_amount=55000, currency="RUB"),
        schedule="Полный рабочий день, понедельник-пятница, 09:00-18:00",
        employment_type="Полная занятость",
        address="г. Калининград, ул. Ленина, 1",
    )

    assert _topics(vacancy) == set()


def test_missing_salary_has_empty_quote():
    issues = RuleChecker().check(NormalizedVacancyDTO(external_id="X-3", title="Библиотекарь"))
    salary_issue = next(issue for issue in issues if issue.topic is IssueTopic.SALARY)

    assert salary_issue.quote == ""
    assert salary_issue.source_field == "salary_min, salary_max"


def test_salary_range_contradiction_keeps_both_values():
    vacancy = NormalizedVacancyDTO(
        external_id="X-4",
        title="Оператор",
        duties="Ввод данных в информационную систему и проверка корректности заполнения полей.",
        requirements="Среднее образование, навыки работы с офисными программами.",
        education="Среднее",
        salary=SalaryDTO(from_amount=70000, to_amount=40000),
        schedule="Полный рабочий день, 09:00-18:00",
        employment_type="Полная занятость",
        address="г. Калининград, ул. Мира, 5",
    )

    contradiction = next(issue for issue in RuleChecker().check(vacancy) if issue.topic is IssueTopic.CONTRADICTION)

    assert "70000" in contradiction.quote
    assert "40000" in contradiction.quote


def _complete_vacancy(**overrides: object) -> NormalizedVacancyDTO:
    data: dict[str, object] = {
        "external_id": "X-10",
        "title": "Специалист по документообороту",
        "duties": "Регистрация входящей корреспонденции и ведение электронного архива документов.",
        "requirements": "Среднее профессиональное образование, уверенное владение офисным пакетом.",
        "education": "Среднее профессиональное",
        "experience": "без опыта",
        "salary": {"from_amount": 45000, "to_amount": 55000, "currency": "RUB"},
        "schedule": "Полный рабочий день, понедельник-пятница, 09:00-18:00",
        "employment_type": "Полная занятость",
        "address": "г. Калининград, ул. Ленина, 1",
    }
    data.update(overrides)
    return NormalizedVacancyDTO.model_validate(data)


def test_schedule_details_in_qualification_suppress_false_positive():
    vacancy = _complete_vacancy(
        schedule="Сменная работа",
        qualification="Работа в первую и вторую смены, 8 часов.",
    )

    assert IssueTopic.SCHEDULE not in _topics(vacancy)


def test_schedule_details_in_shift_suppress_false_positive():
    vacancy = _complete_vacancy(schedule=None, shift=["Только дневная смена"])

    assert IssueTopic.SCHEDULE not in _topics(vacancy)


def test_vague_duties_phrase_is_flagged():
    vacancy = _complete_vacancy(duties="Выполнение различных поручений руководителя.")

    assert IssueTopic.DUTIES in _topics(vacancy)


def test_placeholder_employment_is_treated_as_missing():
    vacancy = _complete_vacancy(employment_type="любой")

    assert IssueTopic.EMPLOYMENT in _topics(vacancy)


def test_salary_without_max_is_flagged():
    vacancy = _complete_vacancy(salary=SalaryDTO(from_amount=45000))
    issue = next(item for item in RuleChecker().check(vacancy) if item.topic is IssueTopic.SALARY)

    assert "максимальная" in issue.problem


def test_salary_without_min_is_flagged():
    vacancy = _complete_vacancy(salary=SalaryDTO(to_amount=55000))
    issue = next(item for item in RuleChecker().check(vacancy) if item.topic is IssueTopic.SALARY)

    assert "минимальная" in issue.problem


def test_ambiguous_education_is_flagged():
    vacancy = _complete_vacancy(requirements="высшее или среднее экономическое образование")
    issues = [item for item in RuleChecker().check(vacancy) if item.topic is IssueTopic.REQUIREMENTS]

    assert issues
    assert "неоднозначно" in issues[0].problem
