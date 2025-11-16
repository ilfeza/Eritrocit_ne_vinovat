# Автоматизация предобработки лабораторных данных

Этот проект содержит инструменты для автоматической предобработки CSV/Excel файлов с результатами лабораторных анализов и создания временных референсных диапазонов.

## Структура проекта

```
analytics/
├── data/
│   └── human_immune_health_atlas_metadata_clinical_labs.csv  # Исходные данные
├── lab_data_preprocessing.ipynb  # Основной ноутбук с пайплайном
├── README.md  # Этот файл
├── README_PROVISIONAL_REFS.md  # Инструкция по замене временных референсов
└── output/  # Результаты обработки (создается автоматически)
    ├── lab_data_analysis_report.json  # Полный JSON отчет
    ├── cleaned_lab_data.csv  # Очищенные данные с маркировками
    ├── test_statistics.csv  # Статистика по тестам
    ├── provisional_references.csv  # Временные референсы
    ├── suspect_examples.csv  # Примеры подозрительных значений
    └── outlier_examples.csv  # Примеры выбросов
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install pandas numpy matplotlib seaborn jupyter scikit-learn
```

### 2. Запуск ноутбука

```bash
jupyter notebook lab_data_preprocessing.ipynb
```

Или в JupyterLab:

```bash
jupyter lab lab_data_preprocessing.ipynb
```

### 3. Настройка путей

В первой ячейке ноутбука настройте пути к данным:

```python
DATA_PATH = 'data/human_immune_health_atlas_metadata_clinical_labs.csv'
OUTPUT_DIR = 'output'
```

### 4. Запуск всех ячеек

Выполните все ячейки последовательно (Cell → Run All).

## Что делает пайплайн

### 1. Проверка схемы данных
- Автоматически определяет колонки с `patient_id`, `date`, `test_name`, `value`, `sex`, `age`
- Предлагает нормализованные имена колонок
- Поддерживает префиксы: `am.`, `chem.`, `bc.`, `cmv.`, `infl.`, `lip.`

### 2. Очистка данных
- Удаляет строгие дубликаты
- Парсит даты
- Приводит числовые поля к `float`
- Обнаруживает артефакты:
  - Значения = 0 для тестов, где 0 нереален
  - Экстремальные значения (>10 стандартных отклонений)

### 3. Статистика по тестам
Для каждого теста рассчитывает:
- `count`, `mean`, `median`, `std`
- `min`, `max`
- Перцентили: `p1`, `p2_5`, `p25`, `p75`, `p97_5`, `p99`
- `IQR` (межквартильный размах)

### 4. Временные референсы
Создает временные референсы тремя методами:
- **Метод 1 (рекомендуемый)**: Процентили 2.5-97.5
- **Метод 2**: Median ± 2*IQR
- **Метод 3**: Mean ± 2*Std (z-score)

Поддерживает разделение по:
- Полу (`sex`)
- Возрастным группам (`age_group`)

### 5. Маркировка отклонений
Помечает каждое значение статусом:
- `LOW` - ниже референса
- `NORMAL` - в пределах референса
- `HIGH` - выше референса

### 6. Обнаружение аномалий и выбросов

#### 6a. Аномалии (подсвечивать в дашборде)
Используются методы машинного обучения:
- **Isolation Forest** - изолирует аномалии через случайные деревья
- **DBSCAN** - кластеризация, выявляет точки вне кластеров
- **Local Outlier Factor (LOF)** - обнаруживает локальные аномалии

Консенсус: аномалия, если обнаружена хотя бы двумя методами.

#### 6b. Выбросы (удалять)
Используются строгие статистические методы:
- **IQR (строгий)**: Q1 - 3*IQR, Q3 + 3*IQR
- **Z-score (строгий)**: |z| > 4

### 7. Генерация отчетов
Создает JSON отчет со следующими секциями:
- `schema_suggestions`: Маппинг колонок
- `cleaning_report`: Отчет об очистке
- `stats_by_test`: Статистика по тестам
- `provisional_refs`: Временные референсы
- `flagged_rows`: Помеченные строки
- `sample_dashboard_payload`: Пример для дашборда

## Формат входных данных

Ожидаемые колонки:
- `subject.subjectGuid` или аналогичная → `patient_id`
- `sample.sampleKitGuid` или аналогичная → `sample_id`
- `subject.biologicalSex` → `sex`
- `subject.birthYear` или `subject.ageAtFirstDraw` → `age`
- `sample.drawYear` или аналогичная → `date`
- Тестовые колонки с префиксами: `am.*`, `chem.*`, `bc.*`, `cmv.*`, `infl.*`, `lip.*`

