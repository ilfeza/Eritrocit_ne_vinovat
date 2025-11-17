import json
import re
from typing import Dict, Any, Union, Tuple, List, Optional
from pathlib import Path

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    print("Предупреждение: rapidfuzz не установлен. Установите через: pip install rapidfuzz")


def transliterate_cyrillic_to_latin(text: str) -> str:
    """
    Транслитерирует кириллицу в латиницу.
    
    Args:
        text: Текст с возможными кириллическими символами
    
    Returns:
        Транслитерированный текст
    """
    cyrillic_to_latin = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    
    result = []
    for char in text:
        if char in cyrillic_to_latin:
            result.append(cyrillic_to_latin[char])
        else:
            result.append(char)
    
    return ''.join(result)


def normalize_column_name(name: str) -> str:
    """
    Нормализует название столбца:
    - Приводит к нижнему регистру
    - Транслитерирует кириллицу в латиницу
    - Удаляет цифры
    - Удаляет лишние символы (оставляет только буквы и подчеркивания)
    - Заменяет пробелы и точки на подчеркивания
    - Удаляет множественные подчеркивания
    
    Args:
        name: Исходное название столбца
    
    Returns:
        Нормализованное название
    """
    if not isinstance(name, str):
        name = str(name)
    
    # Транслитерация кириллицы
    normalized = transliterate_cyrillic_to_latin(name)
    
    # Приводим к нижнему регистру
    normalized = normalized.lower()
    
    # Заменяем точки и пробелы на подчеркивания
    normalized = normalized.replace('.', '_').replace(' ', '_').replace('-', '_')
    
    # Удаляем все символы кроме букв и подчеркиваний
    normalized = re.sub(r'[^a-z_]', '', normalized)
    
    # Удаляем цифры (по требованию)
    normalized = re.sub(r'\d+', '', normalized)
    
    # Удаляем множественные подчеркивания
    normalized = re.sub(r'_+', '_', normalized)
    
    # Удаляем подчеркивания в начале и конце
    normalized = normalized.strip('_')
    
    return normalized


def cluster_similar_names(
    names: List[str],
    similarity_threshold: float = 0.85
) -> Dict[str, List[str]]:
    """
    Группирует схожие названия в кластеры используя rapidfuzz.
    
    Args:
        names: Список названий для кластеризации
        similarity_threshold: Порог схожести (0-1), выше которого названия считаются схожими
    
    Returns:
        dict: {cluster_name: [original_names], ...}
    """
    if not RAPIDFUZZ_AVAILABLE:
        # Fallback: простая группировка по нормализованным названиям
        clusters = {}
        for name in names:
            normalized = normalize_column_name(name)
            if normalized not in clusters:
                clusters[normalized] = []
            clusters[normalized].append(name)
        return clusters
    
    # Нормализуем все названия
    normalized_map = {name: normalize_column_name(name) for name in names}
    
    # Кластеризация через rapidfuzz
    clusters = {}  # {cluster_name: [original_names]}
    assigned = set()  # Уже назначенные названия
    
    for name in names:
        if name in assigned:
            continue
        
        normalized = normalized_map[name]
        cluster_members = [name]
        assigned.add(name)
        
        # Ищем схожие названия среди оставшихся
        for other_name in names:
            if other_name in assigned:
                continue
            
            other_normalized = normalized_map[other_name]
            
            # Используем rapidfuzz для сравнения
            similarity = max(
                fuzz.ratio(normalized, other_normalized) / 100.0,
                fuzz.partial_ratio(normalized, other_normalized) / 100.0,
                fuzz.token_sort_ratio(normalized, other_normalized) / 100.0
            )
            
            if similarity >= similarity_threshold:
                cluster_members.append(other_name)
                assigned.add(other_name)
        
        # Выбираем имя кластера (самое короткое или первое по алфавиту)
        cluster_name = min(cluster_members, key=lambda x: (len(x), x))
        clusters[cluster_name] = cluster_members
    
    return clusters


