# Инструкция по развертыванию Video Maker

## Подготовка к деплою

### 1. Настройка переменных окружения

Скопируйте файл `.env.example` в `.env` и заполните необходимые переменные:

```bash
cp .env.example .env
```

Отредактируйте `.env` и укажите:
- `SECRET_KEY` - секретный ключ для Flask (сгенерируйте случайную строку)
- `OPENAI_API_KEY` - ваш API ключ OpenAI (если используете)
- `DEEPSEEK_API_KEY` - ваш API ключ DeepSeek
- `COLAB_API_TOKEN` - токен для Google Colab API (если используете)
- Другие необходимые переменные

### 2. Обновление .gitignore

Убедитесь, что `.gitignore` включает:
- `.env` файлы
- `profiles/` директорию
- `data/task_state.json`
- Другие чувствительные данные

## Вариант 1: Деплой с Docker (Рекомендуется)

### Требования
- Docker
- Docker Compose

### Шаги деплоя

1. **Клонируйте репозиторий на сервер:**
```bash
git clone https://github.com/yourusername/Video_macker3.git
cd Video_macker3
```

2. **Создайте файл .env:**
```bash
cp .env.example .env
nano .env  # или используйте другой редактор
```

3. **Запустите деплой:**
```bash
# Для Linux/Mac
chmod +x deploy.sh
./deploy.sh

# Для Windows
deploy.bat
```

Или вручную:
```bash
# Docker Compose V2 (рекомендуется)
docker compose up -d --build

# Или Docker Compose V1 (старая версия)
docker-compose up -d --build
```

4. **Проверьте статус:**
```bash
# Docker Compose V2
docker compose ps
docker compose logs -f

# Или Docker Compose V1
docker-compose ps
docker-compose logs -f
```

5. **Остановка:**
```bash
# Docker Compose V2
docker compose down

# Или Docker Compose V1
docker-compose down
```

## Вариант 2: Деплой без Docker (Systemd Service)

### Требования
- Python 3.11+
- Установленные системные зависимости (ffmpeg, и т.д.)

### Шаги деплоя

1. **Клонируйте репозиторий:**
```bash
git clone https://github.com/yourusername/Video_macker3.git
cd Video_macker3
```

2. **Создайте виртуальное окружение:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Настройте переменные окружения:**
```bash
cp .env.example .env
nano .env
```

4. **Установите systemd service:**
```bash
sudo cp video-maker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable video-maker
sudo systemctl start video-maker
```

5. **Проверьте статус:**
```bash
sudo systemctl status video-maker
sudo journalctl -u video-maker -f
```

## Вариант 3: Деплой на GitHub и автоматический деплой

### Настройка GitHub Actions (опционально)

Создайте файл `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/video-maker
            git pull
            docker compose up -d --build
```

### Настройка Secrets в GitHub

1. Перейдите в Settings → Secrets and variables → Actions
2. Добавьте:
   - `HOST` - IP адрес вашего сервера
   - `USERNAME` - имя пользователя для SSH
   - `SSH_KEY` - приватный SSH ключ

## Проверка работы

После деплоя приложение должно быть доступно по адресу:
- `http://your-server-ip:5000` (или ваш домен)

Проверьте:
- Откройте главную страницу в браузере
- Проверьте логи на наличие ошибок
- Убедитесь, что все директории созданы и доступны для записи

## Обновление приложения

### С Docker:
```bash
git pull
# Docker Compose V2 (рекомендуется)
docker compose up -d --build
# Или Docker Compose V1
# docker-compose up -d --build
```

### С Systemd:
```bash
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart video-maker
```

## Решение проблем

### Проблемы с правами доступа
```bash
sudo chown -R www-data:www-data /opt/video-maker
sudo chmod -R 755 /opt/video-maker
```

### Проблемы с портами
Убедитесь, что порт 5000 открыт в firewall:
```bash
sudo ufw allow 5000/tcp
```

### Просмотр логов
```bash
# Docker Compose V2
docker compose logs -f
# Или Docker Compose V1
# docker-compose logs -f

# Systemd
sudo journalctl -u video-maker -f

# Файловые логи
tail -f logs/app.log
```

## Безопасность

⚠️ **ВАЖНО для продакшена:**

1. Измените `SECRET_KEY` на случайную строку
2. Настройте reverse proxy (nginx) с SSL сертификатом
3. Ограничьте `SOCKETIO_CORS_ALLOWED_ORIGINS` конкретными доменами
4. Не храните `.env` файл в репозитории
5. Используйте firewall для ограничения доступа
6. Регулярно обновляйте зависимости

## Nginx конфигурация (опционально)

Пример конфигурации для nginx:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

