#!/bin/bash
# Скрипт для деплоя на сервер

set -e

echo "=== Деплой Video Maker ==="

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "ОШИБКА: Файл .env не найден!"
    echo "Скопируйте .env.example в .env и заполните необходимые переменные"
    exit 1
fi

# Загружаем переменные окружения
source .env

# Останавливаем старый контейнер если он запущен
echo "Остановка старых контейнеров..."
docker-compose down || true

# Собираем новый образ
echo "Сборка Docker образа..."
docker-compose build --no-cache

# Запускаем контейнер
echo "Запуск контейнера..."
docker-compose up -d

# Показываем логи
echo "Логи приложения:"
docker-compose logs -f --tail=50

