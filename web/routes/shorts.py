#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Маршрут для создания YouTube Shorts.
"""

import sys
import json
from pathlib import Path

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify
from web.tasks.task_manager import task_manager
from web.tasks.shorts_creation_task import start_shorts_creation_task
from web.routes.tasks_api import generate_subtask_name
from web.config import Config
import time
import logging

logger = logging.getLogger(__name__)

shorts_bp = Blueprint('shorts', __name__, url_prefix='/api/shorts')

# Файл для сохранения глобальных настроек Shorts
SHORTS_SETTINGS_FILE = Config.DATA_DIR / 'shorts_settings.json'

# Значения по умолчанию
DEFAULT_SHORTS_SETTINGS = {
    "banner_path": None,
    "watermark_text": None,
    "watermark_color": "gray",
    "watermark_font_size": 72,
    "watermark_bottom_offset": 180,
    "banner_offset": 100,
    "height_scale": 2.0
}

def _read_shorts_settings() -> dict:
    """Читает глобальные настройки Shorts из файла"""
    if not SHORTS_SETTINGS_FILE.exists():
        return DEFAULT_SHORTS_SETTINGS.copy()
    try:
        with open(SHORTS_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # Объединяем с дефолтными значениями на случай, если в файле не все поля
            result = DEFAULT_SHORTS_SETTINGS.copy()
            result.update(settings)
            return result
    except Exception as e:
        print(f"Ошибка чтения настроек Shorts: {e}")
        return DEFAULT_SHORTS_SETTINGS.copy()

def _write_shorts_settings(settings: dict):
    """Сохраняет глобальные настройки Shorts в файл"""
    try:
        with open(SHORTS_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения настроек Shorts: {e}")
        raise

@shorts_bp.route('/settings', methods=['GET'])
def get_shorts_settings():
    """Получает глобальные настройки Shorts"""
    settings = _read_shorts_settings()
    return jsonify({'success': True, 'settings': settings})

@shorts_bp.route('/settings', methods=['POST'])
def save_shorts_settings():
    """Сохраняет глобальные настройки Shorts"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Данные не предоставлены'}), 400
        
        # Получаем текущие настройки и обновляем только переданные поля
        current_settings = _read_shorts_settings()
        current_settings.update(data)
        
        # Валидация значений
        if 'watermark_font_size' in current_settings:
            current_settings['watermark_font_size'] = int(current_settings.get('watermark_font_size', 72))
        if 'watermark_bottom_offset' in current_settings:
            current_settings['watermark_bottom_offset'] = int(current_settings.get('watermark_bottom_offset', 180))
        if 'banner_offset' in current_settings:
            current_settings['banner_offset'] = int(current_settings.get('banner_offset', 100))
        if 'height_scale' in current_settings:
            current_settings['height_scale'] = float(current_settings.get('height_scale', 2.0))
        
        _write_shorts_settings(current_settings)
        return jsonify({'success': True, 'settings': current_settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@shorts_bp.route('/start', methods=['POST'])
def create_shorts():
    """
    Запускает задачу создания YouTube Shorts из клипов, созданных в рамках workflow.
    """
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        clips_source_sub_task = data.get('clips_source', 'clipping') # Откуда брать клипы
        
        logger.info(f"Запрос на создание Shorts: task_id={task_id}, clips_source={clips_source_sub_task}, data={data}")
        
        if not task_id:
            logger.warning("Запрос без task_id")
            return jsonify({'success': False, 'error': 'task_id обязателен'}), 400

        workflow = task_manager.get_task(task_id)
        if not workflow:
            logger.warning(f"Workflow {task_id} не найден")
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404

        # Определяем file_info для привязки shorts к файлу
        file_info = None
        file_index = None
        
        # Если указан файл в запросе, находим file_info
        if data.get('ai_clips_file'):
            file_path_str = data.get('ai_clips_file')
            if workflow.artifacts.get('ai_clips_files'):
                for idx, fi in enumerate(workflow.artifacts['ai_clips_files']):
                    if fi.get('path') == file_path_str:
                        file_info = fi
                        file_index = idx
                        break
        
        # Если file_info не найден, пытаемся найти через clipping подзадачу
        if not file_info and clips_source_sub_task.startswith('clipping_'):
            # Извлекаем информацию из имени подзадачи
            parts = clips_source_sub_task.split('_')
            if len(parts) >= 4:
                system_prompt_id = parts[1]
                user_prompt_id = parts[2]
                timestamp_str = '_'.join(parts[3:])
                
                # Ищем соответствующий файл в artifacts
                if workflow.artifacts.get('ai_clips_files'):
                    for idx, fi in enumerate(workflow.artifacts['ai_clips_files']):
                        if (fi.get('system_prompt_id') == system_prompt_id and 
                            fi.get('user_prompt_id') == user_prompt_id):
                            # Проверяем timestamp
                            created_at = fi.get('created_at', 0)
                            if isinstance(created_at, (int, float)):
                                file_timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime(created_at))
                                if file_timestamp == timestamp_str:
                                    file_info = fi
                                    file_index = idx
                                    break
        
        # Ищем пути к клипам
        clips_paths = None
        
        # Если есть file_info и clips_source начинается с clipping_, ищем клипы в подзадаче файла
        if file_info and clips_source_sub_task.startswith('clipping_'):
            if file_info.get('sub_tasks') and file_info['sub_tasks'].get('clipping'):
                clipping_subtask = file_info['sub_tasks']['clipping']
                if clipping_subtask.get('outputs') and clipping_subtask['outputs'].get('clips'):
                    clips_paths = clipping_subtask['outputs']['clips']
                    logger.info(f"Найдены клипы в подзадаче clipping файла: {len(clips_paths)} клипов")
        
        # Если клипы не найдены в file_info, ищем в основной подзадаче workflow
        if not clips_paths:
            source_task = workflow.sub_tasks.get(clips_source_sub_task)
            logger.info(f"Подзадача '{clips_source_sub_task}': найдена={source_task is not None}, outputs={source_task.outputs if source_task else None}")
            
            if not source_task:
                logger.warning(f"Подзадача '{clips_source_sub_task}' не найдена. Доступные подзадачи: {list(workflow.sub_tasks.keys())}")
                return jsonify({'success': False, 'error': f'Подзадача \'{clips_source_sub_task}\' не найдена. Доступные: {list(workflow.sub_tasks.keys())}'}), 400
            
            if not source_task.outputs or not source_task.outputs.get('clips'):
                logger.warning(f"Клипы не найдены в подзадаче '{clips_source_sub_task}'. Outputs: {source_task.outputs}")
                return jsonify({'success': False, 'error': f'Клипы не найдены в подзадаче \'{clips_source_sub_task}\'. Outputs: {source_task.outputs}'}), 400
            
            clips_paths = source_task.outputs['clips']
        
        # Собираем параметры с приоритетом: настройки файла > глобальные настройки > значения по умолчанию
        global_settings = _read_shorts_settings()
        file_settings = {}
        
        # Если есть file_info, проверяем сохраненные настройки файла
        if file_info and file_info.get('sub_tasks') and file_info['sub_tasks'].get('shorts_creation') and file_info['sub_tasks']['shorts_creation'].get('params'):
            file_settings = file_info['sub_tasks']['shorts_creation']['params']
        
        # Объединяем настройки с приоритетом
        shorts_params = DEFAULT_SHORTS_SETTINGS.copy()
        shorts_params.update(global_settings)  # Глобальные настройки перезаписывают дефолтные
        shorts_params.update(file_settings)    # Настройки файла перезаписывают глобальные
        
        # Параметры из запроса имеют наивысший приоритет (для переопределения)
        for key in ['banner_path', 'watermark_text', 'watermark_color', 'watermark_font_size', 
                    'watermark_bottom_offset', 'banner_offset', 'height_scale']:
            if data.get(key) is not None:
                shorts_params[key] = data.get(key)
        
        # Валидация и преобразование типов
        if shorts_params.get('watermark_font_size'):
            shorts_params['watermark_font_size'] = int(shorts_params['watermark_font_size'])
        if shorts_params.get('watermark_bottom_offset'):
            shorts_params['watermark_bottom_offset'] = int(shorts_params['watermark_bottom_offset'])
        if shorts_params.get('banner_offset'):
            shorts_params['banner_offset'] = int(shorts_params['banner_offset'])
        if shorts_params.get('height_scale'):
            shorts_params['height_scale'] = float(shorts_params['height_scale'])

        # Генерируем уникальное имя подзадачи, если есть file_info
        unique_subtask_name = "shorts_creation"
        if file_info:
            unique_subtask_name = generate_subtask_name(file_info, 'shorts_creation')
            
            # Обновляем file_info.sub_tasks перед запуском
            if 'sub_tasks' not in file_info:
                file_info['sub_tasks'] = {}
            file_info['sub_tasks']['shorts_creation'] = {
                'status': 'running',
                'message': 'Начало создания Shorts',
                'progress': 0,
                'error': None,
                'outputs': {},
                'updated_at': time.time()
            }
            
            # Сохраняем обновленный file_info в artifacts
            if file_index is not None and workflow.artifacts.get('ai_clips_files'):
                workflow.artifacts['ai_clips_files'][file_index] = file_info
                task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})

        start_shorts_creation_task(
            workflow_id=task_id,
            clips_paths=clips_paths,
            sub_task_name=unique_subtask_name,
            file_info=file_info,
            file_index=file_index,
            **shorts_params
        )
        
        return jsonify({'success': True, 'message': f'Задача создания Shorts запущена для workflow {task_id}'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500