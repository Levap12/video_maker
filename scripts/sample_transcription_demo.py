#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример использования ColabVideoTranscriber
Демонстрирует формат вывода транскрибации
"""

import json
from datetime import datetime

def create_sample_transcription():
    """Создает пример транскрибации для демонстрации формата"""
    
    # Пример данных транскрибации
    sample_data = {
        "video_info": {
            "title": "Рик и Морти S01E01 - Пилот",
            "file_size": "125.3 MB",
            "duration": "1234.5 сек",
            "model_used": "base",
            "processed_at": "2024-01-15T10:30:00"
        },
        "transcription": {
            "language": "ru",
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.523,
                    "text": "Привет, Морти! Пошли в приключение!",
                    "words": [
                        {"start": 0.0, "end": 0.847, "word": "Привет", "probability": 0.95},
                        {"start": 0.847, "end": 1.156, "word": ",", "probability": 0.99},
                        {"start": 1.156, "end": 2.034, "word": "Морти", "probability": 0.98},
                        {"start": 2.034, "end": 2.234, "word": "!", "probability": 0.99},
                        {"start": 2.234, "end": 2.456, "word": " ", "probability": 0.99},
                        {"start": 2.456, "end": 3.012, "word": "Пошли", "probability": 0.94},
                        {"start": 3.012, "end": 3.234, "word": " ", "probability": 0.99},
                        {"start": 3.234, "end": 3.456, "word": "в", "probability": 0.97},
                        {"start": 3.456, "end": 3.523, "word": "приключение!", "probability": 0.96}
                    ]
                },
                {
                    "start": 3.523,
                    "end": 8.234,
                    "text": "Рик, ты сошёл с ума! Мы не можем просто взорвать планету!",
                    "words": [
                        {"start": 3.523, "end": 4.012, "word": "Рик", "probability": 0.98},
                        {"start": 4.012, "end": 4.234, "word": ",", "probability": 0.99},
                        {"start": 4.234, "end": 4.456, "word": " ", "probability": 0.99},
                        {"start": 4.456, "end": 4.789, "word": "ты", "probability": 0.97},
                        {"start": 4.789, "end": 5.234, "word": "сошёл", "probability": 0.95},
                        {"start": 5.234, "end": 5.456, "word": " ", "probability": 0.99},
                        {"start": 5.456, "end": 5.678, "word": "с", "probability": 0.98},
                        {"start": 5.678, "end": 6.012, "word": "ума", "probability": 0.96},
                        {"start": 6.012, "end": 6.234, "word": "!", "probability": 0.99},
                        {"start": 6.234, "end": 6.456, "word": " ", "probability": 0.99},
                        {"start": 6.456, "end": 6.789, "word": "Мы", "probability": 0.97},
                        {"start": 6.789, "end": 7.012, "word": " ", "probability": 0.99},
                        {"start": 7.012, "end": 7.345, "word": "не", "probability": 0.98},
                        {"start": 7.345, "end": 7.678, "word": "можем", "probability": 0.95},
                        {"start": 7.678, "end": 7.890, "word": " ", "probability": 0.99},
                        {"start": 7.890, "end": 8.123, "word": "просто", "probability": 0.94},
                        {"start": 8.123, "end": 8.234, "word": "взорвать планету!", "probability": 0.93}
                    ]
                },
                {
                    "start": 8.234,
                    "end": 12.845,
                    "text": "Морти, это не просто планета. Это новый мир, который мы создадим!",
                    "words": [
                        {"start": 8.234, "end": 8.678, "word": "Морти", "probability": 0.98},
                        {"start": 8.678, "end": 8.890, "word": ",", "probability": 0.99},
                        {"start": 8.890, "end": 9.123, "word": " ", "probability": 0.99},
                        {"start": 9.123, "end": 9.456, "word": "это", "probability": 0.97},
                        {"start": 9.456, "end": 9.678, "word": " ", "probability": 0.99},
                        {"start": 9.678, "end": 10.012, "word": "не", "probability": 0.98},
                        {"start": 10.012, "end": 10.345, "word": "просто", "probability": 0.96},
                        {"start": 10.345, "end": 10.678, "word": "планета", "probability": 0.95},
                        {"start": 10.678, "end": 10.890, "word": ".", "probability": 0.99},
                        {"start": 10.890, "end": 11.123, "word": " ", "probability": 0.99},
                        {"start": 11.123, "end": 11.456, "word": "Это", "probability": 0.97},
                        {"start": 11.456, "end": 11.789, "word": "новый", "probability": 0.96},
                        {"start": 11.789, "end": 12.123, "word": "мир", "probability": 0.95},
                        {"start": 12.123, "end": 12.456, "word": ",", "probability": 0.99},
                        {"start": 12.456, "end": 12.678, "word": " ", "probability": 0.99},
                        {"start": 12.678, "end": 12.845, "word": "который мы создадим!", "probability": 0.94}
                    ]
                }
            ]
        }
    }
    
    return sample_data

def save_sample_files():
    """Сохраняет пример файлов"""
    
    # Создаем папку для примеров
    import os
    os.makedirs("data/sample_output", exist_ok=True)
    
    # Получаем пример данных
    sample_data = create_sample_transcription()
    
    # Сохраняем JSON файл
    json_path = "data/sample_output/sample_transcription.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Пример JSON сохранен: {json_path}")
    
    # Сохраняем текстовый файл
    text_path = "data/sample_output/sample_transcription.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write("ТРАНСКРИБАЦИЯ ВИДЕО\n")
        f.write("=" * 50 + "\n\n")
        
        f.write("ИНФОРМАЦИЯ О ВИДЕО:\n")
        for key, value in sample_data["video_info"].items():
            f.write(f"{key}: {value}\n")
        f.write("\n")
        
        f.write("ТЕКСТ:\n")
        f.write("-" * 30 + "\n")
        
        for segment in sample_data["transcription"]["segments"]:
            start_time = format_time(segment["start"])
            end_time = format_time(segment["end"])
            f.write(f"[{start_time} - {end_time}] {segment['text']}\n")
    
    print(f"✅ Пример текста сохранен: {text_path}")
    
    # Создаем компактную версию для GPT
    compact_data = {
        "segments": [
            {
                "time": f"{segment['start']:.3f}-{segment['end']:.3f}s",
                "text": segment["text"]
            }
            for segment in sample_data["transcription"]["segments"]
        ]
    }
    
    compact_path = "data/sample_output/sample_compact.json"
    with open(compact_path, 'w', encoding='utf-8') as f:
        json.dump(compact_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Компактная версия сохранена: {compact_path}")
    
    return json_path, text_path, compact_path

def format_time(seconds):
    """Форматирует время в HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"

