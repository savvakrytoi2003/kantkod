from app.domain.services.vacancy_normalizer import VacancyNormalizer

RAW = {
    "vacancy": {
        "id": "X-1",
        "job-name": "Инженер по метрологии",
        "salary": "от 45000",
        "salary_min": 45000,
        "salary_max": 66000,
        "currency": "RUB",
        "schedule": "Сменная работа",
        "shift": ["Только дневная смена"],
        "employment": "Полная занятость",
        "qualification": "Уверенный пользователь ПК",
        "requirement": {
            "education": "Высшее образование",
            "experience": 1,
            "qualification": "Навыки работы в 1С",
        },
        "addresses": {"address": [{"location": "г. Калининград, ул. Ленина, 1"}]},
        "workPlaceType": {
            "workPlaceQuota": False,
            "workPlaceForeign": False,
            "workPlaceSpecial": False,
            "workPlaceOrdinary": True,
        },
        "company": {"name": "ООО Ромашка", "companycode": "123"},
        "region": {"name": "Калининградская область", "region_code": "39"},
        "skills": ["SQL", "SQL", "Excel"],
        "creation-date": "2026-01-01",
    },
}


def _normalize(raw: dict = RAW):
    vacancy = VacancyNormalizer().normalize(raw)
    assert vacancy is not None
    return vacancy


def test_merges_top_level_qualification() -> None:
    vacancy = _normalize()
    assert vacancy.qualification is not None
    assert "Навыки работы в 1С" in vacancy.qualification
    assert "Уверенный пользователь ПК" in vacancy.qualification


def test_top_level_qualification_used_when_requirement_is_empty() -> None:
    raw = {
        "vacancy": {
            "id": "X-2",
            "requirement": {"qualification": ""},
            "qualification": "Высшее профессиональное образование",
        },
    }
    assert _normalize(raw).qualification == "Высшее профессиональное образование"


def test_placeholder_qualification_is_skipped() -> None:
    raw = {
        "vacancy": {
            "id": "X-3",
            "requirement": {"qualification": "нет"},
            "qualification": "нет",
        },
    }
    assert _normalize(raw).qualification is None


def test_experience_pluralization() -> None:
    cases = [
        (1, "1 год опыта"),
        (2, "2 года опыта"),
        (5, "5 лет опыта"),
        (11, "11 лет опыта"),
        (21, "21 год опыта"),
        (0, "без опыта"),
        ("1-3 года", "1-3 года"),
    ]
    for value, expected in cases:
        raw = {"vacancy": {"id": "X", "requirement": {"experience": value}}}
        assert _normalize(raw).experience == expected


def test_parses_shift_and_work_place_kind() -> None:
    raw = {
        "vacancy": {
            "id": "X-4",
            "shift": ["По графику сменности"],
            "workPlaceType": {
                "workPlaceQuota": True,
                "workPlaceSpecial": False,
                "workPlaceForeign": False,
                "workPlaceOrdinary": False,
                "workPlaceDisabilityGroup": "Нарушение слуха – глухой",
            },
        },
    }
    vacancy = _normalize(raw)
    assert vacancy.shift == ["По графику сменности"]
    assert vacancy.work_place_kind is not None
    assert "квотируемое" in vacancy.work_place_kind
    assert "Нарушение слуха" in vacancy.work_place_kind


def test_address_from_list_of_dicts() -> None:
    raw = {
        "vacancy": {
            "id": "X-5",
            "addresses": {
                "address": [
                    {"location": "г. Калининград, ул. Ленина, 1"},
                    {"location": "г. Советск, ул. Мира, 2"},
                ],
            },
        },
    }
    assert _normalize(raw).address == "г. Калининград, ул. Ленина, 1; г. Советск, ул. Мира, 2"


def test_address_from_string() -> None:
    raw = {"vacancy": {"id": "X-6", "addresses": {"address": "г. Калининград"}}}
    assert _normalize(raw).address == "г. Калининград"


def test_salary_object_support() -> None:
    raw = {
        "vacancy": {
            "id": "X-7",
            "salary": {"text": "от 45 000", "from": "45000", "to": 66000, "currency": "RUB"},
        },
    }
    salary = _normalize(raw).salary
    assert salary.from_amount == 45000
    assert salary.to_amount == 66000
    assert salary.text == "от 45 000"
    assert salary.currency == "RUB"


def test_company_and_region_as_strings() -> None:
    raw = {
        "vacancy": {
            "id": "X-8",
            "company": "ООО Ромашка",
            "region": "Калининградская область",
        },
    }
    vacancy = _normalize(raw)
    assert vacancy.company_name == "ООО Ромашка"
    assert vacancy.region_name == "Калининградская область"


def test_skills_are_deduplicated() -> None:
    assert _normalize().skills == ["SQL", "Excel"]


def test_vacancy_without_identifier_is_skipped() -> None:
    assert VacancyNormalizer().normalize({"vacancy": {"job-name": "Без id"}}) is None
