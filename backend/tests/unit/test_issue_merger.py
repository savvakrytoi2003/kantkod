from app.domain.services.issue_merger import IssueMerger
from app.schemas.issue import IssueDTO, IssueTopic


def make_issue(topic: IssueTopic, problem: str, quote: str = "") -> IssueDTO:
    return IssueDTO(
        topic=topic,
        source_field=str(topic),
        quote=quote,
        problem=problem,
        recommendation="Указать данные.",
    )


def test_missing_field_issues_merge_by_topic() -> None:
    rule_issue = make_issue(IssueTopic.EMPLOYMENT, "Не указан тип занятости.")
    ai_issue = make_issue(IssueTopic.EMPLOYMENT, "Отсутствует информация о типе занятости.")

    merged = IssueMerger().merge([rule_issue], [ai_issue])

    assert merged == [rule_issue]


def test_quoted_issues_with_different_quotes_are_kept() -> None:
    first = make_issue(IssueTopic.SALARY, "Противоречие.", quote="от 30 000")
    second = make_issue(IssueTopic.SALARY, "Противоречие.", quote="до 20 000")

    merged = IssueMerger().merge([first], [second])

    assert len(merged) == 2


def test_common_issue_is_dropped_when_contradiction_exists() -> None:
    contradiction = IssueDTO(
        topic=IssueTopic.CONTRADICTION,
        source_field="requirement.experience, requirement.qualification",
        quote="experience: 0 / Требуется не менее 5 лет опыта.",
        problem="Опыт противоречит требованию.",
        recommendation="Согласовать требования.",
    )
    echo = IssueDTO(
        topic=IssueTopic.OTHER,
        source_field="DEMO-1.experience",
        quote="experience: без опыта",
        problem="Требования к опыту противоречат обязанностям.",
        recommendation="Уточнить требования.",
    )

    merged = IssueMerger().merge([contradiction], [echo])

    assert merged == [contradiction]


def test_same_quote_is_deduplicated() -> None:
    rule_issue = make_issue(IssueTopic.SCHEDULE, "Нет графика.", quote="сменный график")
    ai_issue = make_issue(IssueTopic.SCHEDULE, "График описан неполно.", quote="Сменный график")

    merged = IssueMerger().merge([rule_issue], [ai_issue])

    assert merged == [rule_issue]


def test_field_only_quote_deduplicates_with_empty_quote() -> None:
    rule_issue = make_issue(IssueTopic.EMPLOYMENT, "Не указан тип занятости.")
    ai_issue = make_issue(
        IssueTopic.EMPLOYMENT,
        "Тип занятости не указан, непонятно, полная или частичная.",
    ).model_copy(update={"quote": "employment:"})

    merged = IssueMerger().merge([rule_issue], [ai_issue])

    assert merged == [rule_issue]
