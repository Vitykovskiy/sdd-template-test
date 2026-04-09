# ensure_issue_project_link.py

## Назначение

Скрипт синхронизирует workflow-статус связанного item в GitHub Project с каноническим полем `Status`, которое хранит `ready`, `in_progress`, `review`, `in_testing` и `done`.

## Контекст применения

Используется automation-слоем, в том числе из GitHub Actions, когда событие по issue требует привести связанный item в GitHub Project к каноническому `Status`.

## Входные параметры

- `--issue-number`
  - номер issue;
  - обязательный параметр.
- `--repository`
  - репозиторий в формате `owner/name`;
  - если не указан, определяется по `origin`.
- `--state-file`
  - путь к `.codex/state.json`;
  - по умолчанию: `.codex/state.json`.

## Внешние зависимости

- `gh`
- `.codex/state.json`
- общий модуль `.codex/routing/_shared/lib/common.py`

## Алгоритм работы

1. Находит корень репозитория.
2. Загружает `state.json` и получает `gh_project_id`.
3. Если project не настроен, завершает работу статусом `skipped`.
4. Определяет целевой репозиторий:
   - из `--repository`;
   - либо по `origin`.
5. Загружает issue через GitHub CLI.
6. Получает поле `Status` GitHub Project и ищет option для нужного workflow status.
7. Ищет project item, связанный с issue.
8. Если item отсутствует, добавляет issue в project.
9. Если текущий project status отличается от требуемого, обновляет его.
10. Возвращает JSON-результат синхронизации.

## Формат результата

Основные статусы:

- `synced`
- `skipped`
- `error`

Основные поля:

- `repository`
- `issue_number`
- `project_item_id`
- `from`
- `to`
- `reason`

## Коды завершения

- `0` — синхронизация выполнена или корректно пропущена.
- `2` — не определён репозиторий через `origin`.
- `3` — не найдено поле `Status` в GitHub Project.
- `4` — в поле `Status` нет нужной option.
- `5` — отсутствует node id у issue.
- `6` — ошибка GitHub CLI или GraphQL.

## Важные инварианты

- Источник желаемого статуса — GitHub Project `Status` с canonical values `ready`, `in_progress`, `review`, `in_testing`, `done`.
- Issue body не используется как источник статуса.
- Скрипт синхронизирует только одну issue за вызов.
