#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер задач для отслеживания фоновых операций на основе иерархической структуры.
"""

import threading
import time
import os
import json
import atexit
from typing import Dict, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path

from web.config import Config

class TaskStatus(Enum):
    """Статусы задачи"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class SubTask:
    """Класс для подзадачи внутри основного рабочего процесса."""
    type: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = ""
    progress: float = 0.0
    updated_at: float = field(default_factory=time.time)
    outputs: Dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data

@dataclass
class WorkflowTask:
    """Основной класс задачи, представляющий собой рабочий процесс (workflow)."""
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = ""
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    artifacts: Dict = field(default_factory=dict)
    sub_tasks: Dict[str, SubTask] = field(default_factory=dict)
    thread: Optional[threading.Thread] = None

    def update_status(self, status: TaskStatus, message: str = None):
        self.status = status
        if message:
            self.message = message
        self.updated_at = time.time()

    def to_dict(self) -> Dict:
        """Конвертирует задачу в словарь для JSON."""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'error': self.error,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'artifacts': self.artifacts,
            'sub_tasks': {name: sub.to_dict() for name, sub in self.sub_tasks.items()}
        }

class TaskManager:
    """Менеджер задач - хранит и управляет иерархическими задачами."""
    
    def __init__(self, save_interval: int = 10):
        self._tasks: Dict[str, WorkflowTask] = {}
        self._lock = threading.Lock()
        self.state_file: Path = Config.TASK_STATE_FILE
        self._dirty = False

        self.load_tasks_from_disk()
        atexit.register(self.save_tasks_to_disk)

        self._stop_event = threading.Event()
        self._save_thread = threading.Thread(target=self._periodic_save, args=(save_interval,), daemon=True)
        self._save_thread.start()

    def _periodic_save(self, interval: int):
        """Периодически сохраняет задачи, если были изменения."""
        while not self._stop_event.is_set():
            time.sleep(interval)
            if self._dirty:
                self.save_tasks_to_disk()

    def save_tasks_to_disk(self):
        """Сохраняет все задачи в JSON файл."""
        # Проверяем dirty без блокировки для оптимизации
        if not self._dirty:
            return
        
        with self._lock:
            # Повторная проверка после получения блокировки
            if not self._dirty:
                return

            tasks_to_save = {tid: t.to_dict() for tid, t in self._tasks.items()}
            
            try:
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(tasks_to_save, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.state_file)
                self._dirty = False
                print(f"[TaskManager] Сохранено {len(tasks_to_save)} задач в {self.state_file}")
            except Exception as e:
                print(f"[TaskManager] Ошибка сохранения задач: {e}")
                import traceback
                traceback.print_exc()

    def load_tasks_from_disk(self):
        """Загружает задачи из JSON файла при старте."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                tasks_from_disk = json.load(f)
            
            with self._lock:
                for task_id, task_data in tasks_from_disk.items():
                    # Простая проверка на старый формат
                    if 'sub_tasks' not in task_data:
                        print(f"[TaskManager] Пропуск задачи {task_id} из-за старого формата.")
                        continue

                    if task_data.get('status') == TaskStatus.RUNNING.value:
                        task_data['status'] = TaskStatus.FAILED.value
                        task_data['error'] = "Процесс был прерван перезапуском сервера."

                    sub_tasks = {
                        name: SubTask(
                            type=sub_data['type'],
                            status=TaskStatus(sub_data['status']),
                            message=sub_data['message'],
                            progress=sub_data['progress'],
                            updated_at=sub_data['updated_at'],
                            outputs=sub_data['outputs'],
                            error=sub_data.get('error')
                        ) for name, sub_data in task_data.get('sub_tasks', {}).items()
                    }

                    self._tasks[task_id] = WorkflowTask(
                        task_id=task_data['task_id'],
                        name=task_data['name'],
                        status=TaskStatus(task_data['status']),
                        message=task_data['message'],
                        error=task_data.get('error'),
                        created_at=task_data['created_at'],
                        updated_at=task_data['updated_at'],
                        artifacts=task_data['artifacts'],
                        sub_tasks=sub_tasks
                    )
                
                # Не помечаем как dirty после загрузки - это не изменение
            print(f"[TaskManager] {len(self._tasks)} задач загружено из {self.state_file}")

        except (json.JSONDecodeError, TypeError) as e:
            print(f"[TaskManager] Ошибка декодирования JSON из {self.state_file}: {e}. Переименование в .bak")
            try:
                os.rename(self.state_file, self.state_file.with_suffix('.bak'))
            except OSError as rename_error:
                print(f"[TaskManager] Не удалось переименовать поврежденный файл: {rename_error}")
        except Exception as e:
            print(f"[TaskManager] Непредвиденная ошибка загрузки задач: {e}")

    def create_workflow(self, task_id: str, name: str, artifacts: Dict = None) -> WorkflowTask:
        """Создает новый рабочий процесс."""
        with self._lock:
            task = WorkflowTask(task_id=task_id, name=name, artifacts=artifacts or {})
            self._tasks[task_id] = task
            self._dirty = True
        
        # Сохраняем вне блока блокировки для безопасности
        self.save_tasks_to_disk()
        return task
    def get_task(self, task_id: str) -> Optional[WorkflowTask]:
        """Получает задачу по ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def update_sub_task(self, task_id: str, sub_task_name: str, sub_task_type: str, status: TaskStatus, 
                        message: str = None, progress: float = None, outputs: Dict = None, error: str = None):
        """Создает или обновляет подзадачу."""
        print(f"[TaskManager] update_sub_task вызван: task_id={task_id}, sub_task_name={sub_task_name}, status={status.value}")
        
        with self._lock:
            # Получаем workflow напрямую, без вызова get_task (чтобы избежать двойной блокировки)
            workflow = self._tasks.get(task_id)
            if not workflow:
                print(f"[TaskManager] Workflow с ID {task_id} не найден. Доступные задачи: {list(self._tasks.keys())}")
                return

            print(f"[TaskManager] Workflow найден: {workflow.task_id}, текущие подзадачи: {list(workflow.sub_tasks.keys())}")

            sub_task = workflow.sub_tasks.get(sub_task_name)
            is_new_subtask = sub_task is None
            if not sub_task:
                sub_task = SubTask(type=sub_task_type)
                workflow.sub_tasks[sub_task_name] = sub_task
                print(f"[TaskManager] Создана новая подзадача '{sub_task_name}' для workflow {task_id}")

            sub_task.status = status
            if message is not None:
                sub_task.message = message
            if progress is not None:
                sub_task.progress = progress
            if outputs is not None:
                # Обновляем, а не перезаписываем
                sub_task.outputs.update(outputs)
            if error is not None:
                sub_task.error = error
                sub_task.status = TaskStatus.FAILED
            
            sub_task.updated_at = time.time()
            workflow.updated_at = time.time() # Обновляем и родительскую задачу
            
            # Обновляем статус основного workflow на RUNNING, если подзадача запущена
            if status == TaskStatus.RUNNING and workflow.status == TaskStatus.PENDING:
                workflow.status = TaskStatus.RUNNING
                workflow.message = f"Выполняется подзадача: {sub_task_name}"
                print(f"[TaskManager] Статус workflow {task_id} изменен на RUNNING")
            
            self._dirty = True
            print(f"[TaskManager] Подзадача '{sub_task_name}' обновлена: status={status.value}, progress={progress}, message={message}")
        
        # Синхронизируем статус в artifacts (если это подзадача, связанная с файлом AI нарезки)
        try:
            self.sync_subtask_to_file_info(task_id, sub_task_name)
        except Exception as e:
            # Не критично, если синхронизация не удалась (например, для обычных подзадач)
            pass
        
        # Сохраняем на диск сразу после создания первой подзадачи или при критических обновлениях
        if is_new_subtask or status == TaskStatus.COMPLETED or status == TaskStatus.FAILED:
            print(f"[TaskManager] Сохранение подзадачи '{sub_task_name}' (новый: {is_new_subtask}, статус: {status.value})")
            try:
                self.save_tasks_to_disk()
                print(f"[TaskManager] Подзадача '{sub_task_name}' успешно сохранена")
            except Exception as e:
                print(f"[TaskManager] ОШИБКА при сохранении подзадачи '{sub_task_name}': {e}")
                import traceback
                traceback.print_exc()

    def delete_sub_task(self, task_id: str, sub_task_name: str) -> bool:
        """Удаляет подзадачу из workflow.
        
        Args:
            task_id: ID задачи
            sub_task_name: Имя подзадачи для удаления
            
        Returns:
            bool: True если подзадача была удалена, False если не найдена
        """
        with self._lock:
            workflow = self._tasks.get(task_id)
            if not workflow:
                print(f"[TaskManager] Workflow с ID {task_id} не найден при попытке удаления подзадачи '{sub_task_name}'")
                return False
            
            if sub_task_name not in workflow.sub_tasks:
                print(f"[TaskManager] Подзадача '{sub_task_name}' не найдена в workflow {task_id}")
                return False
            
            # Удаляем подзадачу
            del workflow.sub_tasks[sub_task_name]
            workflow.updated_at = time.time()
            self._dirty = True
            print(f"[TaskManager] Подзадача '{sub_task_name}' удалена из workflow {task_id}")
        
        # Сохраняем изменения на диск
        try:
            self.save_tasks_to_disk()
            print(f"[TaskManager] Изменения сохранены после удаления подзадачи '{sub_task_name}'")
        except Exception as e:
            print(f"[TaskManager] ОШИБКА при сохранении после удаления подзадачи '{sub_task_name}': {e}")
            import traceback
            traceback.print_exc()
        
        return True

    def update_workflow_status(self, task_id: str, status: TaskStatus, message: str = None, error: str = None):
        """Обновляет статус всего рабочего процесса."""
        with self._lock:
            workflow = self._tasks.get(task_id)
            if workflow:
                workflow.status = status
                if message:
                    workflow.message = message
                if error:
                    workflow.error = error
                    workflow.status = TaskStatus.FAILED
                workflow.updated_at = time.time()
                self._dirty = True
            else:
                print(f"[TaskManager] Workflow {task_id} не найден в update_workflow_status")

    def update_workflow_artifacts(self, task_id: str, artifacts: Dict):
        """Добавляет или обновляет артефакты в рабочем процессе."""
        with self._lock:
            workflow = self._tasks.get(task_id)
            if workflow:
                workflow.artifacts.update(artifacts)
                workflow.updated_at = time.time()
                self._dirty = True
            else:
                print(f"[TaskManager] Workflow {task_id} не найден в update_workflow_artifacts")

    def sync_subtask_to_file_info(self, task_id: str, sub_task_name: str):
        """
        Синхронизирует статус подзадачи в artifacts.ai_clips_files.
        Находит соответствующий файл по имени подзадачи и обновляет его sub_tasks.
        """
        with self._lock:
            workflow = self._tasks.get(task_id)
            if not workflow:
                return False
            
            sub_task = workflow.sub_tasks.get(sub_task_name)
            if not sub_task:
                return False
            
            # Извлекаем тип подзадачи из имени (clipping, compilation, shorts_creation)
            # Формат имени: {type}_{system_prompt_id}_{user_prompt_id}_{timestamp}
            parts = sub_task_name.split('_')
            if len(parts) < 4:
                return False
            
            subtask_type = parts[0]  # clipping, compilation, shorts_creation
            
            # Находим соответствующий файл в artifacts
            if not workflow.artifacts.get('ai_clips_files'):
                return False
            
            for file_info in workflow.artifacts['ai_clips_files']:
                # Проверяем, соответствует ли имя подзадачи этому файлу
                # Генерируем ожидаемое имя подзадачи для этого файла
                system_prompt_id = file_info.get('system_prompt_id', '')
                user_prompt_id = file_info.get('user_prompt_id', '')
                created_at = file_info.get('created_at', 0)
                
                if isinstance(created_at, (int, float)):
                    timestamp_str = time.strftime('%Y%m%d_%H%M%S', time.localtime(created_at))
                else:
                    timestamp_str = ''
                
                expected_name = f"{subtask_type}_{system_prompt_id}_{user_prompt_id}_{timestamp_str}"
                
                if sub_task_name == expected_name:
                    # Обновляем статус подзадачи в file_info
                    if 'sub_tasks' not in file_info:
                        file_info['sub_tasks'] = {}
                    
                    file_info['sub_tasks'][subtask_type] = {
                        'status': sub_task.status.value,
                        'message': sub_task.message,
                        'progress': sub_task.progress,
                        'error': sub_task.error,
                        'outputs': sub_task.outputs.copy() if sub_task.outputs else {},
                        'updated_at': sub_task.updated_at
                    }
                    
                    self._dirty = True
                    return True
            
            return False

    def list_tasks(self) -> list:
        """Возвращает список всех задач."""
        with self._lock:
            return [t.to_dict() for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)]

# Глобальный менеджер задач
task_manager = TaskManager()