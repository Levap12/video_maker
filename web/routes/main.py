#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основные маршруты для создания и управления рабочими процессами (workflow).
"""

import sys
import uuid
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.services.hdrezka_service import HdRezkaService
from web.tasks.task_manager import task_manager
from web.tasks.initial_processing_task import start_initial_processing_task
from web.config import Config

main_bp = Blueprint('main', __name__, url_prefix='/api/workflow')

@main_bp.route('/analyze', methods=['POST'])
def analyze_content():
    """
    Анализирует контент по URL HDRezka для получения информации о видео.
    """
    try:
        data = request.get_json()
        url = data.get('url')
        proxy = data.get('proxy')
        proxy_type = data.get('proxy_type', 'socks5')
        
        if not url:
            return jsonify({'success': False, 'error': 'URL не указан'}), 400
        
        service = HdRezkaService(proxy=proxy, proxy_type=proxy_type)
        result = service.analyze_content(url)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/start', methods=['POST'])
def start_workflow():
    """
    Запускает полный рабочий процесс: скачивание, обработка и т.д.
    """
    try:
        data = request.get_json()
        url = data.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'URL не указан'}), 400

        # Собираем параметры с правильной конвертацией типов
        season = data.get('season')
        episode = data.get('episode')
        translator_id = data.get('translator_id')
        
        params = {
            'url': url,
            'proxy': data.get('proxy'),
            'proxy_type': data.get('proxy_type', 'socks5'),
            'season': int(season) if season else None,
            'episode': int(episode) if episode else None,
            'translator_id': int(translator_id) if translator_id else None,
            'quality': data.get('quality', Config.DEFAULT_QUALITY)
        }

        # Создаем уникальный ID и имя для workflow
        task_id = str(uuid.uuid4())
        workflow_name = f"Workflow for {url}"
        if params['season'] and params['episode']:
            workflow_name += f" S{params['season']}E{params['episode']}"

        # Создаем рабочий процесс
        workflow = task_manager.create_workflow(
            task_id=task_id, 
            name=workflow_name, 
            artifacts=params
        )
        
        # Проверяем, что задача создана в памяти
        verify_task = task_manager.get_task(task_id)
        if not verify_task:
            return jsonify({'success': False, 'error': 'Не удалось создать задачу'}), 500
        
        # Запускаем фоновую задачу начальной обработки
        start_initial_processing_task(
            task_id=task_id,
            **params
        )
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/<task_id>/update-artifacts', methods=['POST'])
def update_workflow_artifacts_endpoint(task_id):
    """Обновляет artifacts workflow"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Данные не предоставлены'}), 400
        
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404
        
        task_manager.update_workflow_artifacts(task_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/status/<task_id>', methods=['GET'])
def get_workflow_status_compat(task_id):
    """Эндпоинт для обратной совместимости со старым фронтендом."""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404
        
        # Вычисляем общий прогресс на основе подзадач
        total_progress = 0.0
        message = task.message or 'Ожидание...'
        
        if task.sub_tasks:
            sub_tasks_list = list(task.sub_tasks.values())
            if sub_tasks_list:
                total_progress = sum(sub.progress for sub in sub_tasks_list) / len(sub_tasks_list)
                # Используем сообщение из активной подзадачи, если есть
                active_subtask = next((st for st in sub_tasks_list if st.status.value == 'running'), None)
                if active_subtask and active_subtask.message:
                    message = active_subtask.message
        
        # Определяем статус: если есть подзадачи в процессе, статус должен быть RUNNING
        status = task.status.value.upper()
        if task.sub_tasks and any(st.status.value == 'running' for st in task.sub_tasks.values()):
            status = 'RUNNING'
        elif task.status.value == 'pending' and not task.sub_tasks:
            # Если задача pending и нет подзадач, может быть она еще не запустилась
            status = 'PENDING'
        
        # Возвращаем данные в формате, который ожидает фронтенд
        return jsonify({
            'success': True,
            'task': {
                'task_id': task.task_id,
                'status': status,
                'message': message,
                'progress': round(total_progress, 1)
            }
        })
    except Exception as e:
        import logging
        logging.exception(f"Ошибка в get_workflow_status_compat для задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500