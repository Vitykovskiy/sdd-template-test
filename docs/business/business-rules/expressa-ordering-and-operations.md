# Business Rules: Expressa ordering and operations

## Metadata
- Canonical path: `docs/business/business-rules/expressa-ordering-and-operations.md`

## Scope
Этот набор правил покрывает бизнес-решения и ограничения для каталога, корзины, оформления заказа, слотов, жизненного цикла заказа, ролей доступа и операционного управления Expressa v1.

## Rule register

### EXP-BR-001: Customer access is Telegram-based
- Statement: Любой пользователь, активировавший customer bot, получает роль customer и доступ к customer web app, если он не заблокирован.
- Applies when: Пользователь входит в customer-контур продукта.
- Does not apply when: Пользователь заблокирован administrator или используется test environment с отключённой Telegram-аутентификацией.
- Source: Product requirements v1, section 3, 4, FR-024, NFR-015.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-002: Blocked users cannot use the product
- Statement: Пользователь, заблокированный administrator, не может пользоваться приложением.
- Applies when: Пользователь пытается войти или использовать customer либо backoffice-контур.
- Does not apply when: Пользователь не находится в состоянии блокировки.
- Source: Product requirements v1, section 3, FR-025, FR-030.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-003: Customer order is pickup-only in v1
- Statement: Customer оформляет только заказ на выдачу, а оплата выполняется офлайн при получении.
- Applies when: Customer создаёт заказ в v1.
- Does not apply when: Рассматриваются будущие версии продукта вне границ v1.
- Source: Product requirements v1, section 2, FR-022, v1 scope.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-004: Menu is grouped by categories
- Statement: Меню должно быть организовано по menu group, а customer просматривает товары внутри категорий.
- Applies when: Customer просматривает каталог или administrator управляет структурой меню.
- Does not apply when: Рассматривается отдельная карточка уже выбранного товара.
- Source: Product requirements v1, FR-001, FR-028.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-005: Drink size is mandatory and price-dependent
- Statement: Для напитков customer обязан выбрать размер `S`, `M` или `L`, и цена товара зависит от выбранного размера.
- Applies when: Customer добавляет напиток в корзину.
- Does not apply when: Товар не относится к напиткам.
- Source: Product requirements v1, FR-003.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-006: Options are inherited through the menu group
- Statement: Группа дополнительных опций назначается на menu group и распространяется на все товары внутри этой группы.
- Applies when: Administrator настраивает каталог или customer настраивает товар.
- Does not apply when: Для товарной группы не задана ни одна группа дополнительных опций.
- Source: Product requirements v1, FR-004, FR-008, assumptions.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-007: Options may be paid, free or mutually exclusive
- Statement: Дополнительные опции могут быть платными или бесплатными, а внутри одной option group система должна поддерживать взаимоисключающие варианты.
- Applies when: Customer настраивает товар перед добавлением в корзину.
- Does not apply when: Для товара нет доступных дополнительных опций.
- Source: Product requirements v1, FR-005, FR-006, FR-007.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-008: Cart remains editable until order creation
- Statement: Customer может просматривать и редактировать корзину до момента создания заказа.
- Applies when: Товары уже добавлены в корзину, но заказ ещё не создан.
- Does not apply when: Заказ уже создан из корзины.
- Source: Product requirements v1, FR-009.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-009: Order must be assigned to an available slot
- Statement: Заказ может быть создан только с выбранным доступным слотом текущего дня.
- Applies when: Customer оформляет заказ.
- Does not apply when: Customer только редактирует корзину без оформления.
- Source: Product requirements v1, FR-010, FR-012.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-010: Slots use operating hours and fixed interval
- Statement: Слоты представляют собой интервалы по 10 минут внутри действующих рабочих часов.
- Applies when: Система формирует список доступных слотов.
- Does not apply when: Рабочие часы на день отсутствуют из-за отдельного операционного решения, не описанного в v1.
- Source: Product requirements v1, FR-011, FR-013.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-011: Slot capacity is limited by active orders
- Statement: Вместимость одного слота по умолчанию равна 5 активным заказам и может быть изменена administrator.
- Applies when: Система определяет доступность слота.
- Does not apply when: Вместимость не достигнута или administrator изменил дефолтное значение.
- Source: Product requirements v1, FR-014.
- Impacted scenarios: `customer-place-pickup-order`, `administrator-manage-menu-and-operations`

### EXP-BR-012: Only active orders occupy slot capacity
- Statement: Заказы в статусах `Создан`, `Подтвержден` и `Готов к выдаче` занимают вместимость слота, а заказы в статусах `Отклонен` и `Закрыт` её не занимают.
- Applies when: Система пересчитывает доступность слота или меняет статус заказа.
- Does not apply when: Заказ ещё не создан.
- Source: Product requirements v1, FR-015, FR-016.
- Impacted scenarios: `customer-place-pickup-order`, `barista-process-order`

