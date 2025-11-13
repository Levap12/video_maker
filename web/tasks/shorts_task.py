#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для создания YouTube Shorts
"""

import sys
import threading
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config

# Импорт socketio через lazy import
def get_socketio():
    """Получает socketio экземпляр"""
    from web.app import socketio
    return socketio

try:
    from scripts.shorts_creator import ShortsCreator
    SHORTS_CREATOR_AVAILABLE = True
except ImportError:
    SHORTS_CREATOR_AVAILABLE = False


def emit_shorts_update(task_id, progress, message, status=None, error=None, result=None):
    """Отправляет обновление задачи создания Shorts через WebSocket"""
    socketio = get_socketio()
    socketio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress,
        'message': message,
        'status': status.value if status else None,
        'error': error,
        'result': result
    })


def start_create_shorts_task(shorts_task_id: str, clip_paths: list,
                            banner_path: str = None,
                            watermark_text: str = None,
                            watermark_color: str = 'gray',
                            watermark_font_size: int = 72,
                            watermark_bottom_offset: int = 180,
                            banner_offset: int = 100,
                            height_scale: float = 2.0):
    """
    Запускает фоновую задачу создания Shorts
    
    Args:
        shorts_task_id: ID задачи для Shorts
        clip_paths: Список путей к клипам
        banner_path: Путь к баннеру (видео)
        watermark_text: Текст водяного знака
        watermark_color: Цвет водяного знака
        watermark_font_size: Размер шрифта
        watermark_bottom_offset: Отступ снизу
        banner_offset: Отступ сверху для баннера
        height_scale: Коэффициент увеличения высоты
    """
    
    def run_task():
        try:
            task_manager.update_task(shorts_task_id, status=TaskStatus.RUNNING,
                                   progress=0, message="Начало создания Shorts")
            emit_shorts_update(shorts_task_id, 0, "Начало создания Shorts", TaskStatus.RUNNING)
            
            if not SHORTS_CREATOR_AVAILABLE:
                error_msg = "ShortsCreator недоступен"
                task_manager.update_task(shorts_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=0)
                emit_shorts_update(shorts_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
                return
            
            # Проверяем клипы
            valid_clips = []
            for clip_path in clip_paths:
                clip_file = Path(clip_path)
                if clip_file.exists():
                    valid_clips.append(clip_file)
                else:
                    print(f"Предупреждение: клип не найден: {clip_path}")
            
            if not valid_clips:
                error_msg = "Не найдено валидных клипов"
                task_manager.update_task(shorts_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=0)
                emit_shorts_update(shorts_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
                return
            
            # Создаем ShortsCreator
            creator = ShortsCreator(
                input_dir=str(Config.CLIPS_DIR),
                output_dir=str(Config.SHORTS_OUTPUT_DIR),
                height_scale=height_scale,
                banner_path=banner_path,
                banner_offset=banner_offset,
                watermark_text=watermark_text,
                watermark_font_size=watermark_font_size,
                watermark_bottom_offset=watermark_bottom_offset,
                watermark_color=watermark_color
            )
            
            successful_shorts = []
            failed_shorts = []
            total = len(valid_clips)
            
            for i, clip_file in enumerate(valid_clips):
                try:
                    progress = int((i / total) * 90)
                    emit_shorts_update(shorts_task_id, progress,
                                    f"Обработка клипа {i+1}/{total}: {clip_file.name}")
                    
                    # Создаем Shorts
                    output_path = creator.process_single_file(clip_file)
                    
                    if output_path:
                        successful_shorts.append({
                            'path': str(output_path),
                            'filename': output_path.name,
                            'source_clip': clip_file.name
                        })
                    else:
                        failed_shorts.append(clip_file.name)
                        
                except Exception as e:
                    print(f"Ошибка создания Shorts из {clip_file.name}: {e}")
                    failed_shorts.append(clip_file.name)
            
            # Сохраняем результаты
            task = task_manager.get_task(shorts_task_id)
            if not task.result:
                task.result = {}
            
            task.result['shorts'] = successful_shorts
            task.result['failed_shorts'] = failed_shorts
            task.result['total_shorts'] = len(successful_shorts)
            
            if successful_shorts:
                task_manager.update_task(shorts_task_id, status=TaskStatus.COMPLETED,
                                       progress=100,
                                       message=f"Создано {len(successful_shorts)} Shorts")
                emit_shorts_update(shorts_task_id, 100,
                                f"Создано {len(successful_shorts)} Shorts",
                                TaskStatus.COMPLETED,
                                result={'shorts': successful_shorts})
            else:
                error_msg = "Не удалось создать ни одного Shorts"
                task_manager.update_task(shorts_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=100)
                emit_shorts_update(shorts_task_id, 100, error_msg, TaskStatus.FAILED, error=error_msg)
                
        except Exception as e:
            error_msg = f"Ошибка создания Shorts: {str(e)}"
            task_manager.update_task(shorts_task_id, status=TaskStatus.FAILED, error=error_msg)
            emit_shorts_update(shorts_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
    
    # Сохраняем поток в задаче
    task = task_manager.create_task(shorts_task_id)
    task.thread = thread
