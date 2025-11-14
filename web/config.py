#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация Flask приложения
"""

import os
from pathlib import Path

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent

# Flask конфигурация
class Config:
    """Базовая конфигурация"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Директории для файлов
    DOWNLOADS_DIR = BASE_DIR / 'downloads'
    CLIPS_DIR = BASE_DIR / 'clips'
    OUTPUT_DIR = BASE_DIR / 'output'
    AUDIO_DIR = BASE_DIR / 'audio'
    SHORTS_OUTPUT_DIR = BASE_DIR / 'shorts_output'
    DATA_DIR = BASE_DIR / 'data' # Добавляем DATA_DIR
    BANER_DIR = BASE_DIR / 'baner' # Добавляем BANER_DIR
    PROFILES_DIR = BASE_DIR / 'profiles' # Директория для профилей Camoufox
    
    # Создаем директории если их нет
    for dir_path in [DOWNLOADS_DIR, CLIPS_DIR, OUTPUT_DIR, AUDIO_DIR, SHORTS_OUTPUT_DIR, DATA_DIR, BANER_DIR, PROFILES_DIR]: # Добавляем DATA_DIR и PROFILES_DIR сюда
        dir_path.mkdir(exist_ok=True)
    
    # Flask-SocketIO
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"  # Для Google Colab
    
    # Максимальный размер загружаемых файлов (100 MB)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    
    # Логирование
    LOG_DIR = BASE_DIR / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    LOG_FILE = LOG_DIR / 'app.log'
    
    # AI сервисы
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    # DeepSeek ключ: сначала из файла настроек, потом из переменной окружения
    _deepseek_key_from_env = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_API_KEY = _deepseek_key_from_env  # Будет обновлено методом get_deepseek_api_key()
    AI_MODEL = os.environ.get('AI_MODEL', 'gpt-3.5-turbo')
    
    @staticmethod
    def get_deepseek_api_key():
        """Получает DeepSeek API ключ: сначала из файла настроек, потом из переменной окружения"""
        try:
            settings_file = Config.DATA_DIR / 'settings.json'
            if settings_file.exists():
                import json
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    if settings.get('deepseek_api_key'):
                        return settings['deepseek_api_key']
        except Exception:
            pass
        # Если в файле нет, используем из переменной окружения
        return Config._deepseek_key_from_env
    
    # Google Colab API
    COLAB_API_TOKEN = os.environ.get('COLAB_API_TOKEN', '')
    
    # Google Colab автоматизация через Camoufox
    # По умолчанию отключена, можно включить через переменную окружения COLAB_AUTOMATION_ENABLED=true
    COLAB_AUTOMATION_ENABLED = os.environ.get('COLAB_AUTOMATION_ENABLED', 'false').lower() == 'true'
    COLAB_PROFILE_PATH = os.environ.get('COLAB_PROFILE_PATH')
    if COLAB_PROFILE_PATH:
        COLAB_PROFILE_PATH = Path(COLAB_PROFILE_PATH)
    else:
        # Используем профиль по умолчанию, если он существует
        default_profile = PROFILES_DIR / '9e5ee0b4-ef53-4465-93a0-34c1622585e6'
        COLAB_PROFILE_PATH = default_profile if default_profile.exists() else None
    
    # URL Colab ноутбука
    COLAB_URL = os.environ.get('COLAB_URL', 'https://colab.research.google.com/drive/1onQ44lOA-I1_W0EvDLI31DZ8NFVsJjBD')
    
    # Селекторы для автоматизации Colab
    # Формат: словарь с селекторами для навигации и запуска скрипта
    COLAB_SELECTORS = {
        'run_button': 'colab-run-button',  # Кнопка запуска ячейки
        'cell_id': 'cell-3oaaOZ04ozsP',  # ID ячейки с кодом транскрибации
        'completion_text': '=== Цикл завершен ===',  # Текст, который появляется при завершении
        # 'completion_selector': 'селектор элемента завершения (опционально)',
    }
    
    # Качество видео по умолчанию (для скорости)
    DEFAULT_QUALITY = '360p'
    
    # Файлы для сохранения промптов
    SYSTEM_PROMPTS_FILE = DATA_DIR / 'system_prompts.json'
    USER_PROMPTS_FILE = DATA_DIR / 'user_prompts.json'

    # Таймауты
    DOWNLOAD_TIMEOUT = 300  # 5 минут
    STREAM_TIMEOUT = 60     # 1 минута

    # Файл для сохранения состояния задач
    TASK_STATE_FILE = DATA_DIR / 'task_state.json'


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    TESTING = False
    
    # В продакшене используем переменные окружения
    # Если SECRET_KEY не установлен, используем дефолтный (небезопасно для реального продакшена!)
    # В реальном продакшене установите переменную окружения SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-CHANGE-THIS-IN-REAL-PRODUCTION'


# Выбор конфигурации
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
