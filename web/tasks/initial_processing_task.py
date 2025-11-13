#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фоновая задача для начальной обработки: скачивание видео и извлечение аудио.
"""

import sys
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web.services.hdrezka_service import HdRezkaService
from web.tasks.task_manager import task_manager, TaskStatus
from web.config import Config
from scripts.audio_extractor import AudioExtractor

def start_initial_processing_task(task_id: str, url: str, proxy: str = None,
                                proxy_type: str = 'socks5',
                                season: int = None, episode: int = None,
                                translator_id: int = None, quality: str = '360p'):
    """Запускает фоновую задачу начальной обработки как подзадачу."""
    
    def run_task():
        sub_task_name = "initial_processing"
        try:
            logger.info(f"[{task_id}] Запуск initial_processing.")
            # Создаем подзадачу ДО начала выполнения тяжелых операций
            task_manager.update_sub_task(
                task_id=task_id, sub_task_name=sub_task_name, sub_task_type='processing',
                status=TaskStatus.RUNNING, progress=0, message="Начало обработки..."
            )
            logger.info(f"[{task_id}] Подзадача '{sub_task_name}' создана и сохранена.")

            service = HdRezkaService(proxy=proxy, proxy_type=proxy_type)
            
            logger.info(f"[{task_id}] Параметры: season={season} (type: {type(season).__name__}), episode={episode} (type: {type(episode).__name__}), translator_id={translator_id}, quality={quality}")
            
            task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.RUNNING, progress=5, message="Анализ контента...")
            logger.info(f"[{task_id}] Вызов service.analyze_content с URL: {url}")
            
            content_info = None
            try:
                logger.info(f"[{task_id}] Начало анализа контента с таймаутом 60 секунд...")
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(service.analyze_content, url)
                    try:
                        content_info = future.result(timeout=60)
                        logger.info(f"[{task_id}] Анализ контента завершен успешно")
                    except FuturesTimeoutError:
                        logger.error(f"[{task_id}] Таймаут анализа контента (60 секунд)")
                        raise TimeoutError("Анализ контента занял более 60 секунд.")
            except Exception as e:
                logger.exception(f"[{task_id}] Ошибка при анализе контента: {e}")
                raise
            
            logger.info(f"[{task_id}] Результат analyze_content: {content_info}")

            if not content_info or not content_info.get('success'):
                error_msg = content_info.get('error', 'Неизвестная ошибка анализа') if content_info else 'Ответ от analyze_content пуст'
                raise ValueError(error_msg)
            
            safe_name = "".join(c for c in content_info.get('name', '') if c.isalnum() or c in (' ', '-', '_')).rstrip()
            logger.info(f"[{task_id}] Сгенерированное safe_name: '{safe_name}'")

            filename = f"{safe_name}_S{season:02d}E{episode:02d}_{quality}.mp4" if season and episode else f"{safe_name}_{quality}.mp4"
            output_path = Config.DOWNLOADS_DIR / filename
            logger.info(f"[{task_id}] Путь для сохранения видео: {output_path}")

            # --- Ключевая проверка ---
            if output_path.exists():
                logger.warning(f"[{task_id}] Файл по пути {output_path} уже существует. Пропускаю скачивание.")
                task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.RUNNING, progress=60, message="Видео уже существует")
            else:
                logger.info(f"[{task_id}] Файл не найден. Вхожу в блок скачивания.")
                task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.RUNNING, progress=15, message="Скачивание видео...")
                
                def progress_callback(percent, message):
                    mapped_progress = 15 + int(percent * 0.45)
                    task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.RUNNING, progress=mapped_progress, message=message)
                
                success, error = service.download_video(
                    url=url, output_path=output_path, season=season, episode=episode,
                    quality=quality, translator_id=translator_id, progress_callback=progress_callback
                )
                if not success:
                    raise ConnectionError(f"Ошибка скачивания: {error}")

            task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.RUNNING, progress=65, message="Извлечение аудио...")
            extractor = AudioExtractor(base_output_dir=str(Config.AUDIO_DIR))
            audio_path = extractor.extract_audio_from_video(video_path=output_path, overwrite=True)
            
            if not audio_path or not Path(audio_path).exists():
                raise IOError("Не удалось извлечь аудио.")
            logger.info(f"[{task_id}] Аудио извлечено: {audio_path}")

            artifacts_to_add = {
                'video_path': str(output_path),
                'audio_path': str(audio_path),
                'video_name': safe_name,
                'content_type': 'series' if (season and episode) else 'movie',
                'audio_filename': Path(audio_path).name
            }
            task_manager.update_workflow_artifacts(task_id, artifacts_to_add)

            task_manager.update_sub_task(
                task_id=task_id, sub_task_name=sub_task_name, sub_task_type='processing',
                status=TaskStatus.COMPLETED, progress=100, message="Скачивание и извлечение аудио завершено",
                outputs=artifacts_to_add
            )
            task_manager.update_workflow_status(task_id, TaskStatus.RUNNING, message="Начальная обработка завершена. Ожидание следующих шагов.")
            
            # Проверяем, нужно ли запускать автоматизацию Colab
            workflow = task_manager.get_task(task_id)
            if workflow:
                # Если включена автоматизация Colab, запускаем её напрямую
                # Config уже импортирован глобально в начале файла
                if Config.COLAB_AUTOMATION_ENABLED:
                    try:
                        logger.info(f"[{task_id}] Запуск Colab автоматизации после завершения initial_processing")
                        from web.routes.simple_api import _start_colab_transcription_automation
                        _start_colab_transcription_automation(task_id)
                    except Exception as e:
                        logger.error(f"[{task_id}] Ошибка при запуске Colab автоматизации: {e}", exc_info=True)
                
                # Также проверяем auto_mode для других автоматических переходов
                if workflow.artifacts.get('auto_mode', False):
                    try:
                        from web.routes.simple_api import auto_continue_workflow
                        auto_continue_workflow(task_id)
                    except Exception as e:
                        logger.warning(f"[{task_id}] Не удалось автоматически продолжить workflow после initial_processing: {e}")

        except Exception as e:
            logger.exception(f"[{task_id}] КРИТИЧЕСКАЯ ОШИБКА в initial_processing!")
            error_msg = f"Ошибка начальной обработки: {str(e)}"
            task_manager.update_sub_task(task_id, sub_task_name, 'processing', TaskStatus.FAILED, error=error_msg)
            task_manager.update_workflow_status(task_id, TaskStatus.FAILED, error=error_msg)
    
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
