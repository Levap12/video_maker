@echo off
REM Скрипт для деплоя на Windows сервер

echo === Деплой Video Maker ===

REM Проверяем наличие .env файла
if not exist .env (
    echo ОШИБКА: Файл .env не найден!
    echo Скопируйте .env.example в .env и заполните необходимые переменные
    exit /b 1
)

REM Останавливаем старый контейнер если он запущен
echo Остановка старых контейнеров...
docker-compose down

REM Собираем новый образ
echo Сборка Docker образа...
docker-compose build --no-cache

REM Запускаем контейнер
echo Запуск контейнера...
docker-compose up -d

REM Показываем логи
echo Логи приложения:
docker-compose logs -f --tail=50

