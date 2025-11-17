"""
Утилиты для парсинга файлов (CSV, JSON, Excel).
"""
import pandas as pd
import json
from typing import Dict, Any, List
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def parse_csv(file_content: bytes) -> Dict[str, Any]:
    """
    Парсит CSV файл.
    
    Args:
        file_content: Байты файла
        
    Returns:
        Словарь с данными таблицы
    """
    try:
        df = pd.read_csv(BytesIO(file_content))
        return dataframe_to_dict(df)
    except Exception as e:
        logger.error(f"Ошибка при парсинге CSV: {e}")
        raise ValueError(f"Не удалось распарсить CSV файл: {str(e)}")


def parse_json(file_content: bytes) -> Dict[str, Any]:
    """
    Парсит JSON файл.
    
    Поддерживает два формата:
    1. Новый формат: {"test_names": {...}, "patients": [...]} - словарь тестов и массив пациентов с анализами
    2. Старый формат: список словарей или словарь с данными
    
    Args:
        file_content: Байты файла
        
    Returns:
        Словарь с данными таблицы
    """
    try:
        # Пробуем декодировать как JSON
        json_str = file_content.decode('utf-8')
        data = json.loads(json_str)
        
        # Проверяем, это новый формат с test_names и patients?
        if isinstance(data, dict) and 'test_names' in data and 'patients' in data:
            # Новый формат: преобразуем в широкий формат таблицы
            return parse_new_json_format(data)
        
        # Старый формат: обрабатываем как раньше
        # Если это список словарей, создаем DataFrame
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            df = pd.DataFrame(data)
        # Если это словарь с данными
        elif isinstance(data, dict):
            # Пробуем найти ключ с данными
            if 'data' in data:
                df = pd.DataFrame(data['data'])
            elif 'rows' in data:
                df = pd.DataFrame(data['rows'])
            else:
                # Пробуем создать DataFrame из словаря
                df = pd.DataFrame([data])
        else:
            raise ValueError("Неподдерживаемый формат JSON")
        
        return dataframe_to_dict(df)
    except Exception as e:
        logger.error(f"Ошибка при парсинге JSON: {e}")
        raise ValueError(f"Не удалось распарсить JSON файл: {str(e)}")


