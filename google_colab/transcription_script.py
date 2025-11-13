#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
(DEBUG) Скрипт-воркер для Google Colab для выполнения ОДНОЙ задачи.
"""

import requests
import os
import time
import logging
import sys
import json # Добавляем импорт json

import http.client

# --- Настройка ---
SERVER_URL = "https://52d06bb05cd3.ngrok-free.app" 
MODEL_NAME = "tiny"
# --- Конец настройки ---

# Настройка логирования с принудительным выводом
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Явно указываем поток вывода
)

def force_print(message):
    """Функция для вывода сообщений с принудительной очисткой буфера."""
    print(message, flush=True)

def setup_whisper():
    force_print("--> Этап 1: Настройка Whisper...")
    try:
        import whisper
        force_print("    Whisper уже импортирован.")
    except ImportError:
        force_print("    Установка зависимостей: openai-whisper, requests...")
        os.system("pip install -q openai-whisper requests")
        time.sleep(5)
        try:
            import whisper
            force_print("    Зависимости успешно установлены.")
        except ImportError:
            force_print("    КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить/импортировать whisper.")
            return None

    force_print(f"    Загрузка модели Whisper '{MODEL_NAME}'...")
    try:
        model = whisper.load_model(MODEL_NAME)
        force_print("    Модель Whisper успешно загружена!")
        return model
    except Exception as e:
        force_print(f"    КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить модель Whisper: {e}")
        return None

def get_task():
    force_print("--> Этап 2: Поиск задачи на сервере...")
    try:
        url = f"{SERVER_URL}/api/colab/next-task"
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            force_print("    Задача найдена!")
            return response.json()
        elif response.status_code == 404:
            force_print("    Нет активных задач для транскрибации.")
            return None
        else:
            force_print(f"    ОШИБКА: Сервер ответил с кодом {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        force_print(f"    КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к серверу {SERVER_URL}. Проверьте URL. Ошибка: {e}")
        return None

def download_audio(task_id, audio_url, filename, retries=3, delay=5):
    """Скачивает аудиофайл с логикой повторных попыток и индикатором прогресса."""
    for attempt in range(retries):
        try:
            force_print(f"[{task_id}] Попытка скачивания #{attempt + 1}/{retries} из {audio_url}...")
            response = requests.get(audio_url, stream=True, timeout=120)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            downloaded_size_at_last_print = 0 # Инициализируем переменную
            start_time = time.time()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Вывод прогресса
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            elapsed_time = time.time() - start_time
                            # Обновляем прогресс каждые 5% или каждые 5 секунд
                            if (progress - (downloaded_size_at_last_print / total_size * 100 if total_size > 0 else 0)) >= 5 or elapsed_time > 5:
                                force_print(f"    Прогресс скачивания: {progress:.1f}% ({downloaded_size / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)")
                                downloaded_size_at_last_print = downloaded_size
                                start_time = time.time()
            
            file_size = os.path.getsize(filename) / (1024 * 1024)
            force_print(f"    Аудиофайл '{filename}' ({file_size:.2f} MB) успешно скачан.")
            return filename
        except (requests.exceptions.RequestException, requests.exceptions.ChunkedEncodingError, ConnectionError, http.client.IncompleteRead) as e:
            force_print(f"[{task_id}] Ошибка скачивания (попытка {attempt + 1}): {e}. Повтор через {delay} сек...")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                force_print(f"[{task_id}] КРИТИЧЕСКАЯ ОШИБКА: Не удалось скачать аудиофайл после {retries} попыток.")
                return None
    return None

def upload_transcription_files(task_id, file_paths: list):
    force_print(f"--> Этап 5: Отправка файлов транскрипции на сервер...")
    try:
        url = f"{SERVER_URL}/api/colab/transcription/{task_id}"
        files = []
        for fp in file_paths:
            file_basename = os.path.basename(fp)
            # Определяем тип файла по расширению
            if fp.endswith('.json'):
                mime_type = 'application/json'
            elif fp.endswith('.txt'):
                mime_type = 'text/plain'
            else:
                mime_type = 'application/octet-stream' # Дефолтный тип
            
            files.append(('transcription_files', (file_basename, open(fp, 'rb'), mime_type)))

        force_print(f"    Попытка отправки {len(file_paths)} файлов на {url} ...")
        response = requests.post(url, files=files, timeout=60)
        response.raise_for_status()
        
        force_print("    Файлы транскрипции успешно отправлены!")
        return True
    except Exception as e:
        force_print(f"    ОШИБКА при отправке файлов транскрипции: {e}")
        return False
    finally:
        # Закрываем все открытые файлы после отправки
        for _, (filename, file_obj, mime_type) in files:
            file_obj.close()

def format_and_save_transcription_files(task_id, result, original_filename):
    force_print("--> Этап 4.1: Форматирование и сохранение транскрипции...")
    base_name = os.path.splitext(original_filename)[0]
    
    # 1. Сохраняем упрощенный формат (для AI)
    simple_output_filename = f"{base_name}_simple.txt"
    with open(simple_output_filename, "w", encoding="utf-8") as f:
        for segment in result["segments"]:
            start, end, text = segment['start'], segment['end'], segment['text'].strip()
            start_h, start_rem = divmod(start, 3600); start_m, start_s = divmod(start_rem, 60)
            end_h, end_rem = divmod(end, 3600); end_m, end_s = divmod(end_rem, 60)
            time_str = f"[{int(start_h):02}:{int(start_m):02}:{start_s:06.3f} - {int(end_h):02}:{int(end_m):02}:{end_s:06.3f}] {text}"
            f.write(time_str + "\n")
    force_print(f"    Упрощенная транскрипция сохранена в: {simple_output_filename}")

    # 2. Сохраняем детализированный JSON (для нарезки)
    detailed_output_filename = f"{base_name}_detailed.json"
    with open(detailed_output_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    force_print(f"    Детализированная транскрипция сохранена в: {detailed_output_filename}")

    return [simple_output_filename, detailed_output_filename]

def run_one_task():
    """Выполняет один полный цикл: поиск задачи, транскрибация, отправка."""
    model = setup_whisper()
    if not model:
        return

    task = get_task()
    if not (task and task.get('success')):
        force_print("Завершение работы, так как нет доступных задач.")
        return

    task_id, audio_url, audio_filename = task['task_id'], task['audio_url'], task['audio_filename']
    
    local_audio_path = download_audio(task_id, audio_url, audio_filename)
    if not local_audio_path:
        return

    force_print(f"--> Этап 4: Начало транскрибации для задачи {task_id}...")
    try:
        result = model.transcribe(local_audio_path, language="ru", fp16=False, verbose=True, word_timestamps=True)
        force_print("    Транскрибация успешно завершена.")
    except Exception as e:
        force_print(f"    КРИТИЧЕСКАЯ ОШИБКА во время транскрибации: {e}")
        return

    transcription_file_paths = format_and_save_transcription_files(task_id, result, audio_filename)
    
    upload_success = upload_transcription_files(task_id, transcription_file_paths)
    
    try:
        os.remove(local_audio_path)
        for fp in transcription_file_paths:
            os.remove(fp)
        force_print("--> Этап 6: Временные файлы удалены.")
    except OSError as e:
        force_print(f"    ОШИБКА при удалении временных файлов: {e}")
    
    force_print("=== Цикл завершен ===")

if __name__ == "__main__":
    run_one_task()
