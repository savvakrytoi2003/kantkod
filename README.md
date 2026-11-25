# KantKod — «Прозрачная вакансия»

Сервис получает вакансии Калининградской области (регион 39) с портала «Работа в России», проверяет, насколько понятно описаны условия работы, и формирует JSON-отчёт с замечаниями для редактора вакансии.

## Стек

Python 3.12, FastAPI, Dishka (DI), SQLAlchemy 2 + PostgreSQL, Redis (кеш), Alembic, APScheduler, Pydantic, httpx. Всё запускается в Docker.

## Команда и вклад

| Участник | Зона ответственности |
| --- | --- |
| Савва Мухин | Backend |
| Паша Нефедьев | Backend |
| Александр Хакана | Frontend |
| Любовь | Frontend |
| Полина Сенина | Дизайн |

Backend — API, синхронизация с источником, правила проверки, ИИ-пайплайн и БД. Frontend — React-интерфейс, загрузка своих JSON, вкладка «Резюме под вакансию». Дизайн — визуальный стиль, макеты и оформление интерфейса.

## Структура

```
kantkod/
├── backend/           # приложение
│   ├── app/           # config, di, schemas, domain, infrastructure, presentation
│   ├── migrations/    # Alembic
│   ├── scripts/       # start.sh — миграции + запуск API
│   ├── examples/      # sample.json — учебный набор, resume.json — демо-резюме
│   ├── reports/       # сюда пишутся отчёты
│   └── tests/         # pytest (запускаются локально)
├── composer/          # docker-compose.yml
└── frontend/          # React + Vite: просмотр вакансий с замечаниями
```

## Пайплайн и точка входа

- **Автоматический режим:** `backend/scripts/start.sh` → `app.main:create_app` → `SchedulerService` (интервал `SYNC_INTERVAL_MINUTES`) → `JobRunner.run_cycle`: `SyncVacanciesUseCase` → `AnalyzeVacanciesUseCase` → `GenerateReportUseCase`.
- **Ручной запуск:** `POST /api/v1/sync` → `JobRunner.run_sync`; `POST /api/v1/analysis`; `POST /api/v1/reports/generate`; статус запуска — `GET /api/v1/runs/{id}`.
- **Проверочный режим:** `python -m app validate` (файл) или `POST /api/v1/validation/analyze` (JSON в теле) → `ValidateJsonUseCase` → тот же пайплайн без обращения к порталу.
- **Доп. сценарий «Резюме под вакансию»:** `POST /api/v1/resume/draft` → `GenerateResumeDraftUseCase` → промпт `resume_prompt_builder.py` → DeepSeek → `resume_response_validator.py`; резюме не сохраняется.
- **Где используется ИИ:** `BatchVacancyAnalyzer.analyze` вызывается из `AnalyzeVacanciesUseCase` и `ValidateJsonUseCase`; ответ модели валидируется, затем мержится с правилами (`IssueMerger`) и проверяется `IssueVerifier` перед записью отчёта. Промпт — `app/domain/services/ai_prompt_builder.py`.

## Запуск (Docker)

```bash
# 1) создайте локальный конфиг (ключ ИИ можно оставить пустым — будет режим «только правила»)
cp -n backend/.env.example backend/.env

# 2) при необходимости вставьте AI_API_KEY в backend/.env

# 3) запуск
cd composer
docker compose up --build
```

Настройки ИИ (`AI_*`) читаются из `backend/.env`. `SOURCE_*`, `SYNC_INTERVAL_MINUTES` и `SCHEDULER_ENABLED` задаются в окружении compose (shell или `composer/.env`); значения по умолчанию уже настроены на 100 вакансий двумя страницами по 50.

Без ключа ИИ сервис работает в режиме «только правила» — отчёт строится, но без ИИ.

ИИ по умолчанию настроен на **DeepSeek V4.1 Flash** (`deepseek-flash`) через OpenAI-совместимый API `https://api.deepseek.com`. Ключ удобно хранить в `backend/.env` в переменной `AI_API_KEY` (файл в `.gitignore`): после вставки ключа перезапустите backend. Модель и base URL уже прописаны в `.env.example`; для другого OpenAI-совместимого провайдера достаточно поменять `AI_BASE_URL` и `AI_MODEL`.

### Конфигурация

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `SOURCE_API_URL` | URL API региона 39 | `http://opendata.trudvsem.ru/api/v1/vacancies/region/39` |
| `SOURCE_REGION` | Код региона | `39` |
| `SOURCE_MAX_VACANCIES` | Максимум вакансий за цикл | `100` |
| `SOURCE_PAGE_SIZE` | Размер страницы источника | `50` (две страницы по 50) |
| `SYNC_INTERVAL_MINUTES` | Интервал автоматического цикла | `60` |
| `AI_BASE_URL` / `AI_MODEL` / `AI_API_KEY` | Провайдер, модель и ключ ИИ | DeepSeek V4.1 Flash |
| `AI_THINKING` | Reasoning у DeepSeek | `false` (быстрее для JSON) |

