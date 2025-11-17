"""
Глобальное хранилище для таблиц в памяти.
Используется вместо базы данных.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

# Глобальное хранилище кэша (капсом)
STORAGE: Dict[str, Dict[str, Any]] = {}


def save_table(table_data: Dict[str, Any]) -> str:
    """
    Сохраняет таблицу в хранилище.
    
    Args:
        table_data: Словарь с данными таблицы (data, columns, etc.)
        
    Returns:
        ID сохраненной таблицы
    """
    table_id = str(uuid.uuid4())
    table_data['id'] = table_id
    table_data['created_at'] = datetime.now().isoformat()
    STORAGE[table_id] = table_data
    return table_id


def get_table(table_id: str) -> Optional[Dict[str, Any]]:
    """
    Получает таблицу по ID.
    
    Args:
        table_id: ID таблицы
        
    Returns:
        Данные таблицы или None, если не найдена
    """
    return STORAGE.get(table_id)


def get_all_tables() -> Dict[str, Dict[str, Any]]:
    """
    Получает все таблицы.
    
    Returns:
        Словарь всех таблиц
    """
    return STORAGE.copy()


def delete_table(table_id: str) -> bool:
    """
    Удаляет таблицу по ID.
    
    Args:
        table_id: ID таблицы
        
    Returns:
        True если удалена, False если не найдена
    """
    if table_id in STORAGE:
        del STORAGE[table_id]
        return True
    return False


def update_table(table_id: str, table_data: Dict[str, Any]) -> bool:
    """
    Обновляет таблицу.
    
    Args:
        table_id: ID таблицы
        table_data: Новые данные таблицы
        
    Returns:
        True если обновлена, False если не найдена
    """
    if table_id in STORAGE:
        table_data['id'] = table_id
        table_data['updated_at'] = datetime.now().isoformat()
        if 'created_at' not in table_data:
            table_data['created_at'] = STORAGE[table_id].get('created_at')
        STORAGE[table_id] = table_data
        return True
    return False

