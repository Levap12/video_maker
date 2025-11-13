#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Processor
Комплексный скрипт для нарезки и склеивания видео по JSON файлу
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from moviepy.editor import VideoFileClip, concatenate_videoclips


class VideoProcessor:
    def __init__(self, source_dir="downloads", output_dir="output", temp_dir="temp_clips"):
        """Инициализация процессора"""
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        
        # Создаем папки
        self.output_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
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
    
    def find_source_video(self):
        """Находит основное видео в папке downloads"""
        video_files = list(self.source_dir.glob("*.mp4"))
        
        if not video_files:
            print(f"❌ Не найдено видео файлов в {self.source_dir}")
            return None
        
        if len(video_files) == 1:
            return video_files[0]
        
        # Если несколько файлов, выбираем самый большой
        largest_file = max(video_files, key=lambda f: f.stat().st_size)
        print(f"📁 Найдено несколько видео файлов, выбран: {largest_file.name}")
        return largest_file
    
    def create_clip_from_source(self, source_video, start_time, end_time, title, index):
        """Создает клип из основного видео"""
        try:
            print(f"✂️ Нарезаю клип {index}: {title}")
            print(f"   Время: {start_time} - {end_time}")
            
            # Загружаем основное видео
            video = VideoFileClip(str(source_video))
            
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
            temp_path = self.temp_dir / filename
            
            # Сохраняем клип во временную папку
            print(f"   💾 Сохраняю: {temp_path}")
            clip.write_videofile(
                str(temp_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None,
                preset='fast',
                threads=8
            )
            
            # Закрываем клип
            clip.close()
            
            print(f"   ✅ Клип сохранен: {temp_path}")
            return temp_path
            
        except Exception as e:
            print(f"❌ Ошибка при создании клипа '{title}': {e}")
            return None
    
    def join_clips(self, clip_paths, output_filename):
        """Склеивает клипы в одно видео"""
        try:
            if not clip_paths:
                print("❌ Нет клипов для склеивания")
                return False
            
            print(f"\n🎬 Склеиваю {len(clip_paths)} клипов...")
            
            # Загружаем все клипы
            video_clips = []
            total_duration = 0
            
            for i, clip_path in enumerate(clip_paths, 1):
                print(f"   📁 Загружаю клип {i}: {clip_path.name}")
                clip = VideoFileClip(str(clip_path))
                video_clips.append(clip)
                total_duration += clip.duration
                print(f"      Длительность: {self.seconds_to_time(clip.duration)}")
            
            print(f"📊 Общая длительность: {self.seconds_to_time(total_duration)}")
            
            # Склеиваем все клипы
            final_video = concatenate_videoclips(video_clips, method="compose")
            
            # Путь для финального видео
            output_path = self.output_dir / output_filename
            
            # Сохраняем финальное видео
            print(f"💾 Сохраняю финальное видео: {output_path}")
            final_video.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None,
                preset='fast',
                threads=8
            )
            
            # Закрываем все клипы
            for clip in video_clips:
                clip.close()
            final_video.close()
            
            print(f"✅ Финальное видео сохранено: {output_path}")
            print(f"📊 Итоговая длительность: {self.seconds_to_time(total_duration)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при склеивании: {e}")
            return False
    
    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                print(f"🧹 Временные файлы очищены: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ Не удалось очистить временные файлы: {e}")
    
    def process_json_file(self, json_path, output_filename=None, cleanup=True):
        """Основной метод обработки JSON файла"""
        try:
            # Читаем JSON файл
            with open(json_path, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            print(f"📋 Загружено {len(clips_data)} отрывков из {json_path}")
            
            # Находим основное видео
            source_video = self.find_source_video()
            if not source_video:
                return False
            
            print(f"🎬 Основное видео: {source_video}")
            
            # Фильтруем клипы с join_sequence = true
            clips_to_process = [clip for clip in clips_data if clip.get('join_sequence', False)]
            
            if not clips_to_process:
                print("❌ Не найдено клипов для обработки (join_sequence = true)")
                return False
            
            print(f"🎬 Найдено {len(clips_to_process)} клипов для обработки")
            
            # Создаем имя выходного файла
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"compilation_{timestamp}.mp4"
            
            successful_clips = []
            failed_clips = 0
            
            # Обрабатываем каждый клип
            for i, clip_data in enumerate(clips_to_process, 1):
                try:
                    start_time = clip_data['start_time']
                    end_time = clip_data['end_time']
                    title = clip_data['title']
                    caption = clip_data.get('caption', '')
                    
                    print(f"\n--- Обрабатываю клип {i}/{len(clips_to_process)} ---")
                    print(f"📝 Название: {title}")
                    print(f"💬 Капшен: {caption}")
                    
                    # Создаем клип из основного видео
                    clip_path = self.create_clip_from_source(
                        source_video, start_time, end_time, title, i
                    )
                    
                    if clip_path:
                        successful_clips.append(clip_path)
                    else:
                        failed_clips += 1
                        
                except KeyError as e:
                    print(f"❌ Ошибка в данных клипа {i}: отсутствует поле {e}")
                    failed_clips += 1
                except Exception as e:
                    print(f"❌ Неожиданная ошибка в клипе {i}: {e}")
                    failed_clips += 1
            
            # Склеиваем успешно созданные клипы
            if successful_clips:
                success = self.join_clips(successful_clips, output_filename)
                
                if success:
                    print(f"\n📊 Результаты обработки:")
                    print(f"✅ Успешно обработано: {len(successful_clips)}")
                    print(f"❌ Ошибок: {failed_clips}")
                    print(f"📁 Результат сохранен в: {self.output_dir}")
                    
                    # Очищаем временные файлы
                    if cleanup:
                        self.cleanup_temp_files()
                    
                    return True
                else:
                    print("❌ Ошибка при склеивании клипов")
                    return False
            else:
                print("❌ Не удалось создать ни одного клипа")
                return False
            
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
                "end_time": "00:00:10",
                "title": "Рик будит Морти",
                "caption": "Пошли, Морти! У нас важное дело!",
                "join_sequence": True
            },
            {
                "start_time": "00:00:32",
                "end_time": "00:00:45",
                "title": "Рик хочет взорвать планету",
                "caption": "Мы создадим новый мир, Морти! 💣",
                "join_sequence": True
            },
            {
                "start_time": "00:01:25",
                "end_time": "00:01:45",
                "title": "Морти спорит с Риком",
                "caption": "Рик, ты сошёл с ума!",
                "join_sequence": True
            },
            {
                "start_time": "00:02:39",
                "end_time": "00:02:50",
                "title": "Морти и Джессика",
                "caption": "Привет, Джессика… 😳",
                "join_sequence": True
            },
            {
                "start_time": "00:05:45",
                "end_time": "00:06:00",
                "title": "Семена знаний",
                "caption": "Семена знаний, Морти! Они особенные… 🌌",
                "join_sequence": True
            },
            {
                "start_time": "00:07:40",
                "end_time": "00:08:00",
                "title": "Первая планета",
                "caption": "Мы не в Канзасе, Морти…",
                "join_sequence": True
            },
            {
                "start_time": "00:09:45",
                "end_time": "00:10:00",
                "title": "Морти падает",
                "caption": "Рик, мне больно! 💀",
                "join_sequence": True
            },
            {
                "start_time": "00:10:52",
                "end_time": "00:11:10",
                "title": "Рик продолжает миссию",
                "caption": "Давай быстрее, Морти!",
                "join_sequence": True
            },
            {
                "start_time": "00:17:25",
                "end_time": "00:17:40",
                "title": "Философия Рика",
                "caption": "Иногда просто нужно лететь вперёд… 🚀",
                "join_sequence": True
            },
            {
                "start_time": "00:20:00",
                "end_time": "00:20:30",
                "title": "100 лет Рика и Морти",
                "caption": "100 лет приключений! 🔥",
                "join_sequence": True
            }
        ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print(f"📝 Создан пример JSON файла: {output_path}")
        return output_path
    
    def list_source_videos(self):
        """Показывает доступные исходные видео"""
        if not self.source_dir.exists():
            print(f"❌ Папка с исходными видео не найдена: {self.source_dir}")
            return
        
        video_files = list(self.source_dir.glob("*.mp4"))
        
        if not video_files:
            print(f"📁 Папка {self.source_dir} пуста")
            return
        
        print(f"📁 Найдено {len(video_files)} видео в {self.source_dir}:")
        for i, video_file in enumerate(sorted(video_files), 1):
            size_mb = video_file.stat().st_size / (1024 * 1024)
            print(f"  {i:2d}. {video_file.name} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description='Video Processor - нарезка и склеивание видео')
    parser.add_argument('--json', '-j', help='Путь к JSON файлу с клипами')
    parser.add_argument('--output', '-o', help='Имя выходного файла')
    parser.add_argument('--source-dir', '-s', default='downloads', help='Папка с исходными видео')
    parser.add_argument('--output-dir', '-d', default='output', help='Папка для сохранения результата')
    parser.add_argument('--no-cleanup', action='store_true', help='Не удалять временные файлы')
    parser.add_argument('--sample', action='store_true', help='Создать пример JSON файла')
    parser.add_argument('--list', action='store_true', help='Показать доступные исходные видео')
    
    args = parser.parse_args()
    
    processor = VideoProcessor(args.source_dir, args.output_dir)
    
    if args.sample:
        processor.create_sample_json()
        return
    
    if args.list:
        processor.list_source_videos()
        return
    
    if not args.json:
        print("❌ Необходимо указать JSON файл")
        print("Использование: python video_processor.py --json clips.json")
        print("Дополнительные опции:")
        print("  --sample  - создать пример JSON файла")
        print("  --list    - показать доступные исходные видео")
        return
    
    success = processor.process_json_file(
        args.json, 
        args.output, 
        cleanup=not args.no_cleanup
    )
    
    if success:
        print("\n🎉 Обработка завершена успешно!")
    else:
        print("\n❌ Обработка завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()




