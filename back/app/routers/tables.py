"""
Роутер для работы с таблицами.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import Dict, Any, List
from pydantic import BaseModel
import logging
import sys
from pathlib import Path

# Добавляем путь к модулям аналитики
analytics_path = Path(__file__).parent.parent.parent / 'analytics'
sys.path.insert(0, str(analytics_path))

from app.services.storage import (
    save_table,
    get_table as get_table_from_storage,
    get_all_tables,
    delete_table as delete_table_from_storage
)
from app.services.analytics import process_table, get_pie_chart_data
from app.utils.file_parser import (
    parse_csv, 
    parse_json, 
    parse_excel,
    wide_format_to_json_format,
    json_format_to_wide_format
)

logger = logging.getLogger(__name__)

# Импортируем функции предобработки
try:
    import importlib.util
    back_module_path = analytics_path / 'back.py'
    spec = importlib.util.spec_from_file_location("back", back_module_path)
    back_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(back_module)
    preprocess_json = back_module.preprocess_json
except Exception as e:
    logger.error(f"Не удалось импортировать back.py: {e}")
    raise ImportError(f"Не удалось импортировать back.py. Убедитесь, что файл находится в back/analytics/: {e}")

try:
    import importlib.util
    name_module_path = analytics_path / 'name_of_analysis.py'
    spec = importlib.util.spec_from_file_location("name_of_analysis", name_module_path)
    name_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(name_module)
    enrich_json_with_names = name_module.process_json
except Exception as e:
    logger.error(f"Не удалось импортировать name_of_analysis.py: {e}")
    raise ImportError(f"Не удалось импортировать name_of_analysis.py. Убедитесь, что файл находится в back/analytics/: {e}")

router = APIRouter(prefix="/api/tables", tags=["tables"])


class ReferenceCheckRequest(BaseModel):
    """Модель запроса для проверки референсных значений."""
    test_names: List[str]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_table(
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Загружает таблицу в систему.
    Поддерживает форматы: CSV, JSON, Excel.
    
    Args:
        file: Загружаемый файл
        
    Returns:
        Информация о загруженной таблице
    """
    try:
        # Читаем содержимое файла
        file_content = await file.read()
        
        # Определяем тип файла по расширению
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        
        # Парсим файл в зависимости от типа
        if file_extension == 'csv':
            table_data = parse_csv(file_content)
        elif file_extension == 'json':
            table_data = parse_json(file_content)
        elif file_extension in ['xlsx', 'xls']:
            table_data = parse_excel(file_content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат файла: {file_extension}. Поддерживаются: csv, json, xlsx, xls"
            )
        
        # Добавляем метаданные о файле
        table_data['filename'] = file.filename
        table_data['file_type'] = file_extension
        
        # Логируем начальные данные
        initial_rows = len(table_data.get('data', []))
        initial_cols = len(table_data.get('columns', []))
        logger.info(f"Парсинг завершен. Исходные данные: {initial_rows} строк, {initial_cols} колонок")
        
        # Шаг 1: Конвертируем в JSON формат для предобработки
        logger.info("Конвертация данных в JSON формат для предобработки...")
        json_format_data = wide_format_to_json_format(table_data)
        json_patients_count = len(json_format_data.get('patients', []))
        logger.info(f"Конвертация в JSON формат: {json_patients_count} пациентов, {len(json_format_data.get('test_names', {}))} тестов")
        
        # Шаг 2: Предобработка данных (удаление пустых, дубликатов, выбросов)
        # ВАЖНО: Для Excel файлов с метаданными (human_immune_health_atlas_metadata)
        # временно отключаем агрессивную предобработку, чтобы не потерять данные
        is_metadata_file = 'metadata' in file.filename.lower() or 'human_immune' in file.filename.lower()
        
        logger.info(f"Применение предобработки данных (back.py)... (метаданные: {is_metadata_file})")
        try:
            # Для файлов метаданных отключаем удаление выбросов (может удалить много данных)
            # и делаем менее агрессивную очистку
            preprocessed_data, preprocess_stats = preprocess_json(
                json_format_data,
                remove_empty=not is_metadata_file,  # Для метаданных не удаляем пустые
                remove_duplicates=True,
                remove_outliers=not is_metadata_file  # Для метаданных не удаляем выбросы
            )
            preprocessed_patients_count = len(preprocessed_data.get('patients', []))
            logger.info(f"Предобработка завершена. Осталось пациентов: {preprocessed_patients_count}")
            logger.info(f"Статистика предобработки: {preprocess_stats}")
        except Exception as e:
            logger.error(f"Ошибка при предобработке данных: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при предобработке данных: {str(e)}"
            )
        
        # Шаг 3: Обогащение JSON данными из JSON файла (переименование анализов)
        logger.info("Обогащение данных названиями анализов (name_of_analysis.py)...")
        try:
            # Определяем путь к JSON файлу (проверяем оба возможных расположения)
            json_path = analytics_path / 'data.json'
            if not json_path.exists():
                # Пробуем альтернативный путь
                json_path = analytics_path / 'data' / 'data.json'
            
            if not json_path.exists():
                logger.warning(f"JSON файл не найден по пути {json_path}, пропускаем обогащение")
                enriched_data = preprocessed_data
            else:
                enriched_data = enrich_json_with_names(
                    preprocessed_data,
                    json_path=str(json_path),
                    similarity_threshold=0.85
                )
                logger.info("Обогащение данными из JSON завершено")
        except Exception as e:
            logger.error(f"Ошибка при обогащении данных: {e}")
            # Продолжаем с предобработанными данными, если обогащение не удалось
            enriched_data = preprocessed_data
        
        # Шаг 4: Конвертируем обратно в широкий формат
        logger.info("Конвертация обратно в широкий формат...")
        enriched_patients_count = len(enriched_data.get('patients', []))
        logger.info(f"Перед конвертацией в широкий формат: {enriched_patients_count} пациентов")
        processed_data = json_format_to_wide_format(enriched_data)
        final_rows = len(processed_data.get('data', []))
        final_cols = len(processed_data.get('columns', []))
        logger.info(f"Конвертация завершена. Итоговые данные: {final_rows} строк, {final_cols} колонок")
        
        # Сохраняем метаданные о файле
        processed_data['filename'] = file.filename
        processed_data['file_type'] = file_extension
        
        # Отправляем в аналитику (заглушка)
        processed_data = process_table(processed_data)
        
        # Сохраняем в хранилище
        table_id = save_table(processed_data)
        
        logger.info(f"Таблица загружена: {table_id}, файл: {file.filename}")
        
        return {
            "table_id": table_id,
            "filename": file.filename,
            "file_type": file_extension,
            "shape": processed_data.get('shape'),
            "columns": processed_data.get('columns'),
            "message": "Таблица успешно загружена и обработана"
        }
    
    except ValueError as e:
        logger.error(f"Ошибка парсинга файла: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при загрузке файла: {str(e)}"
        )


