#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для создания YouTube Shorts из клипов.
"""

import sys
import threading
from pathlib import Path

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config
from scripts.shorts_creator import ShortsCreator

def start_shorts_creation_task(workflow_id: str, clips_paths: list, sub_task_name: str = "shorts_creation", file_info: dict = None, file_index: int = None, **kwargs):
    """
    Запускает фоновую задачу создания Shorts как подзадачу.
    
    Args:
        workflow_id: ID workflow задачи
        clips_paths: Список путей к клипам для обработки
        sub_task_name: Уникальное имя подзадачи
        file_info: Метаданные файла AI нарезки (для синхронизации статуса)
        file_index: Индекс файла в artifacts.ai_clips_files
        **kwargs: Дополнительные параметры для ShortsCreator
    """
    
    def run_task():
        try:
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='shorts_creation',
                status=TaskStatus.RUNNING, progress=0, message="Начало создания Shorts"
            )
            
            creator = ShortsCreator(
                input_dir=str(Config.CLIPS_DIR),
                output_dir=str(Config.SHORTS_OUTPUT_DIR),
                **kwargs
            )
            
            # Получаем метаданные клипов из подзадачи clipping
            workflow = task_manager.get_task(workflow_id)
            clips_metadata = {}  # Маппинг: путь к клипу → метаданные
            
            if workflow:
                # Ищем подзадачу clipping, которая содержит эти клипы
                for sub_task_name, sub_task in workflow.sub_tasks.items():
                    if sub_task_name.startswith('clipping_') and sub_task.outputs:
                        sub_task_clips = sub_task.outputs.get('clips', [])
                        # Проверяем, что это та же подзадача (содержит те же клипы)
                        if set(sub_task_clips) == set(clips_paths):
                            clips_metadata = sub_task.outputs.get('clips_metadata', {})
                            break
            
            successful_shorts, failed_clips = [], []
            shorts_metadata = {}  # Маппинг: путь к Shorts → метаданные
            total_clips = len(clips_paths)

            if not total_clips:
                raise ValueError("Список клипов для обработки пуст.")

            for i, clip_path_str in enumerate(clips_paths):
                progress = int(((i + 1) / total_clips) * 100)
                clip_path = Path(clip_path_str)
                task_manager.update_sub_task(
                    task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='shorts_creation',
                    status=TaskStatus.RUNNING, progress=progress, message=f"Обработка {i+1}/{total_clips}: {clip_path.name}"
                )
                
                try:
                    if not clip_path.exists():
                        raise FileNotFoundError(f"Клип не найден: {clip_path}")

                    output_filename = f"shorts_{clip_path.stem}.mp4"
                    output_path_target = creator.output_dir / output_filename
                    
                    output_path = creator.convert_to_shorts_format(clip_path, output_path_target)
                    
                    if output_path and output_path.exists():
                        output_path_str = str(output_path)
                        successful_shorts.append(output_path_str)
                        
                        # Сохраняем метаданные для этого Shorts (по пути исходного клипа)
                        if clip_path_str in clips_metadata:
                            shorts_metadata[output_path_str] = clips_metadata[clip_path_str]
                        else:
                            # Если метаданных нет, создаем минимальный объект
                            shorts_metadata[output_path_str] = {
                                'start_time': '',
                                'end_time': '',
                                'title': clip_path.stem,
                                'summary': '',
                                'full_quote': ''
                            }
                    else:
                        failed_clips.append(clip_path_str)
                except Exception as clip_error:
                    failed_clips.append(clip_path_str)
                    print(f"Ошибка при обработке клипа {clip_path_str}: {clip_error}") # Логируем ошибку

            outputs = {
                'shorts': successful_shorts,
                'failed_shorts': failed_clips,
                'shorts_metadata': shorts_metadata
            }
            if not successful_shorts:
                raise ValueError(f"Не удалось создать ни одного Shorts из {total_clips} клипов.")

            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='shorts_creation',
                status=TaskStatus.COMPLETED, progress=100, 
                message=f"Создано {len(successful_shorts)} из {total_clips} Shorts",
                outputs=outputs
            )

        except Exception as e:
            task_manager.update_sub_task(
                task_id=workflow_id, sub_task_name=sub_task_name, sub_task_type='shorts_creation',
                status=TaskStatus.FAILED, error=str(e)
            )

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()