import json

from app.schemas.resume import ResumeDTO
from app.schemas.vacancy import NormalizedVacancyDTO

_SYSTEM = (
    "Ты помогаешь соискателю подготовить черновик резюме под конкретную вакансию.\n\n"
    "Жёсткие правила:\n"
    "- Используй ТОЛЬКО факты из резюме соискателя: компании, должности, периоды, опыт, навыки, "
    "образование, сертификаты и языки. Не придумывай ничего, чего нет в резюме.\n"
    "- Не добавляй требования вакансии в опыт или навыки, если они не подтверждены резюме. "
    "Вместо этого вынеси их в gaps со status partial или missing и дай конкретный совет.\n"
    "- Не добавляй личные данные (телефон, адрес, возраст), которых нет в резюме.\n"
    "- Не делай выводов о дискриминации, нарушениях закона и не оценивай кандидата по возрасту/полу.\n"
    "- Пиши по-русски, кратко и конкретно; не используй вымышленные цифры и достижения.\n\n"
    "Верни строго один JSON-объект без markdown и комментариев:\n"
    '{"summary": "краткое резюме под вакансию", '
    '"highlighted_skills": ["навыки из резюме, важные для вакансии"], '
    '"experience_highlights": ["факты/достижения из опыта, уместные для вакансии"], '
    '"education_highlights": ["образование из резюме"], '
    '"gaps": [{"requirement": "требование вакансии", "status": "matched|partial|missing", '
    '"advice": "что уточнить или добавить"}], '
    '"draft_text": "готовый черновик резюме в Markdown: цель, краткое summary, опыт, образование, навыки"}\n\n'
    "Если требование вакансии подтверждено резюме — status matched. Если подтверждено частично — partial. "
    "Если не подтверждено — missing, и в advice напиши, что именно уточнить, не выдумывая факт."
)


class ResumePromptBuilder:
    """Промпт для черновика резюме под вакансию."""

    def system_prompt(self) -> str:
        return _SYSTEM

    def user_prompt(self, vacancy: NormalizedVacancyDTO, resume: ResumeDTO) -> str:
        salary = vacancy.salary
        vacancy_context = {
            "vacancy_id": vacancy.external_id,
            "title": vacancy.title,
            "company": vacancy.company_name or "",
            "region": vacancy.region_name or "",
            "duties": vacancy.duties,
            "requirements": vacancy.requirements,
            "qualification": vacancy.qualification or "",
            "experience": vacancy.experience or "",
            "education": vacancy.education or "",
            "skills": vacancy.skills,
            "salary": salary.text
            or " ".join(
                part
                for part in [
                    f"от {salary.from_amount}" if salary.from_amount is not None else "",
                    f"до {salary.to_amount}" if salary.to_amount is not None else "",
                    salary.currency or "",
                ]
                if part
            ),
            "schedule": vacancy.schedule or "",
            "employment": vacancy.employment_type or "",
            "location": vacancy.address or vacancy.work_place_type or "",
        }
        resume_context = resume.model_dump()
        return (
            "Вакансия (регион 39):\n"
            + json.dumps(vacancy_context, ensure_ascii=False, indent=1)
            + "\n\nРезюме соискателя:\n"
            + json.dumps(resume_context, ensure_ascii=False, indent=1)
            + "\n\nСоставь черновик резюме под эту вакансию и верни JSON по схеме. "
            "Все факты — только из резюме; чего не хватает — в gaps."
        )

    def repair_prompt(self, invalid_answer: str) -> str:
        return (
            "Предыдущий ответ не соответствует JSON-схеме. Верни строго один JSON-объект вида "
            '{"summary": "...", "highlighted_skills": [...], "experience_highlights": [...], '
            '"education_highlights": [...], "gaps": [{"requirement": "...", "status": "matched|partial|missing", '
            '"advice": "..."}], "draft_text": "..."} без markdown и комментариев.\n\n'
            "Предыдущий ответ:\n" + invalid_answer[:4000]
        )
