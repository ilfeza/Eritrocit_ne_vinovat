# ИСПРАВЛЕНИЕ для функции detect_anomalies_with_clustering
# Замените проблемную часть функции на этот код:

# В функции detect_anomalies_with_clustering найдите строку:
#     X[col] = X[col].fillna(X[col].median())
#
# И замените на:

    # Создаем матрицу данных (заполняем пропуски медианой)
    X = df[valid_test_cols].copy()
    for col in valid_test_cols:
        # Безопасное заполнение пропусков
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
            X[col] = col_data.fillna(0)

# Также добавьте проверку числовых типов перед циклом:
    # Подготовка данных: выбираем только числовые тестовые колонки с достаточным количеством данных
    valid_test_cols = []
    for col in test_columns:
        if col in df.columns:
            # Проверяем, что колонка числовая
            if not pd.api.types.is_numeric_dtype(df[col]):
                try:
                    # Пытаемся преобразовать в числовой тип
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    continue
            
            non_null_count = df[col].notna().sum()
            if non_null_count >= 20:  # Минимум 20 значений
                valid_test_cols.append(col)



