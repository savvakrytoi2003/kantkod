import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRun, generateReport, startAnalysis, startSync } from "./api";
import { Icon } from "./icons";
import type { RunState } from "./types";

/**
 * Панель загрузки вакансий из портала без curl: ставит синхронизацию в очередь,
 * опрашивает статус, затем запускает анализ и пересобирает отчёт.
 *
 * Количество ограничено конфигом бэкенда (SOURCE_MAX_VACANCIES) — больше
 * запросить нельзя, значение отсюда не расширяет лимит, только сужает.
 */

const DEFAULT_COUNT = 100;
/** SOURCE_MAX_VACANCIES / AnalysisRequestDTO.limit на бэкенде. */
const MAX_COUNT = 10000;
/** Жёсткий потолок, чтобы брошенная вкладка не опрашивала сервер вечно. */
const MAX_POLL_MS = 10 * 60 * 1000;
const POLL_INTERVAL_MS = 1500;

type Stage = "idle" | "sync" | "analysis" | "report";

const STAGE_LABELS: Record<Exclude<Stage, "idle">, string> = {
  sync: "Загружаем вакансии с портала",
  analysis: "Анализируем вакансии",
  report: "Собираем отчёт",
};

const TERMINAL = new Set(["success", "partial", "failed"]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/** Опрашивает run, пока он не в финальном статусе. Возвращает последнее состояние. */
async function waitForRun(runId: string, deadline: number): Promise<RunState> {
  let last: RunState | null = null;
  while (Date.now() < deadline) {
    try {
      last = await fetchRun(runId);
    } catch {
      // задача могла быть ещё не записана в БД — пробуем снова
    }
    if (last && TERMINAL.has(last.status)) {
      return last;
    }
    await sleep(POLL_INTERVAL_MS);
  }
  if (last) {
    return last;
  }
  throw new Error("Не удалось узнать статус задачи. Проверьте, что бэкенд запущен.");
}

export default function SyncPanel({ onDone }: { onDone: () => void }) {
  const [count, setCount] = useState(DEFAULT_COUNT);
  const [force, setForce] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const report = useCallback(
    (text: string) => {
      if (mounted.current) {
        setProgress(text);
      }
    },
    [],
  );

  const run = useCallback(async () => {
    const limit = Math.max(1, Math.min(MAX_COUNT, Math.round(count) || DEFAULT_COUNT));
    const deadline = Date.now() + MAX_POLL_MS;

    setError(null);
    setProgress(null);
    try {
      setStage("sync");
      report("Ставим синхронизацию в очередь…");
      const syncTask = await startSync(limit);
      report("Синхронизация идёт…");
      const syncRun = await waitForRun(syncTask.run_id, deadline);

      if (syncRun.status === "failed") {
        throw new Error(syncRun.error_message ?? "Синхронизация завершилась с ошибкой");
      }
      if (syncRun.status !== "success") {
        report(`Синхронизация: ${syncRun.status}. Продолжаем анализ.`);
      }

      setStage("analysis");
      report(syncRun.processed_count > 0 ? `Синхронизировано: ${syncRun.processed_count}. Анализируем…` : "Анализируем…");
      const analysisTask = await startAnalysis(limit, force);
      const analysisRun = await waitForRun(analysisTask.run_id, deadline);

      setStage("report");
      report("Пересобираем отчёт…");
      await generateReport().catch(() => {
        // отчёт пересоберёт планировщик; список замечаний после анализа уже есть
      });

      if (analysisRun.status === "failed") {
        throw new Error(analysisRun.error_message ?? "Анализ завершился с ошибкой");
      }

      const failedPart =
        analysisRun.failed_count > 0 ? `, сбоев ИИ: ${analysisRun.failed_count}` : "";
      const analysisMessage = `Готово: обработано ${analysisRun.processed_count}${failedPart}`;
      setProgress(analysisMessage);
      setStage("idle");
      onDone();
    } catch (reason) {
      if (mounted.current) {
        setError(reason instanceof Error ? reason.message : String(reason));
        setProgress(null);
        setStage("idle");
      }
    }
  }, [count, force, onDone, report]);

  const busy = stage !== "idle";
  const busyLabel = busy ? STAGE_LABELS[stage] : null;

  return (
    <section className="sync-panel" aria-label="Загрузить вакансии с портала">
      <div className="sync-panel__row">
        <label className="sync-panel__count">
          <span>Вакансий</span>
          <input
            type="number"
            min={1}
            max={MAX_COUNT}
            step={50}
            value={count}
            disabled={busy}
            onChange={(event) => setCount(Number(event.target.value))}
          />
        </label>

        <label className="sync-panel__force" title="Переанализировать вакансии, у которых анализ уже прошёл">
          <input
            type="checkbox"
            checked={force}
            disabled={busy}
            onChange={(event) => setForce(event.target.checked)}
          />
          <span>Переанализировать</span>
        </label>

        <button type="button" className="button" disabled={busy} onClick={() => void run()}>
          {busy ? <span className="spinner spinner--small" aria-hidden="true" /> : <Icon name="sparkles" size={15} />}
          {busy ? "Загружаем…" : "Загрузить вакансии"}
        </button>
      </div>

      {busyLabel ? (
        <p className="sync-panel__status" aria-busy="true">
          <span className="pill pill--busy">
            <span className="pill__dot" /> {busyLabel}
          </span>
          {progress ? <span className="sync-panel__hint">{progress}</span> : null}
        </p>
      ) : null}

      {!busy && progress ? <p className="sync-panel__status">{progress}</p> : null}

      {error ? (
        <div className="alert" role="alert">
          <strong>Загрузка не удалась.</strong> {error}
        </div>
      ) : null}
    </section>
  );
}