def parse_new_json_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсит новый формат JSON со структурой:
    {
        "test_names": {"test_code": "test_name", ...},
        "patients": [
            {
                "patient_id": "...",
                "date": "...",
                "analyses": {"test_code": {"value": ..., "unit": ..., "status": ...}, ...}
            }
        ]
    }
    
    Преобразует в широкий формат таблицы:
    - Каждая строка = один пациент
    - Колонки: patient_id, date, затем все test_code
    
    Args:
        data: JSON данные в новом формате
        
    Returns:
        Словарь с данными таблицы в формате для хранения
    """
    test_names = data.get('test_names', {})
    patients = data.get('patients', [])
    
    if not patients:
        # Пустой массив пациентов
        return {
            'data': [],
            'columns': ['patient_id', 'date'],
            'dtypes': {},
            'shape': {'rows': 0, 'columns': 2}
        }
    
    # Собираем все возможные test_code из всех пациентов и из test_names
    all_test_codes = set()
    for patient in patients:
        analyses = patient.get('analyses', {})
        all_test_codes.update(analyses.keys())
    # Добавляем также все из test_names (на случай если у пациентов нет данных)
    all_test_codes.update(test_names.keys())
    
    # Сортируем test_code для консистентности
    sorted_test_codes = sorted(list(all_test_codes))
    
    # Создаем колонки: patient_id, date, затем все test_code
    columns = ['patient_id', 'date'] + sorted_test_codes
    
    # Преобразуем пациентов в строки таблицы
    rows = []
    for patient in patients:
        patient_id = patient.get('patient_id', '')
        date = patient.get('date', '')
        analyses = patient.get('analyses', {})
        
        # Создаем строку данных
        row = {
            'patient_id': patient_id,
            'date': date
        }
        
        # Добавляем значения анализов
        # Используем test_code из test_names или сам test_code как название колонки
        for test_code in sorted_test_codes:
            if test_code in analyses:
                analysis = analyses[test_code]
                # Сохраняем только value, unit и status можно получить отдельно при необходимости
                # Для совместимости с фронтендом сохраняем value
                row[test_code] = analysis.get('value')
            else:
                # У пациента нет этого анализа - пустое значение
                row[test_code] = None
        
        rows.append(row)
    
    # Создаем DataFrame
    df = pd.DataFrame(rows, columns=columns)
    
    # Нормализуем test_names: сохраняем простой формат {test_code: "name"}
    # ВАЖНО: Формат должен быть простым - {test_code: name} (строка)
    normalized_test_names = {}
    for test_code, name_data in test_names.items():
        if isinstance(name_data, dict):
            # Формат {name: "...", unit: "..."} - извлекаем только name
            normalized_test_names[test_code] = name_data.get('name', test_code)
        else:
            # Простой формат: строка - сохраняем как есть
            normalized_test_names[test_code] = name_data
    
    # Сохраняем test_names в метаданные для последующего использования
    result = dataframe_to_dict(df)
    result['test_names'] = normalized_test_names  # Сохраняем простой формат
    
    return result


def parse_excel(file_content: bytes) -> Dict[str, Any]:
    """
    Парсит Excel файл.
    
    Args:
        file_content: Байты файла
        
    Returns:
        Словарь с данными таблицы
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Читаем Excel файл
        # Пробуем разные движки для совместимости
        try:
            df = pd.read_excel(BytesIO(file_content), engine='openpyxl')
            logger.info(f"Excel файл прочитан с движком openpyxl: {df.shape[0]} строк, {df.shape[1]} колонок")
        except Exception as e1:
            logger.warning(f"Не удалось прочитать с openpyxl: {e1}")
            # Если openpyxl не работает, пробуем xlrd (для старых .xls)
            try:
                df = pd.read_excel(BytesIO(file_content), engine='xlrd')
                logger.info(f"Excel файл прочитан с движком xlrd: {df.shape[0]} строк, {df.shape[1]} колонок")
            except Exception as e2:
                logger.warning(f"Не удалось прочитать с xlrd: {e2}")
                # Последняя попытка - без указания движка
                df = pd.read_excel(BytesIO(file_content))
                logger.info(f"Excel файл прочитан без указания движка: {df.shape[0]} строк, {df.shape[1]} колонок")
        
        initial_rows = len(df)
        initial_cols = len(df.columns)
        
        # Удаляем полностью пустые строки
        df = df.dropna(how='all')
        after_empty_rows = len(df)
        logger.info(f"Удалено пустых строк: {initial_rows - after_empty_rows} (было: {initial_rows}, стало: {after_empty_rows})")
        
        # Удаляем полностью пустые колонки
        df = df.dropna(axis=1, how='all')
        after_empty_cols = len(df.columns)
        logger.info(f"Удалено пустых колонок: {initial_cols - after_empty_cols} (было: {initial_cols}, стало: {after_empty_cols})")
        
        # Очищаем названия колонок от пробелов и лишних символов
        df.columns = df.columns.str.strip()
        
        # Заменяем NaN в названиях колонок на "Unnamed"
        df.columns = [f"Unnamed_{i}" if pd.isna(col) or str(col).strip() == '' else str(col).strip() 
                      for i, col in enumerate(df.columns)]
        
        # Сбрасываем индекс после удаления строк
        df = df.reset_index(drop=True)
        
        logger.info(f"Итоговый размер после парсинга Excel: {len(df)} строк, {len(df.columns)} колонок")
        logger.debug(f"Первые колонки: {list(df.columns[:10])}")
        
        result = dataframe_to_dict(df)
        logger.info(f"Результат parse_excel: {len(result.get('data', []))} строк в данных")
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при парсинге Excel: {e}")
        raise ValueError(f"Не удалось распарсить Excel файл: {str(e)}")