### EXP-BR-013: Order lifecycle starts from Created
- Statement: После оформления заказ сразу получает статус `Создан`.
- Applies when: Customer завершает оформление заказа.
- Does not apply when: Заказ не был успешно создан.
- Source: Product requirements v1, FR-017, FR-018.
- Impacted scenarios: `customer-place-pickup-order`

### EXP-BR-014: Only barista rejects an order and must record reason
- Statement: Только barista может перевести заказ в статус `Отклонен`, и причина отклонения должна быть сохранена.
- Applies when: Заказ ожидает решения по обработке.
- Does not apply when: Заказ подтверждается или закрывается без отклонения.
- Source: Product requirements v1, FR-019.
- Impacted scenarios: `barista-process-order`

### EXP-BR-015: Barista controls operational order progression
- Statement: Barista может подтвердить заказ, перевести его в статус `Готов к выдаче` и закрыть после офлайн-выдачи.
- Applies when: Заказ находится в операционной обработке.
- Does not apply when: Пользователь не имеет роли barista.
- Source: Product requirements v1, FR-020.
- Impacted scenarios: `barista-process-order`

### EXP-BR-016: Customer is informed about order status changes
- Statement: Customer получает Telegram-уведомления о смене статуса заказа, а уведомление об отклонении должно содержать причину отказа.
- Applies when: Статус заказа изменяется после создания.
- Does not apply when: Статус заказа не изменился.
- Source: Product requirements v1, FR-023.
- Impacted scenarios: `customer-place-pickup-order`, `barista-process-order`

### EXP-BR-017: Backoffice access is role-based through a separate bot
- Statement: Доступ к backoffice выполняется через отдельный Telegram-бот, а доступные вкладки и действия зависят от роли пользователя.
- Applies when: Barista или administrator работают с backoffice.
- Does not apply when: Рассматривается customer-контур.
- Source: Product requirements v1, BR-002, BR-003, FR-035.
- Impacted scenarios: `barista-process-order`, `administrator-manage-menu-and-operations`

### EXP-BR-018: Administrator governs menu and operational settings
- Statement: Administrator управляет структурой меню, товарами, ценами, рабочими часами, вместимостью слотов, ролями пользователей и блокировкой пользователей.
- Applies when: Требуется постоянное изменение каталогов, настроек или доступов.
- Does not apply when: Нужно только временно менять доступность товаров и опций.
- Source: Product requirements v1, FR-028, FR-029, FR-030.
- Impacted scenarios: `administrator-manage-menu-and-operations`

### EXP-BR-019: Barista may change availability but not menu structure
- Statement: Barista может временно менять доступность позиций меню и дополнительных опций, но не может менять цены и структуру меню.
- Applies when: Требуется оперативно скрыть или вернуть товар либо опцию.
- Does not apply when: Требуется изменение каталога, цен или системных настроек.
- Source: Product requirements v1, FR-031, FR-035.
- Impacted scenarios: `barista-process-order`, `administrator-manage-menu-and-operations`

### EXP-BR-020: Key barista actions are auditable
- Statement: Система должна фиксировать, какой barista подтвердил заказ, перевёл его в `Готов к выдаче` и отклонил заказ.
- Applies when: Выполняется одно из ключевых действий barista по заказу.
- Does not apply when: Заказ только создаётся customer или закрывается без требования к отдельной фиксации в текущем наборе правил.
- Source: Product requirements v1, FR-032, FR-033, FR-034.
- Impacted scenarios: `barista-process-order`

### EXP-BR-021: One main administrator is bootstrapped from environment
- Statement: Главный administrator задаётся через `ADMIN_TELEGRAM_ID`, создаётся при старте backend при отсутствии в БД и не должен дублироваться при повторном старте.
- Applies when: Система инициализируется или запускается на пустой либо существующей базе.
- Does not apply when: Назначаются остальные administrator вручную из backoffice.
- Source: Product requirements v1, FR-026.
- Impacted scenarios: `administrator-manage-menu-and-operations`

### EXP-BR-022: Barista receives reminders for orders awaiting action
- Statement: Barista получает периодические Telegram-напоминания о заказах, ожидающих действий.
- Applies when: В системе есть заказы, требующие реакции barista.
- Does not apply when: Нет заказов, ожидающих действий.
- Source: Product requirements v1, FR-027.
- Impacted scenarios: `barista-process-order`

## Exceptions
- В test environment Telegram-аутентификация может быть отключена через `DISABLE_TG_AUTH=true`; это исключение относится только к тестированию и не меняет production-правила доступа.
- Точная периодичность напоминаний barista пока не зафиксирована и не ограничивает сам факт обязательности напоминаний.

## Open questions
- Нужно ли фиксировать в бизнес-аудите также barista, закрывшего заказ, или для v1 достаточно подтверждения, отклонения и перевода в `Готов к выдаче`.
