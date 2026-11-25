/** Темы замечаний, которые умеет сервис (для файлов тема может быть любой строкой). */
export type IssueTopic =
  | "title"
  | "duties"
  | "requirements"
  | "salary"
  | "schedule"
  | "location"
  | "employment"
  | "contradiction"
  | "other";

export interface Issue {
  topic: string;
  source_field: string;
  quote: string;
  problem: string;
  recommendation: string;
}

/** Дополнительные сведения о вакансии из сырой выгрузки «Работа в России». */
export interface VacancyDetails {
  salary: string | null;
  employment: string | null;
  schedule: string | null;
  duty: string | null;
  requirements: string | null;
  location: string | null;
  created: string | null;
}

/** Внутреннее представление вакансии (из API или из загруженного файла). */
export interface VacancyItem {
  vacancy_id: string;
  title: string;
  company_name: string | null;
  region_name: string | null;
  source_url: string | null;
  issues: Issue[];
  details: VacancyDetails | null;
}

/** Ответ GET /api/v1/vacancies/issues. */
export interface IssueVacancy {
  vacancy_id: string;
  title: string;
  company_name: string | null;
  region_name: string | null;
  source_url: string | null;
  issues: Issue[];
  issues_count: number;
}

/** Ответ GET /api/v1/reports/latest. */
export interface Report {
  generated_at: string;
  region: number;
  vacancies: Array<{
    vacancy_id: string;
    name: string;
    source_url: string | null;
    issues: Issue[];
  }>;
}

/** Результат разбора загруженного JSON-файла. */
export interface ParsedFile {
  vacancies: VacancyItem[];
  generated_at?: string;
  region?: number;
}

/** Элемент списка GET /api/v1/vacancies (для выбора вакансии под резюме). */
export interface SalaryInfo {
  from_amount: number | null;
  to_amount: number | null;
  currency: string | null;
  text: string | null;
}

export interface VacancyListItem {
  id: string;
  external_id: string;
  title: string;
  source_url: string | null;
  company_name: string | null;
  region_name: string | null;
  salary: SalaryInfo;
  schedule: string | null;
  employment_type: string | null;
  is_active: boolean;
  updated_at: string;
}

export interface VacancyPage {
  items: VacancyListItem[];
  total: number;
  limit: number;
  offset: number;
}

/** Ответ POST /api/v1/sync и POST /api/v1/analysis — задача поставлена в очередь. */
export interface SyncTask {
  run_id: string;
  status: string;
}

/** Ответ GET /api/v1/runs/{id} — общий DTO для sync / analysis / report. */
export interface RunState {
  kind: "sync" | "analysis" | "report";
  id: string;
  status: "pending" | "running" | "success" | "partial" | "failed" | string;
  started_at: string;
  finished_at: string | null;
  processed_count: number;
  failed_count: number;
  error_message: string | null;
}

export type ResumeGapStatus = "matched" | "partial" | "missing";

export interface ResumeGap {
  requirement: string;
  status: ResumeGapStatus;
  advice: string;
}

/** Ответ POST /api/v1/resume/draft. */
export interface ResumeDraft {
  vacancy_id: string;
  vacancy_title: string;
  company_name: string | null;
  source_url: string | null;
  summary: string;
  highlighted_skills: string[];
  experience_highlights: string[];
  education_highlights: string[];
  gaps: ResumeGap[];
  draft_text: string;
  notes: string[];
}
