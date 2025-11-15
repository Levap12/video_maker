# Simple API - Документация

## Обзор

Simple API (`web/routes/simple_api.py`) - это упрощенный REST API для автоматической обработки видео. API автоматически выполняет полный workflow от скачивания видео до создания Shorts без необходимости ручного управления каждым этапом.

## Базовый URL

```
http://localhost:5000/api/v1/video
```

## Автоматический Workflow

API автоматически выполняет следующие этапы:

1. **Скачивание видео** (`downloading`) - 0-20%
2. **Транскрипция** (`waiting_transcription` → `transcribing`) - 20-30%
3. **AI генерация клипов** (`ai_generation`) - 30-50%
4. **Нарезка клипов** (`clipping`) - 50-70%
5. **Создание Shorts** (`shorts_creation`) - 70-100%

## Endpoints

### 1. Создание задачи на обработку видео

**POST** `/api/v1/video/create`

Создает новую задачу на обработку видео и автоматически запускает полный workflow.

#### Параметры запроса (JSON)

**Обязательные:**
- `url` (string) - URL видео для скачивания
- `system_prompt_id` (string) - ID системного промпта для AI генерации
- `user_prompt_id` (string) - ID пользовательского промпта для AI генерации

**Опциональные:**
- `season` (integer) - Номер сезона (для сериалов)
- `episode` (integer) - Номер серии (для сериалов)
- `translator_id` (integer) - ID переводчика/озвучки
- `quality` (string) - Качество видео (по умолчанию: `360p`)
- `proxy` (string) - Прокси-сервер (если требуется)
- `proxy_type` (string) - Тип прокси (по умолчанию: `socks5`)
- `shorts_settings` (object) - Настройки для создания Shorts:
  - `banner_path` (string) - Путь к файлу баннера (видео). Если не указан, баннер не используется. Можно получить список доступных баннеров через `/api/files/list/banners`
  - `banner_offset` (integer) - Отступ сверху для баннера в пикселях (по умолчанию: 100)
  - `watermark_text` (string) - Текст водяного знака
  - `watermark_color` (string) - Цвет водяного знака (по умолчанию: `gray`)
  - `watermark_font_size` (integer) - Размер шрифта водяного знака (по умолчанию: 72)
  - `watermark_bottom_offset` (integer) - Отступ водяного знака снизу в пикселях (по умолчанию: 180)
  - `height_scale` (float) - Масштаб высоты для формата Shorts (по умолчанию: 2.0)

#### Пример запроса

```bash
curl -X POST http://localhost:5000/api/v1/video/create \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=example",
    "system_prompt_id": "abc123def456",
    "user_prompt_id": "xyz789uvw012",
    "season": 1,
    "episode": 1,
    "translator_id": 66,
    "quality": "720p",
    "shorts_settings": {
      "banner_path": "baner/IMG_2196.MOV",
      "banner_offset": 100,
      "watermark_text": "@MyChannel",
      "watermark_color": "white",
      "watermark_font_size": 72,
      "watermark_bottom_offset": 180,
      "height_scale": 2.0
    }
  }'
```

#### Пример запроса (Python)

```python
import requests

url = "http://localhost:5000/api/v1/video/create"
payload = {
    "url": "https://www.youtube.com/watch?v=example",
    "system_prompt_id": "abc123def456",
    "user_prompt_id": "xyz789uvw012",
    "season": 1,
    "episode": 1,
    "translator_id": 66,
    "quality": "720p",
    "shorts_settings": {
        "banner_path": "baner/IMG_2196.MOV",
        "banner_offset": 100,
        "watermark_text": "@MyChannel",
        "watermark_color": "white",
        "watermark_font_size": 72,
        "watermark_bottom_offset": 180,
        "height_scale": 2.0
    }
}

response = requests.post(url, json=payload)
data = response.json()

if data.get('success'):
    task_id = data.get('task_id')
    print(f"Задача создана: {task_id}")
else:
    print(f"Ошибка: {data.get('error')}")
```

