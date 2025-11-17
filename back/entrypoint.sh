#!/bin/bash
# Entrypoint скрипт для копирования демо-файлов в volume при первом запуске

DATA_DIR="/app/data"
BACKUP_DATA_DIR="/app/data_backup"

echo "=== Инициализация данных ==="
echo "DATA_DIR: $DATA_DIR"
echo "BACKUP_DATA_DIR: $BACKUP_DATA_DIR"

# Создаем директорию, если её нет
mkdir -p "$DATA_DIR"

# Копируем файлы из резервной копии, если их нет в volume
if [ -d "$BACKUP_DATA_DIR" ]; then
    echo "Проверяю файлы в резервной копии..."
    for file in "$BACKUP_DATA_DIR"/*; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            if [ ! -f "$DATA_DIR/$filename" ]; then
                echo "Копирую $filename из резервной копии в $DATA_DIR"
                cp "$file" "$DATA_DIR/$filename"
            else
                echo "Файл $filename уже существует в $DATA_DIR, пропускаю"
            fi
        fi
    done
else
    echo "Предупреждение: резервная директория $BACKUP_DATA_DIR не найдена"
fi

# Показываем содержимое директории данных
echo "=== Содержимое $DATA_DIR ==="
ls -la "$DATA_DIR" || echo "Директория пуста или недоступна"

echo "=== Запуск приложения ==="

# Запускаем основную команду
exec "$@"
