#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для управления промптами (системными и пользовательскими)
"""

import sys
import json
import uuid
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.config import Config

prompts_api_bp = Blueprint('prompts_api', __name__, url_prefix='/api/prompts')

# --- Хелперы для работы с JSON файлами ---

def _read_prompts(file_path: Path) -> list:
    if not file_path.exists():
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _write_prompts(file_path: Path, data: list):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- API для Системных Промптов ---

@prompts_api_bp.route('/system', methods=['GET'])
def get_system_prompts():
    prompts = _read_prompts(Config.SYSTEM_PROMPTS_FILE)
    return jsonify({'success': True, 'prompts': prompts})

@prompts_api_bp.route('/system', methods=['POST'])
def create_system_prompt():
    data = request.get_json()
    if not data or 'name' not in data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Необходимы поля name и text'}), 400
    
    prompts = _read_prompts(Config.SYSTEM_PROMPTS_FILE)
    new_prompt = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'text': data['text']
    }
    prompts.append(new_prompt)
    _write_prompts(Config.SYSTEM_PROMPTS_FILE, prompts)
    return jsonify({'success': True, 'prompt': new_prompt}), 201

@prompts_api_bp.route('/system/<prompt_id>', methods=['PUT'])
def update_system_prompt(prompt_id):
    data = request.get_json()
    if not data or 'name' not in data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Необходимы поля name и text'}), 400

    prompts = _read_prompts(Config.SYSTEM_PROMPTS_FILE)
    prompt_found = False
    for i, p in enumerate(prompts):
        if p['id'] == prompt_id:
            prompts[i]['name'] = data['name']
            prompts[i]['text'] = data['text']
            prompt_found = True
            break
    
    if not prompt_found:
        return jsonify({'success': False, 'error': 'Промпт не найден'}), 404

    _write_prompts(Config.SYSTEM_PROMPTS_FILE, prompts)
    return jsonify({'success': True})

@prompts_api_bp.route('/system/<prompt_id>', methods=['DELETE'])
def delete_system_prompt(prompt_id):
    prompts = _read_prompts(Config.SYSTEM_PROMPTS_FILE)
    original_len = len(prompts)
    prompts = [p for p in prompts if p['id'] != prompt_id]

    if len(prompts) == original_len:
        return jsonify({'success': False, 'error': 'Промпт не найден'}), 404

    _write_prompts(Config.SYSTEM_PROMPTS_FILE, prompts)
    return jsonify({'success': True})

# --- API для Пользовательских Промптов (аналогично) ---

@prompts_api_bp.route('/user', methods=['GET'])
def get_user_prompts():
    prompts = _read_prompts(Config.USER_PROMPTS_FILE)
    return jsonify({'success': True, 'prompts': prompts})

@prompts_api_bp.route('/user', methods=['POST'])
def create_user_prompt():
    data = request.get_json()
    if not data or 'name' not in data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Необходимы поля name и text'}), 400
    
    prompts = _read_prompts(Config.USER_PROMPTS_FILE)
    new_prompt = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'text': data['text']
    }
    prompts.append(new_prompt)
    _write_prompts(Config.USER_PROMPTS_FILE, prompts)
    return jsonify({'success': True, 'prompt': new_prompt}), 201

@prompts_api_bp.route('/user/<prompt_id>', methods=['PUT'])
def update_user_prompt(prompt_id):
    data = request.get_json()
    if not data or 'name' not in data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Необходимы поля name и text'}), 400

    prompts = _read_prompts(Config.USER_PROMPTS_FILE)
    prompt_found = False
    for i, p in enumerate(prompts):
        if p['id'] == prompt_id:
            prompts[i]['name'] = data['name']
            prompts[i]['text'] = data['text']
            prompt_found = True
            break
    
    if not prompt_found:
        return jsonify({'success': False, 'error': 'Промпт не найден'}), 404

    _write_prompts(Config.USER_PROMPTS_FILE, prompts)
    return jsonify({'success': True})

@prompts_api_bp.route('/user/<prompt_id>', methods=['DELETE'])
def delete_user_prompt(prompt_id):
    prompts = _read_prompts(Config.USER_PROMPTS_FILE)
    original_len = len(prompts)
    prompts = [p for p in prompts if p['id'] != prompt_id]

    if len(prompts) == original_len:
        return jsonify({'success': False, 'error': 'Промпт не найден'}), 404

    _write_prompts(Config.USER_PROMPTS_FILE, prompts)
    return jsonify({'success': True})