#### Ответ (успех)

```json
{
  "success": true,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Задача создана, начинается скачивание видео"
}
```

**HTTP статус:** 201 Created

#### Ответ (ошибка)

```json
{
  "success": false,
  "error": "URL не указан"
}
```

**HTTP статус:** 400 Bad Request

### 2. Получение статуса задачи

**GET** `/api/v1/video/status/<task_id>`

Возвращает текущий статус обработки видео с информацией о прогрессе и этапе.

#### Параметры URL

- `task_id` (string) - ID задачи, полученный при создании

#### Пример запроса

```bash
curl http://localhost:5000/api/v1/video/status/550e8400-e29b-41d4-a716-446655440000
```

#### Пример запроса (Python)

```python
import requests
import time

task_id = "550e8400-e29b-41d4-a716-446655440000"
url = f"http://localhost:5000/api/v1/video/status/{task_id}"

while True:
    response = requests.get(url)
    data = response.json()
    
    if data.get('success'):
        status = data.get('status')
        stage = data.get('stage')
        progress = data.get('progress', 0)
        message = data.get('message', '')
        
        print(f"[{stage}] {progress}% - {message}")
        
        if status == 'completed':
            videos = data.get('videos', [])
            print(f"Готово! Создано {len(videos)} видео")
            break
        elif status == 'failed':
            error = data.get('error', 'Неизвестная ошибка')
            print(f"Ошибка: {error}")
            break
    
    time.sleep(5)  # Проверяем каждые 5 секунд
```

#### Ответ (обработка)

```json
{
  "success": true,
  "status": "processing",
  "stage": "ai_generation",
  "progress": 45.2,
  "message": "Генерация клипов через AI..."
}
```

#### Ответ (завершено)

```json
{
  "success": true,
  "status": "completed",
  "stage": "completed",
  "progress": 100.0,
  "message": "Все видео готовы!",
  "videos": [
    {
      "filename": "clip_001.mp4",
      "url": "/api/files/short/clip_001.mp4",
      "size_mb": 12.5,
      "duration_seconds": 60.0,
      "metadata": {
        "start_time": "00:00:33.080",
        "end_time": "00:01:34.420",
        "title": "Снапплз становится умным: начало собачьего бунта",
        "summary": "Джерри просит Рика сделать собаку Снапплза умнее...",
        "full_quote": "Считается, что коллекционирование монет..."
      }
    },
    {
      "filename": "clip_002.mp4",
      "url": "/api/files/short/clip_002.mp4",
      "size_mb": 11.8,
      "duration_seconds": 58.5,
      "metadata": {
        "start_time": "00:02:15.200",
        "end_time": "00:03:13.700",
        "title": "Второй клип",
        "summary": "Описание второго клипа...",
        "full_quote": "..."
      }
    }
  ]
}
```

#### Ответ (ошибка)

```json
{
  "success": true,
  "status": "failed",
  "stage": "failed",
  "progress": 35.0,
  "message": "Произошла ошибка при обработке",
  "error": "Детальное описание ошибки"
}
```

#### Этапы обработки (stage)

- `downloading` - Скачивание видео (0-20%)
- `waiting_transcription` - Ожидание транскрипции (20-30%)
- `transcribing` - Выполнение транскрипции (20-30%)
- `ai_generation` - Генерация клипов через AI (30-50%)
- `clipping` - Нарезка клипов из видео (50-70%)
- `waiting_shorts` - Ожидание запуска создания Shorts (70-100%)
- `shorts_creation` - Создание Shorts (70-100%)
- `completed` - Все этапы завершены (100%)
- `failed` - Произошла ошибка

**HTTP статус:** 200 OK (или 404 Not Found, если задача не найдена)

### 3. Получение ссылок на скачивание

**GET** `/api/v1/video/<task_id>/download`