@router.get("/")
async def list_tables() -> Dict[str, Any]:
    """
    Получает список всех таблиц.
    
    Returns:
        Список всех таблиц с их метаданными
    """
    all_tables = get_all_tables()
    
    # Возвращаем только метаданные, без полных данных
    tables_list = []
    for table_id, table_data in all_tables.items():
        tables_list.append({
            "table_id": table_id,
            "filename": table_data.get('filename', 'Unknown'),
            "file_type": table_data.get('file_type', 'Unknown'),
            "shape": table_data.get('shape'),
            "columns": table_data.get('columns'),
            "created_at": table_data.get('created_at'),
            "updated_at": table_data.get('updated_at')
        })
    
    return {
        "count": len(tables_list),
        "tables": tables_list
    }


@router.get("/{table_id}")
async def get_table(table_id: str) -> Dict[str, Any]:
    """
    Получает таблицу по ID.
    
    Args:
        table_id: ID таблицы
        
    Returns:
        Данные таблицы
    """
    table = get_table_from_storage(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Таблица с ID {table_id} не найдена"
        )
    
    return table


@router.delete("/{table_id}")
async def delete_table(table_id: str) -> Dict[str, str]:
    """
    Удаляет таблицу по ID.
    
    Args:
        table_id: ID таблицы
        
    Returns:
        Сообщение об успешном удалении
    """
    deleted = delete_table_from_storage(table_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Таблица с ID {table_id} не найдена"
        )
    
    return {"message": f"Таблица {table_id} успешно удалена"}