def create_test_mapping(
    json_test_ids: List[str],
    excel_test_ids: List[str],
    excel_test_names: Optional[Dict[str, str]] = None,
    similarity_threshold: float = 0.85
) -> Dict[str, str]:
    """
    Создает маппинг между test_id из JSON и test_id из Excel на основе схожести названий.
    
    Args:
        json_test_ids: Список test_id из JSON (например, ["chem.alt", "Alanine Transaminase"])
        excel_test_ids: Список test_id из Excel (например, ["chem.alt", "chem.ast"])
        excel_test_names: Опциональный словарь {test_id: test_name} из Excel для более точного сопоставления
        similarity_threshold: Порог схожести для кластеризации
    
    Returns:
        dict: {json_test_id: excel_test_id, ...} - маппинг JSON test_id на Excel test_id
    """
    mapping = {}
    
    # Сначала пытаемся точное совпадение
    json_set = set(json_test_ids)
    excel_set = set(excel_test_ids)
    
    for json_id in json_test_ids:
        if json_id in excel_set:
            mapping[json_id] = json_id
            continue
    
    # Для оставшихся используем fuzzy matching
    remaining_json = [jid for jid in json_test_ids if jid not in mapping]
    remaining_excel = [eid for eid in excel_test_ids if eid not in mapping.values()]
    
    if not remaining_json or not remaining_excel:
        return mapping
    
    # Нормализуем все названия
    json_normalized = {jid: normalize_column_name(jid) for jid in remaining_json}
    excel_normalized = {eid: normalize_column_name(eid) for eid in remaining_excel}
    
    # Если есть названия тестов из Excel, используем их для более точного сопоставления
    if excel_test_names:
        for json_id in remaining_json:
            json_norm = json_normalized[json_id]
            best_match = None
            best_score = 0.0
            
            for excel_id in remaining_excel:
                if excel_id in mapping.values():
                    continue
                
                excel_norm = excel_normalized[excel_id]
                
                # Сравниваем нормализованные ID
                score1 = max(
                    fuzz.ratio(json_norm, excel_norm) / 100.0,
                    fuzz.partial_ratio(json_norm, excel_norm) / 100.0,
                    fuzz.token_sort_ratio(json_norm, excel_norm) / 100.0
                ) if RAPIDFUZZ_AVAILABLE else 0.0
                
                # Если есть название теста, сравниваем и с ним
                if excel_id in excel_test_names:
                    excel_name = excel_test_names[excel_id]
                    excel_name_norm = normalize_column_name(excel_name)
                    score2 = max(
                        fuzz.ratio(json_norm, excel_name_norm) / 100.0,
                        fuzz.partial_ratio(json_norm, excel_name_norm) / 100.0,
                        fuzz.token_sort_ratio(json_norm, excel_name_norm) / 100.0
                    ) if RAPIDFUZZ_AVAILABLE else 0.0
                    score = max(score1, score2)
                else:
                    score = score1
                
                if score > best_score and score >= similarity_threshold:
                    best_score = score
                    best_match = excel_id
            
            if best_match:
                mapping[json_id] = best_match
    else:
        # Простое сопоставление по нормализованным названиям
        for json_id in remaining_json:
            json_norm = json_normalized[json_id]
            best_match = None
            best_score = 0.0
            
            for excel_id in remaining_excel:
                if excel_id in mapping.values():
                    continue
                
                excel_norm = excel_normalized[excel_id]
                
                if RAPIDFUZZ_AVAILABLE:
                    score = max(
                        fuzz.ratio(json_norm, excel_norm) / 100.0,
                        fuzz.partial_ratio(json_norm, excel_norm) / 100.0,
                        fuzz.token_sort_ratio(json_norm, excel_norm) / 100.0
                    )
                else:
                    score = 1.0 if json_norm == excel_norm else 0.0
                
                if score > best_score and score >= similarity_threshold:
                    best_score = score
                    best_match = excel_id
            
            if best_match:
                mapping[json_id] = best_match
    
    return mapping


