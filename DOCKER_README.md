# Инструкция по развертыванию с Docker

## Быстрый старт (локально)

1. **Соберите и запустите контейнеры:**
   ```bash
   docker-compose up -d --build
   ```

2. **Проверьте статус контейнеров:**
   ```bash
   docker-compose ps
   ```

3. **Откройте приложение в браузере:**
   - Фронтенд: http://localhost/
   - API документация: http://localhost/api/docs
   - Health check: http://localhost/health

## Развертывание на хостинге

**См. подробную инструкцию в файле [DEPLOY.md](DEPLOY.md)**

### Основные шаги:

1. Загрузите проект на сервер
2. Убедитесь, что установлены Docker и Docker Compose
3. Запустите: `docker-compose up -d --build`
4. **Если у вас есть домен:** Настройте DNS записи (см. подробности в DEPLOY.md)
   - В панели управления доменом добавьте A-запись: `@` → IP вашего сервера
5. Приложение будет доступно:
   - По IP: `http://YOUR_SERVER_IP/`
   - По домену: `http://yourdomain.com/` (после настройки DNS)

**Nginx настроен для работы с любым доменом**, поэтому дополнительная настройка не требуется.

## Остановка

```bash
docker-compose down
```

## Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только бэкенд
docker-compose logs -f backend

# Только фронтенд
docker-compose logs -f frontend
```

## Пересборка после изменений

```bash
docker-compose up -d --build
```

## Структура

- **Backend**: FastAPI приложение на порту 8000 (внутри контейнера)
- **Frontend**: Nginx сервер на порту 80, отдает статику и проксирует API запросы
- **Данные**: Сохраняются в `./back/data/` (монтируется как volume)

## Порты

- `80` - Фронтенд (nginx)
- `8000` - Backend API (доступен напрямую, если нужно)

## Переменные окружения

Можно добавить в `docker-compose.yml` в секцию `backend.environment`:
- `PYTHONUNBUFFERED=1` - уже установлено для корректного логирования

