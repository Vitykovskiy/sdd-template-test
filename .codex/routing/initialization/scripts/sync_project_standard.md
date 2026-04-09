# sync_project_standard.py

## Назначение

Скрипт приводит labels role/priority репозитория и поле `Status` в GitHub Project к шаблонному стандарту, а затем синхронизирует project item status с каноническим workflow-статусом GitHub Project.

## Контекст применения

Используется на стадии `initialization` после привязки GitHub Project и до создания initiating task. Может применяться и как remediation-скрипт при дрейфе стандарта.

## Входные параметры

- `--standard-file`
  - путь к Markdown-стандарту GitHub Project;
  - по умолчанию: `.codex/routing/initialization/standards/gh-project-standard.md`.

## Внешние зависимости

- `gh`
- `.codex/state.json`
- стандарт GitHub Project
- общий модуль `.codex/routing/_shared/lib/common.py`

## Что синхронизирует

1. Обязательные repository labels (role и priority):
   - создание отсутствующих;
   - обновление цвета и описания существующих.
2. Поле `Status` в GitHub Project:
   - состав options;
   - порядок и описание options через mutation GraphQL.
   - канонические значения: `ready`, `in_progress`, `review`, `in_testing`, `done`.
3. Project items для issue:
   - статус project item;
   - при необходимости добавление issue в project.

## Алгоритм работы

1. Находит корень репозитория и GitHub repository.
2. Загружает стандарт labels role/priority и канонические workflow status Project Status.
3. Загружает `state.json` и проверяет наличие `gh_project_id` и `gh_project_url`.
4. Получает текущие labels репозитория.
5. Для каждой label-спецификации:
   - создаёт label, если её нет;
   - редактирует label, если цвет или описание не совпадают.
6. Получает поле `Status` проекта.
7. Обновляет список single-select options в поле `Status`.
8. Обходит project items.
9. Для каждой issue:
   - использует project `Status` как источник желаемого статуса;
   - пропускает неконсистентные issue и фиксирует причину в `skipped_project_items`;
   - если issue ещё не в project, добавляет её;
   - если текущий status project item не совпадает, обновляет его.
10. Возвращает JSON с результатом синхронизации.

## Формат результата

Основные поля ответа:

- `status`
  - `synced` или `error`;
- `repository_full_name`
- `created_labels`
- `updated_labels`
- `required_label_count`
- `project_url`
- `project_status_field`
- `project_status_option_names`
- `synced_project_items`
- `skipped_project_items`

## Коды завершения

- `0` — синхронизация завершена.
- `2` — не выполнены предусловия конфигурации.
- `3` — ошибка выполнения внешних команд или GraphQL mutation.

## Важные инварианты

- Источник стандарта только один: Markdown-файл `gh-project-standard.md`.
- Скрипт не исправляет логические противоречия внутри issue автоматически; такие задачи переводятся в `skipped_project_items`.
- Синхронизация project item status идёт от канонического поля `Status` в GitHub Project.
