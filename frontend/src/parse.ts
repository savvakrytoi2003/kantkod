import type { Issue, ParsedFile, VacancyDetails, VacancyItem } from "./types";

type JsonRecord = Record<string, unknown>;

export type FileParseResult =
  | { ok: true; data: ParsedFile; format: "report" | "trudvsem" | "list"; sourcePayload?: unknown }
  | { ok: false; error: string };

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}

function formatSalary(
  min: number | undefined,
  max: number | undefined,
  currency: string,
): string | null {
  if (min === undefined && max === undefined) {
    return null;
  }
  const suffix = currency.trim() ? ` ${currency.trim()}` : "";
  if (min !== undefined && max !== undefined && min !== max) {
    return `${min.toLocaleString("ru-RU")} – ${max.toLocaleString("ru-RU")}${suffix}`;
  }
  const single = (min ?? max) as number;
  if (single <= 0) {
    return null;
  }
  return `${single.toLocaleString("ru-RU")}${suffix}`;
}

function parseIssue(value: unknown): Issue | null {
  if (!isRecord(value)) {
    return null;
  }
  const problem = asString(value.problem).trim();
  const recommendation = asString(value.recommendation).trim();
  if (!problem && !recommendation) {
    return null;
  }
  return {
    topic: asString(value.topic ?? value.category ?? value.type).trim() || "other",
    source_field: asString(value.source_field ?? value.field),
    quote: asString(value.quote),
    problem,
    recommendation,
  };
}

/** Вакансия в формате отчёта: { vacancy_id, name, source_url, issues: [...] }. */
function parseReportVacancy(record: JsonRecord, index: number): VacancyItem {
  const issuesRaw = Array.isArray(record.issues) ? record.issues : [];
  const issues = issuesRaw
    .map((item) => parseIssue(item))
    .filter((item): item is Issue => item !== null);
  return {
    vacancy_id:
      asString(record.vacancy_id ?? record.id ?? record.external_id).trim() ||
      `vacancy-${index + 1}`,
    title:
      asString(record.name ?? record.title).trim() ||
      asString(record.vacancy_id ?? record.id ?? record.external_id).trim() ||
      "Без названия",
    company_name: nullableString(record.company_name),
    region_name: nullableString(record.region_name),
    source_url: nullableString(record.source_url ?? record.url),
    issues,
    details: null,
  };
}

/** Формат отчёта KantKod: { generated_at, region, vacancies: [...] }. */
function parseReportJson(raw: unknown): ParsedFile | null {
  if (!isRecord(raw) || !Array.isArray(raw.vacancies)) {
    return null;
  }
  return {
    generated_at: typeof raw.generated_at === "string" ? raw.generated_at : undefined,
    region: typeof raw.region === "number" ? raw.region : undefined,
    vacancies: raw.vacancies
      .map((item, index) => (isRecord(item) ? parseReportVacancy(item, index) : null))
      .filter((item): item is VacancyItem => item !== null),
  };
}

/** Просто массив вакансий: [ { vacancy_id, issues... }, ... ] или сырые вакансии источника. */
function parseVacancyList(raw: unknown): ParsedFile | null {
  if (!Array.isArray(raw)) {
    return null;
  }
  return {
    vacancies: raw
      .map((item, index) => (isRecord(item) ? parseReportVacancy(item, index) : null))
      .filter((item): item is VacancyItem => item !== null),
  };
}

function isSourceVacancy(value: unknown): boolean {
  if (!isRecord(value)) {
    return false;
  }
  const vacancy = isRecord(value.vacancy) ? value.vacancy : value;
  return (
    typeof vacancy.id === "string" ||
    typeof vacancy["job-name"] === "string" ||
    typeof vacancy.job_name === "string"
  );
}

/** Оборачивает массив сырых вакансий в формат источника для пайплайна. */
function buildSourcePayload(items: unknown[]): unknown | null {
  if (!items.some(isSourceVacancy)) {
    return null;
  }
  return {
    results: {
      vacancies: items.map((item) =>
        isRecord(item) && isRecord(item.vacancy) ? item : { vacancy: item },
      ),
    },
  };
}

