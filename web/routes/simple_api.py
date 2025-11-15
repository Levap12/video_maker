#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный REST API для внешней интеграции.
Автоматически выполняет полный workflow от скачивания до создания Shorts.
"""

import sys
import json
import time
import threading
import logging
from pathlib import Path
from typing import Dict, Optional, List

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify, url_for
from web.tasks.task_manager import task_manager, TaskStatus, WorkflowTask
from web.tasks.initial_processing_task import start_initial_processing_task
from web.tasks.clipping_task import start_clipping_task
from web.tasks.shorts_creation_task import start_shorts_creation_task
from web.services.ai_service import AIService
from web.routes.tasks_api import generate_subtask_name, get_prompt_name
from web.config import Config
from moviepy.editor import VideoFileClip

logger = logging.getLogger(__name__)
simple_api_bp = Blueprint('simple_api', __name__, url_prefix='/api/v1/video')


def get_simple_status(workflow: WorkflowTask) -> Dict:
    """
    Возвращает упрощенный статус workflow с этапами и прогрессом.
    
    Args:
        workflow: WorkflowTask объект
        
    Returns:
        Словарь с упрощенным статусом
    """
    # Определяем этап
    stage = determine_stage(workflow)
    
    # Вычисляем прогресс
    progress = calculate_progress(workflow)
    
    # Формируем сообщение
    message = get_stage_message(workflow, stage)
    
    # Если завершено, собираем видео
    videos = []
    if stage == 'completed':
        videos = collect_ready_videos(workflow)
    
    status = 'completed' if stage == 'completed' else ('failed' if stage == 'failed' else 'processing')
    
    result = {
        'success': True,
        'status': status,
        'stage': stage,
        'progress': round(progress, 1),
        'message': message
    }
    
    if videos:
        result['videos'] = videos
    
    if stage == 'failed' and workflow.error:
        result['error'] = workflow.error
    
    return result


def determine_stage(workflow: WorkflowTask) -> str:
    """Определяет текущий этап обработки на основе подзадач."""
    sub_tasks = workflow.sub_tasks
    
    # Проверяем на ошибки
    for sub_task in sub_tasks.values():
        if sub_task.status == TaskStatus.FAILED:
            return 'failed'
    
    if workflow.status == TaskStatus.FAILED:
        return 'failed'
    
    # Проверяем этапы по порядку
    initial_processing = sub_tasks.get('initial_processing')
    transcription = sub_tasks.get('transcription')
    ai_generation = sub_tasks.get('ai_clip_generation')
    
    # Проверяем clipping подзадачи (могут быть с уникальными именами)
    clipping_tasks = [st for name, st in sub_tasks.items() if name.startswith('clipping_')]
    active_clipping = next((st for st in clipping_tasks if st.status == TaskStatus.RUNNING), None)
    completed_clipping = next((st for st in clipping_tasks if st.status == TaskStatus.COMPLETED), None)
    
    # Проверяем shorts_creation подзадачи
    shorts_tasks = [st for name, st in sub_tasks.items() if name.startswith('shorts_creation_')]
    active_shorts = next((st for st in shorts_tasks if st.status == TaskStatus.RUNNING), None)
    completed_shorts = next((st for st in shorts_tasks if st.status == TaskStatus.COMPLETED), None)
    
    # Этап 1: Скачивание
    if initial_processing and initial_processing.status == TaskStatus.RUNNING:
        return 'downloading'
    
    # Этап 2: Ожидание транскрипции
    if initial_processing and initial_processing.status == TaskStatus.COMPLETED:
        if not transcription:
            return 'waiting_transcription'
        if transcription.status == TaskStatus.RUNNING:
            return 'transcribing'
        if transcription.status == TaskStatus.COMPLETED:
            # Транскрипция готова, проверяем AI генерацию
            if ai_generation and ai_generation.status == TaskStatus.RUNNING:
                return 'ai_generation'
            if ai_generation and ai_generation.status == TaskStatus.COMPLETED:
                # AI готов, проверяем нарезку
                if active_clipping:
                    return 'clipping'
                if completed_clipping:
                    # Нарезка готова, проверяем Shorts
                    if active_shorts:
                        return 'shorts_creation'
                    if completed_shorts:
                        return 'completed'
                    # Нарезка завершена, но Shorts еще не запущены
                    # Проверяем, есть ли клипы для обработки
                    if completed_clipping.outputs.get('clips'):
                        return 'waiting_shorts'  # Новый этап - ожидание запуска Shorts
                    # Если клипов нет, остаемся на этапе нарезки
                    return 'clipping'
                # AI готов, но нарезка еще не запущена
                return 'ai_generation'
            # Транскрипция готова, но AI еще не запущен
            return 'waiting_transcription'
    
    # Если все этапы завершены
    if completed_shorts:
        return 'completed'
    
    return 'downloading'  # По умолчанию


def calculate_progress(workflow: WorkflowTask) -> float:
    """Вычисляет общий прогресс (0-100%) на основе подзадач."""
    sub_tasks = workflow.sub_tasks
    
    if not sub_tasks:
        return 0.0
    
    # Веса для каждого этапа
    weights = {
        'initial_processing': 20,  # 0-20%
        'transcription': 10,       # 20-30%
        'ai_clip_generation': 20,  # 30-50%
        'clipping': 20,            # 50-70%
        'shorts_creation': 30      # 70-100%
    }
    
    total_progress = 0.0
    current_weight = 0
    
    # Initial processing
    initial = sub_tasks.get('initial_processing')
    if initial:
        if initial.status == TaskStatus.COMPLETED:
            total_progress += weights['initial_processing']
        elif initial.status == TaskStatus.RUNNING:
            total_progress += initial.progress * weights['initial_processing'] / 100
        current_weight += weights['initial_processing']
    
    # Transcription
    transcription = sub_tasks.get('transcription')
    if transcription:
        if transcription.status == TaskStatus.COMPLETED:
            total_progress += weights['transcription']
        elif transcription.status == TaskStatus.RUNNING:
            total_progress += transcription.progress * weights['transcription'] / 100
        current_weight += weights['transcription']
    elif initial and initial.status == TaskStatus.COMPLETED:
        # Транскрипция еще не начата, но initial processing завершен
        current_weight += weights['transcription']
    
    # AI generation
    ai_gen = sub_tasks.get('ai_clip_generation')
    if ai_gen:
        if ai_gen.status == TaskStatus.COMPLETED:
            total_progress += weights['ai_clip_generation']
        elif ai_gen.status == TaskStatus.RUNNING:
            total_progress += ai_gen.progress * weights['ai_clip_generation'] / 100
        current_weight += weights['ai_clip_generation']
    elif transcription and transcription.status == TaskStatus.COMPLETED:
        current_weight += weights['ai_clip_generation']
    
    # Clipping
    clipping_tasks = [st for name, st in sub_tasks.items() if name.startswith('clipping_')]
    if clipping_tasks:
        clipping = clipping_tasks[0]  # Берем первый
        if clipping.status == TaskStatus.COMPLETED:
            total_progress += weights['clipping']
        elif clipping.status == TaskStatus.RUNNING:
            total_progress += clipping.progress * weights['clipping'] / 100
        current_weight += weights['clipping']
    elif ai_gen and ai_gen.status == TaskStatus.COMPLETED:
        current_weight += weights['clipping']
    
    # Shorts creation
    shorts_tasks = [st for name, st in sub_tasks.items() if name.startswith('shorts_creation_')]
    if shorts_tasks:
        shorts = shorts_tasks[0]  # Берем первый
        if shorts.status == TaskStatus.COMPLETED:
            total_progress += weights['shorts_creation']
        elif shorts.status == TaskStatus.RUNNING:
            total_progress += shorts.progress * weights['shorts_creation'] / 100
        current_weight += weights['shorts_creation']
    elif clipping_tasks and clipping_tasks[0].status == TaskStatus.COMPLETED:
        current_weight += weights['shorts_creation']
    
    # Нормализуем прогресс
    if current_weight > 0:
        return min(100.0, (total_progress / current_weight) * 100)
    
    return 0.0


def get_stage_message(workflow: WorkflowTask, stage: str) -> str:
    """Формирует понятное сообщение для текущего этапа."""
    sub_tasks = workflow.sub_tasks
    
    if stage == 'downloading':
        initial = sub_tasks.get('initial_processing')
        if initial:
            return initial.message or "Скачивание и обработка видео..."
        return "Скачивание видео..."
    
    if stage == 'waiting_transcription':
        return "Ожидание транскрипции. Видео скачано, аудио извлечено. Запустите транскрипцию через Colab или вручную."
    
    if stage == 'transcribing':
        transcription = sub_tasks.get('transcription')
        if transcription:
            return transcription.message or "Транскрипция выполняется..."
        return "Транскрипция выполняется..."
    
    if stage == 'ai_generation':
        ai_gen = sub_tasks.get('ai_clip_generation')
        if ai_gen:
            return ai_gen.message or "Генерация клипов через AI..."
        return "Генерация клипов через AI..."
    
    if stage == 'clipping':
        clipping_tasks = [st for name, st in sub_tasks.items() if name.startswith('clipping_')]
        if clipping_tasks:
            return clipping_tasks[0].message or "Нарезка клипов из видео..."
        return "Нарезка клипов из видео..."
    
    if stage == 'waiting_shorts':
        return "Нарезка завершена. Запуск создания Shorts..."
    
    if stage == 'shorts_creation':
        shorts_tasks = [st for name, st in sub_tasks.items() if name.startswith('shorts_creation_')]
        if shorts_tasks:
            return shorts_tasks[0].message or "Создание Shorts..."
        return "Создание Shorts..."
    
    if stage == 'completed':
        return "Все видео готовы!"
    
    if stage == 'failed':
        return workflow.error or "Произошла ошибка при обработке"
    
    return "Обработка..."


def collect_ready_videos(workflow: WorkflowTask) -> List[Dict]:
    """Собирает список готовых видео из outputs подзадачи shorts_creation."""
    videos = []
    
    # Ищем подзадачи shorts_creation
    shorts_tasks = [(name, st) for name, st in workflow.sub_tasks.items() if name.startswith('shorts_creation_')]
    
    for task_name, shorts_task in shorts_tasks:
        if shorts_task.status == TaskStatus.COMPLETED and shorts_task.outputs:
            shorts_paths = shorts_task.outputs.get('shorts', [])
            shorts_metadata = shorts_task.outputs.get('shorts_metadata', {})
            
            for short_path in shorts_paths:
                short_file = Path(short_path)
                if short_file.exists():
                    size_mb = short_file.stat().st_size / (1024 * 1024)
                    
                    # Пытаемся получить длительность
                    duration = None
                    try:
                        clip = VideoFileClip(str(short_file))
                        duration = clip.duration
                        clip.close()
                    except:
                        pass
                    
                    video_obj = {
                        'filename': short_file.name,
                        'url': f'/api/files/short/{short_file.name}',
                        'size_mb': round(size_mb, 2),
                        'duration_seconds': round(duration, 1) if duration else None
                    }
                    
                    # Добавляем метаданные, если они есть
                    short_path_str = str(short_path)
                    if short_path_str in shorts_metadata:
                        video_obj['metadata'] = shorts_metadata[short_path_str]
                    elif short_file.name in shorts_metadata:
                        # Пробуем найти по имени файла (на случай разных форматов путей)
                        video_obj['metadata'] = shorts_metadata[short_file.name]
                    
                    videos.append(video_obj)
    
    return videos


def _start_colab_transcription_automation(task_id: str):
    """
    Вспомогательная функция для автоматического запуска Colab транскрипции через Camoufox.
    ЗАКРЫТА: Colab автоматизация отключена.
    """
    logger.warning(f"[{task_id}] Попытка запуска Colab автоматизации, но она отключена")
    return  # Colab автоматизация отключена
    
    def run_automation():
        try:
            workflow = task_manager.get_task(task_id)
            if not workflow:
                logger.error(f"[{task_id}] Workflow не найден для Colab автоматизации")
                return
            
            # Создаем подзадачу транскрипции
            task_manager.update_sub_task(
                task_id=task_id,
                sub_task_name='transcription',
                sub_task_type='transcription',
                status=TaskStatus.RUNNING,
                message="Запуск Colab автоматизации для транскрибации..."
            )
            
            # Получаем конфигурацию
            selectors = getattr(Config, 'COLAB_SELECTORS', {})
            colab_url = getattr(Config, 'COLAB_URL', '')
            profile_path = getattr(Config, 'COLAB_PROFILE_PATH', None)
            
            if not colab_url:
                raise ValueError("URL Colab не настроен в конфигурации")
            
            # Определяем путь к профилю
            db_path = r"C:\Users\shegl\PycharmProjects\YoutubeUploader2\database.db"
            profile_name = "Youtube Main"
            
            logger.info(f"[{task_id}] Запуск Colab автоматизации: URL={colab_url}, Profile={profile_path or 'из БД'}")
            
            # Создаем и запускаем автоматизацию
            from web.services.colab_automation import ColabAutomation
            
            automation = ColabAutomation(
                profile_path=profile_path,
                db_path=db_path,
                profile_name=profile_name,
                headless=False  # Можно сделать настраиваемым через Config
            )
            
            try:
                # Запускаем браузер
                if not automation.start_browser():
                    raise Exception("Не удалось запустить браузер")
                
                logger.info(f"[{task_id}] Браузер запущен, открываем Colab...")
                
                # Открываем Colab
                if not automation.open_colab(colab_url):
                    raise Exception("Не удалось открыть Colab ноутбук")
                
                logger.info(f"[{task_id}] Colab открыт, запускаем скрипт транскрибации...")
                
                # Запускаем скрипт транскрибации
                if not automation.run_transcription_script(selectors):
                    raise Exception("Не удалось запустить скрипт транскрибации")
                
                logger.info(f"[{task_id}] Скрипт транскрибации запущен, ожидаем завершения...")
                
                # Обновляем статус подзадачи
                task_manager.update_sub_task(
                    task_id=task_id,
                    sub_task_name='transcription',
                    sub_task_type='transcription',
                    status=TaskStatus.RUNNING,
                    message="Транскрибация выполняется в Colab..."
                )
                
                # Ожидаем завершения
                if not automation.wait_for_completion(selectors, timeout=3600):
                    raise Exception("Транскрибация не завершилась в срок")
                
                logger.info(f"[{task_id}] Colab транскрибация успешно завершена!")
                
                # Обновляем статус подзадачи
                task_manager.update_sub_task(
                    task_id=task_id,
                    sub_task_name='transcription',
                    sub_task_type='transcription',
                    status=TaskStatus.COMPLETED,
                    message="Транскрибация завершена через Colab автоматизацию"
                )
                
            finally:
                # Закрываем браузер
                automation.cleanup()
                logger.info(f"[{task_id}] Браузер закрыт")
                
        except Exception as e:
            logger.exception(f"[{task_id}] Ошибка в Colab автоматизации: {e}")
            # Обновляем статус подзадачи на FAILED
            try:
                task_manager.update_sub_task(
                    task_id=task_id,
                    sub_task_name='transcription',
                    sub_task_type='transcription',
                    status=TaskStatus.FAILED,
                    error=str(e)
                )
            except:
                pass
    
    # Запускаем автоматизацию в отдельном потоке
    thread = threading.Thread(target=run_automation, daemon=True)
    thread.start()
    logger.info(f"[{task_id}] Поток Colab автоматизации запущен")


def _generate_ai_clips_direct(task_id: str, system_prompt_id: str, user_prompt_id: str):
    """
    Вспомогательная функция для прямой генерации AI клипов без Flask контекста.
    Используется в auto_continue_workflow.
    """
    sub_task_name = "ai_clip_generation"
    
    workflow = task_manager.get_task(task_id)
    if not workflow or not workflow.artifacts.get('transcription_simple_path'):
        raise ValueError('Workflow или путь к упрощенной транскрипции не найдены')
    
    task_manager.update_sub_task(task_id, sub_task_name, 'ai_clip_generation', TaskStatus.RUNNING, message="Генерация AI нарезки...")
    
    transcription_path = Path(workflow.artifacts['transcription_simple_path'])
    if not transcription_path.exists():
        raise FileNotFoundError(f"Файл транскрипции не найден: {transcription_path}")
    
    transcription_text = transcription_path.read_text(encoding='utf-8')
    
    # Получаем длительность видео
    video_duration = workflow.artifacts.get('video_duration')
    if not video_duration:
        # Вычисляем длительность из видео файла
        video_path = workflow.artifacts.get('video_path')
        if video_path and Path(video_path).exists():
            try:
                video_clip = VideoFileClip(str(video_path))
                video_duration = video_clip.duration
                video_clip.close()
                # Сохраняем в artifacts для будущего использования
                task_manager.update_workflow_artifacts(task_id, {'video_duration': video_duration})
            except Exception as e:
                logger.warning(f"[{task_id}] Не удалось получить длительность видео: {e}")
                video_duration = 25 * 60  # Default 25 mins
        else:
            video_duration = 25 * 60  # Default 25 mins
    
    ai_service = AIService()
    ai_result = ai_service.generate_clips_from_transcription(
        transcription_text, system_prompt_id, user_prompt_id, video_duration
    )
    
    if not ai_result.get('success'):
        raise Exception(ai_result.get('error', 'Неизвестная ошибка от AI сервиса'))
    
    clips_data = ai_result['clips']
    
    # Нормализуем формат: если это словарь с ключом 'clips', извлекаем список
    if isinstance(clips_data, dict) and 'clips' in clips_data:
        normalized_clips = clips_data['clips']
    elif isinstance(clips_data, list):
        normalized_clips = clips_data
    else:
        normalized_clips = []
    
    # Сохраняем метаданные AI в artifacts для использования на последующих этапах
    task_manager.update_workflow_artifacts(task_id, {'ai_metadata': normalized_clips})
    logger.info(f"[{task_id}] Сохранено {len(normalized_clips)} метаданных клипов в artifacts")
    
    ai_clips_dir = Config.DATA_DIR / 'ai_clips'
    ai_clips_dir.mkdir(exist_ok=True)
    
    original_filename = transcription_path.stem
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
        'sub_tasks': {}
    }
    
    # Сохраняем список всех файлов в artifacts
    if 'ai_clips_files' not in workflow.artifacts:
        workflow.artifacts['ai_clips_files'] = []
    
    workflow.artifacts['ai_clips_files'].insert(0, file_info)
    task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})
    
    # Обновляем подзадачу
    task_manager.update_sub_task(
        task_id=task_id,
        sub_task_name=sub_task_name,
        sub_task_type='ai_clip_generation',
        status=TaskStatus.COMPLETED,
        message=f'Файл с AI нарезкой создан: {ai_clips_filename}',
        outputs={'ai_clips_file': str(save_path)}
    )


def auto_continue_workflow(task_id: str, force_check: bool = False):
    """
    Автоматически продолжает workflow на следующем этапе.
    Вызывается после завершения каждой подзадачи.
    
    Args:
        task_id: ID задачи
        force_check: Принудительная проверка (для fallback, игнорирует debounce)
    
    Returns:
        bool: True если был выполнен переход на следующий этап, False иначе
    """
    try:
        workflow = task_manager.get_task(task_id)
        if not workflow:
            logger.warning(f"[{task_id}] Workflow не найден в auto_continue_workflow")
            return False
        
        # Проверяем, включен ли auto_mode
        if not workflow.artifacts.get('auto_mode', False):
            return False
        
        # Защита от повторных вызовов (debounce) - предотвращает race conditions
        # Но не блокируем если предыдущий этап только что завершился
        if not force_check:
            last_check = workflow.artifacts.get('_last_auto_continue', 0)
            time_since_last = time.time() - last_check
            if time_since_last < 1:  # Минимум 1 секунда между проверками (уменьшено для быстрого перехода)
                logger.debug(f"[{task_id}] Debounce: прошло только {time_since_last:.2f} сек с последней проверки")
                return False
        
        # Обновляем время последней проверки
        workflow.artifacts['_last_auto_continue'] = time.time()
        task_manager.update_workflow_artifacts(task_id, {'_last_auto_continue': workflow.artifacts['_last_auto_continue']})
        
        # Защита от параллельных вызовов
        if workflow.artifacts.get('_auto_continue_processing', False):
            logger.debug(f"[{task_id}] auto_continue_workflow уже выполняется, пропускаем")
            return False
        
        workflow.artifacts['_auto_continue_processing'] = True
        task_manager.update_workflow_artifacts(task_id, {'_auto_continue_processing': True})
        
        try:
            sub_tasks = workflow.sub_tasks
            
            # Colab автоматизация отключена - удален код автоматического запуска
            initial_processing = sub_tasks.get('initial_processing')
            transcription = sub_tasks.get('transcription')
            ai_generation = sub_tasks.get('ai_clip_generation')
            
            # Этап 1: Транскрипция завершена → запускаем AI генерацию
            if (initial_processing and initial_processing.status == TaskStatus.COMPLETED and
                transcription and transcription.status == TaskStatus.COMPLETED and
                not ai_generation):
                # Запускаем AI генерацию
                system_prompt_id = workflow.artifacts.get('system_prompt_id')
                user_prompt_id = workflow.artifacts.get('user_prompt_id')
                
                if not system_prompt_id or not user_prompt_id:
                    logger.warning(f"[{task_id}] Не указаны промпты для AI генерации (system: {system_prompt_id}, user: {user_prompt_id})")
                    return False
                
                # Валидация: проверяем наличие транскрипции
                transcription_path = workflow.artifacts.get('transcription_simple_path')
                if not transcription_path or not Path(transcription_path).exists():
                    logger.error(f"[{task_id}] Файл транскрипции не найден: {transcription_path}")
                    return False
                
                logger.info(f"[{task_id}] Auto-continue: запуск AI генерации (system: {system_prompt_id[:8]}..., user: {user_prompt_id[:8]}...)")
                try:
                    # Вызываем логику генерации AI клипов напрямую
                    _generate_ai_clips_direct(task_id, system_prompt_id, user_prompt_id)
                    logger.info(f"[{task_id}] AI генерация завершена, переходим к следующему этапу")
                    # После успешной генерации AI, автоматически запускаем нарезку
                    time.sleep(1)  # Небольшая задержка для сохранения состояния
                    return auto_continue_workflow(task_id, force_check=True)
                except Exception as e:
                    logger.error(f"[{task_id}] Ошибка при автоматическом запуске AI генерации: {e}", exc_info=True)
                    return False
            
            # Этап 2: AI генерация завершена → запускаем нарезку
            if (ai_generation and ai_generation.status == TaskStatus.COMPLETED):
                # Проверяем, есть ли уже запущенная или завершенная нарезка
                clipping_tasks = [name for name in sub_tasks.keys() if name.startswith('clipping_')]
                if clipping_tasks:
                    # Если нарезка уже запущена или завершена, пропускаем этап 2, но продолжаем проверку этапа 3
                    clipping_status = sub_tasks[clipping_tasks[0]].status
                    if clipping_status == TaskStatus.COMPLETED:
                        logger.debug(f"[{task_id}] Нарезка уже завершена: {clipping_tasks[0]}, переходим к проверке этапа 3")
                        # Продолжаем выполнение, чтобы проверить этап 3
                    else:
                        logger.debug(f"[{task_id}] Нарезка уже запущена: {clipping_tasks[0]}, статус: {clipping_status.value}, пропускаем этап 2")
                        # Если нарезка еще выполняется, не запускаем новую, но проверяем этап 3
                        # Продолжаем выполнение без запуска нарезки
                else:
                    # Нарезка еще не запущена - запускаем ее
                    logger.info(f"[{task_id}] Auto-continue: запуск нарезки клипов")
                    try:
                        # Находим последний созданный файл AI нарезки
                        ai_clips_files = workflow.artifacts.get('ai_clips_files', [])
                        if not ai_clips_files:
                            logger.warning(f"[{task_id}] Нет файлов AI нарезки для обработки")
                            return False
                        
                        file_info = ai_clips_files[0]  # Берем последний созданный
                        file_path = Path(file_info['path'])
                        
                        # Валидация: проверяем существование файла
                        if not file_path.exists():
                            logger.error(f"[{task_id}] Файл AI нарезки не найден: {file_path}")
                            return False
                        
                        # Валидация: проверяем формат файла
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                clips_data = json.load(f)
                        except json.JSONDecodeError as e:
                            logger.error(f"[{task_id}] Ошибка парсинга JSON файла AI нарезки: {e}")
                            return False
                        except Exception as e:
                            logger.error(f"[{task_id}] Ошибка чтения файла AI нарезки: {e}")
                            return False
                        
                        # Преобразуем формат для VideoClipper
                        clips_for_clipper = []
                        if isinstance(clips_data, list):
                            for clip in clips_data:
                                start = clip.get('start_time', clip.get('start'))
                                end = clip.get('end_time', clip.get('end'))
                                if not start or not end:
                                    logger.warning(f"[{task_id}] Пропущен клип без временных меток: {clip}")
                                    continue
                                clips_for_clipper.append({
                                    'start': start,
                                    'end': end,
                                    'title': clip.get('title', ''),
                                    'caption': clip.get('summary', clip.get('full_quote', '')),
                                    'type': 'ai_clip'
                                })
                        elif isinstance(clips_data, dict) and 'clips' in clips_data:
                            for clip in clips_data['clips']:
                                start = clip.get('start_time', clip.get('start'))
                                end = clip.get('end_time', clip.get('end'))
                                if not start or not end:
                                    logger.warning(f"[{task_id}] Пропущен клип без временных меток: {clip}")
                                    continue
                                clips_for_clipper.append({
                                    'start': start,
                                    'end': end,
                                    'title': clip.get('title', ''),
                                    'caption': clip.get('summary', clip.get('full_quote', '')),
                                    'type': 'ai_clip'
                                })
                        
                        if not clips_for_clipper:
                            logger.warning(f"[{task_id}] Не найдено клипов для нарезки в файле {file_path}")
                            return False
                        
                        logger.info(f"[{task_id}] Найдено {len(clips_for_clipper)} клипов для нарезки")
                        
                        # Валидация: проверяем наличие видео файла
                        video_path = workflow.artifacts.get('video_path')
                        if not video_path:
                            logger.error(f"[{task_id}] Путь к видео не найден в artifacts")
                            return False
                        
                        if not Path(video_path).exists():
                            logger.error(f"[{task_id}] Видео файл не найден: {video_path}")
                            return False
                        
                        unique_subtask_name = generate_subtask_name(file_info, 'clipping')
                        
                        # Обновляем file_info.sub_tasks
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
                        
                        # Сохраняем обновленный file_info
                        file_index = 0
                        if workflow.artifacts.get('ai_clips_files'):
                            workflow.artifacts['ai_clips_files'][file_index] = file_info
                            task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})
                        
                        logger.info(f"[{task_id}] Запуск нарезки {len(clips_for_clipper)} клипов из видео {Path(video_path).name}")
                        start_clipping_task(
                            workflow_id=task_id,
                            video_path=video_path,
                            clips_data=clips_for_clipper,
                            sub_task_name=unique_subtask_name,
                            file_info=file_info,
                            file_index=file_index
                        )
                        # После запуска нарезки, проверяем этап 3 (на случай если нарезка уже завершена)
                        # Но сначала обновляем workflow чтобы получить актуальное состояние
                        time.sleep(0.5)
                        workflow = task_manager.get_task(task_id)
                        if workflow:
                            sub_tasks = workflow.sub_tasks
                            # Продолжаем проверку этапа 3
                    except Exception as e:
                        logger.error(f"[{task_id}] Ошибка при автоматическом запуске нарезки: {e}", exc_info=True)
                        # Даже при ошибке продолжаем проверку этапа 3
                        pass
            
            # Этап 3: Нарезка завершена → запускаем создание Shorts
            # ВАЖНО: Этот этап проверяется независимо от этапа 2
            # Проверяем независимо от этапа 2 (может быть вызван отдельно после завершения нарезки)
            clipping_tasks_list = [(name, st) for name, st in sub_tasks.items() if name.startswith('clipping_')]
            if clipping_tasks_list:
                clipping_name, clipping_task = clipping_tasks_list[0]
                logger.debug(f"[{task_id}] Проверка этапа 3: нарезка '{clipping_name}' имеет статус {clipping_task.status.value}")
                if clipping_task.status == TaskStatus.COMPLETED:
                    # Проверяем, есть ли уже запущенное создание Shorts
                    shorts_tasks = [name for name in sub_tasks.keys() if name.startswith('shorts_creation_')]
                    if shorts_tasks:
                        logger.debug(f"[{task_id}] Создание Shorts уже запущено: {shorts_tasks[0]}")
                        return False
                    
                    # Валидация: проверяем наличие outputs
                    if not clipping_task.outputs:
                        logger.warning(f"[{task_id}] Подзадача нарезки завершена, но outputs пуст")
                        return False
                    
                    clips_paths = clipping_task.outputs.get('clips', [])
                    if not clips_paths:
                        logger.warning(f"[{task_id}] Нет клипов для создания Shorts в outputs подзадачи нарезки")
                        return False
                    
                    # Валидация: проверяем существование файлов клипов
                    existing_clips = [p for p in clips_paths if Path(p).exists()]
                    if not existing_clips:
                        logger.error(f"[{task_id}] Ни один клип не найден по указанным путям. Ожидалось {len(clips_paths)} клипов")
                        return False
                    
                    if len(existing_clips) < len(clips_paths):
                        missing = len(clips_paths) - len(existing_clips)
                        logger.warning(f"[{task_id}] Найдено только {len(existing_clips)} из {len(clips_paths)} клипов. Пропущено: {missing}")
                        # Продолжаем с существующими клипами
                    
                    logger.info(f"[{task_id}] Auto-continue: запуск создания Shorts для {len(existing_clips)} клипов")
                    try:
                        # Получаем настройки Shorts из artifacts
                        shorts_settings = workflow.artifacts.get('shorts_settings', {})
                        
                        # Находим file_info для привязки
                        file_info = None
                        file_index = None
                        ai_clips_files = workflow.artifacts.get('ai_clips_files', [])
                        if ai_clips_files:
                            # Пытаемся найти file_info по имени подзадачи clipping
                            parts = clipping_name.split('_')
                            if len(parts) >= 4:
                                system_prompt_id = parts[1]
                                user_prompt_id = parts[2]
                                for idx, fi in enumerate(ai_clips_files):
                                    if (fi.get('system_prompt_id') == system_prompt_id and 
                                        fi.get('user_prompt_id') == user_prompt_id):
                                        file_info = fi
                                        file_index = idx
                                        break
                        
                        if not file_info and ai_clips_files:
                            file_info = ai_clips_files[0]
                            file_index = 0
                        
                        unique_subtask_name = "shorts_creation"
                        if file_info:
                            unique_subtask_name = generate_subtask_name(file_info, 'shorts_creation')
                            
                            # Обновляем file_info.sub_tasks
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
                            
                            # Сохраняем обновленный file_info
                            if file_index is not None and workflow.artifacts.get('ai_clips_files'):
                                workflow.artifacts['ai_clips_files'][file_index] = file_info
                                task_manager.update_workflow_artifacts(task_id, {'ai_clips_files': workflow.artifacts['ai_clips_files']})
                        
                        start_shorts_creation_task(
                            workflow_id=task_id,
                            clips_paths=existing_clips,  # Используем только существующие клипы
                            sub_task_name=unique_subtask_name,
                            file_info=file_info,
                            file_index=file_index,
                            **shorts_settings
                        )
                        logger.info(f"[{task_id}] Задача создания Shorts запущена успешно")
                        return True
                    except Exception as e:
                        logger.error(f"[{task_id}] Ошибка при автоматическом запуске создания Shorts: {e}", exc_info=True)
                        return False
            
            # Если ни один этап не был обработан
            return False
        
        finally:
            # Снимаем флаг обработки
            workflow.artifacts['_auto_continue_processing'] = False
            task_manager.update_workflow_artifacts(task_id, {'_auto_continue_processing': False})
    
    except Exception as e:
        logger.exception(f"[{task_id}] Критическая ошибка в auto_continue_workflow: {e}")
        # Снимаем флаг обработки даже при ошибке
        try:
            workflow = task_manager.get_task(task_id)
            if workflow:
                workflow.artifacts['_auto_continue_processing'] = False
                task_manager.update_workflow_artifacts(task_id, {'_auto_continue_processing': False})
        except:
            pass
        return False


@simple_api_bp.route('/create', methods=['POST'])
def create_video():
    """
    Создает задачу на обработку видео и автоматически запускает полный workflow.
    
    Принимает все параметры в одном запросе и автоматически выполняет:
    1. Скачивание видео
    2. Ожидание транскрипции
    3. AI генерацию клипов
    4. Нарезку клипов
    5. Создание Shorts
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Данные не предоставлены'}), 400
        
        # Валидация обязательных полей
        url = data.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'URL не указан'}), 400
        
        system_prompt_id = data.get('system_prompt_id')
        user_prompt_id = data.get('user_prompt_id')
        if not system_prompt_id or not user_prompt_id:
            return jsonify({'success': False, 'error': 'system_prompt_id и user_prompt_id обязательны'}), 400
        
        # Проверяем существование промптов
        def _read_prompts(file_path: Path) -> list:
            if not file_path.exists():
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        system_prompts = _read_prompts(Config.SYSTEM_PROMPTS_FILE)
        user_prompts = _read_prompts(Config.USER_PROMPTS_FILE)
        
        if not any(p['id'] == system_prompt_id for p in system_prompts):
            return jsonify({'success': False, 'error': f'Системный промпт {system_prompt_id} не найден'}), 400
        
        if not any(p['id'] == user_prompt_id for p in user_prompts):
            return jsonify({'success': False, 'error': f'Пользовательский промпт {user_prompt_id} не найден'}), 400
        
        # Собираем параметры
        import uuid
        task_id = str(uuid.uuid4())
        
        season = data.get('season')
        episode = data.get('episode')
        translator_id = data.get('translator_id')
        
        workflow_name = f"Simple API Workflow for {url}"
        if season and episode:
            workflow_name += f" S{season}E{episode}"
        
        # Сохраняем настройки Shorts
        shorts_settings = data.get('shorts_settings', {})
        
        # Получаем настройки прокси: сначала из запроса, если не указаны - из файла настроек
        proxy = data.get('proxy')
        proxy_type = data.get('proxy_type', 'socks5')
        
        if not proxy:
            # Загружаем настройки прокси из файла
            from web.routes.settings_api import load_settings
            settings = load_settings()
            if settings.get('proxy_enabled') and settings.get('proxy'):
                proxy = settings['proxy']
                proxy_type = settings.get('proxy_type', 'socks5')
                logger.info(f"[{task_id}] Используются настройки прокси из файла настроек")
        
        # Создаем workflow с auto_mode
        artifacts = {
            'url': url,
            'proxy': proxy or '',
            'proxy_type': proxy_type,
            'season': int(season) if season else None,
            'episode': int(episode) if episode else None,
            'translator_id': int(translator_id) if translator_id else None,
            'quality': data.get('quality', Config.DEFAULT_QUALITY),
            'system_prompt_id': system_prompt_id,
            'user_prompt_id': user_prompt_id,
            'shorts_settings': shorts_settings,
            'auto_mode': True  # Включаем автоматический режим
        }
        
        workflow = task_manager.create_workflow(
            task_id=task_id,
            name=workflow_name,
            artifacts=artifacts
        )
        
        # Запускаем начальную обработку
        start_initial_processing_task(
            task_id=task_id,
            url=url,
            proxy=proxy,
            proxy_type=proxy_type,
            season=int(season) if season else None,
            episode=int(episode) if episode else None,
            translator_id=int(translator_id) if translator_id else None,
            quality=data.get('quality', Config.DEFAULT_QUALITY)
        )
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'processing',
            'message': 'Задача создана, начинается скачивание видео'
        }), 201
        
    except Exception as e:
        logger.exception("Ошибка при создании задачи через Simple API")
        return jsonify({'success': False, 'error': str(e)}), 500


