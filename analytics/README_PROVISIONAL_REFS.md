# Инструкция по замене временных референсов на официальные

## Обзор

Этот документ описывает, как заменить временные (provisional) референсы, созданные статистическими методами, на официальные референсные диапазоны от лаборатории или клинических стандартов.

## Структура временных референсов

Временные референсы хранятся в файле `output/provisional_references.csv` и в JSON-отчете `output/lab_data_analysis_report.json` в секции `provisional_refs`.

Формат каждого референса:
```json
{
  "test_name": "test_chem_glucose",
  "by": "overall",
  "low": 70.0,
  "high": 199.0,
  "method": "percentile_2.5_97.5",
  "note": "PROVISIONAL - временный референс, требует замены на официальный"
}
```

## Шаги замены

### 1. Подготовка официальных референсов

Соберите официальные референсные диапазоны из следующих источников:
- Лабораторные стандарты (CLSI, IFCC)
- Референсы производителя тест-систем
- Клинические руководства (например, для конкретных возрастных групп или пола)

**Важно:** Убедитесь, что единицы измерения совпадают с данными в датасете.

### 2. Формат официальных референсов

Создайте файл `official_references.json` в следующем формате:

```json
{
  "test_chem_glucose": {
    "by": "overall",
    "low": 70.0,
    "high": 100.0,
    "unit": "mg/dL",
    "source": "CLSI C28-A3",
    "note": "Fasting glucose",
    "is_official": true
  },
  "test_chem_glucose_sex_Male": {
    "by": "sex",
    "sex": "Male",
    "low": 70.0,
    "high": 100.0,
    "unit": "mg/dL",
    "source": "Lab Standard",
    "is_official": true
  },
  "test_chem_glucose_age_Young Adult": {
    "by": "age_group",
    "age_group": "Young Adult",
    "low": 70.0,
    "high": 100.0,
    "unit": "mg/dL",
    "source": "Lab Standard",
    "is_official": true
  }
}
```

### 3. Интеграция в пайплайн

#### Вариант A: Замена в коде

Добавьте функцию загрузки официальных референсов в ноутбук:

```python
def load_official_references(file_path: str) -> Dict[str, Dict[str, Any]]:
    """Загружает официальные референсы из JSON файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Загружаем официальные референсы
official_refs = load_official_references('official_references.json')

# Объединяем с временными (официальные имеют приоритет)
all_refs = {**provisional_refs, **official_refs}
```

#### Вариант B: Замена в данных

Если вы хотите заменить референсы в уже обработанных данных:

```python
# Загружаем очищенные данные
df = pd.read_csv('output/cleaned_lab_data.csv')

# Загружаем официальные референсы
official_refs = load_official_references('official_references.json')

# Пересчитываем статусы с официальными референсами
df_updated = mark_relative_status(df, official_refs)

# Сохраняем обновленные данные
df_updated.to_csv('output/cleaned_lab_data_with_official_refs.csv', index=False)
```

### 4. Валидация замены

После замены проверьте:

1. **Количество изменений статусов:**
   ```python
   # Сравните статусы до и после замены
   status_before = df['test_chem_glucose_status'].value_counts()
   status_after = df_updated['test_chem_glucose_status'].value_counts()
   print("До замены:", status_before)
   print("После замены:", status_after)
   ```

2. **Визуализация изменений:**
   ```python
   # Постройте графики распределения с новыми референсами
   # Убедитесь, что референсы логичны для данных
   ```

3. **Клиническая валидность:**
   - Проверьте, что новые референсы соответствуют клиническим стандартам
   - Убедитесь, что разделение по полу/возрасту корректно

### 5. Обновление отчета

После замены обновите финальный отчет:

```python
# Создайте новый отчет с официальными референсами
final_report_updated = generate_final_report(
    schema_suggestions,
    cleaning_report,
    stats_by_test,
    official_refs,  # Используем официальные вместо временных
    flagged_rows,
    sample_dashboard,
    suspect_examples,
    outlier_examples
)

# Сохраните обновленный отчет
with open('output/lab_data_analysis_report_official.json', 'w', encoding='utf-8') as f:
    json.dump(final_report_updated, f, indent=2, ensure_ascii=False)
```

## Примеры официальных референсов

### Blood Chemistry (chem)

| Test | Low | High | Unit | Source |
|------|-----|------|------|--------|
| chem.glucose | 70 | 100 | mg/dL | ADA Standards |
| chem.creatinine | 0.7 | 1.3 | mg/dL | Lab Standard |
| chem.alt | 7 | 52 | U/L | Lab Standard |

### Blood Counts (bc)

| Test | Low | High | Unit | Source |
|------|-----|------|------|--------|
| bc.hemoglobin | 12.1 | 18.1 | g/dL | Lab Standard |
| bc.wbc | 4.0 | 11.1 | 10³/µL | Lab Standard |
| bc.platelet_count | 150 | 400 | 10³/µL | Lab Standard |

**Примечание:** Эти значения приведены как примеры. Используйте референсы, актуальные для вашей лаборатории и популяции.

## Рекомендации

1. **Приоритет источников:**
   - Референсы производителя тест-систем (наиболее точные)
   - Референсы вашей лаборатории (учитывают местные условия)
   - Клинические стандарты (CLSI, IFCC)
   - Временные референсы (только если нет других источников)

2. **Разделение по группам:**
   - Всегда используйте специфичные референсы (по полу/возрасту), если они доступны
   - Общие референсы используйте только как fallback

3. **Документирование:**
   - Сохраняйте источник каждого референса
   - Отмечайте дату получения референса
   - Ведите версионирование референсов

4. **Периодический пересмотр:**
   - Референсы могут меняться со временем
   - Регулярно проверяйте актуальность референсов
   - Обновляйте при изменении лабораторных стандартов

## Автоматизация

Для автоматической замены можно создать скрипт:

```python
# replace_references.py
import json
import pandas as pd

def replace_references(
    provisional_file: str,
    official_file: str,
    output_file: str
):
    """Заменяет временные референсы на официальные."""
    with open(provisional_file, 'r', encoding='utf-8') as f:
        provisional = json.load(f)
    
    with open(official_file, 'r', encoding='utf-8') as f:
        official = json.load(f)
    
    # Объединяем (официальные имеют приоритет)
    updated = {**provisional, **official}
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
    
    print(f"Референсы обновлены. Сохранено в: {output_file}")

if __name__ == "__main__":
    replace_references(
        'output/provisional_references.json',
        'official_references.json',
        'output/final_references.json'
    )
```

## Контакты и поддержка

При возникновении вопросов:
1. Проверьте документацию лаборатории
2. Обратитесь к клиническому химику или лаборанту
3. Используйте клинические руководства (CLSI, IFCC)

---

**Важно:** Временные референсы созданы статистическими методами и НЕ должны использоваться для клинической диагностики. Замените их на официальные референсы как можно скорее.