def show_usage_examples():
    """Показывает примеры использования"""
    
    print("📋 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ТРАНСКРИБАЦИИ")
    print("=" * 50)
    
    print("\n1. Для анализа диалогов:")
    print("   - Найдите все реплики конкретного персонажа")
    print("   - Проанализируйте эмоциональную окраску по времени")
    print("   - Создайте субтитры с точными временными метками")
    
    print("\n2. Для создания контента:")
    print("   - Найдите самые интересные моменты")
    print("   - Создайте клипы по ключевым словам")
    print("   - Сгенерируйте описания для YouTube")
    
    print("\n3. Для обучения GPT:")
    print("   - Используйте компактный формат для экономии токенов")
    print("   - Включайте только нужные сегменты")
    print("   - Добавляйте контекст о персонажах и сюжете")
    
    print("\n4. Для поиска:")
    print("   - Найдите фразы по ключевым словам")
    print("   - Определите время появления персонажей")
    print("   - Создайте индекс важных моментов")

if __name__ == "__main__":
    print("🎬 Создание примеров транскрибации...")
    
    # Создаем пример файлы
    json_path, text_path, compact_path = save_sample_files()
    
    # Показываем примеры использования
    show_usage_examples()
    
    print(f"\n📁 Все примеры сохранены в папке: data/sample_output/")
    print(f"📄 JSON файл: {json_path}")
    print(f"📄 Текстовый файл: {text_path}")
    print(f"📄 Компактный файл: {compact_path}")
    
    print("\n💡 Используйте эти примеры для понимания формата вывода!")
