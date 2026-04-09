# SDD Template Origin

Краткая карта шаблона. Этот файл нужен для навигации по репозиторию без чтения всех инструкций и скриптов.

## Что это за шаблон

Шаблон задает workflow для агента через:

- маршрутизацию по состоянию проекта;
- выбор одной активной задачи из GitHub Project;
- переход в роль с жестко ограниченной зоной ответственности;
- канонические workflow status: `ready`, `in_progress`, `review`, `in_testing`, `done` в GitHub Project `Status`;
- обязательный git commit, push в default branch и применение защиты default branch после завершения initialization;
- создание первой BA-задачи как готового элемента следующей стадии;
- упрощенную модель labels: `role:*`, `priority:*`; workflow status хранится только в GitHub Project `Status`, а issue body не является носителем статуса.

Сейчас репозиторий находится в режиме `initialization`.
Источник истины для режима: `.codex/state.json`.

## Верхний уровень

```text
sdd-template-origin/
|- AGENTS.md
|- README.md
|- .codex/
|  |- state.json
|  |- roles/
|  `- routing/
`- .github/
   `- workflows/
```

## Куда смотреть в первую очередь

### 1. Точка входа агента

Файл: `AGENTS.md`

Назначение:

- определяет, что агент сначала читает `.codex/state.json`;
- маршрутизирует в один из режимов:
  - `initialization`
  - `issue_driven`
- после выбора задачи маршрутизирует в ролевую инструкцию.

Править здесь, если нужно менять глобальные правила входа в workflow.

### 2. Состояние workflow

Файл: `.codex/state.json`

Назначение:

- хранит текущий `mode`;
- хранит привязку к GitHub Project:
  - `project.gh_project_url`
  - `project.gh_project_id`

Править здесь, если меняется модель состояния workflow или структура project metadata.

## Структура `.codex`

### `.codex/roles/`

Ролевые инструкции. Каждая папка содержит `instruction.md`.

Состав:

- `.codex/roles/business-analyst/`
- `.codex/roles/system-analyst/`
- `.codex/roles/architect/`
- `.codex/roles/frontend-developer/`
- `.codex/roles/backend-developer/`
- `.codex/roles/devops/`

Назначение:

- фиксируют границы ответственности роли;
- задают допустимые артефакты;
- задают запрещенные действия;
- задают требования к результату.

Править здесь, если нужно менять:

- responsibility model;
- artifact ownership;
- role boundaries;
- execution constraints для конкретной роли.

### `.codex/routing/`

Маршрутизация по стадиям workflow.

Состав:

- `.codex/routing/initialization/`
- `.codex/routing/issue-driven/`
- `.codex/routing/_shared/`

#### `.codex/routing/initialization/`

Назначение:

- описывает инициализацию репозитория и GitHub Project;
- задает обязательный порядок mutation scripts;
- запрещает мутации без явного подтверждения пользователя.
- завершает initialization обязательным git commit после успешных mutation scripts.

Содержимое:

- `instruction.md`  
  Главная инструкция стадии инициализации.
- `scripts/check_initialization.py`  
  Аудит текущего состояния.
- `scripts/create_github_repository.py`  
  Создание GitHub repository.
- `scripts/ensure_github_project.py`  
  Создание или привязка GitHub Project.
- `scripts/sync_project_standard.py`  
  Применение template standard к проекту.
- `scripts/create_initiating_task.py`  
  Создание первой BA-задачи, подготовка ее для `issue_driven` и перевод `mode` в `issue_driven`.
- `scripts/protect_main_branch.py`  
  Применение защиты default branch от прямого push после commit и push изменений.
- `standards/gh-project-standard.md`  
  Норматив для структуры GitHub Project.
- `templates/initiating-task.md`  
  Шаблон initiating task.

Править здесь, если нужно менять:

- initialization flow;
- обязательный порядок шагов;
- аудит и критерии готовности;
- стандарт GitHub Project;
- шаблон initiating task.
- обязательный commit, push в default branch и защита default branch после initialization.

#### `.codex/routing/issue-driven/`

Назначение:

- переводит агента в режим работы от задачи;
- запрещает ручной выбор задачи;
- требует выбирать задачу только через selector script.

Содержимое:

- `instruction.md`  
  Правила стадии `issue_driven`.
- `scripts/select_task.py`  
  Единственный допустимый механизм выбора активной задачи.

Править здесь, если нужно менять:

- task selection policy;
- правила перехода от GitHub Project item к роли;
- структуру результата selector script.

#### `.codex/routing/_shared/`

Общие библиотеки и скрипты для нескольких стадий.

Содержимое:

- `lib/common.py`  
  Общие вспомогательные функции.
- `scripts/commit_push_pr.py`  
  Общий стандартный путь публикации результата в `issue-driven`: branch, commit, push и PR в default branch.
- `scripts/ensure_issue_project_link.py`  
  Синхронизация project item status через canonical field `Status` в GitHub Project.

Править здесь, если нужно менять общую интеграционную механику между issue и project.

## Структура `.github`

### `.github/workflows/ensure-issue-project-link.yml`

Назначение:

- слушает события `issues`;
- запускает Python-скрипт синхронизации статуса issue в GitHub Project.

Править здесь, если нужно менять:

- GitHub Actions trigger conditions;
- permissions workflow;
- способ запуска `ensure_issue_project_link.py`.

## Куда вносить правки по типам изменений

### Если меняется вход в workflow

Читать и править:

- `AGENTS.md`
- `.codex/state.json`
- при необходимости соответствующий `instruction.md` в `.codex/routing/`

### Если меняется логика инициализации

Читать и править:

- `.codex/routing/initialization/instruction.md`
- нужный файл в `.codex/routing/initialization/scripts/`
- при необходимости:
  - `.codex/routing/initialization/standards/gh-project-standard.md`
  - `.codex/routing/initialization/templates/initiating-task.md`

### Если меняется выбор задач

Читать и править:

- `.codex/routing/issue-driven/instruction.md`
- `.codex/routing/issue-driven/scripts/select_task.py`
- при необходимости `.codex/routing/_shared/lib/common.py`

### Если меняется публикация результата issue-driven

Читать и править:

- `.codex/routing/issue-driven/instruction.md`
- `.codex/routing/_shared/scripts/commit_push_pr.py`

### Если меняются роли и границы ответственности

Читать и править:

- нужный файл `.codex/roles/<role>/instruction.md`
- `AGENTS.md`, если меняется сама модель role routing

### Если меняется синхронизация issue <-> project

Читать и править:

- `.github/workflows/ensure-issue-project-link.yml`
- `.codex/routing/_shared/scripts/ensure_issue_project_link.py`
- при необходимости `.codex/routing/_shared/lib/common.py`

## Что обычно не нужно трогать

- `.git/`
- `__pycache__/`

Это не рабочие артефакты шаблона.

## Правило для субагентов

Чтобы не переполнять контекст, субагенту нужно задавать не тему целиком, а точный read set.

Рекомендуемый формат поручения:

1. цель изменения;
2. список файлов, которые обязательно прочитать;
3. список файлов, которые разрешено менять;
4. запрет читать остальной репозиторий без необходимости.

### Минимальные read sets

#### Для правок маршрутизации входа

Читать только:

- `AGENTS.md`
- `.codex/state.json`
- нужный `instruction.md` из `.codex/routing/`

#### Для правок initialization

Читать только:

- `.codex/routing/initialization/instruction.md`
- конкретный изменяемый script из `.codex/routing/initialization/scripts/`
- при необходимости:
  - `.codex/routing/initialization/standards/gh-project-standard.md`
  - `.codex/routing/initialization/templates/initiating-task.md`

#### Для правок issue-driven selection

Читать только:

- `.codex/routing/issue-driven/instruction.md`
- `.codex/routing/issue-driven/scripts/select_task.py`
- при необходимости `.codex/routing/_shared/lib/common.py`

#### Для правок конкретной роли

Читать только:

- `.codex/roles/<role>/instruction.md`
- `AGENTS.md`, если меняется role routing, а не только сама роль

#### Для правок sync automation

Читать только:

- `.github/workflows/ensure-issue-project-link.yml`
- `.codex/routing/_shared/scripts/ensure_issue_project_link.py`
- при необходимости `.codex/routing/_shared/lib/common.py`

## Критическое замечание

Шаблон уже хорошо разделен по стадиям и ролям, но без этого README навигация действительно неочевидна: рабочая логика спрятана в скрытых каталогах `.codex` и `.github`, а верхний уровень почти пустой. Поэтому дальнейшие правки разумно вести от этого файла как от index-документа.

Для этого workflow важно помнить: initialization завершается только после git commit, push в default branch и применения защиты default branch, а initiating task является подготовленной BA-задачей для `issue_driven`, а не работой текущей стадии.
