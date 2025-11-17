# FastAPI Backend для обработки таблиц

Бэкенд на FastAPI для загрузки и обработки таблиц в форматах CSV, JSON и Excel.

## Структура проекта

```
back/
├── app/
│   ├── __init__.py
│   ├── main.py              # Главный файл FastAPI приложения
│   ├── routers/
│   │   ├── __init__.py
│   │   └── tables.py        # Роутер для работы с таблицами
│   ├── services/
│   │   ├── __init__.py
│   │   ├── storage.py       # Глобальное хранилище в памяти
│   │   └── analytics.py     # Заглушка для аналитики
│   └── utils/
│       ├── __init__.py
│       └── file_parser.py   # Утилиты для парсинга файлов
├── main.py                   # Точка входа для запуска
├── requirements.txt          # Зависимости
└── README.md                 # Документация
```

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Запуск

### Вариант 1: Через main.py
```bash
python main.py
```

### Вариант 2: Через uvicorn напрямую
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: `http://localhost:8000`

## API Эндпоинты

### 1. Загрузка таблицы
**POST** `/api/tables/upload`

Загружает таблицу в систему. Поддерживает форматы: CSV, JSON, Excel (xlsx, xls).

**Request:**
- Content-Type: `multipart/form-data`
- Body: файл (file)

**Response:**
```json
{
  "table_id": "uuid",
  "filename": "example.csv",
  "file_type": "csv",
  "shape": {
    "rows": 100,
    "columns": 5
  },
  "columns": ["col1", "col2", "col3"],
  "message": "Таблица успешно загружена и обработана"
}
```

### 2. Получение таблицы
**GET** `/api/tables/{table_id}`

Получает таблицу по ID.

**Response:**
```json
{
  "id": "uuid",
  "filename": "example.csv",
  "file_type": "csv",
  "data": [...],
  "columns": ["col1", "col2"],
  "shape": {
    "rows": 100,
    "columns": 5
  },
  "created_at": "2024-01-01T00:00:00",
  "metadata": {
    "analytics_processed": true,
    "analytics_status": "stub"
  }
}
```

### 3. Список всех таблиц
**GET** `/api/tables/`

Получает список всех загруженных таблиц (без полных данных).

**Response:**
```json
{
  "count": 2,
  "tables": [
    {
      "table_id": "uuid1",
      "filename": "example1.csv",
      "file_type": "csv",
      "shape": {...},
      "columns": [...],
      "created_at": "..."
    }
  ]
}
```

### 4. Удаление таблицы
**DELETE** `/api/tables/{table_id}`

Удаляет таблицу по ID.

**Response:**
```json
{
  "message": "Таблица {table_id} успешно удалена"
}
```

### 5. Корневой эндпоинт
**GET** `/`

Возвращает информацию об API.

### 6. Health check
**GET** `/health`

Проверка здоровья приложения.

## Особенности

- **Глобальное хранилище**: Данные хранятся в памяти Python (класс `TableStorage`)
- **Заглушка аналитики**: Таблицы отправляются в аналитику, но пока возвращаются без изменений
- **Поддержка форматов**: CSV, JSON, Excel (xlsx, xls)
- **CORS**: Настроен для работы с фронтендом

## Примеры использования

### Загрузка CSV файла через curl:
```bash
curl -X POST "http://localhost:8000/api/tables/upload" \
  -F "file=@data.csv"
```

### Получение таблицы:
```bash
curl "http://localhost:8000/api/tables/{table_id}"
```

### Список всех таблиц:
```bash
curl "http://localhost:8000/api/tables/"
```

## Документация API

После запуска приложения доступна интерактивная документация:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

