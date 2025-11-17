"""
Роутер для демо варианта.
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from typing import Dict, Any, List
import logging
import json
from pathlib import Path
import csv
import pandas as pd
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])

# Пути к файлам демо вариантов
DEMO_FILES = {
    '1': Path(__file__).parent.parent.parent / "data" / "patient_long_table_realistic_dynamic.csv",
    '2': Path(__file__).parent.parent.parent / "data" / "patient_long_table2.csv"
}
# Путь к файлу с несколькими пациентами для demo2
MORE_PATIENTS_FILE = Path(__file__).parent.parent.parent / "data" / "more_patients.csv"
# Путь к файлу test_table.csv с несколькими пациентами
TEST_TABLE_FILE = Path(__file__).parent.parent.parent / "data" / "test_table.csv"
# Путь к файлу с загруженными данными
UPLOADED_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "uploaded_data.csv"
# Путь по умолчанию (для обратной совместимости)
TEST_TABLE_PATH = DEMO_FILES['1']

# Путь к файлу с нормами
NORMS_PATH = Path(__file__).parent.parent.parent / "analytics" / "data.json"


def load_norms() -> Dict[str, Dict[str, Any]]:
    """Загружает нормы из data.json"""
    try:
        with open(NORMS_PATH, 'r', encoding='utf-8') as f:
            norms_list = json.load(f)
        
        # Преобразуем в словарь: test_code -> {min, max, unit, name}
        # Также создаем маппинг по названию для случаев несоответствия кодов
        norms_dict = {}
        name_to_code = {}
        
        for norm in norms_list:
            test_id = norm.get('id', '')
            name = norm.get('name', '').lower()
            
            norms_dict[test_id] = {
                'min': norm.get('min'),
                'max': norm.get('max'),
                'unit': norm.get('unit', ''),
                'name': norm.get('name', '')
            }
            
            # Создаем маппинг по названию
            if name:
                name_to_code[name] = test_id
        
        # Добавляем специальные маппинги для несоответствий
        # В CSV может быть chem.chol, а в нормах lip.cholesterol_total
        norms_dict['chem.chol'] = norms_dict.get('lip.cholesterol_total', {})
        if 'lip.cholesterol_total' in norms_dict:
            norms_dict['chem.chol'] = norms_dict['lip.cholesterol_total'].copy()
        
        # Добавляем обратный маппинг в name_to_code для "total cholesterol"
        if 'total cholesterol' not in name_to_code and 'lip.cholesterol_total' in norms_dict:
            name_to_code['total cholesterol'] = 'lip.cholesterol_total'
        
        norms_dict['_name_mapping'] = name_to_code
        
        return norms_dict
    except Exception as e:
        logger.error(f"Ошибка загрузки норм: {e}")
        return {}


def get_test_category(test_code: str, test_name: str = '', norms: Dict[str, Dict[str, Any]] = None) -> str:
    """Определяет категорию анализа по test_code и названию"""
    if not test_code:
        return 'other'
    
    test_code_lower = test_code.lower()
    test_name_lower = (test_name or '').lower()
    
    # ВАЖНО: Сначала проверяем на известные биохимические тесты по названию
    # Это должно быть ДО проверки префиксов, чтобы избежать неправильной категоризации
    biochemistry_name_keywords = [
        'alanine', 'transaminase', 'alt', 'ast', 'aspartate', 'glucose', 
        'creatinine', 'albumin', 'bilirubin', 'urea', 'bun', 'calcium',
        'potassium', 'sodium', 'chloride', 'phosphate', 'magnesium',
        'protein', 'ldh', 'alkaline', 'phosphatase', 'egfr', 'gfr',
        'lactate', 'dehydrogenase', 'troponin', 'ck', 'creatine', 'kinase'
    ]
    
    # Если название содержит ключевые слова биохимии - всегда биохимия
    if test_name_lower and any(keyword in test_name_lower for keyword in biochemistry_name_keywords):
        return 'biochemistry'
    
    # Специальная обработка для холестерина - может быть в chem. или lip.
    if test_code_lower == 'chem.chol' or 'cholesterol' in test_code_lower:
        return 'lipid_profile'
    
    # Если нет префикса, пытаемся определить по коду или названию
    # Известные биохимические тесты (ферменты печени, глюкоза, креатинин и т.д.)
    biochemistry_tests = {
        'alt', 'ast', 'glucose', 'creatinine', 'albumin', 'bilirubin', 'bun', 
        'calcium', 'co2', 'cl', 'egfr', 'ldh', 'magnesium', 'phosphate', 
        'potassium', 'protein', 'sodium', 't_bili', 'alkaline_phosphatase',
        'globin', 'egfr_aa', 'egfr_non_aa', 'troponin', 'ck', 'ck_mb'
    }
    
    # Извлекаем базовое имя из кода (без префикса)
    base_code = test_code_lower.replace('chem.', '').replace('bc.', '').replace('lip.', '').strip()
    
    # Проверяем, является ли это известным биохимическим тестом
    # ВАЖНО: Если это биохимический тест, возвращаем биохимию, даже если есть префикс bc.
    if base_code in biochemistry_tests:
        return 'biochemistry'
    
    # Проверка по префиксам (только если не определили выше)
    if test_code_lower.startswith('am.'):
        return 'anthropometry'
    elif test_code_lower.startswith('chem.'):
        return 'biochemistry'
    elif test_code_lower.startswith('bc.'):
        # ВАЖНО: Проверяем, не является ли это биохимическим тестом с неправильным префиксом
        # Если базовый код - это биохимический тест, возвращаем биохимию
        if base_code in biochemistry_tests:
            return 'biochemistry'
        return 'blood_count'
    elif test_code_lower.startswith('cmv.'):
        return 'infections'
    elif test_code_lower.startswith('infl.'):
        return 'inflammation'
    elif test_code_lower.startswith('lip.'):
        return 'lipid_profile'
    
    # Проверяем по названию, если есть нормы
    if norms and test_name:
        test_name_lower = test_name.lower()
        # Ищем в нормах по названию
        for code, norm_data in norms.items():
            if code == '_name_mapping':
                continue
            norm_name = norm_data.get('name', '').lower()
            # Если название содержит ключевые слова биохимии
            if test_name_lower in norm_name or norm_name in test_name_lower:
                # Определяем категорию по коду из норм
                if code.startswith('chem.'):
                    return 'biochemistry'
                elif code.startswith('bc.'):
                    return 'blood_count'
                elif code.startswith('lip.'):
                    return 'lipid_profile'
                elif code.startswith('am.'):
                    return 'anthropometry'
                elif code.startswith('infl.'):
                    return 'inflammation'
                elif code.startswith('cmv.'):
                    return 'infections'
    
    # Проверяем по ключевым словам в названии
    if test_name:
        test_name_lower = test_name.lower()
        # Биохимические маркеры
        biochemistry_keywords = [
            'alanine', 'transaminase', 'alt', 'ast', 'aspartate', 'glucose', 
            'creatinine', 'albumin', 'bilirubin', 'urea', 'bun', 'calcium',
            'potassium', 'sodium', 'chloride', 'phosphate', 'magnesium',
            'protein', 'ldh', 'alkaline', 'phosphatase', 'egfr', 'gfr'
        ]
        # Общий анализ крови
        blood_count_keywords = [
            'hemoglobin', 'hgb', 'hct', 'hematocrit', 'rbc', 'wbc', 'platelet',
            'lymphocyte', 'neutrophil', 'monocyte', 'eosinophil', 'basophil',
            'mcv', 'mch', 'mchc', 'rdw'
        ]
        
        if any(keyword in test_name_lower for keyword in biochemistry_keywords):
            return 'biochemistry'
        elif any(keyword in test_name_lower for keyword in blood_count_keywords):
            return 'blood_count'
    
    # По умолчанию для неизвестных тестов без префикса - биохимия
    # (так как большинство лабораторных тестов - это биохимия)
    return 'biochemistry'


def check_value_against_norm(value: float, norm_min: float, norm_max: float) -> str:
    """Проверяет значение на соответствие норме"""
    if norm_min is None and norm_max is None:
        return 'NORMAL'
    
    if norm_min is not None and value < norm_min:
        return 'LOW'
    
    if norm_max is not None and value > norm_max:
        return 'HIGH'
    
    return 'NORMAL'


def is_significantly_abnormal(value: float, norm_min: float, norm_max: float) -> bool:
    """Проверяет, является ли отклонение значительным (более 10% от нормы)"""
    if norm_min is None and norm_max is None:
        return False
    
    # Если значение ниже нормы
    if norm_min is not None and value < norm_min:
        deviation = (norm_min - value) / norm_min
        return deviation > 0.1  # Более 10% отклонения вниз
    
    # Если значение выше нормы
    if norm_max is not None and value > norm_max:
        deviation = (value - norm_max) / norm_max
        return deviation > 0.1  # Более 10% отклонения вверх
    
    return False


def get_norm_info(test_code: str, test_name: str, norms: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Получает информацию о нормах для теста, учитывая возможные несоответствия кодов"""
    # Прямое совпадение по коду
    norm_info = norms.get(test_code, {})
    
    # Если не найдено и есть маппинг по названию
    if not norm_info and '_name_mapping' in norms:
        name_mapping = norms['_name_mapping']
        test_name_lower = test_name.lower()
        mapped_code = name_mapping.get(test_name_lower)
        if mapped_code:
            norm_info = norms.get(mapped_code, {})
    
    # Если все еще не найдено, пробуем найти по части названия
    if not norm_info:
        test_name_lower = test_name.lower()
        for code, norm_data in norms.items():
            if code != '_name_mapping' and isinstance(norm_data, dict):
                norm_name = norm_data.get('name', '').lower()
                if norm_name and (test_name_lower in norm_name or norm_name in test_name_lower):
                    norm_info = norm_data
                    break
    
    return norm_info if norm_info else {}


