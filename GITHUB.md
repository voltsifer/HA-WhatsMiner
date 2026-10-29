# GitHub и HACS

Репозиторий проекта: **https://github.com/voltsifer/HA-WhatsMiner**.

## Установка и обновления

1. HACS → меню ⋮ → «Пользовательские репозитории».
2. Добавьте `https://github.com/voltsifer/HA-WhatsMiner`, тип **Integration**.
3. Скачайте HA-WhatsMiner и перезапустите Home Assistant.
4. Настройки → Устройства и службы → Добавить интеграцию → **HA-WhatsMiner**.

HACS устанавливает единственную интеграцию `custom_components/whatsminer_local`, включая JS карточки. Второй репозиторий для карточки не нужен. Подключение её ресурса описано в [HEATMAP.md](HEATMAP.md).

Пока нет GitHub Release, установка выполняется из ветки по умолчанию. Статус проверок доступен на вкладке **Actions**. Публикация в общий каталог HACS — отдельная процедура, для установки по URL она не требуется и здесь не заявляется выполненной.

## Для разработки

Исходники интеграции находятся в `custom_components/whatsminer_local`. Тесты — в `tests`; workflow — `.github/workflows/tests.yml`. Версия указана в manifest. WEB-адаптер экспериментальный: для поддержки конкретной прошивки нужен фактический ответ с отдельными температурами.

При переносе в другой репозиторий `tools/configure_repository.py` меняет только локальные ссылки и codeowners. Он не создаёт репозиторий и не публикует файлы.

HACS работает с публичными репозиториями. Пароли и Cookie вводятся в Home Assistant; реальные данные доступа в репозиторий не включены.

Источники:

- https://www.hacs.xyz/docs/publish/integration/
- https://www.hacs.xyz/docs/faq/custom_repositories/
- https://www.hacs.xyz/docs/faq/private_repositories/