def dataframe_to_dict(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Конвертирует DataFrame в словарь для хранения.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        Словарь с данными таблицы
    """
    # Заменяем NaN на None для JSON сериализации
    df_clean = df.where(pd.notnull(df), None)
    
    # Конвертируем в список словарей
    data = df_clean.to_dict('records')
    
    # Очищаем данные: заменяем NaN, NaT и пустые строки на None
    for row in data:
        for key, value in row.items():
            if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
                row[key] = None
    
    # Получаем названия колонок
    columns = df.columns.tolist()
    
    # Получаем информацию о типах данных
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    
    return {
        'data': data,
        'columns': columns,
        'dtypes': dtypes,
        'shape': {
            'rows': len(df),
            'columns': len(columns)
        }
    }


def dict_to_dataframe(table_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Конвертирует словарь обратно в DataFrame.
    
    Args:
        table_dict: Словарь с данными таблицы
        
    Returns:
        pandas DataFrame
    """
    data = table_dict.get('data', [])
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    return df


def wide_format_to_json_format(table_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Конвертирует широкий формат таблицы в JSON формат для предобработки.
    
    Широкий формат: {data: [{col1: val1, col2: val2, ...}], columns: [...], test_names: {...}}
    JSON формат: {test_names: {...}, patients: [{patient_id, date, analyses: {...}}]}
    
    Args:
        table_dict: Данные в широком формате
        
    Returns:
        Данные в JSON формате для предобработки
    """
    import logging
    logger = logging.getLogger(__name__)
    
    data = table_dict.get('data', [])
    columns = table_dict.get('columns', [])
    test_names = table_dict.get('test_names', {})
    
    logger.info(f"wide_format_to_json_format: входные данные - {len(data)} строк, {len(columns)} колонок")
    logger.debug(f"Колонки: {columns[:10]}...")
    
    # Проверяем, может быть это уже длинный формат (test_name, value, patient_id)
    long_format_indicators = ['test_name', 'test', 'analysis', 'анализ', 'value', 'значение']
    is_long_format = any(col.lower() in long_format_indicators for col in columns)
    
    if is_long_format:
        logger.warning("Обнаружен длинный формат данных в wide_format_to_json_format! Это может быть ошибкой.")
        logger.warning(f"Колонки содержат индикаторы длинного формата: {[col for col in columns if col.lower() in long_format_indicators]}")
    
    # Ищем колонку с patient_id
    patient_id_col = None
    date_col = None
    
    for col in columns:
        col_lower = col.lower()
        if col_lower in ['patient_id', 'id', 'patient id', 'пациент', 'subject_id', 'subject.subjectguid'] and not patient_id_col:
            patient_id_col = col
        elif col_lower in ['date', 'дата'] and not date_col:
            date_col = col
    
    # Если не нашли patient_id, используем первую колонку или создаем индекс
    if not patient_id_col and columns:
        patient_id_col = columns[0]
        logger.warning(f"Не найдена колонка patient_id, используем первую колонку: {patient_id_col}")
    
    logger.info(f"Найдены колонки: patient_id={patient_id_col}, date={date_col}")
    
    # Определяем колонки анализов (все кроме patient_id и date)
    analysis_columns = [col for col in columns 
                       if col != patient_id_col and col != date_col]
    logger.info(f"Определено {len(analysis_columns)} колонок анализов")
    
    # Создаем test_names если его нет
    if not test_names:
        test_names = {col: col for col in analysis_columns}
    else:
        # Нормализуем test_names: сохраняем простой формат {test_code: "name"}
        # Для JSON формата используем простой формат {test_code: name}
        normalized_test_names = {}
        for test_code, name_data in test_names.items():
            if isinstance(name_data, dict):
                # Формат {name: "...", unit: "..."} - извлекаем только name
                normalized_test_names[test_code] = name_data.get('name', test_code)
            else:
                # Простой формат: строка - сохраняем как есть
                normalized_test_names[test_code] = name_data
        test_names = normalized_test_names
    
    # Преобразуем данные в формат patients
    patients = []
    skipped_empty = 0
    skipped_no_analyses = 0
    
    for row_idx, row in enumerate(data):
        patient_id = row.get(patient_id_col, '') if patient_id_col else ''
        date = row.get(date_col, '') if date_col else ''
        
        # Пропускаем полностью пустые строки
        if not patient_id and not any(row.get(col) for col in analysis_columns if row.get(col) is not None and row.get(col) != ''):
            skipped_empty += 1
            continue
        
        analyses = {}
        for test_code in analysis_columns:
            value = row.get(test_code)
            if value is not None and value != '':
                # Пытаемся преобразовать в число, но сохраняем и строки
                try:
                    # Пробуем преобразовать в число
                    if isinstance(value, str):
                        # Убираем пробелы и пробуем преобразовать
                        value_clean = value.strip()
                        if value_clean:
                            num_value = float(value_clean)
                            analyses[test_code] = {
                                'value': num_value
                            }
                    else:
                        num_value = float(value)
                        analyses[test_code] = {
                            'value': num_value
                        }
                except (ValueError, TypeError):
                    # Если не число, все равно сохраняем как строку (для совместимости)
                    # Но только если это не пустая строка
                    if str(value).strip():
                        analyses[test_code] = {
                            'value': str(value).strip()
                        }
        
        # Добавляем пациента даже если нет анализов (может быть только patient_id и date)
        # Но только если есть хотя бы patient_id
        if patient_id or analyses:
            patient = {
                'patient_id': str(patient_id) if patient_id else f'Patient_{len(patients) + 1}',
                'date': str(date) if date else '',
                'analyses': analyses
            }
            patients.append(patient)
        else:
            skipped_no_analyses += 1
    
    logger.info(f"Конвертация завершена: создано {len(patients)} пациентов, пропущено пустых: {skipped_empty}, без анализов: {skipped_no_analyses}")
    
    if len(patients) == 0:
        logger.error(f"ВНИМАНИЕ: Не создано ни одного пациента! Проверьте структуру данных.")
        logger.error(f"Первые 3 строки данных: {data[:3] if len(data) > 0 else 'Нет данных'}")
        logger.error(f"Колонки: {columns}")
        logger.error(f"patient_id_col: {patient_id_col}, analysis_columns: {analysis_columns[:5]}...")
    
    return {
        'test_names': test_names,
        'patients': patients
    }


def json_format_to_wide_format(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Конвертирует JSON формат обратно в широкий формат таблицы.
    
    JSON формат: {test_names: {...}, patients: [{patient_id, date, analyses: {...}}]}
    Широкий формат: {data: [{col1: val1, col2: val2, ...}], columns: [...], test_names: {...}}
    
    Args:
        json_data: Данные в JSON формате
        
    Returns:
        Данные в широком формате
    """
    # ВАЖНО: Формат test_names теперь {название_колонки_из_таблицы: название_из_excel}
    # Например: {"% Monocytes": "Hematocrit"}
    test_names = json_data.get('test_names', {})
    patients = json_data.get('patients', [])
    
    # Получаем маппинг название_колонки -> test_code для преобразования analyses
    # Формат: {название_колонки: test_code_из_excel}
    # Например: {"% Monocytes": "bc.perc_monocytes"}
    column_name_to_test_code = json_data.get('column_name_to_test_code', {})
    
    if not patients:
        return {
            'data': [],
            'columns': ['patient_id', 'date'],
            'dtypes': {},
            'shape': {'rows': 0, 'columns': 2},
            'test_names': test_names
        }
    
    # ВАЖНО: В analyses ключи - это названия колонок из загруженной таблицы (например, "% Monocytes")
    # test_names имеет формат {название_колонки: название_из_excel} (например, {"% Monocytes": "Hematocrit"})
    # Используем название из Excel для columns
    
    # Собираем все названия колонок из пациентов
    all_column_names = set()
    for patient in patients:
        analyses = patient.get('analyses', {})
        all_column_names.update(analyses.keys())
    # Добавляем все из test_names (на случай если у пациентов нет данных)
    all_column_names.update(test_names.keys())
    
    # Создаем маппинг название_колонки -> название_из_excel для columns
    # ВАЖНО: В columns используем название из Excel для анализов, название из таблицы для метаданных
    columns = []
    column_name_to_column_display = {}  # Маппинг название_колонки -> название для отображения в columns
    
    # Сначала добавляем метаданные (patient_id, date) - они всегда первые
    for meta_col in ['patient_id', 'date']:
        if meta_col in all_column_names:
            columns.append(meta_col)
            column_name_to_column_display[meta_col] = meta_col
    
    # Теперь добавляем анализы - формат: "test_code_из_excel: название_из_excel"
    # ВАЖНО: Оба значения берутся из Excel через name_of_analysis.py
    for col_name in sorted(all_column_names):
        # Пропускаем метаданные - они уже добавлены
        if col_name in ['patient_id', 'date']:
            continue
        
        # Получаем test_code из Excel (из column_name_to_test_code)
        test_code = column_name_to_test_code.get(col_name, col_name)
        
        # Получаем название из Excel (из test_names)
        excel_name = test_names.get(col_name)
        
        if excel_name is None:
            # Если не найдено в test_names, используем test_code как название
            print(f"[file_parser] Предупреждение: колонка '{col_name}' не найдена в test_names, используется test_code")
            excel_name = test_code
        
        # Формат: "test_code_из_excel: название_из_excel"
        # Оба значения из Excel!
        test_code_clean = str(test_code).strip()
        excel_name_clean = str(excel_name).strip()
        column_display_name = f"{test_code_clean}:{excel_name_clean}"
        
        if column_display_name:  # Не добавляем пустые строки
            columns.append(column_display_name)
            # Сохраняем маппинг для преобразования данных
            column_name_to_column_display[col_name] = column_display_name
    
    # Преобразуем пациентов в строки
    rows = []
    for patient in patients:
        patient_id = patient.get('patient_id', '')
        date = patient.get('date', '')
        analyses = patient.get('analyses', {})
        
        row = {
            'patient_id': patient_id,
            'date': date
        }
        
        for col_name in sorted(all_column_names):
            # Получаем название колонки для отображения из маппинга
            # Формат: "название_из_таблицы: название_из_excel" для анализов
            column_display_name = column_name_to_column_display[col_name]
            
            if col_name in analyses:
                analysis = analyses[col_name]
                # Извлекаем value из объекта анализа
                if isinstance(analysis, dict):
                    value = analysis.get('value')
                else:
                    # Если analysis не словарь, используем его как значение (для обратной совместимости)
                    value = analysis
                # Сохраняем значение под названием колонки (формат: "название_из_таблицы: название_из_excel")
                row[column_display_name] = value
            else:
                row[column_display_name] = None
        
        rows.append(row)
    
    # ВАЖНО: Убеждаемся, что columns - это простой список строк без индексов
    # Преобразуем в список, если это не список
    if not isinstance(columns, list):
        columns = list(columns)
    
    # Убеждаемся, что все элементы - строки и убираем пустые
    columns = [str(col).strip() for col in columns if col and str(col).strip()]
    
    # Убираем дубликаты, сохраняя порядок
    seen = set()
    columns_clean = []
    for col in columns:
        if col not in seen:
            seen.add(col)
            columns_clean.append(col)
    columns = columns_clean
    
    # Создаем DataFrame для получения dtypes
    df = pd.DataFrame(rows, columns=columns)
    
    return {
        'data': rows,
        'columns': columns,  # Простой список строк, без индексов
        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
        'shape': {
            'rows': len(rows),
            'columns': len(columns)
        },
        'test_names': test_names
    }