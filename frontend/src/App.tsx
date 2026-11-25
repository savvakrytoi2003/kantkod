import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { analyzePayload, fetchIssueVacancies, fetchReport } from "./api";
import { Icon } from "./icons";
import ResumePanel from "./ResumePanel";
import SyncHeaderButton from "./SyncHeaderButton";
import { parseVacanciesJson } from "./parse";
import type { Issue, IssueVacancy, ParsedFile, Report, VacancyDetails, VacancyItem } from "./types";

type Mode = "api" | "file" | "resume";
type SortKey = "issues" | "title" | "company";
type Theme = "light" | "dark";

interface PipelineInfo {
  aiUsed: boolean;
  aiFailed: number;
  status: string;
}

interface LoadedFile {
  name: string;
  size: number;
  format: string;
  data: ParsedFile;
  /** Сырой JSON для повторного прогона через пайплайн (только для формата источника). */
  sourcePayload: unknown | null;
  pipeline: PipelineInfo | null;
}

const TOPIC_LABELS: Record<string, string> = {
  title: "Должность",
  duties: "Обязанности",
  requirements: "Требования",
  salary: "Оплата",
  schedule: "График",
  location: "Место работы",
  employment: "Занятость",
  contradiction: "Противоречие",
  other: "Прочее",
};

const TOPIC_ORDER: string[] = [
  "contradiction",
  "salary",
  "schedule",
  "employment",
  "location",
  "duties",
  "requirements",
  "title",
  "other",
];

const TOPIC_CLASS: Record<string, string> = {
  contradiction: "t-rose",
  salary: "t-amber",
  schedule: "t-blue",
  employment: "t-violet",
  location: "t-teal",
  duties: "t-cyan",
  requirements: "t-pink",
  title: "t-slate",
  other: "t-gray",
};

const FORMAT_LABELS: Record<string, string> = {
  report: "отчёт KantKod",
  trudvsem: "выгрузка «Работа в России»",
  list: "список вакансий",
};

function topicLabel(topic: string): string {
  return TOPIC_LABELS[topic] ?? topic;
}

function topicClass(topic: string): string {
  return TOPIC_CLASS[topic] ?? "t-gray";
}

function formatDate(value: string | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  return date.toLocaleString(
    "ru-RU",
    dateOnly ? { dateStyle: "long" } : { dateStyle: "long", timeStyle: "short" },
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} Б`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} КБ`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function matches(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.trim().toLowerCase());
}

function vacancyText(vacancy: VacancyItem): string {
  return [
    vacancy.title,
    vacancy.company_name ?? "",
    vacancy.region_name ?? "",
    ...vacancy.issues.flatMap((issue) => [issue.quote, issue.problem, issue.recommendation]),
  ].join(" ");
}

function readInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem("kantkod:theme");
    if (saved === "dark" || saved === "light") {
      return saved;
    }
  } catch {
    // localStorage недоступен — используем системную тему
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/* ---------------------------------- Иконки ---------------------------------- */

/* ------------------------------ Мелкие блоки UI ----------------------------- */

function IssueCard({
  issue,
  copyKey,
  copied,
  onCopy,
}: {
  issue: Issue;
  copyKey: string;
  copied: boolean;
  onCopy: (issue: Issue, key: string) => void;
}) {
  return (
    <li className={`issue ${topicClass(issue.topic)}`}>
      <div className="issue__head">
        <span className="topic">{topicLabel(issue.topic)}</span>
        {issue.source_field.trim() ? <code className="issue__field">{issue.source_field}</code> : null}
        <button
          type="button"
          className="issue__copy"
          title="Скопировать замечание"
          aria-label="Скопировать замечание"
          onClick={() => onCopy(issue, copyKey)}
        >
          <Icon name={copied ? "check" : "copy"} size={15} />
        </button>
      </div>
      {issue.quote.trim() ? <blockquote className="issue__quote">«{issue.quote}»</blockquote> : null}
      {issue.problem.trim() ? <p className="issue__problem">{issue.problem}</p> : null}
      {issue.recommendation.trim() ? (
        <div className="issue__recommendation">
          <span className="issue__rec-label">Как исправить</span>
          <p>{issue.recommendation}</p>
        </div>
      ) : null}
    </li>
  );
}

const DETAIL_ROWS: Array<[string, keyof VacancyDetails]> = [
  ["Оплата", "salary"],
  ["Занятость", "employment"],
  ["График", "schedule"],
  ["Место работы", "location"],
  ["Обязанности", "duty"],
  ["Требования", "requirements"],
  ["Дата публикации", "created"],
];

function VacancyCard({
  vacancy,
  issues,
  cardKey,
  open,
  copiedKey,
  onToggle,
  onCopy,
}: {
  vacancy: VacancyItem;
  issues: Issue[];
  cardKey: string;
  open: boolean;
  copiedKey: string | null;
  onToggle: (key: string) => void;
  onCopy: (issue: Issue, key: string) => void;
}) {
  const uniqTopics = useMemo(() => [...new Set(vacancy.issues.map((issue) => issue.topic))], [vacancy]);
  const details = vacancy.details;
  const detailRows = useMemo(() => {
    if (!details) {
      return [];
    }
    return DETAIL_ROWS.map(([label, key]) => {
      const value = details[key];
      if (!value) {
        return null;
      }
      return { label, value: key === "created" ? formatDate(value) : value };
    }).filter((row): row is { label: string; value: string } => row !== null);
  }, [details]);

  return (
    <li className="vacancy">
      <div className="vacancy__head">
        <button
          type="button"
          className="vacancy__toggle"
          aria-expanded={open}
          onClick={() => onToggle(cardKey)}
        >
          <Icon name="chevron" size={20} />
          <div className="vacancy__titles">
            <h2>{vacancy.title || "Без названия"}</h2>
            <p className="vacancy__meta">
              <span className="vacancy__company">
                {vacancy.company_name || "Работодатель не указан"}
              </span>
              {vacancy.region_name ? (
                <>
                  <span className="dot-sep">·</span>
                  <span>{vacancy.region_name}</span>
                </>
              ) : null}
            </p>
          </div>
        </button>
        <div className="vacancy__aside">
          <div className="vacancy__dots" aria-hidden="true">
            {uniqTopics.map((topic) => (
              <span key={topic} className={`topic-dot ${topicClass(topic)}`} title={topicLabel(topic)} />
            ))}
          </div>
          {vacancy.issues.length > 0 ? (
            <span className="counter">
              {vacancy.issues.length} <span className="counter__label">замеч.</span>
            </span>
          ) : (
            <span className="badge badge--ok">
              <Icon name="check" size={13} /> без замечаний
            </span>
          )}
          {vacancy.source_url ? (
            <a className="link" href={vacancy.source_url} target="_blank" rel="noreferrer noopener">
              На портале <span aria-hidden="true">↗</span>
            </a>
          ) : null}
        </div>
      </div>

      {open && issues.length > 0 ? (
        <ul className="issues">
          {issues.map((issue, index) => (
            <IssueCard
              key={`${cardKey}-${index}`}
              issue={issue}
              copyKey={`${cardKey}-${index}`}
              copied={copiedKey === `${cardKey}-${index}`}
              onCopy={onCopy}
            />
          ))}
        </ul>
      ) : null}

      {open && issues.length === 0 && detailRows.length > 0 ? (
        <dl className="details">
          {detailRows.map((row) => (
            <div key={row.label} className="details__row">
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {open && issues.length === 0 && detailRows.length === 0 ? (
        <p className="vacancy__clean">Замечаний нет — описание вакансии прозрачное.</p>
      ) : null}
    </li>
  );
}

/* ---------------------------------- Приложение ------------------------------ */

export default function App() {
  const [mode, setMode] = useState<Mode>("api");
  const [apiVacancies, setApiVacancies] = useState<IssueVacancy[] | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [file, setFile] = useState<LoadedFile | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [query, setQuery] = useState("");
  const [topics, setTopics] = useState<Set<string>>(() => new Set());
  const [sort, setSort] = useState<SortKey>("issues");
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const [theme, setTheme] = useState<Theme>(readInitialTheme);
  const [toast, setToast] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toastTimer = useRef<number | null>(null);
  const copyTimer = useRef<number | null>(null);

  const notify = useCallback((text: string) => {
    setToast(text);
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current);
    }
    toastTimer.current = window.setTimeout(() => setToast(null), 2400);
  }, []);

  const load = useCallback(() => {
    let alive = true;
    setApiError(null);
    setApiVacancies(null);
    Promise.all([fetchIssueVacancies(), fetchReport()])
      .then(([items, latest]) => {
        if (!alive) {
          return;
        }
        setApiVacancies(items);
        setReport(latest);
      })
      .catch((reason: unknown) => {
        if (alive) {
          setApiError(reason instanceof Error ? reason.message : String(reason));
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => load(), [load]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("kantkod:theme", theme);
    } catch {
      // нет доступа к localStorage — не критично
    }
  }, [theme]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT");
      if (event.key === "/" && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const items: VacancyItem[] = useMemo(() => {
    if (mode === "file" && file) {
      return file.data.vacancies;
    }
    return (apiVacancies ?? []).map((vacancy) => ({
      vacancy_id: vacancy.vacancy_id,
      title: vacancy.title,
      company_name: vacancy.company_name,
      region_name: vacancy.region_name,
      source_url: vacancy.source_url,
      issues: vacancy.issues,
      details: null,
    }));
  }, [mode, file, apiVacancies]);

  const topicList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const vacancy of items) {
      for (const issue of vacancy.issues) {
        counts.set(issue.topic, (counts.get(issue.topic) ?? 0) + 1);
      }
    }
    const known = TOPIC_ORDER.filter((topic) => counts.has(topic));
    const unknown = [...counts.keys()]
      .filter((topic) => !TOPIC_ORDER.includes(topic))
      .sort((a, b) => a.localeCompare(b, "ru"));
    return [...known, ...unknown].map((topic) => ({ topic, count: counts.get(topic) ?? 0 }));
  }, [items]);

  const filtered = useMemo(() => {
    const needle = query.trim();
    const list = [...items];
    if (sort === "title") {
      list.sort(
        (a, b) => a.title.localeCompare(b.title, "ru") || a.vacancy_id.localeCompare(b.vacancy_id),
      );
    } else if (sort === "company") {
      list.sort(
        (a, b) =>
          (a.company_name ?? "").localeCompare(b.company_name ?? "", "ru") ||
          a.title.localeCompare(b.title, "ru"),
      );
    } else {
      list.sort(
        (a, b) => b.issues.length - a.issues.length || a.title.localeCompare(b.title, "ru"),
      );
    }
    const seen = new Map<string, number>();
    return list
      .map((vacancy) => {
        const occurrence = (seen.get(vacancy.vacancy_id) ?? 0) + 1;
        seen.set(vacancy.vacancy_id, occurrence);
        const issues = topics.size
          ? vacancy.issues.filter((issue) => topics.has(issue.topic))
          : vacancy.issues;
        return { vacancy, issues, cardKey: `${vacancy.vacancy_id}#${occurrence}` };
      })
      .filter((item) => topics.size === 0 || item.issues.length > 0)
      .filter(({ vacancy }) => (needle ? matches(vacancyText(vacancy), needle) : true));
  }, [items, query, topics, sort]);

  const totalCount = useMemo(() => {
    if (mode === "file" && file) {
      return file.data.vacancies.length;
    }
    return report?.vacancies.length ?? apiVacancies?.length ?? 0;
  }, [mode, file, report, apiVacancies]);

  const withIssues = items.filter((vacancy) => vacancy.issues.length > 0).length;
  const totalIssues = items.reduce((sum, vacancy) => sum + vacancy.issues.length, 0);
  const cleanCount = Math.max(totalCount - withIssues, 0);
  const filteredIssues = filtered.reduce((sum, item) => sum + item.issues.length, 0);
  const hasData = mode === "api" ? apiVacancies !== null : mode === "file" ? file !== null : false;
  const allCollapsed =
    filtered.length > 0 && filtered.every((item) => collapsed.has(item.cardKey));

  const toggleTopic = (topic: string) => {
    setTopics((current) => {
      const next = new Set(current);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
      }
      return next;
    });
  };

  const toggleCard = (key: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const collapseAll = () => {
    setCollapsed(
      allCollapsed ? new Set() : new Set(filtered.map((item) => item.cardKey)),
    );
  };

  const copyIssue = useCallback(
    async (issue: Issue, key: string) => {
      const text = [
        issue.problem ? `Проблема: ${issue.problem}` : "",
        issue.recommendation ? `Рекомендация: ${issue.recommendation}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      try {
        await navigator.clipboard.writeText(text);
        setCopiedKey(key);
        if (copyTimer.current !== null) {
          window.clearTimeout(copyTimer.current);
        }
        copyTimer.current = window.setTimeout(() => setCopiedKey(null), 1600);
      } catch {
        notify("Не удалось скопировать текст");
      }
    },
    [notify],
  );

  const runPipeline = useCallback(
    async (loaded: LoadedFile) => {
      if (loaded.sourcePayload === null) {
        return;
      }
      setAnalyzing(true);
      setAnalysisError(null);
      try {
        const result = await analyzePayload(loaded.sourcePayload);
        const localById = new Map(loaded.data.vacancies.map((vacancy) => [vacancy.vacancy_id, vacancy]));
        const analysed: VacancyItem[] = result.report.vacancies.map((vacancy, index) => {
          const local = localById.get(vacancy.vacancy_id);
          return {
            vacancy_id: vacancy.vacancy_id || `vacancy-${index + 1}`,
            title: vacancy.name.trim() || local?.title || vacancy.vacancy_id || "Без названия",
            company_name: local?.company_name ?? null,
            region_name: local?.region_name ?? null,
            source_url: vacancy.source_url ?? local?.source_url ?? null,
            issues: vacancy.issues,
            details: local?.details ?? null,
          };
        });
        setFile((current) =>
          current !== null && current.name === loaded.name && current.size === loaded.size
            ? {
                ...current,
                data: {
                  ...current.data,
                  vacancies: analysed,
                  generated_at: result.report.generated_at,
                  region: result.report.region,
                },
                pipeline: {
                  aiUsed: result.ai_used,
                  aiFailed: result.ai_failed,
                  status: result.status,
                },
              }
            : current,
        );
        setQuery("");
        setTopics(new Set());
        const issuesCount = analysed.reduce((sum, vacancy) => sum + vacancy.issues.length, 0);
        notify(`Анализ готов: ${issuesCount} замечаний`);
      } catch (reason) {
        setAnalysisError(reason instanceof Error ? reason.message : String(reason));
      } finally {
        setAnalyzing(false);
      }
    },
    [notify],
  );

  const applyFile = (chosen: File) => {
    if (!chosen.name.toLowerCase().endsWith(".json")) {
      setFileError("Поддерживаются только файлы .json.");
      return;
    }
    if (chosen.size > 10 * 1024 * 1024) {
      setFileError("Файл слишком большой (больше 10 МБ).");
      return;
    }
    chosen
      .text()
      .then((text) => {
        const result = parseVacanciesJson(text);
        if (!result.ok) {
          setFileError(result.error);
          return;
        }
        const loaded: LoadedFile = {
          name: chosen.name,
          size: chosen.size,
          format: result.format,
          data: result.data,
          sourcePayload: result.sourcePayload ?? null,
          pipeline: null,
        };
        setFile(loaded);
        setFileError(null);
        setAnalysisError(null);
        setQuery("");
        setTopics(new Set());
        setCollapsed(new Set());
        if (loaded.sourcePayload !== null) {
          void runPipeline(loaded);
        } else {
          notify(`Загружено вакансий: ${result.data.vacancies.length}`);
        }
      })
      .catch(() => setFileError("Не удалось прочитать файл."));
  };

  const onFiles = (list: FileList | null) => {
    const chosen = list?.[0];
    if (chosen) {
      applyFile(chosen);
    }
  };

  const exportJson = () => {
    const payload = {
      generated_at: (mode === "file" && file?.data.generated_at) || report?.generated_at || new Date().toISOString(),
      region: (mode === "file" ? file?.data.region : report?.region) ?? 39,
      vacancies: filtered.map(({ vacancy, issues }) => ({
        vacancy_id: vacancy.vacancy_id,
        name: vacancy.title,
        company_name: vacancy.company_name,
        region_name: vacancy.region_name,
        source_url: vacancy.source_url,
        issues,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "kantkod-issues.json";
    anchor.click();
    URL.revokeObjectURL(url);
    notify("Файл сохранён: kantkod-issues.json");
  };

  const metaLine =
    mode === "api"
      ? `Регион ${report?.region ?? 39} · отчёт от ${formatDate(report?.generated_at)}`
      : mode === "file"
        ? file
          ? `Файл «${file.name}» · ${formatSize(file.size)} · ${FORMAT_LABELS[file.format] ?? "JSON"} · вакансий: ${file.data.vacancies.length}`
          : "Файл ещё не загружен"
        : "Дополнительный сценарий · регион 39";

  return (
    <div className="page">
      <header className="hero">
        <div className="hero__top">
          <div className="hero__brand">
            <span className="logo" aria-hidden="true">
              K
            </span>
            <div>
              <p className="brand">KantKod</p>
              <h1>Прозрачная вакансия</h1>
              <p className="subtitle">
                Вакансии Калининградской области с замечаниями к описанию условий работы
              </p>
            </div>
          </div>
          <div className="hero__actions">
            <SyncHeaderButton
              active={mode === "api"}
              onLoaded={() => {
                load();
                notify("Загрузка завершена");
              }}
              onBlocked={notify}
            />
            <button
              type="button"
              className="icon-button"
              title={theme === "light" ? "Тёмная тема" : "Светлая тема"}
              aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
              onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
            >
              <Icon name={theme === "light" ? "moon" : "sun"} />
            </button>
          </div>
        </div>

        <dl className="stats">
          <div className="stat">
            <dt>Вакансий с замечаниями</dt>
            <dd>{hasData ? withIssues : "—"}</dd>
          </div>
          <div className="stat">
            <dt>Замечаний</dt>
            <dd>{hasData ? totalIssues : "—"}</dd>
          </div>
          <div className="stat">
            <dt>Без замечаний</dt>
            <dd>{hasData ? cleanCount : "—"}</dd>
          </div>
          <div className="stat">
            <dt>{mode === "file" ? "Всего в файле" : "Всего в отчёте"}</dt>
            <dd>{hasData ? totalCount : "—"}</dd>
          </div>
        </dl>
      </header>

      <section className="sources-row">
        <div className="segmented" role="tablist" aria-label="Режим работы">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "api"}
            className={`segmented__button${mode === "api" ? " segmented__button--active" : ""}`}
            onClick={() => setMode("api")}
          >
            <Icon name="server" size={15} /> Данные сервиса
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "file"}
            className={`segmented__button${mode === "file" ? " segmented__button--active" : ""}`}
            onClick={() => setMode("file")}
          >
            <Icon name="file" size={15} /> Свой JSON-файл
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "resume"}
            className={`segmented__button${mode === "resume" ? " segmented__button--active" : ""}`}
            onClick={() => setMode("resume")}
          >
            <Icon name="user" size={15} /> Резюме под вакансию
          </button>
        </div>
        <p className="meta">{metaLine}</p>
      </section>

      <ResumePanel active={mode === "resume"} />

      {mode === "file" && !file ? (
        <>
          {fileError ? (
            <div className="alert" role="alert">
              <strong>Файл не загружен.</strong> {fileError}
            </div>
          ) : null}
          <section
            className={`dropzone${dragActive ? " dropzone--active" : ""}`}
            role="button"
            tabIndex={0}
            aria-label="Загрузить JSON-файл с вакансиями"
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              onFiles(event.dataTransfer.files);
            }}
          >
            <span className="dropzone__icon">
              <Icon name="upload" size={26} />
            </span>
            <p className="dropzone__title">Перетащите JSON-файл сюда</p>
            <p className="dropzone__hint">или нажмите, чтобы выбрать файл · до 10 МБ</p>
            <p className="dropzone__formats">
              Выгрузка «Работа в России» (<code>results.vacancies</code>) прогоняется через
              пайплайн правил и ИИ-анализа. Готовый отчёт KantKod (<code>vacancies</code> +{" "}
              <code>issues</code>) откроется как есть.
            </p>
          </section>
        </>
      ) : null}

      {mode === "file" && file ? (
        <aside className="filebar">
          <span className="filebar__icon">
            <Icon name="file" size={20} />
          </span>
          <div className="filebar__info">
            <span className="filebar__name">
              {file.name}
              {analyzing ? (
                <span className="pill pill--busy">
                  <span className="pill__dot" /> анализ…
                </span>
              ) : file.pipeline ? (
                <span
                  className={`pill ${file.pipeline.aiFailed > 0 ? "pill--warn" : "pill--ok"}`}
                  title={
                    file.pipeline.aiFailed > 0
                      ? `ИИ не смог обработать вакансий: ${file.pipeline.aiFailed}`
                      : "Файл прогнан через пайплайн"
                  }
                >
                  {file.pipeline.aiUsed ? "правила + ИИ" : "только правила"}
                </span>
              ) : null}
            </span>
            <span className="filebar__meta">
              {formatSize(file.size)} · {FORMAT_LABELS[file.format] ?? "JSON"} · вакансий:{" "}
              {file.data.vacancies.length}
              {file.pipeline ? ` · замечаний: ${totalIssues}` : ""}
            </span>
          </div>
          <div className="filebar__actions">
            {file.sourcePayload !== null && !analyzing && (file.pipeline === null || analysisError) ? (
              <button type="button" className="button" onClick={() => void runPipeline(file)}>
                Запустить анализ
              </button>
            ) : null}
            <button type="button" className="button button--ghost" onClick={() => fileInputRef.current?.click()}>
              Заменить
            </button>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => {
                setFile(null);
                setFileError(null);
                setAnalysisError(null);
              }}
            >
              Убрать
            </button>
          </div>
        </aside>
      ) : null}

      {mode === "file" && analysisError ? (
        <div className="alert alert--actions" role="alert">
          <span>
            <strong>Не удалось прогнать файл через пайплайн.</strong> {analysisError}
          </span>
          {file && file.sourcePayload !== null ? (
            <button type="button" className="button" onClick={() => void runPipeline(file)}>
              Повторить анализ
            </button>
          ) : null}
        </div>
      ) : null}

      {mode === "api" && apiError ? (
        <section className="state state--error">
          <span className="state__icon">
            <Icon name="x" size={22} />
          </span>
          <h2>Не удалось загрузить данные</h2>
          <p>{apiError}</p>
          <p className="hint">
            Проверьте, что бэкенд запущен на <code>127.0.0.1:8000</code> и отчёт уже сформирован.
            Кнопка «Загрузить вакансии» в шапке подтянет данные с портала. Или откройте вкладку
            «Свой JSON-файл» — загруженная выгрузка прогоняется через тот же пайплайн (правила и
            ИИ).
          </p>
          <button type="button" className="button" onClick={load}>
            Повторить
          </button>
        </section>
      ) : null}

      {mode === "api" && !apiError && apiVacancies === null ? (
        <div className="skeleton" aria-busy="true" aria-label="Загрузка">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="skeleton__card">
              <div className="sk sk--title" />
              <div className="sk sk--meta" />
              <div className="sk sk--line" />
              <div className="sk sk--line sk--short" />
            </div>
          ))}
        </div>
      ) : null}

      {mode === "file" && analyzing ? (
        <section className="state state--busy" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <h2>Анализируем вакансии</h2>
          <p>
            Прогоняем файл через пайплайн: программные правила и ИИ-анализ неоднозначных
            формулировок. Обычно это занимает несколько секунд.
          </p>
        </section>
      ) : null}

      {hasData && !(mode === "file" && analyzing) ? (
        <>
          <section className="toolbar" aria-label="Поиск и фильтры">
            <div className="toolbar__row">
              <div className="search">
                <span className="search__icon">
                  <Icon name="search" size={17} />
                </span>
                <input
                  ref={searchRef}
                  className="search__input"
                  type="search"
                  value={query}
                  placeholder="Поиск по названию, компании, цитате или проблеме…"
                  onChange={(event) => setQuery(event.target.value)}
                />
                {query ? (
                  <button
                    type="button"
                    className="search__clear"
                    aria-label="Очистить поиск"
                    onClick={() => setQuery("")}
                  >
                    <Icon name="x" size={15} />
                  </button>
                ) : null}
              </div>
              <label className="sort">
                <span className="sort__label">Сортировка</span>
                <select
                  className="sort__select"
                  value={sort}
                  onChange={(event) => setSort(event.target.value as SortKey)}
                >
                  <option value="issues">По числу замечаний</option>
                  <option value="title">По названию</option>
                  <option value="company">По работодателю</option>
                </select>
              </label>
            </div>
            <div className="toolbar__row toolbar__row--bottom">
              <div className="chips">
                {topicList.map(({ topic, count }) => {
                  const active = topics.has(topic);
                  return (
                    <button
                      key={topic}
                      type="button"
                      className={`chip ${topicClass(topic)}${active ? " chip--active" : ""}`}
                      aria-pressed={active}
                      onClick={() => toggleTopic(topic)}
                    >
                      <span className="chip__dot" aria-hidden="true" />
                      <span className="chip__label">{topicLabel(topic)}</span>
                      <span className="chip__count">{count}</span>
                    </button>
                  );
                })}
                {topics.size > 0 ? (
                  <button type="button" className="chip chip--reset" onClick={() => setTopics(new Set())}>
                    <Icon name="x" size={13} /> Сбросить
                  </button>
                ) : null}
              </div>
              <div className="toolbar__actions">
                <button type="button" className="button button--ghost" onClick={collapseAll}>
                  {allCollapsed ? "Развернуть все" : "Свернуть все"}
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={exportJson}
                  disabled={filtered.length === 0}
                >
                  <Icon name="download" size={15} /> Скачать JSON
                </button>
              </div>
            </div>
          </section>

          {filtered.length === 0 ? (
            <section className="state">
              <span className="state__icon">
                <Icon name="inbox" size={24} />
              </span>
              <h2>Ничего не найдено</h2>
              <p>
                {items.length === 0
                  ? mode === "file"
                    ? "В загруженном файле нет вакансий."
                    : "В последнем отчёте нет вакансий с замечаниями."
                  : "Под текущий поиск и фильтры не подошла ни одна вакансия."}
              </p>
              {items.length > 0 ? (
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    setQuery("");
                    setTopics(new Set());
                  }}
                >
                  Сбросить фильтры
                </button>
              ) : null}
            </section>
          ) : null}

          {filtered.length > 0 ? (
            <>
              <p className="results">
                Показано вакансий: <strong>{filtered.length}</strong> из {totalCount} · замечаний:{" "}
                <strong>{filteredIssues}</strong>
                {query.trim() || topics.size ? (
                  <span className="results__hint"> (нажмите «Сбросить», чтобы увидеть всё)</span>
                ) : null}
              </p>
              <ul className="vacancies">
                {filtered.map(({ vacancy, issues, cardKey }) => (
                  <VacancyCard
                    key={cardKey}
                    vacancy={vacancy}
                    issues={issues}
                    cardKey={cardKey}
                    open={!collapsed.has(cardKey)}
                    copiedKey={copiedKey}
                    onToggle={toggleCard}
                    onCopy={copyIssue}
                  />
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}

      <footer className="footer">
        <p>
          KantKod · «Прозрачная вакансия» · данные портала «Работа в России», Калининградская
          область. Замечания сформированы правилами сервиса и ИИ-моделью.
        </p>
      </footer>

      <input
        ref={fileInputRef}
        type="file"
        accept=".json,application/json"
        hidden
        onChange={(event) => {
          onFiles(event.target.files);
          event.target.value = "";
        }}
      />

      {toast ? (
        <div className="toast" role="status">
          <Icon name="check" size={16} /> {toast}
        </div>
      ) : null}
    </div>
  );
}