Все настройки читаются из `backend/.env` и переменных окружения; для запуска не нужны ручные правки кода.

Что происходит при старте: `backend/scripts/start.sh` ждёт PostgreSQL, применяет миграции (`alembic upgrade head`) и поднимает uvicorn на `:8000`.

Внутри контейнера планировщик раз в час выполняет цикл: синхронизация → анализ → отчёт.

### Ручной прогон

```bash
curl -X POST http://localhost:8000/api/v1/sync -H 'Content-Type: application/json' -d '{"max_vacancies": 100}'
# → {"run_id": "...", "status": "pending"}

curl http://localhost:8000/api/v1/runs/<run_id>     # дождитесь success перед анализом
curl -X POST http://localhost:8000/api/v1/analysis -H 'Content-Type: application/json' -d '{"limit": 100}'
curl http://localhost:8000/api/v1/vacancies/issues  # вакансии с замечаниями
curl -X POST http://localhost:8000/api/v1/reports/generate
curl http://localhost:8000/api/v1/reports/latest

# Анализ загруженного JSON (правила + ИИ, без записи на диск и в БД)
curl -X POST http://localhost:8000/api/v1/validation/analyze \
  -H 'Content-Type: application/json' --data-binary @examples/sample.json
```

## Проверочный режим (локальный JSON, без портала)

```bash
cd composer
docker compose run --rm -e AI_ENABLED=false --entrypoint python backend -m app validate \
  --input examples/sample.json --output reports/result.json
```

Пример результата на учебных данных лежит в `backend/reports/result.json` (правила, без ИИ — воспроизводимо без ключа). Для проверочного режима с ИИ используйте локальную модель ниже.

## Отчёт

```json
{
  "generated_at": "2026-11-24T20:00:00Z",
  "region": 39,
  "vacancies": [
    {
      "vacancy_id": "DEMO-39-001",
      "source_url": "https://trudvsem.ru/vacancy/card/DEMO-39/DEMO-39-001",
      "issues": [
        {
          "topic": "salary",
          "source_field": "salary",
          "quote": "",
          "problem": "В вакансии отсутствуют сведения об оплате.",
          "recommendation": "Указать размер оплаты труда или диапазон заработной платы."
        }
      ]
    }
  ]
}
```

Поля замечания: `topic` (title, duties, requirements, salary, schedule, location, employment, contradiction), `source_field` — поле вакансии, `quote` — цитата или значение (пустая строка для пропуска), `problem` — суть, `recommendation` — что уточнить. Для противоречия в `quote` оба значения через `" / "`. Одна вакансия — один объект, вакансии без замечаний остаются с пустым массивом.

## Где используется ИИ

`backend/app/infrastructure/ai/` — OpenAI-совместимый клиент. Пакет вакансий уходит одним запросом с промптом из `app/domain/services/ai_prompt_builder.py`; модель ищет неоднозначные формулировки и предлагает уточнения. Ответ валидируется (`ai_response_validator.py`), при невалидном JSON делается один repair-запрос, при повторной ошибке вакансия помечается `failed` — пустые замечания вместо ошибки не сохраняются. Найденное ИИ мержится с результатами правил (`issue_merger.py`).

Локальная модель без аккаунта (Ollama):

```bash
# 1) установите Ollama (https://ollama.com) и скачайте модель
ollama pull qwen2.5:7b

# 2) прогоните проверочный режим через локальную модель
cd composer
docker compose run --rm --add-host=host.docker.internal:host-gateway \
  -e AI_PROVIDER=openai_compatible -e AI_ENABLED=true \
  -e AI_BASE_URL=http://host.docker.internal:11434/v1 -e AI_API_KEY=ollama \
  -e AI_MODEL=qwen2.5:7b --entrypoint python backend -m app validate \
  --input examples/sample.json --output reports/result-local.json
```

На Docker Desktop `host.docker.internal` доступен и без флага; на Linux флаг `--add-host=host.docker.internal:host-gateway` обязателен. Ollama должен быть запущен и слушать `11434`. Флаг `AI_PROVIDER=openai_compatible` обязателен: иначе останется DeepSeek-провайдер и клиент добавит своё поле `thinking`.

Ключи хранятся только в переменных окружения, в репозиторий не попадают.

## Дополнительный сценарий: резюме под вакансию

**Кому помогает:** соискателю, который хочет быстро адаптировать резюме под конкретную вакансию региона 39, и редактору — как пример «двустороннего» использования данных.

