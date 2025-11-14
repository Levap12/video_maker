#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основное Flask приложение
"""

import logging
from flask import Flask, render_template
from flask_socketio import SocketIO
import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь для импортов
if Path(__file__).parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройка логирования (должна быть до импорта других модулей)
from web.logging_config import setup_logging
setup_logging()

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

# Импорт конфигурации
from web.config import config

# Определяем окружение
env = os.environ.get('FLASK_ENV', 'development')
# Всегда используем development для локальной разработки, если явно не указано production
if env not in config:
    env = 'development'
app_config = config.get(env, config['default'])

# Создаем приложение
# Примечание: Flask автоматически загружает .env, но мы загружаем его вручную в run_web.py
# для контроля кодировки. Если Flask все равно пытается загрузить .env и падает,
# это будет обработано в run_web.py
app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
app.config.from_object(app_config)

# Отключаем кэширование для разработки
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Инициализируем SocketIO
socketio = SocketIO(app, 
                   cors_allowed_origins=app.config.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '*'),
                   async_mode='threading')

# Регистрируем blueprints
from web.routes.main import main_bp
from web.routes.colab_api import colab_bp
from web.routes.processing import processing_bp
from web.routes.compilation import compilation_bp
from web.routes.shorts import shorts_bp
from web.routes.files import files_bp
from web.routes.tasks_api import tasks_api_bp
from web.routes.prompts_api import prompts_api_bp # Импортируем новый blueprint
from web.routes.simple_api import simple_api_bp # Импортируем Simple API blueprint
from web.routes.settings_api import settings_api_bp # Импортируем Settings API blueprint
app.register_blueprint(main_bp)
app.register_blueprint(colab_bp)
app.register_blueprint(processing_bp)
app.register_blueprint(compilation_bp)
app.register_blueprint(shorts_bp)
app.register_blueprint(files_bp)
app.register_blueprint(tasks_api_bp)
app.register_blueprint(prompts_api_bp) # Регистрируем новый blueprint
app.register_blueprint(simple_api_bp) # Регистрируем Simple API blueprint
app.register_blueprint(settings_api_bp) # Регистрируем Settings API blueprint

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/tasks')
def tasks():
    """Страница управления задачами."""
    return render_template('tasks.html')

@app.route('/prompts')
def prompts():
    """Страница управления промптами."""
    return render_template('prompts.html')


@app.route('/logs')
def logs():
    """Страница для просмотра логов в реальном времени."""
    return render_template('logs.html')

@app.route('/settings')
def settings():
    """Страница настроек."""
    return render_template('settings.html')


@socketio.on('connect')
def handle_connect():
    """Обработка подключения через WebSocket"""
    logger.info('Клиент подключен')
    return {'status': 'connected'}


@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения через WebSocket"""
    logger.info('Клиент отключен')


@socketio.on('subscribe_task')
def handle_subscribe_task(data):
    """Подписка на обновления задачи"""
    task_id = data.get('task_id')
    if task_id:
        from web.tasks.task_manager import task_manager
        task = task_manager.get_task(task_id)
        if task:
            # Регистрируем callback для отправки через WebSocket
            def send_update(updated_task):
                socketio.emit('task_progress', {
                    'task_id': updated_task.task_id,
                    'progress': updated_task.progress,
                    'message': updated_task.message,
                    'status': updated_task.status.value,
                    'error': updated_task.error,
                    'result': updated_task.result
                })
            
            task_manager.register_callback(task_id, send_update)
            return {'status': 'subscribed', 'task_id': task_id}
    return {'status': 'error', 'message': 'Invalid task_id'}


if __name__ == '__main__':
    # Для разработки
    socketio.run(app, 
                host='0.0.0.0',
                port=5000,
                debug=app.config.get('DEBUG', False))
