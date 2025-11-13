#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки Simple API.
Проверяет создание задачи, получение статуса и скачивание готовых видео.
"""

import requests
import time
import json
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Настройки
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api/v1/video"

# Цвета для вывода в консоль
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message):
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")

def print_header(message):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def test_server_connection():
    """Проверяет доступность сервера"""
    print_header("Проверка подключения к серверу")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print_success(f"Сервер доступен: {BASE_URL}")
            return True
        else:
            print_error(f"Сервер вернул код {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Не удалось подключиться к серверу {BASE_URL}")
        print_info("Убедитесь, что сервер запущен: python run_web.py")
        return False
    except Exception as e:
        print_error(f"Ошибка при подключении: {e}")
        return False


def get_prompts():
    """Получает список доступных промптов"""
    print_header("Получение списка промптов")
    try:
        # Получаем системные промпты
        response = requests.get(f"{BASE_URL}/api/prompts/system", timeout=10)
        if response.status_code == 200:
            system_prompts = response.json().get('prompts', [])
            print_success(f"Найдено системных промптов: {len(system_prompts)}")
        else:
            print_error(f"Ошибка получения системных промптов: {response.status_code}")
            return None, None
        
        # Получаем пользовательские промпты
        response = requests.get(f"{BASE_URL}/api/prompts/user", timeout=10)
        if response.status_code == 200:
            user_prompts = response.json().get('prompts', [])
            print_success(f"Найдено пользовательских промптов: {len(user_prompts)}")
        else:
            print_error(f"Ошибка получения пользовательских промптов: {response.status_code}")
            return None, None
        
        if not system_prompts:
            print_warning("Системные промпты не найдены. Создайте хотя бы один промпт.")
            return None, None
        
        if not user_prompts:
            print_warning("Пользовательские промпты не найдены. Создайте хотя бы один промпт.")
            return None, None
        
        # Выводим список промптов
        print(f"\n{Colors.BOLD}Системные промпты:{Colors.RESET}")
        for i, prompt in enumerate(system_prompts[:5], 1):  # Показываем первые 5
            print(f"  {i}. [{prompt['id'][:8]}...] {prompt['name']}")
        
        print(f"\n{Colors.BOLD}Пользовательские промпты:{Colors.RESET}")
        for i, prompt in enumerate(user_prompts[:5], 1):  # Показываем первые 5
            print(f"  {i}. [{prompt['id'][:8]}...] {prompt['name']}")
        
        return system_prompts[0]['id'], user_prompts[0]['id']
        
    except Exception as e:
        print_error(f"Ошибка при получении промптов: {e}")
        return None, None


def test_create_video(url, season, episode, system_prompt_id, user_prompt_id, quality="720p"):
    """Тестирует создание задачи на обработку видео"""
    print_header("Создание задачи на обработку видео")
    
    payload = {
        "url": url,
        "season": season,
        "episode": episode,
        "quality": quality,
        "translator_id": 66,
        "system_prompt_id": system_prompt_id,
        "user_prompt_id": user_prompt_id,
        "shorts_settings": {
            "watermark_text": "@TestChannel",
            "watermark_color": "gray",
            "watermark_font_size": 72,
            "watermark_bottom_offset": 180,
            "banner_offset": 100,
            "height_scale": 2.0
        }
    }
    
    print_info(f"URL: {url}")
    print_info(f"Сезон: {season}, Серия: {episode}")
    print_info(f"Качество: {quality}")
    print_info(f"Системный промпт: {system_prompt_id[:8]}...")
    print_info(f"Пользовательский промпт: {user_prompt_id[:8]}...")
    
    try:
        response = requests.post(
            f"{API_BASE}/create",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 201:
            data = response.json()
            if data.get('success'):
                task_id = data.get('task_id')
                print_success(f"Задача создана успешно!")
                print_info(f"Task ID: {task_id}")
                return task_id
            else:
                print_error(f"Ошибка создания задачи: {data.get('error')}")
                return None
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print_error("Таймаут при создании задачи (30 секунд)")
        return None
    except Exception as e:
        print_error(f"Ошибка при создании задачи: {e}")
        return None


def test_get_status(task_id, max_wait_time=3600):
    """Тестирует получение статуса задачи и ждет завершения"""
    print_header("Отслеживание статуса задачи")
    
    start_time = time.time()
    last_stage = None
    last_progress = -1
    
    print_info(f"Task ID: {task_id}")
    print_info(f"Максимальное время ожидания: {max_wait_time // 60} минут")
    print_info("Проверка статуса каждые 5 секунд...\n")
    
    while True:
        try:
            response = requests.get(
                f"{API_BASE}/status/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not data.get('success'):
                    print_error(f"Ошибка получения статуса: {data.get('error')}")
                    return False
                
                status = data.get('status')
                stage = data.get('stage')
                progress = data.get('progress', 0)
                message = data.get('message', '')
                
                # Выводим обновление только если изменился этап или прогресс
                if stage != last_stage or abs(progress - last_progress) >= 5:
                    elapsed = int(time.time() - start_time)
                    elapsed_str = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
                    
                    stage_emoji = {
                        'downloading': '📥',
                        'waiting_transcription': '⏳',
                        'transcribing': '📝',
                        'ai_generation': '🤖',
                        'clipping': '✂️',
                        'waiting_shorts': '⏳',
                        'shorts_creation': '🎬',
                        'completed': '✅',
                        'failed': '❌'
                    }
                    
                    emoji = stage_emoji.get(stage, '🔄')
                    print(f"{emoji} [{elapsed_str}] {stage.upper():20s} | {progress:5.1f}% | {message}")
                    
                    last_stage = stage
                    last_progress = progress
                
                # Проверяем завершение
                if status == 'completed':
                    print_success(f"\nЗадача завершена успешно!")
                    print_info(f"Время выполнения: {int(time.time() - start_time)} секунд")
                    
                    # Выводим список готовых видео
                    videos = data.get('videos', [])
                    if videos:
                        print(f"\n{Colors.BOLD}Создано видео:{Colors.RESET}")
                        for i, video in enumerate(videos, 1):
                            print(f"  {i}. {video['filename']} ({video['size_mb']} MB)")
                    else:
                        print_warning("Список видео пуст")
                    
                    return True
                
                elif status == 'failed':
                    error = data.get('error', 'Неизвестная ошибка')
                    print_error(f"\nЗадача завершилась с ошибкой: {error}")
                    return False
                
            else:
                print_error(f"HTTP {response.status_code}: {response.text}")
                return False
            
            # Проверяем таймаут
            if time.time() - start_time > max_wait_time:
                print_error(f"\nПревышено максимальное время ожидания ({max_wait_time} секунд)")
                return False
            
            # Ждем перед следующей проверкой
            time.sleep(5)
            
        except requests.exceptions.Timeout:
            print_warning("Таймаут при получении статуса, повторная попытка...")
            time.sleep(5)
            continue
        except KeyboardInterrupt:
            print_warning("\nПрервано пользователем")
            return False
        except Exception as e:
            print_error(f"Ошибка при получении статуса: {e}")
            time.sleep(5)
            continue


def test_download_links(task_id):
    """Тестирует получение ссылок на готовые видео"""
    print_header("Получение ссылок на готовые видео")
    
    try:
        response = requests.get(
            f"{API_BASE}/{task_id}/download",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                videos = data.get('videos', [])
                metadata = data.get('metadata', {})
                
                print_success(f"Получено {len(videos)} видео")
                
                if metadata:
                    print(f"\n{Colors.BOLD}Метаданные:{Colors.RESET}")
                    print(f"  Источник: {metadata.get('source_url', 'N/A')}")
                    print(f"  Сезон: {metadata.get('season', 'N/A')}, Серия: {metadata.get('episode', 'N/A')}")
                    print(f"  Создано: {metadata.get('created_at', 'N/A')}")
                    print(f"  Общий размер: {metadata.get('total_size_mb', 0)} MB")
                
                print(f"\n{Colors.BOLD}Ссылки на скачивание:{Colors.RESET}")
                for i, video in enumerate(videos, 1):
                    print(f"\n  {i}. {video['filename']}")
                    print(f"     Размер: {video['size_mb']} MB")
                    if video.get('duration_seconds'):
                        print(f"     Длительность: {video['duration_seconds']} сек")
                    print(f"     URL: {video['download_url']}")
                
                return True
            else:
                print_error(f"Ошибка: {data.get('error')}")
                return False
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Ошибка при получении ссылок: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "ТЕСТИРОВАНИЕ SIMPLE API" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print(Colors.RESET)
    
    # Шаг 1: Проверка подключения
    if not test_server_connection():
        print_error("\nНе удалось подключиться к серверу. Завершение теста.")
        return
    
    # Шаг 2: Получение промптов
    system_prompt_id, user_prompt_id = get_prompts()
    if not system_prompt_id or not user_prompt_id:
        print_error("\nНе удалось получить промпты. Завершение теста.")
        print_info("Создайте промпты через веб-интерфейс: http://localhost:5000/prompts")
        return
    
    # Шаг 3: Параметры для теста
    print_header("Параметры теста")
    
    # Можно изменить эти параметры
    test_url = input(f"{Colors.YELLOW}Введите URL HDRezka (или Enter для пропуска теста): {Colors.RESET}").strip()
    if not test_url:
        print_warning("Тест пропущен (не указан URL)")
        return
    
    try:
        season = int(input(f"{Colors.YELLOW}Введите номер сезона (или Enter для пропуска): {Colors.RESET}").strip() or "0")
        episode = int(input(f"{Colors.YELLOW}Введите номер серии (или Enter для пропуска): {Colors.RESET}").strip() or "0")
    except ValueError:
        season = 0
        episode = 0
    
    if season == 0 or episode == 0:
        print_warning("Сезон или серия не указаны, будет использован режим фильма")
        season = None
        episode = None
    
    quality = input(f"{Colors.YELLOW}Введите качество (360p/720p/1080p, по умолчанию 720p): {Colors.RESET}").strip() or "720p"
    
    # Шаг 4: Создание задачи
    task_id = test_create_video(
        url=test_url,
        season=season,
        episode=episode,
        system_prompt_id=system_prompt_id,
        user_prompt_id=user_prompt_id,
        quality=quality
    )
    
    if not task_id:
        print_error("\nНе удалось создать задачу. Завершение теста.")
        return
    
    # Шаг 5: Отслеживание статуса
    success = test_get_status(task_id)
    
    if not success:
        print_error("\nЗадача не завершилась успешно. Завершение теста.")
        return
    
    # Шаг 6: Получение ссылок
    test_download_links(task_id)
    
    print_header("Тестирование завершено")
    print_success("Все тесты пройдены успешно!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Тест прерван пользователем{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