@router.get("/{table_id}/pie-chart")
async def get_pie_chart(table_id: str) -> Dict[str, Any]:
    """
    Получает данные для круговой диаграммы Chart.js по ID таблицы.
    
    Args:
        table_id: ID таблицы
        
    Returns:
        JSON данные в формате для Chart.js pie chart:
        {
            "labels": ["Label1", "Label2", ...],
            "datasets": [{
                "data": [10, 20, ...],
                "backgroundColor": ["#FF6384", "#36A2EB", ...]
            }]
        }
    """
    # Получаем таблицу из хранилища
    table = get_table_from_storage(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Таблица с ID {table_id} не найдена"
        )
    
    # Получаем данные для круговой диаграммы через аналитику (заглушка)
    chart_data = get_pie_chart_data(table)
    
    logger.info(f"Данные для круговой диаграммы подготовлены для таблицы {table_id}")
    
    return chart_data


@router.post("/{table_id}/reference-check")
async def check_reference_values(
    table_id: str,
    request: ReferenceCheckRequest
) -> Dict[str, Any]:
    """
    Проверяет соответствие значений анализов референсным значениям.
    
    Args:
        table_id: ID таблицы
        request: Запрос с списком названий анализов для проверки
        
    Returns:
        Данные для построения графиков с референсными значениями:
        {
            "test_name": {
                "reference_min": float,
                "reference_max": float,
                "patients": [
                    {
                        "patient_id": str,
                        "value": float,
                        "is_normal": bool
                    }
                ]
            }
        }
    """
    # Получаем таблицу из хранилища
    table = get_table_from_storage(table_id)
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Таблица с ID {table_id} не найдена"
        )
    
    # Заглушка для референсных значений
    # В будущем это будет загружаться из JSON файла или базы данных
    reference_values = {
        "Гемоглобин": {"min": 120, "max": 160},
        "Эритроциты": {"min": 4.0, "max": 5.5},
        "Лейкоциты": {"min": 4.0, "max": 9.0},
        "Тромбоциты": {"min": 150, "max": 400},
        "Глюкоза": {"min": 3.9, "max": 5.9},
        "Креатинин": {"min": 62, "max": 106},
        "АЛТ": {"min": 10, "max": 40},
        "АСТ": {"min": 10, "max": 40},
        "Холестерин": {"min": 3.0, "max": 5.2},
        "Билирубин": {"min": 3.4, "max": 20.5}
    }
    
    # Получаем данные таблицы
    columns = table.get('columns', [])
    data = table.get('data', [])
    test_names = table.get('test_names', {})  # Словарь test_code -> test_name для нового формата
    
    # Определяем формат данных: широкий (wide) или длинный (long)
    # Длинный формат: есть колонки test_name, value, patient_id
    # Широкий формат: каждая колонка - это анализ
    is_long_format = 'test_name' in columns or 'test' in [col.lower() for col in columns]
    
    # Создаем обратный маппинг test_name -> test_code для нового формата
    test_name_to_code = {v: k for k, v in test_names.items()} if test_names else {}
    
    # Результат проверки
    result = {}
    
    if is_long_format:
        # Работаем с длинным форматом данных
        test_name_col = None
        value_col = None
        patient_id_col = None
        
        # Ищем колонки
        for col in columns:
            col_lower = col.lower()
            if col_lower in ['test_name', 'test', 'analysis', 'анализ'] and not test_name_col:
                test_name_col = col
            elif col_lower in ['value', 'значение', 'result', 'результат'] and not value_col:
                value_col = col
            elif col_lower in ['patient_id', 'id', 'patient id', 'пациент', 'subject_id'] and not patient_id_col:
                patient_id_col = col
        
        if not test_name_col or not value_col:
            logger.error(f"Не найдены необходимые колонки для длинного формата. test_name: {test_name_col}, value: {value_col}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Таблица в длинном формате, но не найдены колонки test_name или value"
            )
        
        # Группируем данные по названиям анализов
        for requested_test_name in request.test_names:
            # Получаем референсные значения
            ref_min = reference_values.get(requested_test_name, {}).get("min", 0)
            ref_max = reference_values.get(requested_test_name, {}).get("max", 100)
            
            patients_data = []
            
            # Ищем все строки с этим названием анализа
            for row in data:
                row_test_name = row.get(test_name_col)
                
                # Проверяем совпадение (точное или регистронезависимое)
                if not row_test_name or (row_test_name != requested_test_name and row_test_name.lower() != requested_test_name.lower()):
                    continue
                
                value = row.get(value_col)
                
                # Пропускаем пустые значения
                if value is None or value == '':
                    continue
                
                try:
                    # Пытаемся преобразовать в число
                    num_value = float(value)
                    
                    # Проверяем, в пределах ли нормы
                    is_normal = ref_min <= num_value <= ref_max
                    
                    patient_id = row.get(patient_id_col) if patient_id_col else "Unknown"
                    
                    patients_data.append({
                        "patient_id": str(patient_id),
                        "value": num_value,
                        "is_normal": is_normal
                    })
                except (ValueError, TypeError) as e:
                    # Если не число, пропускаем
                    logger.debug(f"Не удалось преобразовать значение '{value}' в число для анализа {requested_test_name}: {e}")
                    continue
            
            # Добавляем результат только если есть данные пациентов
            if patients_data:
                result[requested_test_name] = {
                    "reference_min": ref_min,
                    "reference_max": ref_max,
                    "patients": patients_data
                }
            else:
                logger.warning(f"Не найдено данных пациентов для анализа {requested_test_name}")
    
    else:
        # Работаем с широким форматом данных (каждая колонка - анализ)
        for requested_test in request.test_names:
            # Проверяем, это test_code или test_name
            # Сначала проверяем, есть ли это test_code (название колонки)
            test_code = None
            display_test_name = requested_test  # Для отображения в результате
            
            # 1. Проверяем точное совпадение с названием колонки (test_code)
            if requested_test in columns:
                test_code = requested_test
                # Если есть test_names, получаем человекочитаемое название
                if test_names and test_code in test_names:
                    display_test_name = test_names[test_code]
            # 2. Проверяем регистронезависимое совпадение с test_code
            elif test_name_to_code and requested_test in test_name_to_code:
                # Это test_name, находим соответствующий test_code
                test_code = test_name_to_code[requested_test]
                display_test_name = requested_test
            # 3. Ищем по регистронезависимому совпадению в колонках
            else:
                for col in columns:
                    if col.lower() == requested_test.lower():
                        test_code = col
                        # Если есть test_names, получаем человекочитаемое название
                        if test_names and test_code in test_names:
                            display_test_name = test_names[test_code]
                        else:
                            display_test_name = requested_test
                        break
            
            if not test_code:
                logger.warning(f"Анализ '{requested_test}' не найден в таблице. Доступные колонки: {columns[:10]}")
                # Продолжаем, но не добавляем в результат
                continue
            
            # Используем test_code для поиска в данных (это название колонки)
            # Но в результате используем display_test_name для отображения
            
            # Получаем референсные значения
            # Проверяем сначала по display_test_name, потом по test_code
            ref_min = reference_values.get(display_test_name, {}).get("min") or \
                     reference_values.get(test_code, {}).get("min") or 0
            ref_max = reference_values.get(display_test_name, {}).get("max") or \
                     reference_values.get(test_code, {}).get("max") or 100
            
            # Собираем данные пациентов для этого анализа
            patients_data = []
            patient_id_col = None
            
            # Ищем колонку с ID пациента (может быть patient_id, id, Patient ID и т.д.)
            for col in columns:
                if col.lower() in ['patient_id', 'id', 'patient id', 'пациент']:
                    patient_id_col = col
                    break
            
            # Если не нашли колонку с ID, используем индекс строки
            for idx, row in enumerate(data):
                value = row.get(test_code)  # Используем test_code для поиска значения
                
                # Пропускаем пустые значения
                if value is None or value == '':
                    continue
                
                try:
                    # Пытаемся преобразовать в число
                    num_value = float(value)
                    
                    # Проверяем, в пределах ли нормы
                    is_normal = ref_min <= num_value <= ref_max
                    
                    patient_id = row.get(patient_id_col) if patient_id_col else f"Patient_{idx + 1}"
                    
                    patients_data.append({
                        "patient_id": str(patient_id),
                        "value": num_value,
                        "is_normal": is_normal
                    })
                except (ValueError, TypeError) as e:
                    # Если не число, пропускаем
                    logger.debug(f"Не удалось преобразовать значение '{value}' в число для анализа {test_code}: {e}")
                    continue
            
            # Добавляем результат только если есть данные пациентов
            # Используем display_test_name для ключа в результате
            if patients_data:
                result[display_test_name] = {
                    "reference_min": ref_min,
                    "reference_max": ref_max,
                    "patients": patients_data
                }
            else:
                logger.warning(f"Не найдено данных пациентов для анализа {test_code} ({display_test_name})")
    
    logger.info(f"Проверка референсных значений выполнена для таблицы {table_id}, анализов: {len(request.test_names)}, найдено: {len(result)}")
    
    if not result:
        logger.warning(f"Не найдено данных ни для одного из запрошенных анализов: {request.test_names}")
        logger.info(f"Доступные колонки в таблице: {columns}")
    
    return result
