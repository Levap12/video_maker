@echo off
REM Скрипт для деплоя на Windows сервер

echo === Деплой Video Maker ===

REM Определяем команду docker compose (поддержка V1 и V2)
docker compose version >nul 2>&1
if %errorlevel% == 0 (
    set DOCKER_COMPOSE=docker compose
    echo Используется Docker Compose V2
) else (
    docker-compose --version >nul 2>&1
    if %errorlevel% == 0 (
        set DOCKER_COMPOSE=docker-compose
        echo Используется Docker Compose V1
    ) else (
        echo ОШИБКА: Docker Compose не найден!
        echo Установите Docker и Docker Compose
        exit /b 1
    )
)

REM Проверяем наличие .env файла
if not exist .env (
    echo ОШИБКА: Файл .env не найден!
    echo Скопируйте .env.example в .env и заполните необходимые переменные
    exit /b 1
)

REM Останавливаем старый контейнер если он запущен
echo Остановка старых контейнеров...
%DOCKER_COMPOSE% down

REM Собираем новый образ
echo Сборка Docker образа...
%DOCKER_COMPOSE% build --no-cache

REM Запускаем контейнер
echo Запуск контейнера...
%DOCKER_COMPOSE% up -d

REM Показываем логи
echo Логи приложения:
%DOCKER_COMPOSE% logs -f --tail=50

