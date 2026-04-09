# commit_push_pr.py

## Назначение

Скрипт завершает issue-driven работу через локальный `commit`, `push` в `origin` и создание или переиспользование pull request в default branch репозитория.
Это shared workflow-artifact для финализации изменения после выполнения роли в `issue-driven` режиме.

После успешной публикации результата скрипт:

1. переводит связанный project item в workflow-status `review`;
2. вызывает существующий shared script синхронизации project status.

## Контекст применения

Скрипт запускается из репозитория template workflow и рассчитан на завершение локальной разработки в PR.
Он работает с GitHub repository, где default branch защищён через required pull request.

Если пользователь уже находится не на default branch, скрипт может использовать текущую ветку.
Если пользователь находится на default branch и `--branch` не передан, скрипт создаёт feature-branch автоматически на основе issue number и title.

## Входные параметры

- `--issue-number` - required, номер issue.
- `--commit-message` - required, сообщение коммита.
- `--branch` - явное имя рабочей ветки.
- `--base-branch` - target branch для PR; если не передан, используется default branch репозитория.
- `--pr-title` - явный title для PR.
- `--pr-body` - явный body для PR.
- `--pr-body-file` - файл с body для PR; имеет приоритет над `--pr-body`.
- `--stage-all` - выполнить `git add -A` перед commit.
- `--state-file` - путь к workflow state file, default: `.codex/state.json`.

## Зависимости

- `git`
- `gh`
- GitHub origin remote в локальном репозитории
- доступ к GitHub API через `GH_TOKEN`, `GITHUB_TOKEN` или `gh auth token`
- общий модуль `.codex/routing/_shared/lib/common.py`
- существующий shared script `.codex/routing/_shared/scripts/sync_issue_project_status.py`

## Алгоритм

1. Определяет корень репозитория через `repo_root_from_script`.
2. Загружает `.codex/state.json` через `--state-file`.
3. Определяет `owner/name` репозитория из `origin`.
4. Читает issue и использует связанный GitHub Project `Status` как канон workflow status (`ready`, `in_progress`, `review`, `in_testing`, `done`).
5. Выбирает рабочую ветку:
   - если передан `--branch`, использует её;
   - если текущая ветка не равна `--base-branch`, использует текущую ветку;
   - если текущая ветка равна `--base-branch`, пытается переиспользовать открытый PR по issue;
   - иначе создаёт feature-branch по issue number и title.
6. Проверяет состояние working tree.
   - Без `--stage-all` допускаются только staged changes.
   - Если есть unstaged или untracked changes без `--stage-all`, скрипт завершает работу с `validation_error`.
   - С `--stage-all` выполняет `git add -A`.
7. Если staged changes есть, создаёт commit и пушит ветку в `origin`.
8. Если для ветки уже существует open PR, переиспользует его.
   Иначе создаёт новый PR.
9. После успешного PR:
   - переводит связанный project item в `review`;
   - запускает `.codex/routing/_shared/scripts/sync_issue_project_status.py`.
10. Печатает JSON-результат и завершает работу.

## Формат JSON-результата

Скрипт всегда печатает один JSON-объект.

Основные поля:

- `status`
  - `created`
  - `updated_existing_pr`
  - `validation_error`
  - `error`
- `repository`
- `issue_number`
- `branch`
- `base_branch`
- `commit_sha`
- `pr_number`
- `pr_url`
- `from_status`
- `to_status`
- `changed`
- `project_sync`
- `workflow_mode`

## Exit codes

- `0` - workflow завершён успешно.
- `1` - техническая ошибка Git, GitHub CLI, API или runtime error.
- `2` - validation error: нарушены входные условия или состояние репозитория.

## Важные инварианты

- Скрипт не создаёт duplicate PR для уже открытой ветки.
- Без `--stage-all` он не коммитит unstaged/untracked changes.
- PR создаётся сразу как ready for review; режим черновика не используется.
- PR создаётся в default branch репозитория, если не передан другой `--base-branch`.
- После успешной публикации issue переводится в `review`.
- Project status синхронизируется через existing shared script, а не через встроенную дублирующую логику.
- Повторный запуск в разумном сценарии не плодит PR и переиспользует уже открытый PR.
