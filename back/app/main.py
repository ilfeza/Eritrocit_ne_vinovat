"""
Главный файл FastAPI приложения.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import tables, demo

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Создаем приложение FastAPI
app = FastAPI(
    title="Table Processing API",
    description="API для загрузки и обработки таблиц",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(tables.router)
app.include_router(demo.router)


@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "message": "Table Processing API",
        "version": "1.0.0",
        "endpoints": {
            "upload_table": "/api/tables/upload",
            "get_table": "/api/tables/{table_id}",
            "list_tables": "/api/tables/",
            "delete_table": "/api/tables/{table_id}",
            "get_pie_chart": "/api/tables/{table_id}/pie-chart",
            "check_reference_values": "/api/tables/{table_id}/reference-check"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья приложения."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