@simple_api_bp.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """
    Возвращает упрощенный статус обработки видео.
    
    Включает:
    - Текущий этап (downloading, waiting_transcription, transcribing, ai_generation, clipping, shorts_creation, completed, failed)
    - Общий прогресс (0-100%)
    - Понятное сообщение
    - Список готовых видео (если completed)
    """
    try:
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404
        
        # Fallback: пытаемся автоматически продолжить workflow при запросе статуса
        # Это гарантирует запуск следующего этапа даже если callback не сработал
        if workflow.artifacts.get('auto_mode', False):
            try:
                auto_continue_workflow(task_id, force_check=True)
            except Exception as e:
                logger.warning(f"[{task_id}] Ошибка при fallback auto-continue: {e}")
        
        # Получаем упрощенный статус (обновляем workflow после возможного auto-continue)
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404
        
        status = get_simple_status(workflow)
        return jsonify(status)
        
    except Exception as e:
        logger.exception(f"Ошибка при получении статуса задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@simple_api_bp.route('/<task_id>/download', methods=['GET'])
def get_download_links(task_id):
    """
    Возвращает список всех готовых видео с download URLs.
    
    Используется когда статус = completed.
    """
    try:
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404
        
        # Собираем все готовые видео
        videos = collect_ready_videos(workflow)
        
        if not videos:
            return jsonify({
                'success': False,
                'error': 'Видео еще не готовы. Проверьте статус через /status/{task_id}'
            }), 400
        
        # Формируем полные URLs
        base_url = request.host_url.rstrip('/')
        for video in videos:
            if video['url'].startswith('/'):
                video['download_url'] = f"{base_url}{video['url']}"
            else:
                video['download_url'] = video['url']
        
        # Метаданные
        metadata = {
            'source_url': workflow.artifacts.get('url', ''),
            'season': workflow.artifacts.get('season'),
            'episode': workflow.artifacts.get('episode'),
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(workflow.created_at)),
            'total_videos': len(videos),
            'total_size_mb': round(sum(v['size_mb'] for v in videos), 2)
        }
        
        return jsonify({
            'success': True,
            'status': 'completed',
            'videos': videos,
            'metadata': metadata
        })
        
    except Exception as e:
        logger.exception(f"Ошибка при получении ссылок на скачивание для задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500