def normalize_test_code(test_code: str) -> str:
    """Нормализует test_code: убирает пробелы, приводит к нижнему регистру"""
    if not test_code:
        return ''
    return test_code.strip().lower()


def normalize_test_name(test_name: str) -> str:
    """Нормализует название теста для сравнения"""
    if not test_name:
        return ''
    # Убираем пробелы, приводим к нижнему регистру, убираем лишние символы
    normalized = test_name.strip().lower()
    # Убираем общие слова, которые могут отличаться
    normalized = normalized.replace('alanine', 'alt').replace('transaminase', '')
    normalized = normalized.replace(' ', '').replace('-', '').replace('_', '')
    return normalized


def group_by_category(data: List[Dict[str, Any]], norms: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Группирует данные по категориям"""
    groups = {
        'demography': [],
        'anthropometry': [],
        'biochemistry': [],
        'blood_count': [],
        'infections': [],
        'inflammation': [],
        'lipid_profile': []
    }
    
    # Нормализуем test_code для всех записей и подсчитываем количество
    normalized_code_map = {}  # normalized_code -> original_code
    test_code_counts = {}
    test_name_to_code = {}  # normalized_name -> normalized_code
    
    for row in data:
        original_code = row.get('test_code', '').strip()
        test_name = row.get('test_name', '').strip()
        
        if not original_code:
            continue
        
        # Нормализуем код
        normalized_code = normalize_test_code(original_code)
        if normalized_code:
            normalized_code_map[normalized_code] = original_code
            test_code_counts[normalized_code] = test_code_counts.get(normalized_code, 0) + 1
        
        # Создаем маппинг по нормализованному названию
        if test_name:
            normalized_name = normalize_test_name(test_name)
            if normalized_name and normalized_code:
                # Если название уже есть, но код другой - это может быть дубликат
                if normalized_name in test_name_to_code:
                    existing_code = test_name_to_code[normalized_name]
                    # Если коды похожи (один содержит другой), используем более полный
                    if normalized_code in existing_code or existing_code in normalized_code:
                        if len(normalized_code) > len(existing_code):
                            test_name_to_code[normalized_name] = normalized_code
                else:
                    test_name_to_code[normalized_name] = normalized_code
    
    # Группируем по test_code и категориям, оставляя только уникальные test_code
    # Используем словарь для каждой категории: normalized_code -> test_data (с самой поздней датой)
    category_tests = {}  # category -> {normalized_code -> test_data}
    
    for category in groups.keys():
        category_tests[category] = {}
    
    for row in data:
        original_code = row.get('test_code', '').strip()
        test_name = row.get('test_name', '').strip()
        
        if not original_code:
            continue
        
        # Нормализуем код
        normalized_code = normalize_test_code(original_code)
        
        # Если нормализованный код пустой, пропускаем
        if not normalized_code:
            continue
        
        # Определяем категорию по оригинальному коду и названию
        category = get_test_category(original_code, test_name, norms)
        
        # Пропускаем если категория не в списке
        if category not in groups:
            continue
        
        # Определяем, есть ли динамика (больше одного измерения)
        has_dynamics = test_code_counts.get(normalized_code, 0) > 1
        
        # Получаем нормы по оригинальному коду
        norm_info = get_norm_info(original_code, test_name, norms)
        norm_min = norm_info.get('min')
        norm_max = norm_info.get('max')
        norm_unit = norm_info.get('unit', row.get('unit', ''))
        norm_name = norm_info.get('name', test_name)
        
        # Проверяем значение
        try:
            value = float(row.get('value', 0))
            status = check_value_against_norm(value, norm_min, norm_max)
        except (ValueError, TypeError):
            value = None
            status = 'NORMAL'
        
        test_data = {
            'test_code': original_code,  # Сохраняем оригинальный код
            'name': norm_name or test_name,
            'value': value,
            'unit': row.get('unit', norm_unit),
            'date': row.get('date', ''),
            'status': status,
            'norm_min': norm_min,
            'norm_max': norm_max,
            'has_dynamics': has_dynamics
        }
        
        # Проверяем, есть ли уже тест с таким нормализованным кодом в категории
        if normalized_code in category_tests[category]:
            existing_date = category_tests[category][normalized_code].get('date', '')
            current_date = row.get('date', '')
            # Заменяем только если дата более поздняя
            if current_date > existing_date:
                category_tests[category][normalized_code] = test_data
        else:
            # Проверяем, нет ли дубликата по названию или коду
            normalized_name = normalize_test_name(test_name) if test_name else ''
            is_duplicate = False
            duplicate_key = None
            
            if normalized_name:
                # Проверяем все существующие тесты в категории на дубликаты по названию
                for existing_normalized_code, existing_test in list(category_tests[category].items()):
                    existing_name = normalize_test_name(existing_test.get('name', ''))
                    existing_original = existing_test.get('test_code', '')
                    
                    # Проверяем дубликат по названию
                    if normalized_name == existing_name and normalized_name:
                        # Найден дубликат по названию
                        # Используем более полный код (с префиксом предпочтительнее)
                        new_has_prefix = 'chem.' in original_code.lower() or 'bc.' in original_code.lower() or 'lip.' in original_code.lower()
                        existing_has_prefix = 'chem.' in existing_original.lower() or 'bc.' in existing_original.lower() or 'lip.' in existing_original.lower()
                        
                        if new_has_prefix and not existing_has_prefix:
                            # Новый код более полный, заменяем
                            duplicate_key = existing_normalized_code
                            is_duplicate = True
                            break
                        elif not new_has_prefix and existing_has_prefix:
                            # Существующий код более полный, пропускаем новый
                            is_duplicate = True
                            break
                        elif normalized_code == existing_normalized_code:
                            # Одинаковые нормализованные коды - это точно дубликат
                            # Используем более позднюю дату
                            existing_date = existing_test.get('date', '')
                            current_date = row.get('date', '')
                            if current_date > existing_date:
                                duplicate_key = existing_normalized_code
                            is_duplicate = True
                            break
                    
                    # Также проверяем, не являются ли коды вариантами одного теста
                    # (например, "alt" и "chem.alt", или "alt" и "ALT")
                    if normalized_code != existing_normalized_code:
                        # Извлекаем базовое имя из кода (без префикса)
                        new_base = original_code.lower().replace('chem.', '').replace('bc.', '').replace('lip.', '').strip()
                        existing_base = existing_original.lower().replace('chem.', '').replace('bc.', '').replace('lip.', '').strip()
                        
                        if new_base == existing_base and new_base:
                            # Это один и тот же тест с разными префиксами или без
                            # Предпочитаем версию с префиксом
                            new_has_prefix = 'chem.' in original_code.lower() or 'bc.' in original_code.lower() or 'lip.' in original_code.lower()
                            existing_has_prefix = 'chem.' in existing_original.lower() or 'bc.' in existing_original.lower() or 'lip.' in existing_original.lower()
                            
                            if new_has_prefix and not existing_has_prefix:
                                duplicate_key = existing_normalized_code
                                is_duplicate = True
                                break
                            elif not new_has_prefix and existing_has_prefix:
                                is_duplicate = True
                                break
            
            if is_duplicate and duplicate_key:
                # Удаляем старый дубликат
                if duplicate_key in category_tests[category]:
                    del category_tests[category][duplicate_key]
                # Добавляем новый
                category_tests[category][normalized_code] = test_data
            elif not is_duplicate:
                category_tests[category][normalized_code] = test_data
    
    # Заполняем группы уникальными тестами
    for category in groups.keys():
        groups[category] = list(category_tests[category].values())
    
    return groups


def get_abnormal_tests(data: List[Dict[str, Any]], norms: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Возвращает список анализов значительно не в норме (только последние значения для каждого анализа)"""
    abnormal_by_code = {}  # test_code -> abnormal_data (с самой поздней датой)
    
    for row in data:
        test_code = row.get('test_code', '')
        test_name = row.get('test_name', '')
        norm_info = get_norm_info(test_code, test_name, norms)
        norm_min = norm_info.get('min')
        norm_max = norm_info.get('max')
        
        # Check if status is provided in the row (from CSV)
        status_from_row = row.get('status', '').strip().upper() if row.get('status') else ''
        
        try:
            value = float(row.get('value', 0))
            
            # If status is provided from CSV, use it; otherwise calculate
            if status_from_row in ['HIGH', 'LOW']:
                status = status_from_row
                # Include if status is HIGH or LOW from CSV
                should_include = True
            else:
                # Calculate status from norms
                if norm_min is None and norm_max is None:
                    continue
                status = check_value_against_norm(value, norm_min, norm_max)
                # Проверяем, является ли отклонение значительным (более 10% от нормы)
                should_include = status != 'NORMAL' and is_significantly_abnormal(value, norm_min, norm_max)
            
            if should_include:
                test_date = row.get('date', '')
                abnormal_data = {
                    'test_code': test_code,
                    'name': norm_info.get('name', row.get('test_name', '')),
                    'value': value,
                    'unit': norm_info.get('unit', row.get('unit', '')),
                    'status': status,
                    'norm_min': norm_min,
                    'norm_max': norm_max,
                    'date': test_date
                }
                
                # Если уже есть запись для этого test_code, заменяем только если текущая дата более поздняя
                if test_code in abnormal_by_code:
                    existing_date = abnormal_by_code[test_code].get('date', '')
                    if test_date > existing_date:
                        abnormal_by_code[test_code] = abnormal_data
                else:
                    abnormal_by_code[test_code] = abnormal_data
        except (ValueError, TypeError):
            continue
    
    # Возвращаем список только последних записей для каждого анализа
    return list(abnormal_by_code.values())


def prepare_chart_data(data: List[Dict[str, Any]], norms: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Подготавливает данные для графиков Chart.js"""
    charts = {}
    
    # Группируем данные по test_code и пациенту
    test_data_by_code = {}
    
    for row in data:
        test_code = row.get('test_code', '')
        if not test_code:
            continue
        
        if test_code not in test_data_by_code:
            test_data_by_code[test_code] = []
        
        try:
            value = float(row.get('value', 0))
            date_str = row.get('date', '')
            
            # Используем строку даты для оси X (проще, чем timestamp)
            if date_str:
                test_data_by_code[test_code].append({
                    'x': date_str,
                    'y': value,
                    'patient_id': row.get('patient_id', ''),
                    'date': date_str
                })
        except (ValueError, TypeError):
            continue
    
    # Создаем графики для каждого теста
    for test_code, test_values in test_data_by_code.items():
        if len(test_values) < 1:
            continue
        
        # Получаем название теста
        norm_info = get_norm_info(test_code, '', norms)
        test_name = norm_info.get('name', test_code) if norm_info else test_code
        
        # Группируем по пациенту
        patients_data = {}
        all_dates = set()
        for item in test_values:
            patient_id = item['patient_id']
            date_str = item.get('date', item.get('x', ''))
            all_dates.add(date_str)
            if patient_id not in patients_data:
                patients_data[patient_id] = []
            patients_data[patient_id].append(item)
        
        # Сортируем даты
        sorted_dates = sorted(list(all_dates))
        
        # Создаем датасет для каждого пациента
        datasets = []
        colors = ['#2F80ED', '#EB5757', '#F2C94C', '#219653', '#9B51E0', '#F2994A']
        color_index = 0
        
        # Для одного пациента (все данные из файла относятся к одному пациенту)
        for patient_id, values in patients_data.items():
            # Создаем данные в формате {x, y} для каждой даты
            patient_data = []
            values_by_date = {v.get('date', v.get('x', '')): v['y'] for v in values}
            
            for date in sorted_dates:
                if date in values_by_date:
                    patient_data.append({
                        'x': date,
                        'y': values_by_date[date]
                    })
            
            if patient_data:
                # Для одного пациента используем просто "Пациент" без ID
                datasets.append({
                    'label': 'Пациент',
                    'data': patient_data,
                    'borderColor': colors[color_index % len(colors)],
                    'backgroundColor': colors[color_index % len(colors)],
                    'tension': 0.4,
                    'fill': False,
                    'pointRadius': 6,
                    'pointHoverRadius': 8
                })
                color_index += 1
                break  # Берем только первого пациента, так как все данные для одного
        
        # Добавляем линии нормы
        norm_min = norm_info.get('min') if norm_info else None
        norm_max = norm_info.get('max') if norm_info else None
        
        if norm_min is not None and sorted_dates:
            min_values = [{'x': sorted_dates[0], 'y': norm_min}, 
                         {'x': sorted_dates[-1], 'y': norm_min}]
            datasets.append({
                'label': 'Минимум нормы',
                'data': min_values,
                'borderColor': '#27AE60',
                'borderDash': [5, 5],
                'borderWidth': 2,
                'pointRadius': 0,
                'fill': False
            })
        
        if norm_max is not None and sorted_dates:
            max_values = [{'x': sorted_dates[0], 'y': norm_max}, 
                         {'x': sorted_dates[-1], 'y': norm_max}]
            datasets.append({
                'label': 'Максимум нормы',
                'data': max_values,
                'borderColor': '#EB5757',
                'borderDash': [5, 5],
                'borderWidth': 2,
                'pointRadius': 0,
                'fill': False
            })
        
        charts[test_code] = {
            'title': test_name,
            'labels': sorted_dates,
            'datasets': datasets
        }
    
    return charts


@router.get("/download-file")
async def download_file(demo_version: str = "1"):
    """
    Скачивает файл для указанного демо варианта
    """
    if demo_version not in DEMO_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверная версия демо. Доступны: {list(DEMO_FILES.keys())}"
        )
    
    file_path = DEMO_FILES[demo_version]
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {file_path.name} не найден"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="text/csv"
    )


def map_test_short_to_code(test_short: str, norms: Dict[str, Dict[str, Any]]) -> str:
    """Маппит test_short в test_code на основе норм"""
    test_short_lower = test_short.lower()
    
    # Прямой поиск по названию в нормах
    for code, norm_data in norms.items():
        if code == '_name_mapping':
            continue
        norm_name = norm_data.get('name', '').lower()
        if test_short_lower in norm_name or norm_name in test_short_lower:
            return code
    
    # Маппинг для известных сокращений
    test_mapping = {
        'hdl': 'lip.cholesterol_hdl',
        'chol': 'lip.cholesterol_total',
        'glucose': 'chem.glucose',
        'albumin': 'chem.albumin',
        'alt': 'chem.alt',
        'weight': 'am.weight',
        'bmi': 'am.bmi'
    }
    
    return test_mapping.get(test_short_lower, f'chem.{test_short}')


@router.get("/patients-list")
async def get_patients_list() -> List[Dict[str, Any]]:
    """
    Получает список всех пациентов из файла more_patients.csv
    """
    if not MORE_PATIENTS_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {MORE_PATIENTS_FILE.name} не найден"
        )
    
    try:
        df = pd.read_csv(MORE_PATIENTS_FILE)
        
        # Получаем уникальных пациентов и их статистику
        patients = []
        for patient_id in df['subjectGuid'].unique():
            patient_data = df[df['subjectGuid'] == patient_id]
            
            # Получаем первую и последнюю дату
            dates = sorted(patient_data['date'].unique())
            first_date = dates[0] if dates else None
            last_date = dates[-1] if dates else None
            
            # Подсчитываем количество тестов
            test_count = len(patient_data['test_short'].unique())
            
            # Подсчитываем количество записей
            record_count = len(patient_data)
            
            patients.append({
                'patient_id': patient_id,
                'first_date': first_date,
                'last_date': last_date,
                'test_count': test_count,
                'record_count': record_count
            })
        
        # Сортируем по ID пациента
        patients.sort(key=lambda x: x['patient_id'])
        
        return patients
    
    except Exception as e:
        logger.error(f"Ошибка получения списка пациентов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки данных: {str(e)}"
        )


@router.get("/patient-data-by-id")
async def get_patient_data_by_id(patient_id: str) -> Dict[str, Any]:
    """
    Получает обработанные данные конкретного пациента из файла more_patients.csv
    
    Args:
        patient_id: ID пациента (subjectGuid)
    """
    if not MORE_PATIENTS_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {MORE_PATIENTS_FILE.name} не найден"
        )
    
    try:
        # Загружаем данные из CSV
        df = pd.read_csv(MORE_PATIENTS_FILE)
        
        # Фильтруем по patient_id
        patient_df = df[df['subjectGuid'] == patient_id]
        
        if patient_df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пациент {patient_id} не найден"
            )
        
        # Загружаем нормы
        norms = load_norms()
        
        # Нормализуем структуру данных
        data = []
        for _, row in patient_df.iterrows():
            test_short = row.get('test_short', '')
            test_code = map_test_short_to_code(test_short, norms)
            
            normalized_row = {
                'patient_id': row.get('subjectGuid', ''),
                'test_code': test_code,
                'test_name': test_short,
                'value': row.get('value', None),
                'date': row.get('date', ''),
                'unit': ''  # Будет заполнено из норм
            }
            
            # Пропускаем строки с невалидными значениями
            try:
                float(normalized_row['value'])
            except (ValueError, TypeError):
                continue
            
            data.append(normalized_row)
        
        # Фильтруем проблемные анализы для demo2
        # Исключаем Cholesterol, HDL и Glucose
        excluded_test_codes = ['lip.cholesterol_hdl', 'chem.glucose', 'test_lip_cholesterol_hdl', 'test_chem_glucose']
        excluded_test_names = ['hdl', 'glucose', 'cholesterol, hdl']
        data = [
            row for row in data 
            if row.get('test_code', '') not in excluded_test_codes 
            and row.get('test_name', '').lower() not in [name.lower() for name in excluded_test_names]
        ]
        
        # Группируем по категориям
        groups = group_by_category(data, norms)
        
        # Получаем анализы не в норме
        abnormal_tests = get_abnormal_tests(data, norms)
        
        # Подготавливаем данные для графиков
        charts = prepare_chart_data(data, norms)
        
        return {
            'patient_id': patient_id,
            'groups': groups,
            'abnormal_tests': abnormal_tests,
            'charts': charts
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки данных пациента: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки данных: {str(e)}"
        )


@router.get("/patients-list-from-test-table")
async def get_patients_list_from_test_table() -> List[Dict[str, Any]]:
    """
    Получает список всех пациентов из файла test_table.csv
    Файл имеет long format: patient_id, test_name, test_code, value, unit, date, status
    """
    if not TEST_TABLE_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {TEST_TABLE_FILE.name} не найден"
        )
    
    try:
        df = pd.read_csv(TEST_TABLE_FILE)
        
        # Получаем уникальных пациентов и их статистику
        patients = []
        patient_id_column = None
        
        # Определяем колонку с ID пациента
        possible_columns = ['subjectGuid', 'subject_guid', 'patient_id', 'patientId', 'id']
        for col in possible_columns:
            if col in df.columns:
                patient_id_column = col
                break
        
        if not patient_id_column:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не найдена колонка с ID пациента"
            )
        
        for patient_id in df[patient_id_column].unique():
            patient_data = df[df[patient_id_column] == patient_id]
            
            # Получаем первую и последнюю дату
            date_column = None
            for col in ['date', 'Date', 'DATE', 'draw_date', 'analysis_date']:
                if col in df.columns:
                    date_column = col
                    break
            
            if date_column:
                dates = sorted(patient_data[date_column].dropna().unique())
                first_date = dates[0] if dates else None
                last_date = dates[-1] if dates else None
            else:
                first_date = None
                last_date = None
            
            # Подсчитываем количество уникальных тестов (по test_code или test_name)
            test_code_column = None
            for col in ['test_code', 'original_column']:
                if col in df.columns:
                    test_code_column = col
                    break
            
            if test_code_column:
                test_count = len(patient_data[test_code_column].dropna().unique())
            else:
                # Если нет test_code, считаем по test_name
                test_name_column = None
                for col in ['test_name', 'test_short']:
                    if col in df.columns:
                        test_name_column = col
                        break
                if test_name_column:
                    test_count = len(patient_data[test_name_column].dropna().unique())
                else:
                    test_count = 0
            
            patients.append({
                'patient_id': str(patient_id),
                'first_date': str(first_date) if first_date else None,
                'last_date': str(last_date) if last_date else None,
                'test_count': test_count,
                'record_count': len(patient_data)
            })
        
        # Сортируем по ID пациента
        patients.sort(key=lambda x: x['patient_id'])
        
        return patients
    
    except Exception as e:
        logger.error(f"Ошибка получения списка пациентов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки данных: {str(e)}"
        )


@router.get("/patient-data-from-test-table")
async def get_patient_data_from_test_table(patient_id: str) -> Dict[str, Any]:
    """
    Получает обработанные данные конкретного пациента из файла test_table.csv
    Файл имеет long format: patient_id, test_name, test_code, value, unit, date, status
    
    Args:
        patient_id: ID пациента
    """
    if not TEST_TABLE_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {TEST_TABLE_FILE.name} не найден"
        )
    
    try:
        # Загружаем данные из CSV
        df = pd.read_csv(TEST_TABLE_FILE)
        
        # Определяем колонку с ID пациента
        patient_id_column = None
        possible_columns = ['subjectGuid', 'subject_guid', 'patient_id', 'patientId', 'id']
        for col in possible_columns:
            if col in df.columns:
                patient_id_column = col
                break
        
        if not patient_id_column:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не найдена колонка с ID пациента"
            )
        
        # Фильтруем по patient_id
        patient_df = df[df[patient_id_column].astype(str) == str(patient_id)]
        
        if patient_df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пациент {patient_id} не найден"
            )
        
        # Загружаем нормы
        norms = load_norms()
        
        # Нормализуем структуру данных (long format)
        data = []
        for _, row in patient_df.iterrows():
            # Получаем значения из строки
            test_code = row.get('test_code', '') or row.get('original_column', '')
            test_name = row.get('test_name', '') or row.get('test_short', '')
            value = row.get('value', None)
            date_value = row.get('date', '')
            unit = row.get('unit', '')
            
            # Пропускаем строки с невалидными значениями
            try:
                float_value = float(value)
            except (ValueError, TypeError):
                continue
            
            # Если test_name пустое, пытаемся найти в нормах
            if not test_name and test_code:
                norm_info = get_norm_info(test_code, '', norms)
                if norm_info and norm_info.get('name'):
                    test_name = norm_info.get('name', test_code)
                else:
                    test_name = test_code
            
            # Если unit пустое, пытаемся найти в нормах
            if not unit and test_code:
                norm_info = get_norm_info(test_code, test_name, norms)
                if norm_info and norm_info.get('unit'):
                    unit = norm_info.get('unit', '')
            
            normalized_row = {
                'patient_id': str(row[patient_id_column]),
                'test_code': test_code,
                'test_name': test_name,
                'value': float_value,
                'date': str(date_value) if date_value else '',
                'unit': unit
            }
            
            data.append(normalized_row)
        
        # Группируем по категориям
        groups = group_by_category(data, norms)
        
        # Получаем анализы не в норме
        abnormal_tests = get_abnormal_tests(data, norms)
        
        # Подготавливаем данные для графиков
        charts = prepare_chart_data(data, norms)
        
        return {
            'patient_id': str(patient_id),
            'groups': groups,
            'abnormal_tests': abnormal_tests,
            'charts': charts
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки данных пациента: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки данных: {str(e)}"
        )


@router.get("/patient-data")
async def get_patient_data(demo_version: str = "1") -> Dict[str, Any]:
    """
    Получает обработанные данные пациента из указанного файла демо варианта.
    Группирует данные по категориям и определяет анализы не в норме.
    
    Args:
        demo_version: Версия демо (1 или 2). По умолчанию 1.
    """
    if demo_version not in DEMO_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверная версия демо. Доступны: {list(DEMO_FILES.keys())}"
        )
    
    file_path = DEMO_FILES[demo_version]
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл {file_path.name} не найден"
        )
    
    try:
        # Загружаем данные из CSV
        df = pd.read_csv(file_path)
        
        # Нормализуем структуру данных: patient_long_table.csv имеет другую структуру
        # subjectGuid -> patient_id, original_column -> test_code, test_short -> test_name (но нужно получить из норм)
        data = []
        for _, row in df.iterrows():
            normalized_row = {
                'patient_id': row.get('subjectGuid', ''),
                'test_code': row.get('original_column', ''),
                'test_name': row.get('test_short', ''),  # Это короткое название, нужно найти полное
                'value': row.get('value', None),
                'date': row.get('date', ''),
                'unit': ''  # Будет заполнено из норм
            }
            
            # Пропускаем строки с невалидными значениями (даты вместо чисел)
            try:
                float(normalized_row['value'])
            except (ValueError, TypeError):
                continue
            
            data.append(normalized_row)
        
        # Загружаем нормы
        norms = load_norms()
        
        # Группируем по категориям
        groups = group_by_category(data, norms)
        
        # Получаем анализы не в норме
        abnormal_tests = get_abnormal_tests(data, norms)
        
        # Подготавливаем данные для графиков (только для одного пациента)
        charts = prepare_chart_data(data, norms)
        
        return {
            'groups': groups,
            'abnormal_tests': abnormal_tests,
            'charts': charts
        }
    
    except Exception as e:
        logger.error(f"Ошибка обработки данных пациента: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки данных: {str(e)}"
        )


@router.post("/upload-patient-data")
async def upload_patient_data(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Загружает файл с данными пациента и добавляет их в систему."""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Поддерживаются только CSV файлы")
        contents = await file.read()
        temp_file = Path(__file__).parent.parent.parent / "data" / f"temp_{file.filename}"
        with open(temp_file, 'wb') as f:
            f.write(contents)
        try:
            df = pd.read_csv(temp_file)
            required_columns = ['patient_id', 'test_code', 'value']
            missing = [col for col in required_columns if col not in df.columns]
            if missing:
                raise HTTPException(status_code=400, detail=f"Отсутствуют колонки: {', '.join(missing)}")
            normalized_data = []
            for _, row in df.iterrows():
                patient_id = str(row.get('patient_id', ''))
                test_code = str(row.get('test_code', ''))
                value = row.get('value', None)
                if not patient_id or not test_code or pd.isna(value):
                    continue
                try:
                    float_value = float(value)
                except:
                    continue
                normalized_data.append({
                    'patient_id': patient_id,
                    'test_code': test_code,
                    'test_name': str(row.get('test_name', '')) if 'test_name' in df.columns else test_code,
                    'value': float_value,
                    'unit': str(row.get('unit', '')) if 'unit' in df.columns else '',
                    'date': str(row.get('date', '')) if 'date' in df.columns else '',
                    'status': str(row.get('status', '')) if 'status' in df.columns else ''
                })
            if not normalized_data:
                raise HTTPException(status_code=400, detail="Нет валидных данных")
            if UPLOADED_DATA_FILE.exists():
                existing_df = pd.read_csv(UPLOADED_DATA_FILE)
                new_df = pd.DataFrame(normalized_data)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['patient_id', 'test_code', 'date'], keep='last')
            else:
                combined_df = pd.DataFrame(normalized_data)
            combined_df.to_csv(UPLOADED_DATA_FILE, index=False)
            return {'success': True, 'message': f'Загружено записей: {len(normalized_data)}', 'total': len(combined_df)}
        finally:
            if temp_file.exists():
                temp_file.unlink()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patients-list-from-uploaded")
async def get_patients_list_from_uploaded() -> List[Dict[str, Any]]:
    """Получает список всех пациентов из загруженных файлов"""
    if not UPLOADED_DATA_FILE.exists():
        return []
    try:
        df = pd.read_csv(UPLOADED_DATA_FILE)
        patients = []
        for patient_id in df['patient_id'].unique():
            patient_data = df[df['patient_id'] == patient_id]
            date_column = 'date' if 'date' in df.columns else None
            if date_column:
                dates = sorted(patient_data[date_column].dropna().unique())
                first_date = dates[0] if dates else None
                last_date = dates[-1] if dates else None
            else:
                first_date = None
                last_date = None
            test_code_column = 'test_code' if 'test_code' in df.columns else None
            if test_code_column:
                test_count = len(patient_data[test_code_column].dropna().unique())
            else:
                test_count = 0
            patients.append({
                'patient_id': str(patient_id),
                'first_date': str(first_date) if first_date else None,
                'last_date': str(last_date) if last_date else None,
                'test_count': test_count,
                'record_count': len(patient_data)
            })
        patients.sort(key=lambda x: x['patient_id'])
        return patients
    except Exception as e:
        logger.error(f"Ошибка получения списка пациентов из загруженных данных: {e}")
        return []


@router.get("/patient-data-from-uploaded")
async def get_patient_data_from_uploaded(patient_id: str) -> Dict[str, Any]:
    """Получает данные пациента из загруженных файлов"""
    if not UPLOADED_DATA_FILE.exists():
        raise HTTPException(status_code=404, detail="Загруженные данные не найдены")
    try:
        df = pd.read_csv(UPLOADED_DATA_FILE)
        patient_df = df[df['patient_id'].astype(str) == str(patient_id)]
        if patient_df.empty:
            raise HTTPException(status_code=404, detail=f"Пациент {patient_id} не найден в загруженных данных")
        norms = load_norms()
        data = []
        for _, row in patient_df.iterrows():
            test_code = str(row.get('test_code', ''))
            test_name = str(row.get('test_name', '')) if 'test_name' in patient_df.columns else test_code
            value = row.get('value', None)
            date_value = str(row.get('date', '')) if 'date' in patient_df.columns else ''
            unit = str(row.get('unit', '')) if 'unit' in patient_df.columns else ''
            try:
                float_value = float(value)
            except:
                continue
            if not test_name or test_name == test_code:
                norm_info = get_norm_info(test_code, '', norms)
                if norm_info and norm_info.get('name'):
                    test_name = norm_info.get('name', test_code)
            if not unit and test_code:
                norm_info = get_norm_info(test_code, test_name, norms)
                if norm_info and norm_info.get('unit'):
                    unit = norm_info.get('unit', '')
            # Get status from CSV if available
            status_from_csv = str(row.get('status', '')).strip().upper() if 'status' in patient_df.columns else ''
            
            normalized_row = {
                'patient_id': str(patient_id),
                'test_code': test_code,
                'test_name': test_name,
                'value': float_value,
                'date': date_value,
                'unit': unit,
                'status': status_from_csv if status_from_csv in ['HIGH', 'LOW', 'NORMAL'] else ''
            }
            data.append(normalized_row)
        groups = group_by_category(data, norms)
        abnormal_tests = get_abnormal_tests(data, norms)
        charts = prepare_chart_data(data, norms)
        return {
            'patient_id': str(patient_id),
            'groups': groups,
            'abnormal_tests': abnormal_tests,
            'charts': charts
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки данных пациента: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки данных: {str(e)}")

