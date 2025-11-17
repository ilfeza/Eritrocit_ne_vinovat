# Развертывание на хостинге

Подробная инструкция по развертыванию приложения на сервере (VPS, облачный хостинг).

## 📋 Требования к серверу

### Минимальные требования

- **ОС**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- **RAM**: 2 GB (рекомендуется 4 GB)
- **CPU**: 2 ядра (рекомендуется 4)
- **Диск**: 20 GB свободного места
- **Docker**: версия 20.10+
- **Docker Compose**: версия 2.0+

### Рекомендуемые требования

- **RAM**: 4-8 GB
- **CPU**: 4+ ядер
- **Диск**: 50+ GB SSD
- **Сеть**: статический IP-адрес

---

## 🚀 Подготовка сервера

### 1. Подключение к серверу

```bash
# Подключение по SSH
ssh root@your-server-ip

# Или с указанием ключа
ssh -i ~/.ssh/your-key.pem root@your-server-ip
```

### 2. Обновление системы

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### 3. Установка Docker

#### Ubuntu/Debian

```bash
# Удаление старых версий (если есть)
sudo apt remove docker docker-engine docker.io containerd runc

# Установка зависимостей
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Добавление официального GPG ключа
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Добавление репозитория
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Проверка установки
docker --version
docker compose version
```

#### CentOS/RHEL

```bash
# Установка зависимостей
sudo yum install -y yum-utils

# Добавление репозитория
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Установка Docker
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker

# Проверка
docker --version
docker compose version
```

### 4. Настройка пользователя (опционально)

```bash
# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Применение изменений (перелогин или)
newgrp docker
```

---

## 📦 Загрузка проекта на сервер

### Вариант 1: Через Git (рекомендуется)

```bash
# Установка Git (если не установлен)
sudo apt install -y git  # Ubuntu/Debian
sudo yum install -y git  # CentOS

# Клонирование репозитория
git clone <your-repo-url>
cd Eritrocit_ne_vinovat
```

### Вариант 2: Через SCP/SFTP

```bash
# С локальной машины
scp -r /path/to/Eritrocit_ne_vinovat root@your-server-ip:/root/

# Или используйте FileZilla, WinSCP и т.д.
```

### Вариант 3: Через архив

```bash
# На локальной машине
tar -czf project.tar.gz Eritrocit_ne_vinovat/

# Загрузка на сервер
scp project.tar.gz root@your-server-ip:/root/

# На сервере
cd /root
tar -xzf project.tar.gz
cd Eritrocit_ne_vinovat
```

---

## 🔧 Настройка файрвола

### Ubuntu/Debian (UFW)

```bash
# Установка UFW (если не установлен)
sudo apt install -y ufw

# Разрешение SSH (важно сделать первым!)
sudo ufw allow 22/tcp

# Разрешение HTTP
sudo ufw allow 80/tcp

# Разрешение HTTPS (если планируете использовать)
sudo ufw allow 443/tcp

# Включение файрвола
sudo ufw enable

# Проверка статуса
sudo ufw status
```

### CentOS/RHEL (firewalld)

```bash
# Разрешение HTTP
sudo firewall-cmd --permanent --add-service=http

# Разрешение HTTPS (если нужно)
sudo firewall-cmd --permanent --add-service=https

# Применение изменений
sudo firewall-cmd --reload

# Проверка
sudo firewall-cmd --list-all
```

---

## 🚀 Запуск приложения

### 1. Переход в директорию проекта

```bash
cd /root/Eritrocit_ne_vinovat
# Или путь, куда вы загрузили проект
```

### 2. Запуск контейнеров

```bash
# Сборка и запуск
docker compose up -d --build

# Проверка статуса
docker compose ps
```

### 3. Проверка работы

```bash
# Проверка health endpoint
curl http://localhost/health

# Проверка через IP
curl http://YOUR_SERVER_IP/health
```

---

## 🌐 Настройка домена (DNS)

### Шаг 1: Узнайте IP-адрес сервера

```bash
# На сервере
curl ifconfig.me

# Или
hostname -I
```

### Шаг 2: Настройка DNS записи

Зайдите в панель управления вашего домена (где покупали домен):

#### Добавление A-записи

| Поле | Значение | Пример |
|------|----------|--------|
| **Тип** | `A` | A |
| **Имя/Хост** | `@` (или пусто) | @ |
| **Значение/IP** | IP вашего сервера | 123.45.67.89 |
| **TTL** | По умолчанию | 3600 |

#### Добавление www (опционально)

| Поле | Значение | Пример |
|------|----------|--------|
| **Тип** | `A` | A |
| **Имя/Хост** | `www` | www |
| **Значение/IP** | Тот же IP | 123.45.67.89 |
| **TTL** | По умолчанию | 3600 |

### Шаг 3: Ожидание распространения DNS

DNS изменения распространяются **5-30 минут** (иногда до часа).

### Шаг 4: Проверка

```bash
# С вашего компьютера
ping yourdomain.com

# Должен показать IP вашего сервера
```

### Шаг 5: Доступ к приложению

После настройки DNS приложение будет доступно:
- `http://yourdomain.com/`
- `http://yourdomain.com/api/docs`

**Важно**: Nginx уже настроен для работы с любым доменом, дополнительная настройка не требуется!

---

## 🔒 Настройка HTTPS (SSL/TLS)

### Использование Let's Encrypt (Certbot)

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx  # Ubuntu/Debian
sudo yum install -y certbot python3-certbot-nginx  # CentOS

