# Glossary: Expressa domain

## Metadata
- Canonical path: `docs/business/glossary/expressa-domain.md`

## Scope
Этот glossary фиксирует основные бизнес-термины продукта Expressa v1 для домена заказа на выдачу, обработки заказов и операционного управления меню. Технические детали реализации, API и инфраструктурные термины в этот файл не входят.

## Terms

### Expressa
- Definition: Telegram-центричная платформа заказа на выдачу для бара кафетерия с customer-интерфейсом и единым backoffice.
- Context: Общее название продукта и его бизнес-границы в v1.
- Do not use for: Отдельный бот, отдельный frontend или только backend.
- Related terms: Customer, Barista, Administrator, Backoffice.

### Customer
- Definition: Пользователь кафетерия, оформляющий заказ на выдачу через customer-бот и customer web app.
- Context: Роль клиентского контура.
- Synonyms: Клиент.
- Do not use for: Barista или administrator.
- Related terms: Customer bot, Order, Cart.

### Barista
- Definition: Сотрудник, который обрабатывает заказ, подтверждает или отклоняет его, отмечает готовность и закрывает после выдачи.
- Context: Операционная роль backoffice.
- Do not use for: Administrator, если требуется ссылка именно на исполнителя заказа.
- Related terms: Backoffice, Order status, Audit.

### Administrator
- Definition: Пользователь backoffice с расширенными правами на управление меню, настройками, ролями и блокировкой пользователей.
- Context: Административная роль продукта.
- Synonyms: Admin.
- Do not use for: Главный administrator, если требуется подчеркнуть специальный способ назначения через env.
- Related terms: Backoffice, Working hours, Slot capacity.

### Customer bot
- Definition: Telegram-бот, через который customer открывает customer web app и получает уведомления по заказу.
- Context: Канал входа и уведомлений для customer.
- Do not use for: Backoffice bot.
- Related terms: Customer, Telegram authorization.

### Backoffice bot
- Definition: Отдельный Telegram-бот, через который barista и administrator открывают backoffice и получают служебные уведомления.
- Context: Канал входа и уведомлений для операционных ролей.
- Do not use for: Customer bot.
- Related terms: Backoffice, Barista, Administrator.

### Backoffice
- Definition: Единый web-интерфейс для ролей barista и administrator с ролевым разграничением вкладок и действий.
- Context: Операционный контур продукта.
- Do not use for: Customer web app.
- Related terms: Barista, Administrator, Availability, Settings.

### Menu group
- Definition: Категория меню, объединяющая товары одной бизнес-группы и задающая общие группы дополнительных опций для входящих товаров.
- Context: Каталог и администрирование меню.
- Synonyms: Категория меню, группа товаров.
- Do not use for: Отдельный товар или группу дополнительных опций.
- Related terms: Menu item, Option group.

### Menu item
- Definition: Товар, который customer может выбрать и добавить в корзину.
- Context: Каталог customer и управление меню administrator.
- Synonyms: Товар, позиция меню.
- Do not use for: Дополнительную опцию.
- Related terms: Menu group, Size, Option group.

### Size
- Definition: Обязательный вариант объёма напитка `S`, `M` или `L`, влияющий на цену товара.
- Context: Выбор напитков перед добавлением в корзину.
- Do not use for: Количество единиц товара в корзине.
- Related terms: Menu item, Cart line.

### Option group
- Definition: Группа дополнительных опций, назначенная группе меню и доступная для выбора у товаров этой группы.
- Context: Настройка товара перед добавлением в корзину.
- Synonyms: Группа допов, группа дополнительных опций.
- Do not use for: Категорию меню или самостоятельный товар.
- Related terms: Option, Menu group.

### Option
- Definition: Дополнительная настройка товара, которая может быть платной, бесплатной или взаимоисключающейся внутри своей группы.
- Context: Конфигурация товара customer и управление доступностью.
- Synonyms: Доп, дополнительная опция.
- Do not use for: Самостоятельную позицию меню.
- Related terms: Option group, Availability.

### Cart
- Definition: Набор выбранных customer товаров с их настройками, количеством и итогами до создания заказа.
- Context: Путь customer до оформления заказа.
- Synonyms: Корзина.
- Do not use for: Уже созданный заказ.
- Related terms: Cart line, Order.

### Order
- Definition: Зафиксированный customer заказ на выдачу, созданный из корзины и привязанный к временному слоту.
- Context: Основная бизнес-сущность обработки и выдачи.
- Synonyms: Заказ.
- Do not use for: Черновик выбора товаров до оформления.
- Related terms: Order status, Slot, Audit.

### Order status
- Definition: Бизнес-состояние заказа в жизненном цикле `Создан`, `Подтвержден`, `Отклонен`, `Готов к выдаче`, `Закрыт`.
- Context: Обработка заказа, уведомления и логика вместимости слота.
- Do not use for: Технический статус фоновой операции.
- Related terms: Order, Active order.

### Slot
- Definition: Временной интервал выдачи заказа длительностью 10 минут внутри рабочих часов текущего дня.
- Context: Оформление заказа и контроль операционной нагрузки.
- Synonyms: Временной слот, слот выдачи.
- Do not use for: Любой произвольный период времени вне логики выдачи заказа.
- Related terms: Working hours, Slot capacity, Active order.

### Slot capacity
- Definition: Максимальное число активных заказов, которые могут быть назначены на один слот.
- Context: Планирование нагрузки на выдачу.
- Do not use for: Общее количество заказов за день.
- Related terms: Slot, Active order.

### Active order
- Definition: Заказ, который занимает вместимость слота, пока находится в статусе `Создан`, `Подтвержден` или `Готов к выдаче`.
- Context: Правила расчёта доступности слотов.
- Do not use for: Заказы в статусах `Отклонен` и `Закрыт`.
- Related terms: Order, Order status, Slot capacity.

### Working hours
- Definition: Интервал времени, в пределах которого доступны слоты выдачи заказов в конкретный день.
- Context: Операционные настройки продукта.
- Synonyms: Рабочие часы.
- Do not use for: График смен barista.
- Related terms: Slot, Slot capacity.

### Availability
- Definition: Временное состояние доступности товара или дополнительной опции для выбора customer.
- Context: Операционное управление menu item и option без изменения структуры меню.
- Synonyms: Доступность.
- Do not use for: Права доступа пользователя.
- Related terms: Menu item, Option, Backoffice.

### Audit
- Definition: Бизнес-фиксация того, какой barista выполнил ключевое действие по заказу.
- Context: Контроль ответственности и история обработки заказа.
- Do not use for: Полный технический журнал системы.
- Related terms: Order, Barista, Order status.

### Blocked user
- Definition: Пользователь, которому administrator запретил использование продукта независимо от его исходной роли.
- Context: Управление доступом.
- Do not use for: Пользователя без назначенной операционной роли.
- Related terms: Administrator, Telegram authorization.

## Open questions
- Не зафиксировано, требуется ли отдельный термин для главного administrator как отличной бизнес-роли или достаточно рассматривать его как способ первичного назначения administrator.
