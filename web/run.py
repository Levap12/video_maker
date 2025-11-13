#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт запуска Flask приложения
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.app import app, socketio

if __name__ == '__main__':
    # Определяем окружение
    env = os.environ.get('FLASK_ENV', 'development')
    debug = (env == 'development')
    
    # Запускаем приложение
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=debug,
        allow_unsafe_werkzeug=True
    )