def process_json(data: Union[Dict[str, Any], str], json_path: str = None, similarity_threshold: float = 0.85) -> Dict[str, Any]:
    """
    Обрабатывает JSON от фронтенда и обогащает его данными из JSON файла с метаданными.
    Использует fuzzy matching для сопоставления названий тестов, даже если они написаны по-разному.
    
    Args:
        data: JSON данные (dict или JSON строка) с полями test_names и patients
        json_path: Путь к JSON файлу с метаданными. Если None, используется 'data/data.json'
        similarity_threshold: Порог схожести для fuzzy matching (0-1, по умолчанию 0.85)
        
    Returns:
        dict: Обогащенный JSON с добавленными именами и единицами из JSON файла
    """
    # Если передан JSON строка, парсим её
    if isinstance(data, str):
        data = json.loads(data)
    
    # Определяем путь к JSON файлу с метаданными
    if json_path is None:
        current_dir = Path(__file__).parent
        json_path = str(current_dir / 'data.json')
    
    # Загружаем метаданные из JSON файла
    # Структура data.json: массив объектов с полями 'id', 'name', 'unit', 'min', 'max'
    # id - это test_code (например, "bc.perc_monocytes")
    # name - это название теста (например, "% Monocytes")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
    except FileNotFoundError:
        print(f"[name_of_analysis] ОШИБКА: JSON файл не найден по пути {json_path}")
        # Пробуем альтернативный путь
        current_dir = Path(__file__).parent
        json_path = str(current_dir / 'data' / 'data.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
        except FileNotFoundError:
            print(f"[name_of_analysis] ОШИБКА: JSON файл не найден по альтернативному пути {json_path}")
            raise FileNotFoundError(f"JSON файл с метаданными не найден: {json_path}")
    
    metadata = {}
    excel_test_ids = []
    excel_test_names = {}
    # Обратный маппинг: name -> id для быстрого поиска
    excel_name_to_id = {}
    
    # Также создаем список всех названий из JSON для fuzzy matching
    excel_all_names = []  # Список всех названий из JSON для поиска
    
    for item in metadata_list:
        test_id = str(item.get('id', '')).strip() if item.get('id') else None
        if test_id and test_id.lower() not in ['nan', 'none', '']:
            excel_test_ids.append(test_id)
            test_name = str(item.get('name', '')).strip() if item.get('name') else test_id
            excel_test_names[test_id] = test_name
            metadata[test_id] = {
                'name': test_name,
                'unit': str(item.get('unit', '')).strip() if item.get('unit') else '',
                'min': item.get('min'),
                'max': item.get('max')
            }
            # Создаем обратный маппинг: name -> id
            if test_name:
                # Сохраняем оригинальное название (регистронезависимо)
                excel_name_to_id[test_name.lower()] = test_id
                # Также сохраняем нормализованное название
                normalized_name = normalize_column_name(test_name)
                if normalized_name:
                    excel_name_to_id[normalized_name] = test_id
                # Добавляем в список для fuzzy matching
                excel_all_names.append((test_name, test_id))
    
    # Создаем копию данных
    result = data.copy()
    
    # Собираем все test_id из JSON (из test_names и из analyses пациентов)
    json_test_ids = []
    if 'test_names' in result:
        json_test_ids.extend(result['test_names'].keys())
    
    if 'patients' in result:
        for patient in result['patients']:
            if 'analyses' in patient:
                json_test_ids.extend(patient['analyses'].keys())
    
    # Убираем дубликаты
    json_test_ids = list(set(json_test_ids))
    
    # Создаем маппинг между JSON test_id и Excel test_id
    test_mapping = create_test_mapping(
        json_test_ids=json_test_ids,
        excel_test_ids=excel_test_ids,
        excel_test_names=excel_test_names,
        similarity_threshold=similarity_threshold
    )
    
    # Обогащаем test_names: сопоставляем колонки загруженной таблицы с data.xlsx
    # ВАЖНО: Формат должен быть {название_колонки: test_code_из_excel}
    # Например: {"% Monocytes": "bc.perc_monocytes"}
    # Сопоставление: название колонки из таблицы -> name в Excel -> id из Excel
    
    # Если test_names не существует, создаем его из анализов пациентов
    if 'test_names' not in result and 'patients' in result:
        result['test_names'] = {}
        for patient in result['patients']:
            if 'analyses' in patient:
                for test_id in patient['analyses'].keys():
                    if test_id not in result['test_names']:
                        result['test_names'][test_id] = test_id  # Временно, будет заменено ниже
    
    if 'test_names' in result:
        enriched_test_names = {}
        
        for test_id, existing_name_data in result['test_names'].items():
            # test_id - это название колонки из загруженной таблицы (например, "% Monocytes")
            # Нужно найти соответствующий test_code (id) из Excel по name
            
            found_excel_id = None
            
            # 1. Прямое совпадение с name в Excel (регистронезависимо)
            if test_id.lower() in excel_name_to_id:
                found_excel_id = excel_name_to_id[test_id.lower()]
            
            # 2. Если не нашли, пробуем нормализованное сравнение
            if not found_excel_id:
                test_id_normalized = normalize_column_name(test_id)
                if test_id_normalized in excel_name_to_id:
                    found_excel_id = excel_name_to_id[test_id_normalized]
            
            # 3. Если не нашли, пробуем через маппинг (fuzzy matching уже был создан)
            if not found_excel_id:
                excel_test_id = test_mapping.get(test_id, None)
                if excel_test_id and excel_test_id in metadata:
                    found_excel_id = excel_test_id
            
            # 4. Если не нашли, пробуем поиск по частичному совпадению
            if not found_excel_id:
                test_id_lower = test_id.lower()
                for excel_name, excel_id in excel_name_to_id.items():
                    if test_id_lower in excel_name or excel_name in test_id_lower:
                        found_excel_id = excel_id
                        break
            
            # 5. Если не нашли, используем fuzzy matching с названиями из Excel
            if not found_excel_id and RAPIDFUZZ_AVAILABLE:
                test_id_normalized = normalize_column_name(test_id)
                best_match = None
                best_score = 0.0
                
                for excel_name, excel_id in excel_all_names:
                    excel_name_normalized = normalize_column_name(excel_name)
                    
                    # Сравниваем нормализованные названия
                    score = max(
                        fuzz.ratio(test_id_normalized, excel_name_normalized) / 100.0,
                        fuzz.partial_ratio(test_id_normalized, excel_name_normalized) / 100.0,
                        fuzz.token_sort_ratio(test_id_normalized, excel_name_normalized) / 100.0,
                        fuzz.token_set_ratio(test_id_normalized, excel_name_normalized) / 100.0
                    )
                    
                    # Также сравниваем с оригинальными названиями
                    score2 = max(
                        fuzz.ratio(test_id.lower(), excel_name.lower()) / 100.0,
                        fuzz.partial_ratio(test_id.lower(), excel_name.lower()) / 100.0,
                        fuzz.token_sort_ratio(test_id.lower(), excel_name.lower()) / 100.0
                    )
                    
                    final_score = max(score, score2)
                    
                    if final_score > best_score and final_score >= similarity_threshold:
                        best_score = final_score
                        best_match = excel_id
                
                if best_match:
                    found_excel_id = best_match
            
            # 6. Если нашли, используем test_code (id) из Excel
            if found_excel_id:
                # Формат: {название_колонки: test_code_из_excel}
                # Например: {"% Monocytes": "bc.perc_monocytes"}
                enriched_test_names[test_id] = found_excel_id
            else:
                # Если не нашли, оставляем как есть (название колонки)
                enriched_test_names[test_id] = test_id
        
        # Сохраняем маппинг название_колонки -> test_code для использования в analyses
        result['column_name_to_test_code'] = enriched_test_names
        
        # ВАЖНО: Формат test_names должен быть {название_колонки_из_таблицы: название_из_excel}
        # Например: {"% Monocytes": "Hematocrit"}
        # ВАЖНО: ВСЕГДА используем название из Excel, никогда не используем название из таблицы
        column_name_to_excel_name = {}
        for col_name, test_code in enriched_test_names.items():
            excel_name = None
            
            # 1. Пытаемся получить название из metadata по test_code
            if test_code in metadata:
                excel_name = metadata[test_code]['name']
            
            # 2. Если не нашли, пытаемся через excel_test_names
            if excel_name is None and test_code in excel_test_names:
                excel_name = excel_test_names[test_code]
            
            # 3. Если все еще не нашли, пытаемся найти col_name напрямую в Excel
            if excel_name is None:
                if col_name.lower() in excel_name_to_id:
                    found_test_code = excel_name_to_id[col_name.lower()]
                    if found_test_code in metadata:
                        excel_name = metadata[found_test_code]['name']
            
            # 4. Если все еще не нашли, пытаемся через нормализованное название
            if excel_name is None:
                col_name_normalized = normalize_column_name(col_name)
                if col_name_normalized in excel_name_to_id:
                    found_test_code = excel_name_to_id[col_name_normalized]
                    if found_test_code in metadata:
                        excel_name = metadata[found_test_code]['name']
            
            # 5. Если все еще не нашли, используем fuzzy matching
            if excel_name is None and RAPIDFUZZ_AVAILABLE:
                best_match = None
                best_score = 0.0
                for excel_name_candidate, excel_id in excel_all_names:
                    score = max(
                        fuzz.ratio(col_name.lower(), excel_name_candidate.lower()) / 100.0,
                        fuzz.partial_ratio(col_name.lower(), excel_name_candidate.lower()) / 100.0,
                        fuzz.token_sort_ratio(col_name.lower(), excel_name_candidate.lower()) / 100.0
                    )
                    if score > best_score and score >= similarity_threshold:
                        best_score = score
                        best_match = excel_id
                
                if best_match and best_match in metadata:
                    excel_name = metadata[best_match]['name']
            
            # 6. Если ВСЕ ЕЩЕ не нашли, это критическая ошибка
            if excel_name is None:
                print(f"[name_of_analysis] КРИТИЧЕСКАЯ ОШИБКА: не удалось найти название из Excel для колонки '{col_name}' (test_code: '{test_code}')")
                print(f"[name_of_analysis] Доступные названия в Excel: {list(excel_test_names.values())[:10]}")
                # В крайнем случае используем col_name, но это НЕПРАВИЛЬНО
                excel_name = col_name
            
            # ВСЕГДА сохраняем название из Excel (или col_name в крайнем случае)
            column_name_to_excel_name[col_name] = excel_name
        
        result['test_names'] = column_name_to_excel_name
        
        # Логируем результаты сопоставления для отладки
        matched_count = sum(1 for k, v in enriched_test_names.items() if k != v)
        total_count = len(enriched_test_names)
        print(f"[name_of_analysis] Сопоставлено {matched_count} из {total_count} анализов с Excel")
        if matched_count > 0:
            print(f"[name_of_analysis] Примеры сопоставления (название_колонки -> название_из_excel):")
            for i, (col_name, excel_name) in enumerate(list(column_name_to_excel_name.items())[:5]):
                if col_name != excel_name:
                    test_code = enriched_test_names.get(col_name, col_name)
                    print(f"  '{col_name}' -> '{excel_name}' (test_code: '{test_code}')")
    
    # Обогащаем анализы пациентов: добавляем unit из Excel
    # ВАЖНО: В analyses ключи остаются как названия колонок из загруженной таблицы
    # Но мы используем test_code из Excel для получения unit
    if 'patients' in result:
        # Создаем маппинг: название_колонки -> test_code_из_excel (из column_name_to_test_code)
        column_to_excel_id = {}
        if 'column_name_to_test_code' in result:
            column_to_excel_id = result['column_name_to_test_code'].copy()
        
        for patient in result['patients']:
            if 'analyses' in patient:
                for test_id, analysis in patient['analyses'].items():
                    # test_id - это название колонки из загруженной таблицы
                    # Находим соответствующий test_code из Excel
                    excel_test_id = column_to_excel_id.get(test_id, test_id)
                    
                    # Если excel_test_id это test_code из Excel, используем его для получения unit
                    if excel_test_id in metadata:
                        analysis['unit'] = metadata[excel_test_id]['unit']
                    elif 'unit' not in analysis:
                        analysis['unit'] = ''
    
    return result