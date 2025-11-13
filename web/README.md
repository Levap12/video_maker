# Веб-интерфейс Video Maker

Веб-интерфейс на Flask для автоматизации работы с видео контентом из HDRezka.

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Убедитесь, что установлены все зависимости из корневого `requirements.txt`

## Запуск

### Режим разработки

**Важно:** Убедитесь, что виртуальное окружение активировано!

**Windows:**
```bash
# Активируйте виртуальное окружение
venv\Scripts\activate

# Запустите приложение (из корневой директории проекта)
python run_web.py
```

**Или используйте готовый скрипт:**
```bash
start_web.bat
```

**Linux/Mac:**
```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Запустите приложение
python run_web.py
```

Приложение будет доступно по адресу: `http://localhost:5000`

### Production

Используйте Gunicorn:
```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 web.app:app
```

## Структура

```
web/
├── app.py                 # Основное Flask приложение
├── config.py              # Конфигурация
├── run.py                 # Скрипт запуска
├── routes/
│   └── main.py            # API маршруты
├── services/
│   └── hdrezka_service.py # Сервис для работы с HDRezka
├── tasks/
│   ├── task_manager.py    # Менеджер задач
│   └── workflow_task.py   # Фоновая задача workflow
├── templates/
│   ├── base.html          # Базовый шаблон
│   └── index.html         # Главная страница
└── static/
    ├── css/
    │   └── main.css       # Стили
    └── js/
        └── main.js        # JavaScript логика
```

## API Endpoints

### POST /api/workflow/analyze
Анализирует контент по URL HDRezka

**Request:**
```json
{
  "url": "https://hdrezka.ag/...",
  "proxy": "user:pass@host:port"  // опционально
}
```

**Response:**
```json
{
  "success": true,
  "name": "Название",
  "type": "tv_series" | "movie",
  "translators": {...},
  "series_info": {...}  // для сериалов
}
```

### POST /api/workflow/start
Запускает полный workflow обработки

**Request:**
```json
{
  "url": "https://hdrezka.ag/...",
  "proxy": "user:pass@host:port",
  "season": 1,          // для сериалов
  "episode": 1,         // для сериалов
  "translator_id": 66,  // опционально
  "quality": "360p"
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "uuid"
}
```

### GET /api/workflow/status/<task_id>
Получает статус workflow задачи

**Response:**
```json
{
  "success": true,
  "task": {
    "task_id": "...",
    "status": "running",
    "progress": 50,
    "message": "..."
  }
}
```

## WebSocket

Приложение использует Flask-SocketIO для обновления прогресса в реальном времени.

**События:**
- `subscribe_task` - подписка на обновления задачи
- `task_progress` - обновление прогресса задачи

## Особенности

- **Поддержка прокси**: SOCKS прокси в формате `user:pass@host:port`
- **Автоопределение типа**: Автоматически определяет фильм или сериал
- **Фоновые задачи**: Длительные операции выполняются в фоне
- **WebSocket прогресс**: Обновления в реальном времени

## Требования

- Python 3.7+
- Flask 2.0+
- Flask-SocketIO 5.0+
- HdRezkaApi 1.0+
- MoviePy для обработки видео
