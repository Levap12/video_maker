#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для создания видеокомпиляции из моментов.
"""

import sys
import threading
from pathlib import Path

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config
from scripts.video_processor import VideoProcessor

def start_compilation_task(workflow_id: str, video_path: str, moments: list, sub_task_name: str = "compilation",
                          file_info: dict = None, file_index: int = None):
    """
    Запускает фоновую задачу создания видеокомпиляции как подзадачу.
    
    Args:
        workflow_id: ID основного рабочего процесса.
        video_path: Путь к видео файлу.
        moments: Список моментов для компиляции.
        sub_task_name: Имя подзадачи.
        file_info: Информация о файле AI нарезки (для синхронизации статусов).
        file_index: Индекс файла в artifacts.ai_clips_files (для синхронизации статусов).
    """
    
    def run_task():
        processor = None
        try:
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='compilation',
                status=TaskStatus.RUNNING, progress=0, message="Начало создания компиляции"
            )
            
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
            
            processor = VideoProcessor(source_dir=str(video_file.parent), output_dir=str(Config.OUTPUT_DIR))
            
            # Этап 1: Нарезка временных клипов
            clip_paths = []
            total_moments = len(moments)
            for i, moment in enumerate(moments):
                progress = int((i / total_moments) * 50)  # 0-50% на нарезку
                task_manager.update_sub_task(
                    task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='compilation',
                    status=TaskStatus.RUNNING, progress=progress, message=f"Нарезка клипа {i+1}/{total_moments}"
                )
                
                clip_path = processor.create_clip_from_source(
                    source_video=video_file,
                    start_time=moment['start'], # Ожидаем 'start' и 'end'
                    end_time=moment['end'],
                    title=moment.get('title', f'moment_{i+1}'),
                    index=i
                )
                if clip_path:
                    clip_paths.append(clip_path)
            
            if not clip_paths:
                raise ValueError("Не удалось создать ни одного клипа для компиляции")
            
            # Этап 2: Склейка клипов
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='compilation',
                status=TaskStatus.RUNNING, progress=50, message="Склейка клипов..."
            )
            output_filename = f"compilation_{workflow_id}.mp4"
            
            compilation_path = processor.join_clips(clip_paths, output_filename)
            
            if not compilation_path:
                raise RuntimeError("Ошибка при склейке клипов")
            
            # Этап 3: Завершение
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='compilation',
                status=TaskStatus.COMPLETED, progress=100, message="Компиляция успешно создана",
                outputs={'compilation_path': str(compilation_path)}
            )
            
        except Exception as e:
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='compilation',
                status=TaskStatus.FAILED, error=str(e)
            )
        finally:
            if processor:
                processor.cleanup_temp_files()

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()