## Формат выходных данных

### JSON отчет (`lab_data_analysis_report.json`)

```json
{
  "schema_suggestions": {"old_col": "new_col", ...},
  "cleaning_report": {
    "rows_before": 1000,
    "rows_after": 950,
    "removed_duplicates": 50,
    "suspect_count": 10
  },
  "stats_by_test": {
    "test_chem_glucose": {
      "count": 500,
      "mean": 95.5,
      "median": 94.0,
      "p2_5": 70.0,
      "p97_5": 120.0
    }
  },
  "provisional_refs": {
    "test_chem_glucose": {
      "by": "overall",
      "low": 70.0,
      "high": 120.0,
      "method": "percentile_2.5_97.5",
      "note": "PROVISIONAL - временный референс"
    }
  },
  "anomaly_detection": {
    "total_anomalies": 15,
    "methods_used": ["IsolationForest", "DBSCAN", "LocalOutlierFactor"],
    "note": "Аномалии обнаружены методами кластеризации - подсвечивать в дашборде"
  },
  "outlier_detection": {
    "total_outliers": 5,
    "methods_used": ["IQR_strict", "Z-score_strict"],
    "note": "Выбросы обнаружены строгими статистическими методами - рекомендуется удалить"
  }
}
```

### CSV файлы

- `cleaned_lab_data.csv`: Очищенные данные с аномалиями (подсвечивать)
- `cleaned_lab_data_no_outliers.csv`: Данные без выбросов (выбросы удалены)
- `anomalies_to_highlight.csv`: Только аномалии для подсветки в дашборде
- `test_statistics.csv`: Статистика по каждому тесту
- `provisional_references.csv`: Временные референсы в табличном формате

## Важные замечания

⚠️ **ВНИМАНИЕ**: Все референсы помечены как `PROVISIONAL` (временные) и созданы статистическими методами. Они **НЕ должны использоваться для клинической диагностики**.

### Замена на официальные референсы

См. подробную инструкцию в `README_PROVISIONAL_REFS.md`:
1. Соберите официальные референсы от лаборатории
2. Создайте файл `official_references.json`
3. Замените временные референсы в пайплайне

## Примеры использования

### Загрузка и анализ данных

```python
import pandas as pd
import json

# Загружаем результаты
with open('output/lab_data_analysis_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

# Загружаем очищенные данные
df = pd.read_csv('output/cleaned_lab_data.csv')

# Фильтруем отклонения
high_glucose = df[df['test_chem_glucose_status'] == 'HIGH']
print(f"Найдено {len(high_glucose)} пациентов с высоким уровнем глюкозы")
```

### Использование для дашборда

JSON payload для дашборда содержит:
- `time_series`: Временной ряд для одного пациента
- `current_snapshot`: Текущие значения с цветными метками

```python
# Пример payload
{
  "patient_id": "BR1001",
  "time_series": [
    {
      "visit_date": "2019",
      "days_since_first": 0,
      "tests": {
        "test_chem_glucose": {
          "value": 95.0,
          "status": "NORMAL",
          "unit": "mg/dL"
        }
      }
    }
  ],
  "current_snapshot": {
    "test_chem_glucose": {
      "value": 95.0,
      "status": "NORMAL",
      "color": "green"
    }
  }
}
```

## Поддерживаемые типы анализов

1. **Anthropometric measures** (`am.*`): BMI, height, weight
2. **Blood chemistry** (`chem.*`): ALT, albumin, glucose, creatinine, и др.
3. **Blood counts** (`bc.*`): WBC, RBC, hemoglobin, platelets, и др.
4. **HCMV Serology** (`cmv.*`): IgG serology
5. **Inflammatory Markers** (`infl.*`): HS-CRP, ESR, RF, и др.
6. **Lipid Profile** (`lip.*`): Cholesterol, triglycerides, и др.

## Устранение неполадок

### Ошибка: "File not found"
- Проверьте путь к данным в `DATA_PATH`
- Убедитесь, что файл существует

### Ошибка: "Memory error"
- Обработайте данные частями
- Используйте `chunksize` при чтении CSV

### Ошибка: "No numeric columns found"
- Проверьте формат данных
- Убедитесь, что тестовые колонки содержат числовые значения

## Контакты и поддержка

При возникновении вопросов:
1. Проверьте документацию в ноутбуке
2. Изучите примеры в `README_PROVISIONAL_REFS.md`
3. Проверьте формат входных данных

---

**Версия**: 1.0  
**Дата**: 2024  
**Лицензия**: Для внутреннего использования

