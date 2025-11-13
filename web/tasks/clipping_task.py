#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для нарезки клипов из видео.
"""

import sys
import threading
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config
from scripts.video_clipper import VideoClipper

def start_clipping_task(workflow_id: str, video_path: str, clips_data: list, sub_task_name: str = "clipping", 
                       file_info: dict = None, file_index: int = None):
    """
    Запускает фоновую задачу нарезки клипов как подзадачу workflow.

    Args:
        workflow_id: ID основного рабочего процесса.
        video_path: Путь к видео файлу.
        clips_data: Список словарей с данными для нарезки (start, end, title, etc.).
        sub_task_name: Имя подзадачи.
        file_info: Информация о файле AI нарезки (для синхронизации статусов).
        file_index: Индекс файла в artifacts.ai_clips_files (для синхронизации статусов).
    """
    
    def run_task():
        try:
            task_manager.update_sub_task(
                task_id=workflow_id,
                sub_task_name=sub_task_name,
                sub_task_type='clipping',
                status=TaskStatus.RUNNING,
                progress=0,
                message="Начало нарезки клипов"
            )
            
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
            
            clipper = VideoClipper(output_dir=str(Config.CLIPS_DIR))
            
            successful_clips = []
            total_clips = len(clips_data)
            for i, clip_info in enumerate(clips_data):
                progress = int(((i + 1) / total_clips) * 100)
                task_manager.update_sub_task(
                    task_id=workflow_id,
                    sub_task_name=sub_task_name,
                    sub_task_type='clipping',
                    status=TaskStatus.RUNNING,
                    progress=progress,
                    message=f"Нарезка клипа {i+1}/{total_clips}"
                )
                
                # В video_clipper.py create_clip ожидает start_time, end_time, title, caption, clip_type, index
                clip_path = clipper.create_clip(
                    video_path=str(video_file),
                    start_time=clip_info['start'],
                    end_time=clip_info['end'],
                    title=clip_info.get('title', f'moment_{i+1}'),
                    caption=clip_info.get('caption', ''),
                    clip_type=clip_info.get('type', 'clip'),
                    index=i
                )
                if clip_path:
                    successful_clips.append(str(clip_path))
            
            if not successful_clips:
                raise ValueError("Не удалось создать ни одного клипа")

            task_manager.update_sub_task(
                task_id=workflow_id,
                sub_task_name=sub_task_name,
                sub_task_type='clipping',
                status=TaskStatus.COMPLETED,
                progress=100,
                message=f"Нарезано {len(successful_clips)} клипов",
                outputs={'clips': successful_clips}
            )
            
            # Проверяем auto_mode и пытаемся продолжить workflow
            workflow = task_manager.get_task(workflow_id)
            if workflow and workflow.artifacts.get('auto_mode', False):
                try:
                    from web.routes.simple_api import auto_continue_workflow
                    # Используем force_check=True чтобы обойти debounce сразу после завершения нарезки
                    result = auto_continue_workflow(workflow_id, force_check=True)
                    if result:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"[{workflow_id}] Автоматически запущено создание Shorts после завершения нарезки")
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug(f"[{workflow_id}] auto_continue_workflow вернул False (возможно, Shorts уже запущены или нет данных)")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"[{workflow_id}] Не удалось автоматически продолжить workflow после clipping: {e}", exc_info=True)
            
        except Exception as e:
            task_manager.update_sub_task(
                task_id=workflow_id,
                sub_task_name=sub_task_name,
                sub_task_type='clipping',
                status=TaskStatus.FAILED,
                error=str(e)
            )

    # Запускаем в отдельном потоке
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()