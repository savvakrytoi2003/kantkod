import type { IssueVacancy, Report, ResumeDraft, RunState, SyncTask, VacancyPage } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Запрос ${url} вернул ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchIssueVacancies(): Promise<IssueVacancy[]> {
  return getJson<IssueVacancy[]>("/api/v1/vacancies/issues?limit=500");
}

export async function fetchReport(): Promise<Report | null> {
  try {
    return await getJson<Report>("/api/v1/reports/latest");
  } catch {
    return null;
  }
}

export interface PayloadAnalysis {
  status: string;
  report: Report;
  ai_used: boolean;
  ai_failed: number;
}

function errorDetail(value: unknown): string | null {
  if (!value || typeof value !== "object" || !("detail" in value)) {
    return null;
  }
  const detail = (value as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return typeof item === "string" ? item : JSON.stringify(item);
      })
      .join("; ");
  }
  return null;
}

async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let detail: string | null = null;
    try {
      detail = errorDetail(await response.json());
    } catch {
      // тело ответа не JSON
    }
    throw new Error(detail ?? `Запрос вернул ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Прогоняет загруженный JSON через бэкенд-пайплайн: правила + ИИ. */
export function analyzePayload(payload: unknown): Promise<PayloadAnalysis> {
  return postJson<PayloadAnalysis>("/api/v1/validation/analyze", payload);
}

/** Список вакансий для выбора в сценарии «Резюме под вакансию». */
export function fetchVacancyList(limit = 200): Promise<VacancyPage> {
  return getJson<VacancyPage>(`/api/v1/vacancies?limit=${limit}`);
}

/** Черновик резюме под выбранную вакансию (резюме не сохраняется). */
export function generateResumeDraft(vacancyId: string, resume: unknown): Promise<ResumeDraft> {
  return postJson<ResumeDraft>("/api/v1/resume/draft", {
    vacancy_id: vacancyId,
    resume,
  });
}

/* --------------------------- Загрузка из источника --------------------------- */

/** Ставит синхронизацию с порталом в очередь (POST /api/v1/sync). */
export function startSync(maxVacancies: number): Promise<SyncTask> {
  return postJson<SyncTask>("/api/v1/sync", { max_vacancies: maxVacancies });
}

/** Ставит анализ сохранённых вакансий в очередь (POST /api/v1/analysis). */
export function startAnalysis(limit: number, force = false): Promise<SyncTask> {
  return postJson<SyncTask>("/api/v1/analysis", { limit, force });
}

/** Пересобирает latest-отчёт (POST /api/v1/reports/generate). */
export function generateReport(): Promise<Report> {
  return postJson<Report>("/api/v1/reports/generate", {});
}

/** Статус фоновой задачи (GET /api/v1/runs/{id}). */
export function fetchRun(runId: string): Promise<RunState> {
  return getJson<RunState>(`/api/v1/runs/${runId}`);
}
