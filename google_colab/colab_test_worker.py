#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый воркер, имитирующий поведение Google Colab.

Он запрашивает задачу, мгновенно создает фейковую транскрибацию
и отправляет ее на сервер. Полезно для быстрой отладки workflow.
"""

import requests
import time
import os

# --- Настройка ---
# URL вашего локального сервера
SERVER_URL = "http://localhost:5000"

# Задержка между опросами, если нет задач (в секундах)
POLL_INTERVAL = 10
# --- Конец настройки ---

def get_next_task():
    """Запрашивает следующую задачу с сервера."""
    try:
        url = f"{SERVER_URL}/api/colab/next-task"
        print(f"\n[INFO] Запрос задачи с {url} ...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("[SUCCESS] Задача найдена!")
            return response.json()
        elif response.status_code == 404:
            print("[INFO] Нет активных задач для транскрибации.")
            return None
        else:
            print(f"[ERROR] Сервер ответил с кодом {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Не удалось подключиться к серверу {SERVER_URL}. Убедитесь, что он запущен. Ошибка: {e}")
        return None

def upload_fake_transcription(task_id, audio_filename):
    """Создает и загружает фейковый файл транскрипции."""
    try:
        # Создаем фейковый контент
        fake_content = f"""[00:00:00.000 - 00:00:02.500] Это тестовая транскрипция для файла {audio_filename}.
[00:00:02.500 - 00:00:05.000] Она была сгенерирована автоматически тестовым воркером.
"""
        
        # Создаем временный файл
        fake_filename = "dummy_transcription.txt"
        with open(fake_filename, "w", encoding="utf-8") as f:
            f.write(fake_content)
        
        print(f"[INFO] Создан фейковый файл транскрипции: {fake_filename}")

        # Отправляем файл на сервер
        url = f"{SERVER_URL}/api/colab/transcription/{task_id}"
        print(f"[INFO] Отправка файла на {url} ...")
        with open(fake_filename, 'rb') as f:
            files = {'transcription_file': (fake_filename, f, 'text/plain')}
            response = requests.post(url, files=files, timeout=20)
            response.raise_for_status()
        
        print("[SUCCESS] Фейковая транскрипция успешно отправлена!")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при отправке фейковой транскрипции: {e}")
        return False
    finally:
        # Очищаем временный файл
        if os.path.exists(fake_filename):
            os.remove(fake_filename)
            print(f"[INFO] Временный файл {fake_filename} удален.")

def main():
    """Основной цикл."""
    print("--- Запуск тестового воркера Colab ---" )
    print(f"Сервер: {SERVER_URL}")
    
    while True:
        task = get_next_task()
        
        if task and task.get('success'):
            task_id = task['task_id']
            audio_filename = task['audio_filename']
            
            print(f"--- Обработка задачи {task_id} ---")
            
            # Имитируем работу и отправляем результат
            time.sleep(2) # Небольшая задержка для имитации работы
            upload_fake_transcription(task_id, audio_filename)
            
            print(f"--- Задача {task_id} завершена ---")
        
        print(f"Следующая проверка через {POLL_INTERVAL} секунд...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Тестовый воркер остановлен.")
