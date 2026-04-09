# create_initiating_task.py

## Назначение

Скрипт создаёт initiating task в виде GitHub issue, добавляет её в GitHub Project, назначает проектный `Status` как канонический workflow-статус `ready` и переводит workflow из режима `initialization` в `issue_driven`.

## Контекст применения

Это финальный mutation-шаг стадии `initialization`. После его успешного выполнения состояние workflow меняется.

## Входные параметры

- `--state-file`
  - путь к `.codex/state.json`;
  - по умолчанию: `.codex/state.json`.
- `--template-file`
  - путь к Markdown-шаблону initiating task;
  - по умолчанию: `.codex/routing/initialization/templates/initiating-task.md`.

## Внешние зависимости

- `gh`
- `.codex/state.json`
- шаблон initiating task
- общий модуль `.codex/routing/_shared/lib/common.py`

## Предусловия

- `origin` должен быть привязан к GitHub-репозиторию;
- в `state.json` должны быть заданы `project.gh_project_url` и `project.gh_project_id`;
- шаблон initiating task должен содержать обязательные секции:
  - `Id`
  - `Role`
  - `Title`
  - `Purpose`
  - `Artifacts`
  - `Priority`
- Канонические workflow status для шаблона: `ready`, `in_progress`, `review`, `in_testing`, `done`.

## Алгоритм работы

1. Находит корень репозитория и определяет GitHub repository через `origin`.
2. Загружает состояние workflow и проверяет, что GitHub Project уже привязан.
3. Загружает шаблон initiating task и разбирает Markdown-секции.
4. Валидирует обязательные секции шаблона.
5. Строит набор issue labels из полей `Role` и `Priority`.
6. Проверяет, существует ли issue с таким заголовком.
7. Если issue уже существует:
   - повторно добавляет её в project;
   - доустанавливает labels;
   - возвращает статус `already_exists`.
8. Если issue не существует:
   - создаёт новую issue из шаблона;
   - добавляет её в project;
   - возвращает статус `created`.
9. Получает поле `Status` проекта и находит option, соответствующий статусу следующей стадии.
10. Находит project item для issue или создаёт его привязку, если item ещё отсутствует.
11. Обновляет поле `Status` project item.
12. Переводит `state["mode"]` в `issue_driven` и сохраняет состояние.
13. Печатает JSON-результат.

## Формат результата

Основные поля ответа:

- `status`
  - `created`, `already_exists` или `error`;
- `issue_title`
- `issue_url`
- `labels`
- `mode`

## Коды завершения

- `0` — initiating task создана или уже существовала и успешно синхронизирована.
- `2` — нарушены предусловия конфигурации.
- `3` — ошибка выполнения команд или несоответствие шаблона/проекта.

## Важные инварианты

- Скрипт создаёт ровно одну initiating task по шаблонному заголовку.
- После успешного выполнения `mode` обязан стать `issue_driven`.
- Статус initiating task должен храниться только в поле `Status` GitHub Project.

## Архитектурное замечание

Этот скрипт не просто создаёт issue. Он выполняет state transition workflow. Поэтому его нельзя вызывать до завершения стандартализации GitHub Project и labels.
