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
