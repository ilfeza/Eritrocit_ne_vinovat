import json
import numpy as np
from typing import Dict, Any, Union, Tuple


def remove_empty_and_duplicates(data: Union[Dict[str, Any], str]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Удаляет пустые записи и дубликаты из JSON данных.
    
    Args:
        data: JSON данные (dict или JSON строка) с полями test_names и patients
        
    Returns:
        tuple: (очищенные данные, статистика удаления)
        Статистика содержит: removed_empty, removed_duplicates, total_before, total_after
    """
    # Если передан JSON строка, парсим её
    if isinstance(data, str):
        data = json.loads(data)
    
    result = data.copy()
    stats = {
        'removed_empty': 0,
        'removed_duplicates': 0,
        'total_before': 0,
        'total_after': 0
    }
    
    if 'patients' not in result:
        return result, stats
    
    patients = result['patients']
    stats['total_before'] = len(patients)
    
    # Шаг 1: Удаление пустых записей
    # Пустая запись = нет анализов или все анализы с пустыми/невалидными значениями
    valid_patients = []
    for patient in patients:
        if 'analyses' not in patient or not patient['analyses']:
            stats['removed_empty'] += 1
            continue
        
        # Проверяем, есть ли хотя бы один валидный анализ
        has_valid_analysis = False
        for test_id, analysis in patient['analyses'].items():
            if 'value' in analysis:
                try:
                    value = float(analysis['value'])
                    if not np.isnan(value) and np.isfinite(value):
                        has_valid_analysis = True
                        break
                except (ValueError, TypeError):
                    continue
        
        if has_valid_analysis:
            valid_patients.append(patient)
        else:
            stats['removed_empty'] += 1
    
    # Шаг 2: Удаление дубликатов
    # Дубликат = одинаковые patient_id, date и все анализы
    seen = set()
    unique_patients = []
    
    for patient in valid_patients:
        # Создаем ключ для проверки дубликатов
        patient_id = patient.get('patient_id', '')
        date = patient.get('date', '')
        
        # Сортируем анализы для консистентного сравнения
        analyses_key = json.dumps(
            {k: v for k, v in sorted(patient.get('analyses', {}).items())},
            sort_keys=True
        )
        
        duplicate_key = f"{patient_id}|{date}|{analyses_key}"
        
        if duplicate_key not in seen:
            seen.add(duplicate_key)
            unique_patients.append(patient)
        else:
            stats['removed_duplicates'] += 1
    
    result['patients'] = unique_patients
    stats['total_after'] = len(unique_patients)
    
    return result, stats


def remove_outliers_3sigma(data: Union[Dict[str, Any], str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Удаляет выбросы по правилу трех сигм (μ ± 3σ) для каждого теста отдельно.
    
    Args:
        data: JSON данные (dict или JSON строка) с полями test_names и patients
        
    Returns:
        tuple: (очищенные данные, статистика удаления)
        Статистика содержит: outliers_by_test (словарь с количеством выбросов по каждому тесту),
                            total_outliers, total_removed_patients
    """
    # Если передан JSON строка, парсим её
    if isinstance(data, str):
        data = json.loads(data)
    
    result = data.copy()
    stats = {
        'outliers_by_test': {},
        'total_outliers': 0,
        'total_removed_patients': 0
    }
    
    if 'patients' not in result or not result['patients']:
        return result, stats
    
    # Собираем все значения для каждого теста
    test_values = {}  # {test_id: [список значений]}
    patient_indices = {}  # {test_id: [список индексов пациентов]}
    
    for idx, patient in enumerate(result['patients']):
        if 'analyses' not in patient:
            continue
        
        for test_id, analysis in patient['analyses'].items():
            if 'value' not in analysis:
                continue
            
            try:
                value = float(analysis['value'])
                if np.isnan(value) or not np.isfinite(value):
                    continue
                
                if test_id not in test_values:
                    test_values[test_id] = []
                    patient_indices[test_id] = []
                
                test_values[test_id].append(value)
                patient_indices[test_id].append(idx)
            except (ValueError, TypeError):
                continue
    
    # Вычисляем границы для каждого теста по правилу трех сигм
    test_bounds = {}  # {test_id: (lower_bound, upper_bound)}
    
    for test_id, values in test_values.items():
        if len(values) < 2:  # Нужно минимум 2 значения для вычисления σ
            continue
        
        values_array = np.array(values)
        mean = np.mean(values_array)
        std = np.std(values_array)
        
        if std == 0:  # Если все значения одинаковые, нет выбросов
            continue
        
        lower_bound = mean - 3 * std
        upper_bound = mean + 3 * std
        
        test_bounds[test_id] = (lower_bound, upper_bound)
    
    # Помечаем выбросы
    outliers_to_remove = set()  # Множество (patient_idx, test_id) для удаления
    
    for test_id, bounds in test_bounds.items():
        lower, upper = bounds
        outlier_count = 0
        
        for idx, patient_idx in enumerate(patient_indices[test_id]):
            value = test_values[test_id][idx]
            
            if value < lower or value > upper:
                outliers_to_remove.add((patient_idx, test_id))
                outlier_count += 1
        
        if outlier_count > 0:
            stats['outliers_by_test'][test_id] = {
                'count': outlier_count,
                'bounds': {'lower': float(lower), 'upper': float(upper)},
                'mean': float(np.mean(test_values[test_id])),
                'std': float(np.std(test_values[test_id]))
            }
    
    stats['total_outliers'] = len(outliers_to_remove)
    
    # Удаляем выбросы из анализов пациентов
    patients_to_remove = set()
    
    for patient_idx, patient in enumerate(result['patients']):
        if 'analyses' not in patient:
            continue
        
        analyses_to_remove = []
        for test_id in patient['analyses'].keys():
            if (patient_idx, test_id) in outliers_to_remove:
                analyses_to_remove.append(test_id)
        
        # Удаляем выбросы из анализов
        for test_id in analyses_to_remove:
            del patient['analyses'][test_id]
        
        # Если у пациента не осталось анализов, помечаем для удаления
        if not patient.get('analyses'):
            patients_to_remove.add(patient_idx)
    
    # Удаляем пациентов без анализов
    if patients_to_remove:
        result['patients'] = [
            patient for idx, patient in enumerate(result['patients'])
            if idx not in patients_to_remove
        ]
        stats['total_removed_patients'] = len(patients_to_remove)
    
    return result, stats


def preprocess_json(data: Union[Dict[str, Any], str], 
                    remove_empty: bool = True,
                    remove_duplicates: bool = True,
                    remove_outliers: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Полная предобработка JSON данных: удаление пустых, дубликатов и выбросов.
    
    Args:
        data: JSON данные (dict или JSON строка) с полями test_names и patients
        remove_empty: Удалять ли пустые записи
        remove_duplicates: Удалять ли дубликаты
        remove_outliers: Удалять ли выбросы по правилу трех сигм
        
    Returns:
        tuple: (очищенные данные, общая статистика)
    """
    # Если передан JSON строка, парсим её
    if isinstance(data, str):
        data = json.loads(data)
    
    result = data.copy()
    all_stats = {
        'empty_and_duplicates': {},
        'outliers': {},
        'total_before': 0,
        'total_after': 0
    }
    
    if 'patients' in result:
        all_stats['total_before'] = len(result['patients'])
    
    # Шаг 1: Удаление пустых и дубликатов
    if remove_empty or remove_duplicates:
        result, empty_stats = remove_empty_and_duplicates(result)
        all_stats['empty_and_duplicates'] = empty_stats
    
    # Шаг 2: Удаление выбросов
    if remove_outliers:
        result, outlier_stats = remove_outliers_3sigma(result)
        all_stats['outliers'] = outlier_stats
    
    if 'patients' in result:
        all_stats['total_after'] = len(result['patients'])
    
    return result, all_stats

