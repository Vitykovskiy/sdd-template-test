# check_initialization.py

## Назначение

Скрипт выполняет аудит стадии `initialization` без мутаций. Он проверяет, готов ли репозиторий к завершению и какие обязательные действия ещё не выполнены.

## Контекст применения

Используется как диагностический шаг перед вызовами mutation-скриптов стадии `initialization`.

## Входные параметры

- `--state-file`
  - путь к `.codex/state.json`;
  - по умолчанию: `.codex/state.json`.

## Внешние зависимости

- `git`
- `gh`
- `.codex/state.json`
- `.codex/routing/initialization/standards/gh-project-standard.md`
- `.codex/routing/initialization/templates/initiating-task.md`
- общий модуль `.codex/routing/_shared/lib/common.py`

## Что проверяет

1. Инициализирован ли локальный Git-репозиторий.
2. Авторизован ли GitHub CLI.
3. Настроен ли `origin`.
4. Указывает ли `origin` на GitHub-репозиторий.
5. Существует ли удалённый GitHub-репозиторий.
6. Загружается ли `state.json`.
7. Привязан ли GitHub Project и существует ли он.
8. Записан ли `gh_project_id` в состоянии.
9. Соответствует ли поле `Status` в GitHub Project шаблонному стандарту.
10. Синхронизированы ли статусы Project item с каноническим полем `Status` в GitHub Project.
11. Созданы ли все обязательные labels role/priority и соответствуют ли они стандарту.
12. Валиден ли шаблон initiating task.
13. Существует ли initiating task в репозитории.

## Алгоритм работы

1. Находит корень репозитория через `.codex/state.json`.
2. Загружает label-спецификации role/priority и спецификацию Project `Status` из стандарта GitHub Project.
3. Формирует `report` со статусом, набором проверок и списком обязательных действий.
4. Проверяет локальный Git и GitHub CLI.
5. Анализирует `origin` и удалённый GitHub-репозиторий.
6. Пытается загрузить состояние workflow.
7. Если в состоянии указан GitHub Project, валидирует его доступность, поля и status options.
8. Если project доступен, проверяет выравнивание статусов между issue и project item.
9. Сверяет labels репозитория со стандартом.
10. Загружает шаблон initiating task и проверяет его обязательные секции.
11. Проверяет наличие initiating task в issue-трекере.
12. Нормализует `required_actions` в фиксированном порядке.
13. Печатает JSON-отчёт.

## Формат результата

Скрипт печатает JSON с полями:

- `status`
  - `ok` или `action_required`;
- `checks`
  - детализированные результаты проверок;
- `required_actions`
  - упорядоченный список требуемых действий.

## Коды завершения

- `0` — состояние соответствует стандарту.
- `2` — найдены блокеры или незавершённые шаги `initialization`.

## Важные инварианты

- Скрипт не должен выполнять мутации.
- Источник истины для стадии — `.codex/state.json`.
- Порядок `required_actions` фиксирован и задаёт допустимую последовательность remediation-шагов.

## Типовые причины статуса `action_required`

- отсутствует Git-репозиторий;
- не настроен GitHub CLI;
- не создан или не привязан GitHub repository;
- не создан или не привязан GitHub Project;
- labels role/priority или поле `Status` не соответствуют стандарту;
- отсутствует initiating task;
- повреждён `state.json`.
