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