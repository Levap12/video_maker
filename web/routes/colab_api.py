#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для интеграции с Google Colab для выполнения транскрибации.
"""

import sys
import logging
from pathlib import Path

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, request, jsonify, url_for
from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config

logger = logging.getLogger(__name__)
colab_bp = Blueprint('colab', __name__, url_prefix='/api/colab')

@colab_bp.route('/next-task', methods=['GET'])
def get_next_task():
    """
    Находит подходящий workflow и передает его Colab для транскрибации.
    """
    try:
        all_workflows = task_manager.list_tasks()
        
        for workflow_dict in all_workflows:
            workflow = task_manager.get_task(workflow_dict['task_id'])
            if not workflow:
                continue

            # Условия: начальная обработка завершена и транскрибация еще не начиналась/не завершена
            initial_processing = workflow.sub_tasks.get('initial_processing')
            transcription_task = workflow.sub_tasks.get('transcription')

            # Проверяем, что начальная обработка завершена
            if not (initial_processing and initial_processing.status == TaskStatus.COMPLETED):
                continue

            # Проверяем, что транскрибация либо не существует, либо в статусе RUNNING без завершенных outputs (еще не обработана)
            transcription_available = (
                not transcription_task or  # Подзадача не создана
                (transcription_task.status == TaskStatus.RUNNING and 
                 (not transcription_task.outputs or 
                  not transcription_task.outputs.get('simple_path') or 
                  not transcription_task.outputs.get('detailed_path')))  # Создана, но еще не обработана (нет файлов)
            )

            if transcription_available:
                audio_filename = workflow.artifacts.get('audio_filename')
                if not audio_filename:
                    continue

                audio_url = url_for('files.download_audio', filename=audio_filename, _external=True)
                
                # Создаем или обновляем подзадачу транскрибации (если она уже существует, просто обновим сообщение)
                if not transcription_task:
                    task_manager.update_sub_task(
                        task_id=workflow.task_id,
                        sub_task_name='transcription',
                        sub_task_type='transcription',
                        status=TaskStatus.RUNNING,
                        message="Передано в Colab для транскрибации"
                    )
                else:
                    # Обновляем только сообщение, если подзадача уже существует
                    task_manager.update_sub_task(
                        task_id=workflow.task_id,
                        sub_task_name='transcription',
                        sub_task_type='transcription',
                        status=TaskStatus.RUNNING,
                        message="Передано в Colab для транскрибации"
                    )
                
                logger.info(f"Отдаю задачу {workflow.task_id} для транскрибации Colab.")

                return jsonify({
                    'success': True,
                    'task_id': workflow.task_id,
                    'audio_url': audio_url,
                    'audio_filename': audio_filename
                })

        return jsonify({'success': False, 'error': 'Нет задач для транскрибации'}), 404

    except Exception as e:
        logger.exception("Ошибка при выдаче задачи для Colab")
        return jsonify({'success': False, 'error': str(e)}), 500


@colab_bp.route('/transcription/<task_id>', methods=['POST'])
def receive_transcription(task_id):
    """
    Принимает файлы транскрипции от Colab и обновляет соответствующую подзадачу.
    """
    try:
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow не найден'}), 404

        if 'transcription_files' not in request.files:
            return jsonify({'success': False, 'error': 'Файлы транскрипции не найдены'}), 400

        transcription_dir = Config.DATA_DIR / 'transcriptions'
        transcription_dir.mkdir(exist_ok=True)

        saved_files = {}
        for file in request.files.getlist('transcription_files'):
            if file.filename:
                save_path = transcription_dir / file.filename
                file.save(str(save_path))
                logger.info(f"Файл транскрипции {file.filename} для задачи {task_id} сохранен.")
                if file.filename.endswith('_simple.txt'):
                    saved_files['simple_path'] = str(save_path)
                elif file.filename.endswith('_detailed.json'):
                    saved_files['detailed_path'] = str(save_path)
        
        if 'simple_path' not in saved_files or 'detailed_path' not in saved_files:
            raise ValueError("Не получены оба файла транскрипции (simple.txt и detailed.json).")

        # Обновляем подзадачу
        task_manager.update_sub_task(
            task_id=task_id,
            sub_task_name='transcription',
            sub_task_type='transcription',
            status=TaskStatus.COMPLETED,
            message="Транскрипция получена и сохранена.",
            outputs=saved_files
        )
        
        # Также обновляем артефакты основного workflow для легкого доступа
        task_manager.update_workflow_artifacts(task_id, {
            'transcription_simple_path': saved_files['simple_path'],
            'transcription_detailed_path': saved_files['detailed_path']
        })
        
        # Проверяем auto_mode и пытаемся продолжить workflow
        if workflow.artifacts.get('auto_mode', False):
            try:
                from web.routes.simple_api import auto_continue_workflow
                auto_continue_workflow(task_id)
            except Exception as e:
                logger.warning(f"[{task_id}] Не удалось автоматически продолжить workflow после transcription: {e}")

        return jsonify({'success': True, 'message': 'Транскрипции успешно получены'})

    except Exception as e:
        logger.exception(f"Ошибка при получении транскрипции для задачи {task_id}")
        task_manager.update_sub_task(task_id, 'transcription', 'transcription', TaskStatus.FAILED, error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


@colab_bp.route('/reset-transcription/<task_id>', methods=['POST'])
def reset_transcription(task_id):
    """
    Сбрасывает подзадачу transcription для задачи, позволяя ей снова появиться в очереди для Colab.
    """
    try:
        workflow = task_manager.get_task(task_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Задача не найдена'}), 404

        # Проверяем существование подзадачи transcription
        transcription_task = workflow.sub_tasks.get('transcription')
        if not transcription_task:
            return jsonify({
                'success': False, 
                'error': 'Подзадача transcription не найдена. Задача уже доступна для обработки.'
            }), 400

        # Удаляем подзадачу transcription
        deleted = task_manager.delete_sub_task(task_id, 'transcription')
        if not deleted:
            return jsonify({'success': False, 'error': 'Не удалось удалить подзадачу transcription'}), 500

        logger.info(f"Подзадача transcription для задачи {task_id} успешно сброшена")
        return jsonify({
            'success': True, 
            'message': f'Подзадача transcription для задачи {task_id} успешно сброшена. Задача теперь доступна для обработки в Colab.'
        })

    except Exception as e:
        logger.exception(f"Ошибка при сбросе подзадачи transcription для задачи {task_id}")
        return jsonify({'success': False, 'error': str(e)}), 500