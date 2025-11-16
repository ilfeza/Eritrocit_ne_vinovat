"""
Скрипт для исправления функции detect_anomalies_with_clustering в ноутбуке
"""
import json
import re

# Читаем ноутбук
with open('lab_data_preprocessing.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Ищем ячейку с функцией
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell.get('source', []))
        if 'def detect_anomalies_with_clustering' in source:
            # Заменяем проблемную строку
            old_code = "X[col] = X[col].fillna(X[col].median())"
            new_code = """# Безопасное заполнение пропусков
        col_data = X[col]
        if col_data.notna().sum() > 0:  # Есть хотя бы одно не-NaN значение
            try:
                median_val = col_data.median()
                if pd.notna(median_val):
                    X[col] = col_data.fillna(median_val)
                else:
                    # Если медиана NaN, используем 0
                    X[col] = col_data.fillna(0)
            except (TypeError, ValueError):
                # Если не удалось вычислить медиану, используем 0
                X[col] = col_data.fillna(0)
        else:
            # Если все значения NaN, заполняем нулями
            X[col] = col_data.fillna(0)"""
            
            # Заменяем в исходном коде
            if old_code in source:
                cell['source'] = source.replace(old_code, new_code).split('\n')
                print(f"Исправлена ячейка {i}")
            
            # Также добавляем проверку числовых типов
            old_check = "if col in df.columns:\n            non_null_count = df[col].notna().sum()"
            new_check = """if col in df.columns:
            # Проверяем, что колонка числовая
            if not pd.api.types.is_numeric_dtype(df[col]):
                try:
                    # Пытаемся преобразовать в числовой тип
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    continue
            
            non_null_count = df[col].notna().sum()"""
            
            if old_check in source:
                cell['source'] = ''.join(cell['source']).replace(old_check, new_check).split('\n')
                print(f"Добавлена проверка числовых типов в ячейке {i}")

# Сохраняем исправленный ноутбук
with open('lab_data_preprocessing.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("Ноутбук исправлен!")

