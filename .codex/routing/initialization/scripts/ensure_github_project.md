# ensure_github_project.py

## Назначение

Скрипт создаёт новый GitHub Project или привязывает существующий, затем фиксирует его идентификаторы в `.codex/state.json`.

## Контекст применения

Используется на стадии `initialization` после подготовки GitHub repository и до синхронизации project standard.

## Входные параметры

- `--state-file`
  - путь к `.codex/state.json`;
  - по умолчанию: `.codex/state.json`.
- `--owner`
  - владелец GitHub Project;
  - по умолчанию берётся owner репозитория.
- `--title`
  - заголовок нового проекта;
  - обязателен, если проект нужно создать.
- `--project-url`
  - URL существующего GitHub Project для привязки вместо создания.

## Внешние зависимости

- `gh`
- `.codex/state.json`
- общий модуль `.codex/routing/_shared/lib/common.py`

## Алгоритм работы

1. Находит корень репозитория.
2. Определяет GitHub repository через `origin`.
3. Загружает `state.json`.
4. Выбирает источник project reference:
   - `--project-url`;
   - либо `project.gh_project_url` из состояния;
   - либо создаёт новый project.
5. Если project URL уже известен:
   - парсит URL;
   - читает project через GitHub CLI.
6. Если project ещё не задан:
   - определяет owner;
   - требует `--title`;
   - проверяет точные конфликты по заголовку;
   - при конфликте возвращает `name_conflict`;
   - иначе создаёт project.
7. Связывает project с репозиторием через `gh project link`.
8. Записывает `gh_project_url` и `gh_project_id` в `.codex/state.json`.
9. Возвращает JSON со статусом `ready`.

## Формат результата

Основные статусы:

- `ready`
- `name_conflict`
- `error`

Типичные поля результата:

- `project_url`
- `project_id`
- `project_number`
- `project_title`
- `repository_full_name`
- `resolution_options`

## Коды завершения

- `0` — project существует или создан и корректно привязан.
- `2` — ошибка входных данных или детектирован неоднозначный конфликт.
- `3` — ошибка вызова GitHub CLI или сохранения состояния.

## Важные инварианты

- В `state.json` после успеха должны быть записаны оба поля:
  - `project.gh_project_url`
  - `project.gh_project_id`
- При конфликте одинаковых project titles автоматический выбор запрещён.