Возвращает список всех готовых видео с полными URL для скачивания. Используется когда статус задачи = `completed`.

#### Параметры URL

- `task_id` (string) - ID задачи

#### Пример запроса

```bash
curl http://localhost:5000/api/v1/video/550e8400-e29b-41d4-a716-446655440000/download
```

#### Пример запроса (Python)

```python
import requests

task_id = "550e8400-e29b-41d4-a716-446655440000"
url = f"http://localhost:5000/api/v1/video/{task_id}/download"

response = requests.get(url)
data = response.json()

if data.get('success'):
    videos = data.get('videos', [])
    metadata = data.get('metadata', {})
    
    print(f"Всего видео: {metadata.get('total_videos', 0)}")
    print(f"Общий размер: {metadata.get('total_size_mb', 0)} MB")
    
    for video in videos:
        print(f"\n{video['filename']}")
        print(f"  Размер: {video['size_mb']} MB")
        print(f"  Длительность: {video['duration_seconds']} сек")
        print(f"  Скачать: {video['download_url']}")
        if 'metadata' in video:
            meta = video['metadata']
            print(f"  Заголовок: {meta.get('title', 'N/A')}")
            print(f"  Описание: {meta.get('summary', 'N/A')}")
```

#### Ответ (успех)

```json
{
  "success": true,
  "status": "completed",
  "videos": [
    {
      "filename": "clip_001.mp4",
      "url": "/api/files/short/clip_001.mp4",
      "download_url": "http://localhost:5000/api/files/short/clip_001.mp4",
      "size_mb": 12.5,
      "duration_seconds": 60.0,
      "metadata": {
        "start_time": "00:00:33.080",
        "end_time": "00:01:34.420",
        "title": "Снапплз становится умным: начало собачьего бунта",
        "summary": "Джерри просит Рика сделать собаку Снапплза умнее...",
        "full_quote": "Считается, что коллекционирование монет..."
      }
    },
    {
      "filename": "clip_002.mp4",
      "url": "/api/files/short/clip_002.mp4",
      "download_url": "http://localhost:5000/api/files/short/clip_002.mp4",
      "size_mb": 11.8,
      "duration_seconds": 58.5,
      "metadata": {
        "start_time": "00:02:15.200",
        "end_time": "00:03:13.700",
        "title": "Второй клип",
        "summary": "Описание второго клипа...",
        "full_quote": "..."
      }
    }
  ],
  "metadata": {
    "source_url": "https://www.youtube.com/watch?v=example",
    "season": 1,
    "episode": 1,
    "created_at": "2024-01-15T10:30:00Z",
    "total_videos": 2,
    "total_size_mb": 24.3
  }
}
```

#### Ответ (ошибка - видео не готовы)

```json
{
  "success": false,
  "error": "Видео еще не готовы. Проверьте статус через /status/{task_id}"
}
```

**HTTP статус:** 400 Bad Request

**HTTP статус:** 200 OK (или 404 Not Found, если задача не найдена)

## Полный пример использования

