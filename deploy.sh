#!/bin/bash
# Скрипт для деплоя на сервер

set -e

echo "=== Деплой Video Maker ==="

# Определяем команду docker compose (поддержка V1 и V2)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
    echo "Используется Docker Compose V2"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo "Используется Docker Compose V1"
else
    echo "ОШИБКА: Docker Compose не найден!"
    echo "Установите Docker и Docker Compose"
    exit 1
fi

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
$DOCKER_COMPOSE down || true

# Собираем новый образ
echo "Сборка Docker образа..."
$DOCKER_COMPOSE build --no-cache

# Запускаем контейнер
echo "Запуск контейнера..."
$DOCKER_COMPOSE up -d

# Показываем логи
echo "Логи приложения:"
$DOCKER_COMPOSE logs -f --tail=50

