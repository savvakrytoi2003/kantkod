import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchVacancyList, generateResumeDraft } from "./api";
import { Icon } from "./icons";
import { DEMO_RESUME_JSON, DEMO_RESUME_TEXT } from "./resumeDemo";
import type { ResumeDraft, ResumeGapStatus, SalaryInfo, VacancyListItem } from "./types";

type ResumeInputMode = "text" | "json";

const GAP_LABELS: Record<ResumeGapStatus, string> = {
  matched: "есть",
  partial: "частично",
  missing: "нет",
};

function salaryText(salary: SalaryInfo): string {
  if (salary.text) {
    return salary.text;
  }
  if (salary.from_amount && salary.to_amount) {
    return `${salary.from_amount.toLocaleString("ru-RU")} – ${salary.to_amount.toLocaleString("ru-RU")} ${salary.currency ?? ""}`.trim();
  }
  if (salary.from_amount) {
    return `от ${salary.from_amount.toLocaleString("ru-RU")} ${salary.currency ?? ""}`.trim();
  }
  if (salary.to_amount) {
    return `до ${salary.to_amount.toLocaleString("ru-RU")} ${salary.currency ?? ""}`.trim();
  }
  return "Оплата не указана";
}

function downloadFile(name: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function ResumePanel({ active }: { active: boolean }) {
  const [vacancies, setVacancies] = useState<VacancyListItem[] | null>(null);
  const [vacancyError, setVacancyError] = useState<string | null>(null);
  const [vacancyQuery, setVacancyQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inputMode, setInputMode] = useState<ResumeInputMode>("text");
  const [resumeText, setResumeText] = useState("");
  const [resumeJson, setResumeJson] = useState<unknown | null>(null);
  const [jsonName, setJsonName] = useState<string | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ResumeDraft | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const resumeInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLElement>(null);
  const copyTimer = useRef<number | null>(null);
  const linkTimer = useRef<number | null>(null);

  const loadVacancies = useCallback(() => {
    let alive = true;
    setVacancyError(null);
    fetchVacancyList()
      .then((page) => {
        if (alive) {
          setVacancies(page.items);
        }
      })
      .catch((reason: unknown) => {
        if (alive) {
          setVacancyError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!active || vacancies !== null) {
      return;
    }
    return loadVacancies();
  }, [active, vacancies, loadVacancies]);

  useEffect(
    () => () => {
      if (copyTimer.current !== null) {
        window.clearTimeout(copyTimer.current);
      }
      if (linkTimer.current !== null) {
        window.clearTimeout(linkTimer.current);
      }
    },
    [],
  );

  const filteredVacancies = useMemo(() => {
    const needle = vacancyQuery.trim().toLowerCase();
    const list = vacancies ?? [];
    if (!needle) {
      return list;
    }
    return list.filter((vacancy) =>
      [vacancy.title, vacancy.company_name ?? "", vacancy.region_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [vacancies, vacancyQuery]);

  const selectedVacancy = useMemo(
    () => (vacancies ?? []).find((vacancy) => vacancy.external_id === selectedId) ?? null,
    [vacancies, selectedId],
  );

  const hasResume = inputMode === "json" ? resumeJson !== null : resumeText.trim().length > 0;
  const canGenerate = Boolean(selectedVacancy) && hasResume && !loading;

  const useDemoText = () => {
    setInputMode("text");
    setResumeText(DEMO_RESUME_TEXT);
    setDraftError(null);
  };

  const useDemoJson = () => {
    setInputMode("json");
    setResumeJson(DEMO_RESUME_JSON);
    setJsonName("demo-resume.json");
    setJsonError(null);
    setDraftError(null);
  };

  const onResumeFile = (file: File | undefined) => {
    if (!file) {
      return;
    }
    if (!file.name.toLowerCase().endsWith(".json")) {
      setJsonError("Поддерживается только .json.");
      return;
    }
    if (file.size > 1024 * 1024) {
      setJsonError("Файл больше 1 МБ.");
      return;
    }
    file
      .text()
      .then((text) => {
        const parsed: unknown = JSON.parse(text);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          setJsonError("Ожидается JSON-объект с полями резюме.");
          return;
        }
        setResumeJson(parsed);
        setJsonName(file.name);
        setJsonError(null);
        setInputMode("json");
        setDraftError(null);
      })
      .catch(() => setJsonError("Не удалось прочитать JSON."));
  };

  const generate = () => {
    if (!selectedVacancy) {
      setDraftError("Сначала выберите вакансию.");
      return;
    }
    const resume = inputMode === "json" ? resumeJson : resumeText.trim();
    if (resume === null || (typeof resume === "string" && !resume)) {
      setDraftError("Добавьте резюме: вставьте текст или загрузите JSON.");
      return;
    }
    setLoading(true);
    setDraftError(null);
    setCopied(false);
    generateResumeDraft(selectedVacancy.external_id, resume)
      .then((result) => {
        setDraft(result);
        if (window.matchMedia?.("(max-width: 900px)").matches) {
          resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      })
      .catch((reason: unknown) => {
        setDraftError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => setLoading(false));
  };

  const copyDraft = () => {
    if (!draft) {
      return;
    }
    navigator.clipboard
      .writeText(draft.draft_text)
      .then(() => {
        setCopied(true);
        if (copyTimer.current !== null) {
          window.clearTimeout(copyTimer.current);
        }
        copyTimer.current = window.setTimeout(() => setCopied(false), 1800);
      })
      .catch(() => setDraftError("Не удалось скопировать текст."));
  };

  const copyLink = (url: string) => {
    if (!url) {
      return;
    }
    navigator.clipboard
      .writeText(url)
      .then(() => {
        setLinkCopied(true);
        if (linkTimer.current !== null) {
          window.clearTimeout(linkTimer.current);
        }
        linkTimer.current = window.setTimeout(() => setLinkCopied(false), 1800);
      })
      .catch(() => setDraftError("Не удалось скопировать ссылку."));
  };

  const downloadDraft = (format: "md" | "json") => {
    if (!draft) {
      return;
    }
    const base = `resume-${draft.vacancy_id}`;
    if (format === "md") {
      downloadFile(`${base}.md`, draft.draft_text, "text/markdown;charset=utf-8");
      return;
    }
    downloadFile(`${base}.json`, JSON.stringify(draft, null, 2), "application/json;charset=utf-8");
  };

  return (
    <section className="resume-workspace" hidden={!active} aria-label="Резюме под вакансию">
      <header className="resume-intro">
        <div>
          <p className="brand">Дополнительный сценарий</p>
          <h2>Резюме под вакансию</h2>
          <p className="subtitle">
            Выберите вакансию региона 39 и вставьте своё резюме. ИИ соберёт черновик только из ваших
            фактов, а спорные требования вынесет в «чего не хватает».
          </p>
        </div>
      </header>

      <div className="resume-grid">
        <section className="resume-card" aria-label="Данные для черновика">
          <div className="resume-card__head">
            <span className="resume-step">1</span>
            <h3>Вакансия</h3>
          </div>

          {vacancyError ? (
            <div className="alert" role="alert">
              <strong>Не удалось загрузить вакансии.</strong> {vacancyError}
              <button type="button" className="button button--ghost resume-inline-button" onClick={loadVacancies}>
                Повторить
              </button>
            </div>
          ) : null}

          <div className="resume-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={vacancyQuery}
              placeholder="Найти вакансию по названию или компании…"
              aria-label="Поиск вакансии для резюме"
              onChange={(event) => setVacancyQuery(event.target.value)}
            />
          </div>

          {vacancies === null && !vacancyError ? (
            <p className="resume-muted">Загружаем вакансии…</p>
          ) : (
            <ul className="vacancy-picker" aria-label="Список вакансий">
              {filteredVacancies.map((vacancy) => {
                const selected = vacancy.external_id === selectedId;
                return (
                  <li key={vacancy.external_id}>
                    <button
                      type="button"
                      className={`vacancy-option${selected ? " vacancy-option--active" : ""}`}
                      aria-pressed={selected}
                      onClick={() => setSelectedId(vacancy.external_id)}
                    >
                      <span className="vacancy-option__title">{vacancy.title}</span>
                      <span className="vacancy-option__meta">
                        {[vacancy.company_name, salaryText(vacancy.salary)].filter(Boolean).join(" · ")}
                      </span>
                    </button>
                  </li>
                );
              })}
              {filteredVacancies.length === 0 ? (
                <li className="resume-muted">Ничего не найдено — измените запрос.</li>
              ) : null}
            </ul>
          )}

          {selectedVacancy ? (
            <div className="selected-vacancy">
              <strong>{selectedVacancy.title}</strong>
              <span>{[selectedVacancy.company_name, selectedVacancy.region_name].filter(Boolean).join(" · ")}</span>
              <span>
                {salaryText(selectedVacancy.salary)}
                {selectedVacancy.schedule ? ` · ${selectedVacancy.schedule}` : ""}
                {selectedVacancy.employment_type ? ` · ${selectedVacancy.employment_type}` : ""}
              </span>
              {selectedVacancy.source_url ? (
                <div className="resume-link-row">
                  <a
                    className="button button--ghost button--compact"
                    href={selectedVacancy.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Открыть реальную карточку вакансии на trudvsem.ru"
                  >
                    <Icon name="file" size={14} /> Карточка на портале
                  </a>
                  <button
                    type="button"
                    className="button button--ghost button--compact"
                    title="Скопировать ссылку на карточку"
                    aria-label="Скопировать ссылку на карточку"
                    onClick={() => copyLink(selectedVacancy.source_url ?? "")}
                  >
                    <Icon name={linkCopied ? "check" : "copy"} size={14} />
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="resume-card__head">
            <span className="resume-step">2</span>
            <h3>Ваше резюме</h3>
          </div>

          <div className="segmented segmented--small" role="tablist" aria-label="Формат резюме">
            <button
              type="button"
              role="tab"
              aria-selected={inputMode === "text"}
              className={`segmented__button${inputMode === "text" ? " segmented__button--active" : ""}`}
              onClick={() => setInputMode("text")}
            >
              Текст
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={inputMode === "json"}
              className={`segmented__button${inputMode === "json" ? " segmented__button--active" : ""}`}
              onClick={() => setInputMode("json")}
            >
              JSON-файл
            </button>
          </div>

          {inputMode === "text" ? (
            <>
              <textarea
                className="resume-textarea"
                rows={9}
                value={resumeText}
                aria-label="Текст резюме"
                placeholder="Вставьте резюме: опыт, навыки, образование…"
                onChange={(event) => {
                  setResumeText(event.target.value);
                  setDraftError(null);
                }}
              />
              <div className="resume-actions">
                <button type="button" className="button button--ghost" onClick={useDemoText}>
                  <Icon name="file" size={15} /> Заполнить примером
                </button>
                <span className="resume-muted">Или загрузите JSON-файл</span>
              </div>
            </>
          ) : (
            <div className="resume-json">
              <button
                type="button"
                className="resume-upload"
                onClick={() => resumeInputRef.current?.click()}
              >
                <Icon name="upload" size={18} />
                {jsonName ? `Загружен: ${jsonName}` : "Загрузить JSON-резюме"}
              </button>
              <div className="resume-actions">
                <button type="button" className="button button--ghost" onClick={useDemoJson}>
                  <Icon name="file" size={15} /> Пример JSON
                </button>
                {resumeJson ? <span className="badge badge--ok">JSON готов</span> : null}
              </div>
              {jsonError ? (
                <div className="alert" role="alert">
                  {jsonError}
                </div>
              ) : null}
              <input
                ref={resumeInputRef}
                type="file"
                accept=".json,application/json"
                hidden
                onChange={(event) => {
                  onResumeFile(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
            </div>
          )}

          {draftError ? (
            <div className="alert" role="alert">
              {draftError}
            </div>
          ) : null}

          <button type="button" className="button resume-generate" disabled={!canGenerate} onClick={generate}>
            {loading ? (
              <>
                <span className="spinner spinner--small" aria-hidden="true" /> Составляем черновик…
              </>
            ) : (
              <>
                <Icon name="sparkles" size={15} /> Сгенерировать черновик
              </>
            )}
          </button>
          <p className="resume-privacy">
            <Icon name="user" size={13} /> Резюме не сохраняется на сервере.
          </p>
        </section>

        <section className="resume-card resume-result" ref={resultRef} aria-live="polite">
          {loading ? (
            <div className="resume-empty">
              <span className="spinner" aria-hidden="true" />
              <h3>Составляем черновик</h3>
              <p>Сопоставляем опыт и навыки из резюме с требованиями вакансии.</p>
            </div>
          ) : draft ? (
            <>
              <div className="draft-head">
                <div>
                  <h3>{draft.vacancy_title}</h3>
                  <p>{[draft.company_name, `ID ${draft.vacancy_id}`].filter(Boolean).join(" · ")}</p>
                </div>
                {draft.source_url ? (
                  <a
                    className="button button--ghost button--compact"
                    href={draft.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Icon name="file" size={14} /> На портале
                  </a>
                ) : null}
              </div>

              <div className="draft-section">
                <h4>Кратко под вакансию</h4>
                <p className="draft-summary">{draft.summary || "—"}</p>
              </div>

              {draft.highlighted_skills.length > 0 ? (
                <div className="draft-section">
                  <h4>Подходящие навыки</h4>
                  <div className="skill-chips">
                    {draft.highlighted_skills.map((skill) => (
                      <span key={skill} className="skill-chip">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="draft-section">
                <h4>Чего не хватает</h4>
                {draft.gaps.length === 0 ? (
                  <p className="resume-muted">Ключевые требования вакансии подтверждены резюме.</p>
                ) : (
                  <div className="gap-list">
                    {draft.gaps.map((gap, index) => (
                      <div className={`gap gap--${gap.status}`} key={`${gap.requirement}-${index}`}>
                        <span className="gap__status">{GAP_LABELS[gap.status] ?? gap.status}</span>
                        <div>
                          <p className="gap__req">{gap.requirement}</p>
                          {gap.advice ? <p className="gap__advice">{gap.advice}</p> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {draft.experience_highlights.length > 0 ? (
                <div className="draft-section">
                  <h4>Опыт под вакансию</h4>
                  <ul className="highlight-list">
                    {draft.experience_highlights.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {draft.education_highlights.length > 0 ? (
                <div className="draft-section">
                  <h4>Образование</h4>
                  <ul className="highlight-list">
                    {draft.education_highlights.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="draft-section">
                <h4>Черновик резюме</h4>
                <pre className="draft-text">{draft.draft_text}</pre>
                <div className="draft-actions">
                  <button type="button" className="button button--ghost" onClick={copyDraft}>
                    <Icon name={copied ? "check" : "copy"} size={15} /> {copied ? "Скопировано" : "Скопировать"}
                  </button>
                  <button type="button" className="button button--ghost" onClick={() => downloadDraft("md")}>
                    <Icon name="download" size={15} /> Скачать .md
                  </button>
                  <button type="button" className="button button--ghost" onClick={() => downloadDraft("json")}>
                    <Icon name="download" size={15} /> Скачать .json
                  </button>
                </div>
              </div>

              {draft.notes.length > 0 ? (
                <ul className="resume-notes">
                  {draft.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <div className="resume-empty">
              <Icon name="sparkles" size={30} />
              <h3>Здесь появится черновик</h3>
              <p>
                Выберите вакансию, вставьте резюме и нажмите «Сгенерировать». Опыт, навыки и образование
                берутся только из вашего резюме.
              </p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
