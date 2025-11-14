#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт запуска Flask приложения из корневой директории проекта
Используйте: python run_web.py
"""

import os
import sys
from pathlib import Path

# Убеждаемся, что мы в корневой директории проекта
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Отключаем автоматическую загрузку .env от Flask, если файл в неправильной кодировке
# Flask автоматически загружает .env, но может упасть на неправильной кодировке
# Мы загрузим переменные окружения вручную, если нужно
try:
    from dotenv import load_dotenv
    env_file = project_root / '.env'
    if env_file.exists():
        try:
            load_dotenv(env_file, encoding='utf-8')
        except UnicodeDecodeError:
            print("⚠️  Предупреждение: Файл .env имеет неправильную кодировку. Используйте UTF-8.")
            print("   Пересоздайте файл .env на основе env.example")
except ImportError:
    pass  # python-dotenv не установлен, используем системные переменные окружения

from web.app import app, socketio

if __name__ == '__main__':
    # Определяем окружение
    env = os.environ.get('FLASK_ENV', 'development')
    debug = (env == 'development')
    
    print("=" * 50)
    print("Запуск Video Maker Web Interface")
    print(f"Директория проекта: {project_root}")
    print(f"Сервер будет доступен на: http://localhost:5000")
    print(f"Режим: {env} (debug={debug})")
    print("=" * 50)
    
    # Запускаем приложение
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=debug,
        allow_unsafe_werkzeug=True
    )
