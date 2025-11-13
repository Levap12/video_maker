#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Маршруты для обработки видео: извлечение моментов, нарезка клипов.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.tasks.task_manager import task_manager, TaskStatus
from web.services.ai_service import AIService
from web.services.transcription_service import TranscriptionService
from web.tasks.clipping_task import start_clipping_task

processing_bp = Blueprint('processing', __name__, url_prefix='/api/processing')

@processing_bp.route('/extract-moments', methods=['POST'])
def extract_moments():
    """
    Извлекает интересные моменты из транскрипции и сохраняет как подзадачу.
    """
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        prompt = data.get('prompt')
        
        if not task_id or not prompt:
            return jsonify({'success': False, 'error': 'task_id и prompt обязательны'}), 400
        
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404
        
        # Ищем транскрипцию в артефактах
        transcription_text = workflow.artifacts.get('transcription_text')
        if not transcription_text:
            return jsonify({'success': False, 'error': 'Транскрипция не найдена в артефактах задачи.'}), 400

        # Обновляем статус подзадачи
        sub_task_name = "moment_extraction"
        task_manager.update_sub_task(task_id, sub_task_name, 'moment_extraction', TaskStatus.RUNNING, message="Извлечение моментов...")

        # Извлекаем моменты
        ai_service = AIService()
        moments = ai_service.extract_moments(transcription_text, prompt)
        
        # Сохраняем результат в подзадачу
        task_manager.update_sub_task(
            task_id=task_id,
            sub_task_name=sub_task_name,
            sub_task_type='moment_extraction',
            status=TaskStatus.COMPLETED,
            message=f"Найдено {len(moments)} моментов",
            outputs={'moments': moments, 'extraction_prompt': prompt}
        )
        
        return jsonify({'success': True, 'moments': moments, 'count': len(moments)})
        
    except Exception as e:
        # В случае ошибки обновляем статус подзадачи
        if 'task_id' in locals() and 'sub_task_name' in locals():
            task_manager.update_sub_task(locals()['task_id'], locals()['sub_task_name'], 'moment_extraction', TaskStatus.FAILED, error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


@processing_bp.route('/create-clips', methods=['POST'])
def create_clips():
    """
    Запускает задачу нарезки клипов на основе данных из подзадачи извлечения моментов.
    """
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({'success': False, 'error': 'task_id обязателен'}), 400
        
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404
        
        # Ищем моменты в подзадаче
        moment_extraction_task = workflow.sub_tasks.get('moment_extraction')
        if not moment_extraction_task or not moment_extraction_task.outputs.get('moments'):
            return jsonify({'success': False, 'error': 'Результаты извлечения моментов не найдены. Сначала выполните этот шаг.'}), 400
        
        moments = moment_extraction_task.outputs['moments']
        # Трансформируем 'description' в 'title' для совместимости
        for m in moments:
            m['title'] = m.get('description', '')

        video_path = workflow.artifacts.get('video_path')
        if not video_path:
            return jsonify({'success': False, 'error': 'Путь к видео не найден в артефактах задачи'}), 400
        
        # Запускаем фоновую задачу нарезки
        start_clipping_task(
            workflow_id=task_id,
            video_path=video_path,
            clips_data=moments, # moments теперь содержат start, end, title
            sub_task_name="clipping"
        )
        
        return jsonify({'success': True, 'message': f'Задача нарезки клипов запущена для workflow {task_id}'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500