# Получение сертификата
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Автоматическое обновление
sudo certbot renew --dry-run
```

Certbot автоматически настроит Nginx для HTTPS.

### Ручная настройка Nginx для HTTPS

Если нужно настроить вручную, отредактируйте `nginx.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... остальная конфигурация
}
```

---

## 🛠️ Управление приложением

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Только backend
docker compose logs -f backend

# Только frontend
docker compose logs -f frontend

# Последние 100 строк
docker compose logs --tail=100 backend
```

### Перезапуск

```bash
# Перезапуск всех сервисов
docker compose restart

# Перезапуск конкретного сервиса
docker compose restart backend
```

### Обновление приложения

```bash
# 1. Остановка
docker compose down

# 2. Обновление кода
git pull  # если используете Git
# Или загрузите новые файлы

# 3. Пересборка и запуск
docker compose up -d --build
```

### Остановка

```bash
# Остановка контейнеров
docker compose stop

# Остановка и удаление контейнеров
docker compose down
```

---

## 💾 Резервное копирование

### Автоматическое резервное копирование

Создайте скрипт `/root/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
PROJECT_DIR="/root/Eritrocit_ne_vinovat"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Резервная копия данных
tar -czf $BACKUP_DIR/data_$DATE.tar.gz $PROJECT_DIR/back/data/

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +7 -delete

echo "Backup completed: data_$DATE.tar.gz"
```

Сделайте скрипт исполняемым:

```bash
chmod +x /root/backup.sh
```

Добавьте в cron (ежедневно в 2:00):

```bash
crontab -e

# Добавьте строку:
0 2 * * * /root/backup.sh >> /var/log/backup.log 2>&1
```

### Восстановление из резервной копии

```bash
# Остановка приложения
docker compose down

# Восстановление данных
tar -xzf /root/backups/data_YYYYMMDD_HHMMSS.tar.gz -C /root/Eritrocit_ne_vinovat/

# Запуск
docker compose up -d
```

---

## 📊 Мониторинг

### Проверка использования ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
df -h

# Использование памяти
free -h
```

### Health checks

```bash
# Проверка backend
curl http://yourdomain.com/health

# Автоматическая проверка (скрипт)
#!/bin/bash
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED"
    # Можно добавить уведомление
fi
```

### Настройка мониторинга (опционально)

Можно использовать:
- **Prometheus + Grafana**
- **Uptime Robot** (внешний мониторинг)
- **Sentry** (мониторинг ошибок)

---

## 🔐 Безопасность

### 1. Ограничение CORS

Отредактируйте `back/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Вместо ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Ограничение размера файлов

В `nginx.conf` уже установлено:
```nginx
client_max_body_size 100M;
```

### 3. Регулярные обновления

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Обновление Docker образов
docker compose pull
docker compose up -d --build
```

### 4. SSH безопасность

```bash
# Отключение входа по паролю (только ключи)
sudo nano /etc/ssh/sshd_config
# Установите: PasswordAuthentication no

# Перезапуск SSH
sudo systemctl restart sshd
```

---

## 🐛 Решение проблем

### Контейнеры не запускаются

```bash
# Проверка логов
docker compose logs

# Проверка статуса
docker compose ps -a

# Проверка портов
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :8000
```

### Ошибки подключения к API

```bash
# Проверка, что контейнеры запущены
docker compose ps

# Проверка логов backend
docker compose logs backend

# Проверка сетевого подключения
docker compose exec backend curl http://localhost:8000/health
```

### Проблемы с DNS

```bash
# Проверка DNS
nslookup yourdomain.com

# Проверка с сервера
curl -I http://yourdomain.com

# Если не работает, проверьте настройки DNS в панели домена
```

### Нехватка места на диске

```bash
# Проверка использования диска
df -h

# Очистка Docker
docker system prune -a --volumes

# Очистка старых логов
sudo journalctl --vacuum-time=7d
```

### Высокое использование памяти

```bash
# Проверка использования памяти
free -h
docker stats

# Ограничение памяти для контейнеров (в docker-compose.yml)
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 📈 Масштабирование

### Горизонтальное масштабирование

Для увеличения производительности можно запустить несколько экземпляров backend:

```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      replicas: 3
```

Или использовать load balancer (Nginx, Traefik).

### Вертикальное масштабирование

Увеличьте ресурсы сервера (RAM, CPU) через панель управления хостингом.

---

## 🔄 Автоматический перезапуск

Docker Compose автоматически перезапускает контейнеры при сбое (благодаря `restart: unless-stopped` в `docker-compose.yml`).

Для дополнительной надежности можно использовать:

```bash
# Systemd service (создайте /etc/systemd/system/biodash.service)
[Unit]
Description=BioDash Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/root/Eritrocit_ne_vinovat
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

# Активация
sudo systemctl enable biodash
sudo systemctl start biodash
```

---

## 📝 Чеклист развертывания

- [ ] Сервер подготовлен (Docker установлен)
- [ ] Проект загружен на сервер
- [ ] Файрвол настроен (порты 80, 443 открыты)
- [ ] Контейнеры запущены (`docker compose up -d --build`)
- [ ] Приложение доступно по IP
- [ ] DNS записи настроены (если есть домен)
- [ ] HTTPS настроен (если нужно)
- [ ] Резервное копирование настроено
- [ ] Мониторинг настроен
- [ ] Безопасность проверена

---

## 📚 Дополнительная информация

- [Локальное развертывание](README_LOCAL.md)
- [DNS инструкция](DNS_ИНСТРУКЦИЯ.md)
- [Основной README](../README.MD)
- [Docker README](DOCKER_README.md)

---

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker compose logs`
2. Проверьте статус: `docker compose ps`
3. Проверьте документацию выше
4. Проверьте [Решение проблем](#-решение-проблем)

---

**Версия**: 1.0  
**Последнее обновление**: 2024

