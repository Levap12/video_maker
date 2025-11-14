#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для управления настройками приложения
"""

import json
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from web.config import Config

logger = logging.getLogger(__name__)

settings_api_bp = Blueprint('settings_api', __name__, url_prefix='/api/settings')

# Путь к файлу настроек
SETTINGS_FILE = Config.DATA_DIR / 'settings.json'

def load_settings():
    """Загружает настройки из файла"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")
        return {}

def save_settings(settings):
    """Сохраняет настройки в файл"""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False

@settings_api_bp.route('', methods=['GET'])
def get_settings():
    """Получает настройки"""
    try:
        settings = load_settings()
        # Не возвращаем полный ключ в ответе для безопасности, только маску
        if 'deepseek_api_key' in settings and settings['deepseek_api_key']:
            masked_key = settings['deepseek_api_key'][:8] + '...' if len(settings['deepseek_api_key']) > 8 else '***'
            settings['deepseek_api_key'] = masked_key
        
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        logger.error(f"Ошибка получения настроек: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_api_bp.route('', methods=['POST'])
def update_settings():
    """Обновляет настройки"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Данные не предоставлены'}), 400
        
        # Загружаем текущие настройки
        current_settings = load_settings()
        
        # Обновляем только переданные поля
        if 'deepseek_api_key' in data:
            # Если передан null или пустая строка, удаляем ключ
            if data['deepseek_api_key']:
                current_settings['deepseek_api_key'] = data['deepseek_api_key']
            else:
                current_settings.pop('deepseek_api_key', None)
        
        # Сохраняем обновленные настройки
        if save_settings(current_settings):
            logger.info("Настройки успешно сохранены")
            return jsonify({'success': True, 'message': 'Настройки сохранены'})
        else:
            return jsonify({'success': False, 'error': 'Не удалось сохранить настройки'}), 500
            
    except Exception as e:
        logger.error(f"Ошибка обновления настроек: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_api_bp.route('/deepseek-key', methods=['GET'])
def get_deepseek_key():
    """Получает DeepSeek API ключ (для загрузки в форму настроек)"""
    try:
        settings = load_settings()
        key = settings.get('deepseek_api_key')
        # Если ключ не в настройках, используем из переменной окружения
        if not key:
            key = Config.get_deepseek_api_key()
        return jsonify({'success': True, 'key': key or ''})
    except Exception as e:
        logger.error(f"Ошибка получения DeepSeek ключа: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