/** Выгрузка портала «Работа в России»: { results: { vacancies: [ { vacancy: {...} } ] } }. */
function parseTrudvsemJson(raw: unknown): ParsedFile | null {
  const results = isRecord(raw) && isRecord(raw.results) ? raw.results : raw;
  if (!isRecord(results) || !Array.isArray(results.vacancies)) {
    return null;
  }
  const vacancies = results.vacancies
    .map((item, index) => parseTrudvsemVacancy(item, index))
    .filter((item): item is VacancyItem => item !== null);
  return { vacancies };
}

function parseTrudvsemVacancy(raw: unknown, index: number): VacancyItem | null {
  if (!isRecord(raw)) {
    return null;
  }
  const vacancy = isRecord(raw.vacancy) ? raw.vacancy : raw;
  const company = isRecord(vacancy.company) ? vacancy.company : null;
  const region = isRecord(vacancy.region) ? vacancy.region : null;

  let location = "";
  if (isRecord(vacancy.addresses) && Array.isArray(vacancy.addresses.address)) {
    location = vacancy.addresses.address
      .map((item) => (isRecord(item) ? asString(item.location) : ""))
      .filter(Boolean)
      .join(", ");
  }

  const requirementsObject = isRecord(vacancy.requirement) ? vacancy.requirement : null;
  const details: VacancyDetails = {
    salary: formatSalary(
      numberValue(vacancy.salary_min),
      numberValue(vacancy.salary_max),
      asString(vacancy.currency),
    ),
    employment: nullableString(vacancy.employment),
    schedule: nullableString(vacancy.schedule),
    duty: nullableString(vacancy.duty),
    requirements: nullableString(
      vacancy.requirements ?? (requirementsObject ? requirementsObject.qualification : null),
    ),
    location: location.trim() || null,
    created: nullableString(vacancy["creation-date"] ?? vacancy.creation_date),
  };

  return {
    vacancy_id:
      asString(vacancy.id ?? vacancy["external-id"] ?? vacancy.external_id).trim() ||
      `vacancy-${index + 1}`,
    title: asString(vacancy["job-name"] ?? vacancy.job_name ?? vacancy.name).trim() || "Без названия",
    company_name: company ? nullableString(company.name) : null,
    region_name: region ? nullableString(region.name) : null,
    source_url: nullableString(vacancy["vac_url"] ?? vacancy.vac_url ?? vacancy.source_url),
    issues: [],
    details,
  };
}

/** Точка входа: разбирает любой поддерживаемый формат. */
export function parseVacanciesJson(text: string): FileParseResult {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (error) {
    const detail = error instanceof Error && error.message ? ` (${error.message})` : "";
    return { ok: false, error: `Файл не является корректным JSON${detail}.` };
  }

  if (raw === null || raw === undefined) {
    return { ok: false, error: "Файл пуст." };
  }

  const report = parseReportJson(raw);
  if (report && report.vacancies.length > 0) {
    return { ok: true, data: report, format: "report" };
  }

  const list = parseVacancyList(raw);
  if (list && list.vacancies.length > 0) {
    const sourcePayload = buildSourcePayload(raw as unknown[]);
    return {
      ok: true,
      data: list,
      format: "list",
      ...(sourcePayload === null ? {} : { sourcePayload }),
    };
  }

  const trudvsem = parseTrudvsemJson(raw);
  if (trudvsem && trudvsem.vacancies.length > 0) {
    return { ok: true, data: trudvsem, format: "trudvsem", sourcePayload: raw };
  }

  // Пустой, но структурно верный файл — тоже принимаем.
  if (report) {
    return { ok: true, data: report, format: "report" };
  }
  if (trudvsem) {
    return { ok: true, data: trudvsem, format: "trudvsem", sourcePayload: raw };
  }

  return {
    ok: false,
    error:
      "Не удалось распознать формат файла. Ожидается JSON отчёта KantKod (поле vacancies с issues) или выгрузка портала «Работа в России» (results.vacancies).",
  };
}
