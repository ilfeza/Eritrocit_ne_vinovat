"""
Скрипт для исправления форматирования ячейки с функцией detect_anomalies_with_clustering
"""
import json

# Читаем ноутбук
with open('lab_data_preprocessing.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Ищем ячейку с функцией
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell.get('source', []))
        if 'def detect_anomalies_with_clustering' in source and len(source.split('\n')) < 10:
            # Код в одной строке - нужно переформатировать
            print(f"Найдена ячейка {i} с неправильным форматированием")
            
            # Правильно отформатированный код функции
            new_source = """def detect_anomalies_with_clustering(
    df: pd.DataFrame,
    test_columns: List[str],
    contamination: float = 0.1,
    use_pca: bool = True,
    n_components: Optional[int] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    \"\"\"
    Обнаруживает аномалии с помощью методов кластеризации и машинного обучения.
    
    Args:
        df: DataFrame с данными
        test_columns: Список колонок с тестами для анализа
        contamination: Доля ожидаемых аномалий (для Isolation Forest)
        use_pca: Использовать ли PCA для снижения размерности
        n_components: Количество компонент PCA (None = автоматически)
    
    Returns:
        tuple: (df_with_flags, anomaly_report)
    \"\"\"
    df_anomalies = df.copy()
    
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
    
    if len(valid_test_cols) == 0:
        print("Предупреждение: Не найдено достаточно данных для кластеризации")
        df_anomalies['anomaly_isolation_forest'] = False
        df_anomalies['anomaly_dbscan'] = False
        df_anomalies['anomaly_lof'] = False
        df_anomalies['anomaly_consensus'] = False
        return df_anomalies, {'error': 'Недостаточно данных'}
    
    print(f"Анализ аномалий для {len(valid_test_cols)} тестов...")
    
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
    
    # Удаляем строки, где все значения одинаковые или нулевые
    valid_rows = (X.std(axis=1) > 0) & (X.sum(axis=1) > 0)
    X_clean = X[valid_rows].values
    valid_indices = X[valid_rows].index
    
    if len(X_clean) < 10:
        print("Предупреждение: Слишком мало валидных строк для кластеризации")
        df_anomalies['anomaly_isolation_forest'] = False
        df_anomalies['anomaly_dbscan'] = False
        df_anomalies['anomaly_lof'] = False
        df_anomalies['anomaly_consensus'] = False
        return df_anomalies, {'error': 'Недостаточно валидных строк'}
    
    # Нормализация данных
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)
    
    # PCA для снижения размерности (если нужно)
    if use_pca and len(valid_test_cols) > 3:
        if n_components is None:
            # Выбираем количество компонент, объясняющих 95% дисперсии
            pca = PCA()
            pca.fit(X_scaled)
            cumsum_var = np.cumsum(pca.explained_variance_ratio_)
            n_components = np.argmax(cumsum_var >= 0.95) + 1
            n_components = min(n_components, len(valid_test_cols) - 1, len(X_clean) - 1)
        
        if n_components > 0:
            pca = PCA(n_components=n_components)
            X_scaled = pca.fit_transform(X_scaled)
            print(f"  Использовано {n_components} компонент PCA (объясняют 95% дисперсии)")
    
    # Инициализируем флаги
    df_anomalies['anomaly_isolation_forest'] = False
    df_anomalies['anomaly_dbscan'] = False
    df_anomalies['anomaly_lof'] = False
    df_anomalies['anomaly_score_if'] = 0.0
    df_anomalies['anomaly_score_lof'] = 0.0
    
    anomaly_info = []
    
    # Метод 1: Isolation Forest
    try:
        iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        iso_predictions = iso_forest.fit_predict(X_scaled)
        iso_scores = iso_forest.score_samples(X_scaled)
        
        # -1 = аномалия, 1 = норма
        iso_anomalies = iso_predictions == -1
        df_anomalies.loc[valid_indices, 'anomaly_isolation_forest'] = iso_anomalies
        df_anomalies.loc[valid_indices, 'anomaly_score_if'] = -iso_scores  # Инвертируем для интуитивности
        
        print(f"  Isolation Forest: найдено {iso_anomalies.sum()} аномалий")
    except Exception as e:
        print(f"  Ошибка Isolation Forest: {e}")
    
    # Метод 2: DBSCAN
    try:
        # Автоматический подбор eps на основе k-расстояний
        from sklearn.neighbors import NearestNeighbors
        nbrs = NearestNeighbors(n_neighbors=min(5, len(X_scaled) - 1)).fit(X_scaled)
        distances, _ = nbrs.kneighbors(X_scaled)
        distances = np.sort(distances, axis=0)
        distances = distances[:, -1]
        eps = np.percentile(distances, 75)  # 75-й перцентиль
        
        dbscan = DBSCAN(eps=eps, min_samples=min(3, len(X_scaled) // 10))
        dbscan_labels = dbscan.fit_predict(X_scaled)
        
        # -1 = выброс (noise), остальные = кластеры
        dbscan_outliers = dbscan_labels == -1
        df_anomalies.loc[valid_indices, 'anomaly_dbscan'] = dbscan_outliers
        
        n_clusters = len(set(dbscan_labels)) - (1 if -1 in dbscan_labels else 0)
        print(f"  DBSCAN: найдено {dbscan_outliers.sum()} выбросов, {n_clusters} кластеров")
    except Exception as e:
        print(f"  Ошибка DBSCAN: {e}")
    
    # Метод 3: Local Outlier Factor (LOF)
    try:
        n_neighbors = min(20, len(X_scaled) - 1)
        lof = LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination=contamination
        )
        lof_predictions = lof.fit_predict(X_scaled)
        lof_scores = lof.negative_outlier_factor_
        
        # -1 = аномалия, 1 = норма
        lof_anomalies = lof_predictions == -1
        df_anomalies.loc[valid_indices, 'anomaly_lof'] = lof_anomalies
        df_anomalies.loc[valid_indices, 'anomaly_score_lof'] = -lof_scores
        
        print(f"  Local Outlier Factor: найдено {lof_anomalies.sum()} аномалий")
    except Exception as e:
        print(f"  Ошибка LOF: {e}")
    
    # Консенсус: аномалия, если обнаружена хотя бы двумя методами
    df_anomalies['anomaly_consensus'] = (
        df_anomalies['anomaly_isolation_forest'].astype(int) +
        df_anomalies['anomaly_dbscan'].astype(int) +
        df_anomalies['anomaly_lof'].astype(int)
    ) >= 2
    
    # Собираем информацию об аномалиях
    consensus_anomalies = df_anomalies[df_anomalies['anomaly_consensus'] == True]
    for idx in consensus_anomalies.index[:20]:  # Первые 20 примеров
        row = df_anomalies.loc[idx]
        methods_detected = []
        if row['anomaly_isolation_forest']:
            methods_detected.append('IsolationForest')
        if row['anomaly_dbscan']:
            methods_detected.append('DBSCAN')
        if row['anomaly_lof']:
            methods_detected.append('LOF')
        
        anomaly_info.append({
            'row_index': int(idx),
            'patient_id': str(row.get('patient_id', '')),
            'sample_id': str(row.get('sample_id', '')),
            'methods_detected': methods_detected,
            'anomaly_score_if': float(row.get('anomaly_score_if', 0)),
            'anomaly_score_lof': float(row.get('anomaly_score_lof', 0))
        })
    
    report = {
        'total_anomalies_if': int(df_anomalies['anomaly_isolation_forest'].sum()),
        'total_anomalies_dbscan': int(df_anomalies['anomaly_dbscan'].sum()),
        'total_anomalies_lof': int(df_anomalies['anomaly_lof'].sum()),
        'total_anomalies_consensus': int(df_anomalies['anomaly_consensus'].sum()),
        'tests_analyzed': len(valid_test_cols),
        'examples': anomaly_info[:10]
    }
    
    return df_anomalies, report

def detect_outliers_traditional(
    df: pd.DataFrame,
    stats: Dict[str, Dict[str, float]]
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    \"\"\"
    Обнаруживает выбросы традиционными методами: IQR и Z-score.
    Эти выбросы можно удалять.
    \"\"\"
    df_outliers = df.copy()
    test_columns = [col for col in df.columns if col.startswith('test_')]
    
    # Создаем колонки для флагов выбросов
    df_outliers['outlier_iqr'] = False
    df_outliers['outlier_zscore'] = False
    
    outlier_info = []
    
    for test_col in test_columns:
        if test_col not in stats:
            continue
        
        stat = stats[test_col]
        values = df_outliers[test_col].dropna()
        
        if len(values) < 10:  # Слишком мало данных
            continue
        
        # Метод 1: IQR (более строгий для удаления)
        Q1 = stat['p25']
        Q3 = stat['p75']
        IQR = stat['iqr']
        lower_bound = Q1 - 3 * IQR  # Более строгий порог для удаления
        upper_bound = Q3 + 3 * IQR
        
        iqr_mask = (
            (df_outliers[test_col] < lower_bound) |
            (df_outliers[test_col] > upper_bound)
        ) & df_outliers[test_col].notna()
        
        if iqr_mask.any():
            df_outliers.loc[iqr_mask, 'outlier_iqr'] = True
            for idx in df_outliers[iqr_mask].index[:5]:
                outlier_info.append({
                    'row_index': int(idx),
                    'test': test_col,
                    'value': float(df_outliers.loc[idx, test_col]),
                    'method': 'IQR_strict',
                    'lower_bound': float(lower_bound),
                    'upper_bound': float(upper_bound)
                })
        
        # Метод 2: Z-score (строгий для удаления)
        if stat['count'] >= 30 and stat['std'] > 0:
            mean = stat['mean']
            std = stat['std']
            z_scores = np.abs((df_outliers[test_col] - mean) / std)
            zscore_mask = (z_scores > 4) & df_outliers[test_col].notna()  # Более строгий порог
            
            if zscore_mask.any():
                df_outliers.loc[zscore_mask, 'outlier_zscore'] = True
                for idx in df_outliers[zscore_mask].index[:5]:
                    if not any(o['row_index'] == idx and o['test'] == test_col for o in outlier_info):
                        outlier_info.append({
                            'row_index': int(idx),
                            'test': test_col,
                            'value': float(df_outliers.loc[idx, test_col]),
                            'method': 'Z-score_strict',
                            'z_score': float(z_scores.loc[idx]),
                            'mean': float(mean),
                            'std': float(std)
                        })
    
    # Общий флаг выбросов для удаления
    df_outliers['is_outlier_to_remove'] = df_outliers['outlier_iqr'] | df_outliers['outlier_zscore']
    
    return df_outliers, outlier_info[:20]

# Обнаруживаем аномалии с помощью кластеризации (подсвечиваем)
print("=" * 60)
print("Обнаружение аномалий с помощью методов кластеризации...")
print("=" * 60)

test_columns = [col for col in df_marked.columns if col.startswith('test_')]
df_with_anomalies, anomaly_report = detect_anomalies_with_clustering(
    df_marked,
    test_columns,
    contamination=0.1,  # Ожидаем 10% аномалий
    use_pca=True
)

print(f"\\nОтчет об аномалиях:")
print(json.dumps(anomaly_report, indent=2, ensure_ascii=False))

# Обнаруживаем выбросы традиционными методами (для удаления)
print("\\n" + "=" * 60)
print("Обнаружение выбросов традиционными методами (для удаления)...")
print("=" * 60)

df_with_outliers, outlier_examples = detect_outliers_traditional(df_with_anomalies, stats_by_test)

print(f"\\nНайдено выбросов (IQR строгий): {df_with_outliers['outlier_iqr'].sum()}")
print(f"Найдено выбросов (Z-score строгий): {df_with_outliers['outlier_zscore'].sum()}")
print(f"Всего выбросов для удаления: {df_with_outliers['is_outlier_to_remove'].sum()}")
print(f"\\nПримеры выбросов:")
print(json.dumps(outlier_examples[:5], indent=2, ensure_ascii=False))

# Создаем версию без выбросов (для дальнейшего анализа)
df_clean_no_outliers = df_with_outliers[~df_with_outliers['is_outlier_to_remove']].copy()
print(f"\\nДанные до удаления выбросов: {len(df_with_outliers)} строк")
print(f"Данные после удаления выбросов: {len(df_clean_no_outliers)} строк")
print(f"Удалено строк: {len(df_with_outliers) - len(df_clean_no_outliers)}")
"""
            
            # Заменяем содержимое ячейки
            cell['source'] = new_source.split('\n')
            print(f"Ячейка {i} исправлена!")

# Сохраняем исправленный ноутбук
with open('lab_data_preprocessing.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("Ноутбук исправлен!")

