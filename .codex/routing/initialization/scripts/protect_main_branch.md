# protect_main_branch.py

## Назначение

Скрипт применяет каноническую protection-policy к удалённой default branch репозитория.
Политика запрещает прямой push за счёт обязательного pull request, включает
ограничение для администраторов и отключает force push.

## Контекст применения

Это финальный mutation-шаг стадии `initialization`. Его нужно запускать только
после того, как репозиторий, GitHub Project и initiating task уже созданы, а
изменения локально подготовлены и запушены в удалённый репозиторий.

Если удалённой default branch ещё нет, скрипт не падает с ошибкой, а возвращает
явный статус ожидания предусловия.

## Внешние зависимости

- `gh`
- GitHub origin remote в локальном репозитории
- доступ к GitHub API через токен из `GH_TOKEN`, `GITHUB_TOKEN` или `gh auth token`
- общий модуль `.codex/routing/_shared/lib/common.py`

## Предусловия

- `origin` должен указывать на GitHub repository;
- на GitHub должна существовать удалённая default branch;
- если ветка ещё не запушена, выполнение считается неошибочным и скрипт
  возвращает статус ожидания.

## Алгоритм работы

1. Определяет корень репозитория и читает `origin`.
2. Извлекает `owner/name` репозитория из `origin`.
3. Проверяет, существует ли удалённая default branch.
4. Если ветки ещё нет, печатает JSON со статусом `awaiting_default_branch_push`
   и завершает выполнение без mutation.
5. Если protection уже соответствует канонической политике, печатает JSON со
   статусом `already_protected`.
6. Если protection отсутствует или не совпадает с политикой, отправляет `PUT`
   в GitHub REST API и применяет стандартную конфигурацию.
7. После применения повторно проверяет состояние и печатает JSON с итоговым
   статусом `applied`.
8. При GitHub-ошибках печатает JSON со статусом `error`.

## Формат результата

Скрипт печатает JSON-объект. Основные поля:

- `status`
- `awaiting_default_branch_push`
  - `already_protected`
  - `applied`
  - `error`
- `repository_full_name`
- `default_branch_name`
- `changed`
- `default_branch_exists`
- `default_branch_protection_present`
- `default_branch_protection_ok`
- `policy`

## Коды завершения

- `0` — protection уже была корректной, была успешно применена, либо default
  branch ещё не существует;
- `2` — отсутствует GitHub origin remote;
- `3` — ошибка GitHub API, токена или несоответствие после попытки применения.

## Инварианты

- Скрипт идемпотентен: повторный запуск при уже настроенной policy не меняет
  состояние GitHub.
- Скрипт не создаёт ветку; он работает только с уже существующей удалённой
  default branch.
- Политика считается корректной только тогда, когда direct push заблокирован
  через обязательный pull request и администраторы не могут обойти restriction.
