# common.py

## Назначение

Модуль содержит общие типы, функции и GitHub/Git/GraphQL-обвязку, которые переиспользуются скриптами `initialization`, `issue-driven` и automation-сценариями синхронизации.

## Роль в архитектуре

Это общий инфраструктурный слой workflow. Он инкапсулирует:

- поиск корня репозитория;
- чтение и запись `state.json`;
- запуск внешних команд;
- вызовы GitHub CLI;
- вызовы GitHub GraphQL API;
- разбор Markdown-артефактов стандарта и задач;
- операции над GitHub Project.

## Основные типы

- `CommandError`
  - единый тип ошибок для команд и API-вызовов.
- `ProjectRef`
  - owner, номер и URL GitHub Project.
- `RepoRef`
  - owner и имя GitHub repository;
  - содержит вычисляемое свойство `full_name`.
- `LabelSpec`
  - спецификация label из стандарта.
- `ProjectStatusOptionSpec`
  - спецификация канонического workflow status option для поля `Status`.

## Основные группы функций

### 1. Работа с репозиторием и состоянием

- `repo_root_from_script`
- `load_json_file`
- `write_json_file`
- `load_state`
- `save_state`

### 2. Запуск внешних команд

- `run_command`
- `run_json_command`
- `print_json`

### 3. Парсинг ссылок и удалённых репозиториев

- `parse_project_url`
- `parse_remote_url`
- `get_origin_remote_url`
- `get_repo_from_origin`
- `get_current_login`

### 4. GitHub CLI-обёртки

- `gh_repo_view`
- `gh_project_view`
- `gh_project_list`
- `gh_project_field_list`
- `gh_label_list`
- `gh_issue_list`
- `gh_issue_view`

### 5. Разбор стандартов и Markdown-артефактов

- `extract_backtick_values`
- `load_label_specs`
- `load_project_status_specs`
- `load_required_labels`
- `load_initiating_task_template`
- `extract_markdown_sections`
- `extract_code_value`

### 6. GitHub GraphQL операции

- `graphql_request`
- `get_project_status_field`
- `update_project_status_field`
- `list_project_items`
- `add_issue_to_project`
- `update_project_item_status`

## Алгоритмические особенности

- Корень репозитория определяется не по `git`, а по наличию `.codex/state.json`.
- Для чтения JSON и Markdown используется `utf-8-sig`, чтобы переживать BOM.
- Вызовы GraphQL работают либо через `GH_TOKEN`/`GITHUB_TOKEN`, либо через `gh auth token`.
- Сопоставление label colors и colors поля `Status` задаётся явной картой `PROJECT_STATUS_COLOR_MAP`.

## Важные инварианты

- Все mutation-скрипты должны использовать этот модуль, а не дублировать логику GitHub-интеграции.
- Ошибки внешних команд должны подниматься как `CommandError`, а не растворяться в stdout/stderr.
- Стандарт labels и канонических workflow status извлекается только из `gh-project-standard.md`, а не из hardcode в mutation-скриптах.

## Риски и ограничения

- Модуль жёстко связан с форматом GitHub CLI и GitHub GraphQL schema для ProjectV2.
- Некорректное определение labels или `Status` options приведёт к ошибке маппинга в `load_project_status_specs`.
- Markdown parser минималистичен: он рассчитывает на секции уровня `##`.
