#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для управления иерархическими задачами (workflows)
"""

import sys
import json
import logging
import time
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.tasks.task_manager import task_manager, TaskStatus
from web.services.ai_service import AIService
from web.config import Config

logger = logging.getLogger(__name__)
tasks_api_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')


def get_prompt_name(prompt_type: str, prompt_id: str) -> str:
    """Получает название промпта по его ID из файла промптов."""
    try:
        file_path = Config.SYSTEM_PROMPTS_FILE if prompt_type == 'system' else Config.USER_PROMPTS_FILE
        if not file_path.exists():
            return prompt_id  # Возвращаем ID, если файл не найден
        
        with open(file_path, 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        
        for p in prompts:
            if p['id'] == prompt_id:
                return p.get('name', prompt_id)
        
        return prompt_id  # Возвращаем ID, если промпт не найден
    except Exception as e:
        logger.warning(f"Ошибка при получении названия промпта {prompt_id}: {e}")
        return prompt_id


def generate_subtask_name(file_info: dict, subtask_type: str) -> str:
    """
    Генерирует уникальное имя подзадачи на основе информации о файле.
    
    Args:
        file_info: Словарь с информацией о файле (system_prompt_id, user_prompt_id, created_at)
        subtask_type: Тип подзадачи ('clipping', 'compilation', 'shorts_creation')
    
    Returns:
        Уникальное имя подзадачи в формате: {subtask_type}_{system_prompt_id}_{user_prompt_id}_{timestamp}
    """
    system_prompt_id = file_info.get('system_prompt_id', 'unknown')
    user_prompt_id = file_info.get('user_prompt_id', 'unknown')
    created_at = file_info.get('created_at', time.time())
    
    # Извлекаем timestamp из created_at (если это число) или используем текущее время
    if isinstance(created_at, (int, float)):
        timestamp_str = time.strftime('%Y%m%d_%H%M%S', time.localtime(created_at))
    else:
        timestamp_str = time.strftime('%Y%m%d_%H%M%S')
    
    return f"{subtask_type}_{system_prompt_id}_{user_prompt_id}_{timestamp_str}"


@tasks_api_bp.route('/', methods=['GET'])
def get_tasks():
    """Возвращает список всех рабочих процессов (workflows)."""
    try:
        all_tasks = task_manager.list_tasks()
        return jsonify({'success': True, 'tasks': all_tasks})
    except Exception as e:
        logger.exception("Ошибка при получении списка задач")
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_api_bp.route('/<task_id>', methods=['GET'])
def get_task_details(task_id):
    """Возвращает детальную информацию по одному рабочему процессу."""
    try:
        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404
        return jsonify({'success': True, 'task': task.to_dict()})
    except Exception as e:
        logger.exception(f"Ошибка при получении деталей задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_api_bp.route('/<task_id>/generate-ai-clips', methods=['POST'])
def generate_ai_clips(task_id):
    """Генерирует нарезку клипов с помощью AI как подзадачу."""
    sub_task_name = "ai_clip_generation"
    try:
        data = request.get_json()
        system_prompt_id = data.get('system_prompt_id')
        user_prompt_id = data.get('user_prompt_id')
        if not system_prompt_id or not user_prompt_id:
            return jsonify({'success': False, 'error': 'Не выбраны системный и пользовательский промпты'}), 400

        workflow = task_manager.get_task(task_id)
        if not workflow or not workflow.artifacts.get('transcription_simple_path'):
            return jsonify({'success': False, 'error': 'Workflow или путь к упрощенной транскрипции не найдены'}), 404

        task_manager.update_sub_task(task_id, sub_task_name, 'ai_clip_generation', TaskStatus.RUNNING, message="Генерация AI нарезки...")

        transcription_path = Path(workflow.artifacts['transcription_simple_path'])
        if not transcription_path.exists():
            raise FileNotFoundError(f"Файл транскрипции не найден: {transcription_path}")
        
        transcription_text = transcription_path.read_text(encoding='utf-8')
        video_duration = workflow.artifacts.get('video_duration', 25 * 60) # Default 25 mins

        ai_service = AIService()
        ai_result = ai_service.generate_clips_from_transcription(
            transcription_text, system_prompt_id, user_prompt_id, video_duration
        )

        if not ai_result.get('success'):
            raise Exception(ai_result.get('error', 'Неизвестная ошибка от AI сервиса'))

        clips_data = ai_result['clips']
        ai_clips_dir = Config.DATA_DIR / 'ai_clips'
        ai_clips_dir.mkdir(exist_ok=True)
        
        original_filename = transcription_path.stem
        # Создаем имя файла с информацией о промптах и timestamp для уникальности
        timestamp = int(time.time())
        datetime_str = time.strftime('%Y%m%d_%H%M%S', time.localtime(timestamp))
        ai_clips_filename = f"{original_filename}_ai_clips_{system_prompt_id}_{user_prompt_id}_{datetime_str}.json"
        save_path = ai_clips_dir / ai_clips_filename

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(clips_data, f, ensure_ascii=False, indent=2)

        # Получаем информацию о файле для сохранения в artifacts
        file_info = {
            'path': str(save_path),
            'filename': ai_clips_filename,
            'system_prompt_id': system_prompt_id,
            'user_prompt_id': user_prompt_id,
            'system_prompt_name': get_prompt_name('system', system_prompt_id),
            'user_prompt_name': get_prompt_name('user', user_prompt_id),
            'created_at': time.time(),
            'sub_tasks': {}  # Храним статусы подзадач для этого файла
        }

        # Сохраняем список всех файлов в artifacts
        if 'ai_clips_files' not in workflow.artifacts:
            workflow.artifacts['ai_clips_files'] = []
        
        # Добавляем новый файл в начало списка
        workflow.artifacts['ai_clips_files'].insert(0, file_info)
        task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})

        # Обновляем подзадачу с последним созданным файлом (для обратной совместимости)
        task_manager.update_sub_task(
            task_id=task_id,
            sub_task_name=sub_task_name,
            sub_task_type='ai_clip_generation',
            status=TaskStatus.COMPLETED,
            message=f'Файл с AI нарезкой создан: {ai_clips_filename}',
            outputs={'ai_clips_file': str(save_path)}
        )

        return jsonify({'success': True, 'message': f'Файл с AI нарезкой создан: {ai_clips_filename}', 'path': str(save_path)})

    except Exception as e:
        logger.exception(f"Критическая ошибка в generate_ai_clips для задачи {task_id}")
        task_manager.update_sub_task(task_id, sub_task_name, 'ai_clip_generation', TaskStatus.FAILED, error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_api_bp.route('/<task_id>/create-clips-from-ai', methods=['POST'])
def create_clips_from_ai(task_id):
    """Создает отдельные клипы из AI нарезки."""
    sub_task_name = "clipping"
    try:
        data = request.get_json() or {}
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404

        # Определяем путь к файлу и находим file_info
        file_path = None
        file_info = None
        file_index = None
        
        if data.get('ai_clips_file'):
            # Используем указанный файл
            file_path_str = data['ai_clips_file']
            file_path = Path(file_path_str)
            
            # Находим file_info в artifacts
            if workflow.artifacts.get('ai_clips_files'):
                for idx, fi in enumerate(workflow.artifacts['ai_clips_files']):
                    if fi.get('path') == file_path_str:
                        file_info = fi
                        file_index = idx
                        break
        else:
            # Используем последний созданный файл (обратная совместимость)
            ai_clip_generation = workflow.sub_tasks.get('ai_clip_generation')
            if ai_clip_generation and ai_clip_generation.outputs.get('ai_clips_file'):
                file_path = Path(ai_clip_generation.outputs['ai_clips_file'])
            elif workflow.artifacts.get('ai_clips_files'):
                # Используем первый файл из списка (последний созданный)
                file_info = workflow.artifacts['ai_clips_files'][0]
                file_path = Path(file_info['path'])
                file_index = 0

        if not file_path:
            return jsonify({'success': False, 'error': 'AI нарезка не найдена. Сначала сгенерируйте AI нарезку.'}), 400

        if not file_path.exists():
            return jsonify({'success': False, 'error': f'Файл с AI нарезкой не найден: {file_path}'}), 400

        # Если file_info не найден, создаем базовый
        if not file_info:
            file_info = {
                'path': str(file_path),
                'filename': file_path.name,
                'system_prompt_id': 'unknown',
                'user_prompt_id': 'unknown',
                'created_at': time.time(),
                'sub_tasks': {}
            }

        with open(file_path, 'r', encoding='utf-8') as f:
            clips_data = json.load(f)

        # Преобразуем формат для VideoClipper (start_time → start, end_time → end)
        clips_for_clipper = []
        if isinstance(clips_data, list):
            for clip in clips_data:
                clips_for_clipper.append({
                    'start': clip.get('start_time', clip.get('start')),
                    'end': clip.get('end_time', clip.get('end')),
                    'title': clip.get('title', ''),
                    'caption': clip.get('summary', clip.get('full_quote', '')),
                    'type': 'ai_clip'
                })
        elif isinstance(clips_data, dict) and 'clips' in clips_data:
            for clip in clips_data['clips']:
                clips_for_clipper.append({
                    'start': clip.get('start_time', clip.get('start')),
                    'end': clip.get('end_time', clip.get('end')),
                    'title': clip.get('title', ''),
                    'caption': clip.get('summary', clip.get('full_quote', '')),
                    'type': 'ai_clip'
                })

        if not clips_for_clipper:
            return jsonify({'success': False, 'error': 'Не найдено клипов для нарезки в файле'}), 400

        video_path = workflow.artifacts.get('video_path')
        if not video_path:
            return jsonify({'success': False, 'error': 'Путь к видео не найден в артефактах задачи'}), 400

        # Генерируем уникальное имя подзадачи
        unique_subtask_name = generate_subtask_name(file_info, 'clipping')
        
        # Обновляем file_info.sub_tasks перед запуском
        if 'sub_tasks' not in file_info:
            file_info['sub_tasks'] = {}
        file_info['sub_tasks']['clipping'] = {
            'status': 'running',
            'message': 'Начало нарезки клипов',
            'progress': 0,
            'error': None,
            'outputs': {},
            'updated_at': time.time()
        }
        
        # Сохраняем обновленный file_info в artifacts
        if file_index is not None and workflow.artifacts.get('ai_clips_files'):
            workflow.artifacts['ai_clips_files'][file_index] = file_info
            task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})

        # Запускаем задачу нарезки с уникальным именем и file_info
        from web.tasks.clipping_task import start_clipping_task
        start_clipping_task(
            workflow_id=task_id,
            video_path=video_path,
            clips_data=clips_for_clipper,
            sub_task_name=unique_subtask_name,
            file_info=file_info,
            file_index=file_index
        )

        return jsonify({'success': True, 'message': f'Задача нарезки клипов запущена для workflow {task_id}'})

    except json.JSONDecodeError as e:
        logger.exception(f"Ошибка парсинга JSON в create_clips_from_ai для задачи {task_id}")
        return jsonify({'success': False, 'error': f'Ошибка парсинга файла с AI нарезкой: {str(e)}'}), 400
    except Exception as e:
        logger.exception(f"Ошибка в create_clips_from_ai для задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500