**Данные:** список вакансий из `GET /api/v1/vacancies` (выбор в интерфейсе), полная вакансия из БД и резюме соискателя — структурированный JSON или свободный текст. Для демо есть вымышленное резюме `backend/examples/resume.json` (кнопки «Заполнить примером» / «Пример JSON» в UI).

**Результат:** `POST /api/v1/resume/draft` с телом `{"vacancy_id": "...", "resume": {...} | "текст"}` возвращает:
- `summary` — краткое позиционирование под вакансию;
- `highlighted_skills` — навыки из резюме, важные для вакансии;
- `experience_highlights` / `education_highlights` — факты из резюме;
- `gaps` — требования вакансии со статусом `matched` / `partial` / `missing` и советом, что уточнить;
- `draft_text` — готовый черновик в Markdown.

ИИ использует **только факты из резюме**: если требования вакансии не подтверждены, они попадают в `gaps`, а не выдумываются в опыте. Резюме не сохраняется на сервере. Промпт — `app/domain/services/resume_prompt_builder.py`, ответ валидируется `resume_response_validator.py`.

В интерфейсе это вкладка **«Резюме под вакансию»**: поиск вакансии, текст/JSON резюме, генерация и скачивание `.md` / `.json`. Без настроенного ИИ endpoint вернёт 503; остальной сервис продолжит работать в режиме правил.

## Фронтенд

React + Vite + TypeScript в `frontend/`. Показывает вакансии с замечаниями из `GET /api/v1/vacancies/issues` и метаданные последнего отчёта из `GET /api/v1/reports/latest`. Есть поиск (клавиша `/`), фильтры по темам, сортировка, сворачивание карточек, тёмная тема, копирование замечаний, выгрузка отфильтрованного JSON и вкладка «Резюме под вакансию» (доп. сценарий).

Кроме данных сервиса можно открыть собственный JSON-файл — вкладка «Свой JSON-файл» (перетаскивание или выбор файла). Поддерживаются форматы:

- выгрузка портала «Работа в России» — `{ "results": { "vacancies": [{ "vacancy": {...} }] } }` (как `backend/examples/sample.json`): файл уходит на `POST /api/v1/validation/analyze` и прогоняется через тот же пайплайн, что и CLI-режим `validate` — программные правила + ИИ-анализ неоднозначных формулировок. Результат (замечания) показывается сразу, с пометкой «правила + ИИ» или «только правила»; если бэкенд недоступен, файл можно хотя бы просмотреть локально и повторить анализ;
- отчёт KantKod — `{ "vacancies": [{ "vacancy_id", "name", "source_url", "issues": [...] }] }` (как `backend/reports/result.json`) — открывается как есть, пайплайн не требуется;
- просто массив вакансий.

Ограничение на загружаемый файл — 200 вакансий (`MAX_UPLOAD_VACANCIES` в `app/domain/use_cases/validate_json.py`), чтобы ИИ-анализ оставался предсказуемым.

### Запуск фронтенда

**Требования:** Node.js 18+ и npm, а также запущенный backend на `127.0.0.1:8000`.

```bash
# 1) backend + postgres + redis (из корня репозитория)
cd composer
docker compose up -d --build

# 2) frontend в отдельном терминале
cd frontend
npm ci          # если npm ci недоступен — npm install
npm run dev
```

Откройте **http://127.0.0.1:5173**. Vite проксирует `/api` на `http://127.0.0.1:8000` (см. `frontend/vite.config.ts`), поэтому backend должен быть запущен. Без него интерфейс покажет ошибку загрузки; для анализа загруженного JSON backend тоже нужен.

Production-сборка и локальный предпросмотр:

```bash
cd frontend
npm run build     # dist/
npm run preview   # http://127.0.0.1:4173, /api тоже проксируется
```

Для доступа с другой машины запустите `npm run dev -- --host 0.0.0.0` (порт 5173) и откройте адрес машины. Для публичного деплоя отдайте содержимое `frontend/dist/` любым статическим сервером (nginx и т.п.) и настройте проксирование `/api` на backend `:8000`.

## Тесты (локально)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/pytest -q
```

## Особенности реализации

- Повторный запуск на неизменённых данных не создаёт дубликатов: сравнение по `content_hash`, `external_id` уникален; в отчёте одна запись на ID.
- При недоступности API запуск помечается `failed`, последний успешный отчёт (`reports/latest.json`) не перезаписывается.
- Вакансии анализируются повторно, если они новые, изменились или предыдущий анализ не завершился успешно (`partial`/`failed`); принудительный переанализ — `POST /api/v1/analysis/{id}/retry`.
- Планировщик не запускает свой цикл параллельно (`max_instances=1`); ручные запуски sync/analysis не блокируются и не должны пересекаться.