```python
import requests
import time

# 1. Создаем задачу
print("Создание задачи...")
response = requests.post(
    "http://localhost:5000/api/v1/video/create",
    json={
        "url": "https://www.youtube.com/watch?v=example",
        "system_prompt_id": "abc123def456",
        "user_prompt_id": "xyz789uvw012",
        "season": 1,
        "episode": 1,
        "quality": "720p",
        "shorts_settings": {
            "banner_path": "baner/IMG_2196.MOV",
            "banner_offset": 100,
            "watermark_text": "@MyChannel",
            "watermark_color": "white",
            "watermark_font_size": 72
        }
    }
)

if response.status_code != 201:
    print(f"Ошибка создания задачи: {response.text}")
    exit(1)

task_id = response.json()['task_id']
print(f"Задача создана: {task_id}\n")

# 2. Отслеживаем статус
print("Отслеживание прогресса...")
while True:
    response = requests.get(f"http://localhost:5000/api/v1/video/status/{task_id}")
    data = response.json()
    
    if not data.get('success'):
        print(f"Ошибка: {data.get('error')}")
        break
    
    status = data.get('status')
    stage = data.get('stage')
    progress = data.get('progress', 0)
    message = data.get('message', '')
    
    print(f"[{stage:20s}] {progress:5.1f}% - {message}")
    
    if status == 'completed':
        videos = data.get('videos', [])
        print(f"\n✅ Готово! Создано {len(videos)} видео")
        break
    elif status == 'failed':
        error = data.get('error', 'Неизвестная ошибка')
        print(f"\n❌ Ошибка: {error}")
        break
    
    time.sleep(5)

# 3. Получаем ссылки на скачивание
if status == 'completed':
    print("\nПолучение ссылок на скачивание...")
    response = requests.get(f"http://localhost:5000/api/v1/video/{task_id}/download")
    data = response.json()
    
    if data.get('success'):
        videos = data.get('videos', [])
        metadata = data.get('metadata', {})
        
        print(f"\nВсего видео: {metadata.get('total_videos', 0)}")
        print(f"Общий размер: {metadata.get('total_size_mb', 0)} MB\n")
        
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['filename']}")
            print(f"   Размер: {video['size_mb']} MB")
            print(f"   Длительность: {video['duration_seconds']} сек")
            print(f"   Скачать: {video['download_url']}\n")
```

## Автоматическое продолжение workflow

API автоматически переходит между этапами без необходимости ручного вызова следующих шагов. Это обеспечивается функцией `auto_continue_workflow`, которая:

- Автоматически запускает транскрипцию после скачивания (если включена Colab автоматизация)
- Автоматически запускает AI генерацию после завершения транскрипции
- Автоматически запускает нарезку после завершения AI генерации
- Автоматически запускает создание Shorts после завершения нарезки

## Обработка ошибок

Все endpoints возвращают JSON с полем `success`:
- `true` - операция выполнена успешно
- `false` - произошла ошибка (детали в поле `error`)

При ошибках также возвращается соответствующий HTTP статус код:
- `400` - Неверные параметры запроса
- `404` - Задача не найдена
- `500` - Внутренняя ошибка сервера

## Примечания

1. **Промпты**: `system_prompt_id` и `user_prompt_id` должны существовать в системе. Проверьте доступные промпты через API промптов.

2. **Транскрипция**: Если Colab автоматизация отключена, этап `waiting_transcription` будет ожидать ручного запуска транскрипции.

3. **Таймауты**: Обработка может занять значительное время (от нескольких минут до часа в зависимости от длины видео). Рекомендуется проверять статус периодически (каждые 5-10 секунд).

4. **Прокси**: Если требуется использовать прокси для скачивания, укажите параметры `proxy` и `proxy_type` в запросе создания задачи.

5. **Качество**: По умолчанию используется качество `360p` для ускорения обработки. Можно указать `720p`, `1080p` и т.д.

6. **Баннеры**: Баннеры должны находиться в директории `baner/` проекта. Поддерживаются форматы: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`. Для получения списка доступных баннеров используйте endpoint `/api/files/list/banners`:

```python
import requests

response = requests.get("http://localhost:5000/api/files/list/banners")
data = response.json()

if data.get('success'):
    banners = data.get('banners', [])
    print(f"Доступно баннеров: {len(banners)}")
    for banner in banners:
        print(f"  - {banner['name']}: {banner['path']}")
```

Ответ:
```json
{
  "success": true,
  "banners": [
    {
      "name": "IMG_2196.MOV",
      "path": "C:\\Users\\shegl\\PycharmProjects\\Video_macker3\\baner\\IMG_2196.MOV"
    }
  ],
  "count": 1
}
```

В параметре `banner_path` можно указать либо полный путь к файлу, либо относительный путь от корня проекта (например, `baner/IMG_2196.MOV`).

