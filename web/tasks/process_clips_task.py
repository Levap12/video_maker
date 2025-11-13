#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для создания клипов из моментов
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
    from scripts.video_clipper import VideoClipper
    VIDEO_CLIPPER_AVAILABLE = True
except ImportError:
    VIDEO_CLIPPER_AVAILABLE = False


def emit_clips_update(task_id, progress, message, status=None, error=None, result=None):
    """Отправляет обновление задачи создания клипов через WebSocket"""
    socketio = get_socketio()
    socketio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress,
        'message': message,
        'status': status.value if status else None,
        'error': error,
        'result': result
    })


def start_process_clips_task(clips_task_id: str, video_path: str, moments: list):
    """
    Запускает фоновую задачу создания клипов
    
    Args:
        clips_task_id: ID задачи для клипов
        video_path: Путь к видео файлу
        moments: Список моментов для нарезки
    """
    
    def run_task():
        try:
            task_manager.update_task(clips_task_id, status=TaskStatus.RUNNING,
                                   progress=0, message="Начало создания клипов")
            emit_clips_update(clips_task_id, 0, "Начало создания клипов", TaskStatus.RUNNING)
            
            if not VIDEO_CLIPPER_AVAILABLE:
                error_msg = "VideoClipper недоступен"
                task_manager.update_task(clips_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=0)
                emit_clips_update(clips_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
                return
            
            video_file = Path(video_path)
            if not video_file.exists():
                error_msg = f"Видео файл не найден: {video_path}"
                task_manager.update_task(clips_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=0)
                emit_clips_update(clips_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
                return
            
            clipper = VideoClipper(output_dir=str(Config.CLIPS_DIR))
            
            successful_clips = []
            failed_clips = []
            
            total = len(moments)
            
            for i, moment in enumerate(moments):
                try:
                    start_time = moment.get('start_time')
                    end_time = moment.get('end_time')
                    title = moment.get('description', moment.get('text', f'Момент {i+1}'))[:50]
                    text = moment.get('text', '')
                    
                    progress = int((i / total) * 90)
                    emit_clips_update(clips_task_id, progress,
                                    f"Создание клипа {i+1}/{total}: {title}")
                    
                    # Создаем клип
                    clip_path = clipper.create_clip(
                        video_path=video_file,
                        start_time=start_time,
                        end_time=end_time,
                        title=title,
                        caption=text,
                        clip_type='extracted_moment',
                        index=i+1
                    )
                    
                    if clip_path:
                        successful_clips.append({
                            'path': str(clip_path),
                            'title': title,
                            'start_time': start_time,
                            'end_time': end_time
                        })
                    else:
                        failed_clips.append(i+1)
                        
                except Exception as e:
                    print(f"Ошибка создания клипа {i+1}: {e}")
                    failed_clips.append(i+1)
            
            # Сохраняем результаты
            task = task_manager.get_task(clips_task_id)
            if not task.result:
                task.result = {}
            
            task.result['clips'] = successful_clips
            task.result['failed_clips'] = failed_clips
            task.result['total_clips'] = len(successful_clips)
            
            if successful_clips:
                task_manager.update_task(clips_task_id, status=TaskStatus.COMPLETED,
                                       progress=100,
                                       message=f"Создано {len(successful_clips)} клипов")
                emit_clips_update(clips_task_id, 100,
                                f"Создано {len(successful_clips)} клипов",
                                TaskStatus.COMPLETED,
                                result={'clips': successful_clips})
            else:
                error_msg = "Не удалось создать ни одного клипа"
                task_manager.update_task(clips_task_id, status=TaskStatus.FAILED,
                                       error=error_msg, progress=100)
                emit_clips_update(clips_task_id, 100, error_msg, TaskStatus.FAILED, error=error_msg)
                
        except Exception as e:
            error_msg = f"Ошибка создания клипов: {str(e)}"
            task_manager.update_task(clips_task_id, status=TaskStatus.FAILED, error=error_msg)
            emit_clips_update(clips_task_id, 0, error_msg, TaskStatus.FAILED, error=error_msg)
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
    
    # Сохраняем поток в задаче
    task = task_manager.create_task(clips_task_id)
    task.thread = thread
