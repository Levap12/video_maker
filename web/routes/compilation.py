#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Маршрут для создания видео-компиляций.
"""

import sys
import json
from pathlib import Path

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.tasks.task_manager import task_manager
from web.tasks.compilation_task import start_compilation_task
from web.routes.tasks_api import generate_subtask_name
import time

compilation_bp = Blueprint('compilation', __name__, url_prefix='/api/compilation')

@compilation_bp.route('/start', methods=['POST'])
def create_compilation():
    """
    Запускает задачу создания видео-компиляции из моментов.
    """
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        moments_source = data.get('moments_source', 'ai_clip_generation') # Откуда брать моменты

        if not task_id:
            return jsonify({'success': False, 'error': 'task_id обязателен'}), 400

        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404

        # Определяем, откуда брать данные для нарезки
        moments = []
        source_sub_task = workflow.sub_tasks.get(moments_source)
        file_info = None
        file_index = None
        
        # Определяем путь к файлу и находим file_info
        file_path = None
        if moments_source == 'ai_clip_generation':
            # Проверяем, указан ли файл в запросе
            if data.get('ai_clips_file'):
                file_path_str = data['ai_clips_file']
                file_path = Path(file_path_str)
                
                # Находим file_info в artifacts
                if workflow.artifacts.get('ai_clips_files'):
                    for idx, fi in enumerate(workflow.artifacts['ai_clips_files']):
                        if fi.get('path') == file_path_str:
                            file_info = fi
                            file_index = idx
                            break
            elif source_sub_task and source_sub_task.outputs and 'ai_clips_file' in source_sub_task.outputs:
                # Используем последний созданный файл (обратная совместимость)
                file_path = Path(source_sub_task.outputs['ai_clips_file'])
            elif workflow.artifacts.get('ai_clips_files'):
                # Используем первый файл из списка (последний созданный)
                file_info = workflow.artifacts['ai_clips_files'][0]
                file_path = Path(file_info['path'])
                file_index = 0
            
            if file_path and file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    moments = json.load(f)
            elif file_path:
                return jsonify({'success': False, 'error': f'Файл с моментами не найден: {file_path}'}), 400
        # Для 'moment_extraction' моменты прямо в outputs
        elif moments_source == 'moment_extraction' and source_sub_task and 'moments' in source_sub_task.outputs:
            moments = source_sub_task.outputs['moments']

        if not moments:
            return jsonify({'success': False, 'error': f'Моменты не найдены в источнике: {moments_source}'}), 400
        
        # Трансформируем ключи для совместимости, если нужно
        if moments and isinstance(moments[0], dict):
            if 'start_time' in moments[0]:
                for m in moments:
                    m['start'] = m.pop('start_time')
                    m['end'] = m.pop('end_time')
                    m['title'] = m.get('description', '')

        video_path = workflow.artifacts.get('video_path')
        if not video_path:
            return jsonify({'success': False, 'error': 'Путь к видео не найден в артефактах задачи'}), 400

        # Если file_info не найден, создаем базовый (для обратной совместимости)
        if not file_info and moments_source == 'ai_clip_generation':
            file_info = {
                'path': str(file_path) if file_path else '',
                'filename': file_path.name if file_path else 'unknown',
                'system_prompt_id': 'unknown',
                'user_prompt_id': 'unknown',
                'created_at': time.time(),
                'sub_tasks': {}
            }

        # Генерируем уникальное имя подзадачи, если есть file_info
        unique_subtask_name = "compilation"
        if file_info:
            unique_subtask_name = generate_subtask_name(file_info, 'compilation')
            
            # Обновляем file_info.sub_tasks перед запуском
            if 'sub_tasks' not in file_info:
                file_info['sub_tasks'] = {}
            file_info['sub_tasks']['compilation'] = {
                'status': 'running',
                'message': 'Начало создания компиляции',
                'progress': 0,
                'error': None,
                'outputs': {},
                'updated_at': time.time()
            }
            
            # Сохраняем обновленный file_info в artifacts
            if file_index is not None and workflow.artifacts.get('ai_clips_files'):
                workflow.artifacts['ai_clips_files'][file_index] = file_info
                task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})

        start_compilation_task(
            workflow_id=task_id,
            video_path=video_path,
            moments=moments,
            sub_task_name=unique_subtask_name,
            file_info=file_info,
            file_index=file_index
        )

        return jsonify({'success': True, 'message': f'Задача создания компиляции запущена для workflow {task_id}'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
