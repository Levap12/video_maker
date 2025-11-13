#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Clipper
Скрипт для нарезки видео по отрывкам из JSON файла
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import time

from moviepy.editor import VideoFileClip


class VideoClipper:
    def __init__(self, output_dir="clips"):
        """Инициализация клиппера"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def time_to_seconds(self, time_str):
        """Конвертирует время в формате HH:MM:SS.ms в секунды"""
        try:
            time_parts = time_str.split(':')
            if len(time_parts) == 3:
                hours, minutes, seconds = map(float, time_parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(time_parts) == 2:
                minutes, seconds = map(float, time_parts)
                return minutes * 60 + seconds
            else:
                return float(time_parts[0])
        except ValueError:
            print(f"❌ Ошибка парсинга времени: {time_str}")
            return 0
    
    def seconds_to_time(self, seconds):
        """Конвертирует секунды в формат HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def sanitize_filename(self, filename):
        """Очищает имя файла от недопустимых символов"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()
    
    def create_clip(self, video_path, start_time, end_time, title, caption, clip_type, index):
        """Создает клип из видео"""
        try:
            print(f"🎬 Обрабатываю клип {index}: {title}")
            print(f"   Время: {start_time} - {end_time}")
            print(f"   Тип: {clip_type}")
            
            # Загружаем видео
            video = VideoFileClip(video_path)
            
            # Конвертируем время в секунды
            start_sec = self.time_to_seconds(start_time)
            end_sec = self.time_to_seconds(end_time)
            
            # Проверяем, что время корректно
            if start_sec >= end_sec:
                print(f"❌ Ошибка: время начала ({start_time}) больше или равно времени окончания ({end_time})")
                return None
            
            if end_sec > video.duration:
                print(f"⚠️ Время окончания ({end_time}) больше длительности видео ({self.seconds_to_time(video.duration)})")
                end_sec = video.duration
            
            # Создаем клип
            clip = video.subclip(start_sec, end_sec)
            
            # Создаем имя файла
            safe_title = self.sanitize_filename(title)
            filename = f"{index:02d}_{safe_title}.mp4"
            output_path = self.output_dir / filename
            
            # Сохраняем клип
            print(f"   💾 Сохраняю: {output_path}")
            clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # Закрываем клип
            clip.close()
            
            print(f"   ✅ Клип сохранен: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Ошибка при создании клипа '{title}': {e}")
            return None
    
    def process_json_file(self, json_path, video_path):
        """Обрабатывает JSON файл с отрывками"""
        try:
            # Читаем JSON файл
            with open(json_path, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            print(f"📋 Загружено {len(clips_data)} отрывков из {json_path}")
            
            # Проверяем существование видео файла
            if not os.path.exists(video_path):
                print(f"❌ Видео файл не найден: {video_path}")
                return False
            
            print(f"🎬 Обрабатываю видео: {video_path}")
            
            successful_clips = 0
            failed_clips = 0
            
            # Обрабатываем каждый отрывок
            for i, clip_data in enumerate(clips_data, 1):
                try:
                    start_time = clip_data['start_time']
                    end_time = clip_data['end_time']
                    title = clip_data['title']
                    caption = clip_data['caption']
                    clip_type = clip_data['type']
                    
                    print(f"\n--- Клип {i}/{len(clips_data)} ---")
                    print(f"📝 Описание: {caption}")
                    
                    result = self.create_clip(
                        video_path, start_time, end_time, 
                        title, caption, clip_type, i
                    )
                    
                    if result:
                        successful_clips += 1
                    else:
                        failed_clips += 1
                        
                except KeyError as e:
                    print(f"❌ Ошибка в данных клипа {i}: отсутствует поле {e}")
                    failed_clips += 1
                except Exception as e:
                    print(f"❌ Неожиданная ошибка в клипе {i}: {e}")
                    failed_clips += 1
            
            # Итоговая статистика
            print(f"\n📊 Результаты обработки:")
            print(f"✅ Успешно создано: {successful_clips}")
            print(f"❌ Ошибок: {failed_clips}")
            print(f"📁 Клипы сохранены в: {self.output_dir}")
            
            return successful_clips > 0
            
        except FileNotFoundError:
            print(f"❌ JSON файл не найден: {json_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return False
    
    def create_sample_json(self, output_path="data/sample_clips.json"):
        """Создает пример JSON файла"""
        sample_data = [
            {
                "start_time": "00:00:02",
                "end_time": "00:00:45",
                "title": "Рик решает взорвать планету",
                "caption": "Рик решил начать жизнь с нуля… уничтожив всё живое 😳",
                "type": "shock_mem"
            },
            {
                "start_time": "00:01:25",
                "end_time": "00:01:50",
                "title": "Морти спорит с Риком",
                "caption": "Когда даже Морти понял, что это уже перебор 😂",
                "type": "funny_dialogue"
            },
            {
                "start_time": "00:02:39",
                "end_time": "00:03:10",
                "title": "Морти флиртует с Джессикой",
                "caption": "Каждый Морти, когда видит свою Джессику 😅",
                "type": "relatable_mem"
            },
            {
                "start_time": "00:05:45",
                "end_time": "00:06:15",
                "title": "Рик рассказывает про семена знаний",
                "caption": "Рик всегда знает, где найти… *семена знаний* 🌌",
                "type": "quote_mem"
            },
            {
                "start_time": "00:07:40",
                "end_time": "00:08:20",
                "title": "Первая планета Рика и Морти",
                "caption": "Первый раз в другом измерении — и уже хаос 😂",
                "type": "visual_adventure"
            }
        ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print(f"📝 Создан пример JSON файла: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Video Clipper - нарезка видео по отрывкам')
    parser.add_argument('--json', '-j', help='Путь к JSON файлу с отрывками')
    parser.add_argument('--video', '-v', help='Путь к видео файлу')
    parser.add_argument('--output', '-o', default='clips', help='Папка для сохранения клипов')
    parser.add_argument('--sample', action='store_true', help='Создать пример JSON файла')
    
    args = parser.parse_args()
    
    clipper = VideoClipper(args.output)
    
    if args.sample:
        clipper.create_sample_json()
        return
    
    if not args.json or not args.video:
        print("❌ Необходимо указать JSON файл и видео файл")
        print("Использование: python video_clipper.py --json clips.json --video video.mp4")
        return
    
    success = clipper.process_json_file(args.json, args.video)
    
    if success:
        print("\n🎉 Обработка завершена успешно!")
    else:
        print("\n❌ Обработка завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
