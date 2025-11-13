#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Extractor
Извлекает аудио из видео файлов и сохраняет в папку google_colab/audio
"""

import os
import sys
import argparse
from pathlib import Path
import re
from typing import List, Optional

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    print("❌ Ошибка: Библиотека moviepy не установлена!")
    print("Установите её командой: pip install moviepy")
    sys.exit(1)


class AudioExtractor:
    def __init__(self, base_output_dir="google_colab/audio"):
        """Инициализация извлекателя аудио"""
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Поддерживаемые форматы видео
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        
        # Поддерживаемые форматы аудио
        self.audio_extensions = {'.mp3', '.wav', '.aac', '.ogg', '.m4a'}
    
    def sanitize_filename(self, filename: str) -> str:
        """Очищает имя файла от недопустимых символов"""
        # Удаляем расширение
        name = Path(filename).stem
        
        # Заменяем недопустимые символы на подчеркивания
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        
        # Удаляем множественные подчеркивания
        name = re.sub(r'_+', '_', name)
        
        # Удаляем пробелы в начале и конце
        name = name.strip()
        
        # Если имя пустое, используем "unnamed"
        if not name:
            name = "unnamed"
        
        return name
    
    def get_video_files(self, input_path: Path) -> List[Path]:
        """Получает список видео файлов из указанного пути"""
        video_files = []
        
        if input_path.is_file():
            # Если это файл, проверяем его расширение
            if input_path.suffix.lower() in self.video_extensions:
                video_files.append(input_path)
            else:
                print(f"❌ Файл {input_path} не является видео файлом")
        elif input_path.is_dir():
            # Если это папка, ищем все видео файлы
            for ext in self.video_extensions:
                video_files.extend(input_path.glob(f"*{ext}"))
                video_files.extend(input_path.glob(f"*{ext.upper()}"))
        
        return video_files
    
    def extract_audio_from_video(self, video_path: Path, audio_format: str = "mp3", 
                                audio_bitrate: str = "192k", overwrite: bool = False) -> Optional[Path]:
        """Извлекает аудио из видео файла"""
        try:
            print(f"🎬 Обрабатываю: {video_path.name}")
            
            # Создаем имя аудио файла на основе названия видео
            folder_name = self.sanitize_filename(video_path.name)
            audio_filename = f"{folder_name}.{audio_format}"
            audio_path = self.base_output_dir / audio_filename
            
            # Проверяем, существует ли уже аудио файл
            if audio_path.exists() and not overwrite:
                print(f"⚠️ Аудио файл уже существует: {audio_path}")
                # В неинтерактивном режиме просто пропускаем
                if not sys.stdout.isatty():
                    print("⏭️ Пропускаю файл (неинтерактивный режим)")
                    return audio_path
                
                user_input = input("Перезаписать? (y/N): ").strip().lower()
                if user_input != 'y':
                    print("⏭️ Пропускаю файл")
                    return audio_path
            
            print(f"🎵 Извлекаю аудио в: {audio_path}")
            
            # Загружаем видео
            video = VideoFileClip(str(video_path))
            
            # Проверяем, есть ли аудио в видео
            if video.audio is None:
                print(f"❌ В видео {video_path.name} нет аудио дорожки")
                video.close()
                return None
            
            # Извлекаем аудио
            audio = video.audio
            
            # Сохраняем аудио
            if audio_format == "mp3":
                audio.write_audiofile(
                    str(audio_path), 
                    bitrate=audio_bitrate,
                    verbose=False, 
                    logger=None
                )
            else:
                audio.write_audiofile(
                    str(audio_path),
                    verbose=False, 
                    logger=None
                )
            
            # Закрываем файлы
            audio.close()
            video.close()
            
            # Получаем размер файла
            file_size = audio_path.stat().st_size / (1024 * 1024)  # MB
            
            print(f"✅ Аудио извлечено: {audio_path}")
            print(f"📊 Размер файла: {file_size:.1f} MB")
            
            return audio_path
            
        except Exception as e:
            print(f"❌ Ошибка при извлечении аудио из {video_path.name}: {e}")
            return None
    
    def extract_audio_batch(self, input_path: Path, audio_format: str = "mp3", 
                          audio_bitrate: str = "192k", overwrite: bool = False) -> List[Path]:
        """Извлекает аудио из нескольких видео файлов"""
        video_files = self.get_video_files(input_path)
        
        if not video_files:
            print(f"❌ Видео файлы не найдены в: {input_path}")
            return []
        
        print(f"📁 Найдено видео файлов: {len(video_files)}")
        
        extracted_files = []
        failed_files = []
        
        for i, video_path in enumerate(video_files, 1):
            print(f"\n📹 [{i}/{len(video_files)}] Обрабатываю: {video_path.name}")
            
            result = self.extract_audio_from_video(video_path, audio_format, audio_bitrate, overwrite)
            
            if result:
                extracted_files.append(result)
            else:
                failed_files.append(video_path)
        
        # Выводим итоговую статистику
        print(f"\n📊 Итоги обработки:")
        print(f"✅ Успешно извлечено: {len(extracted_files)}")
        print(f"❌ Ошибок: {len(failed_files)}")
        
        if failed_files:
            print(f"\n❌ Файлы с ошибками:")
            for file in failed_files:
                print(f"  - {file.name}")
        
        return extracted_files
    
    def list_extracted_audio(self):
        """Показывает список извлеченных аудио файлов"""
        print(f"\n📁 Извлеченные аудио файлы в папке {self.base_output_dir}:")
        
        if not self.base_output_dir.exists():
            print("❌ Папка не существует")
            return
        
        audio_files = []
        
        # Ищем все аудио файлы в папке
        for ext in self.audio_extensions:
            audio_files.extend(self.base_output_dir.glob(f"*{ext}"))
            audio_files.extend(self.base_output_dir.glob(f"*{ext.upper()}"))
        
        if audio_files:
            total_size = 0
            for audio_file in sorted(audio_files):
                size_mb = audio_file.stat().st_size / (1024 * 1024)
                print(f"🎵 {audio_file.name} ({size_mb:.1f} MB)")
                total_size += size_mb
            
            print(f"\n📊 Всего файлов: {len(audio_files)}")
            print(f"📊 Общий размер: {total_size:.1f} MB")
        else:
            print("❌ Аудио файлы не найдены")
    
    def interactive_mode(self):
        """Интерактивный режим"""
        print("🎵 Audio Extractor")
        print("=" * 40)
        
        while True:
            print("\nВыберите действие:")
            print("1. Извлечь аудио из видео файла")
            print("2. Извлечь аудио из папки с видео")
            print("3. Показать извлеченные аудио файлы")
            print("4. Настройки")
            print("5. Выход")
            
            choice = input("\nВведите номер (1-5): ").strip()
            
            if choice == "1":
                # Извлечение из одного файла
                file_path = input("Введите путь к видео файлу: ").strip()
                if not file_path:
                    continue
                
                video_path = Path(file_path)
                if not video_path.exists():
                    print(f"❌ Файл не найден: {video_path}")
                    continue
                
                self.extract_audio_from_video(video_path)
            
            elif choice == "2":
                # Извлечение из папки
                folder_path = input("Введите путь к папке с видео: ").strip()
                if not folder_path:
                    continue
                
                folder = Path(folder_path)
                if not folder.exists():
                    print(f"❌ Папка не найдена: {folder}")
                    continue
                
                self.extract_audio_batch(folder)
            
            elif choice == "3":
                # Показать извлеченные файлы
                self.list_extracted_audio()
            
            elif choice == "4":
                # Настройки
                print(f"\n⚙️ Текущие настройки:")
                print(f"📁 Папка для сохранения: {self.base_output_dir}")
                print(f"🎵 Формат аудио: mp3")
                print(f"🎵 Битрейт: 192k")
                
                new_dir = input(f"\nНовая папка для сохранения ({self.base_output_dir}): ").strip()
                if new_dir:
                    self.base_output_dir = Path(new_dir)
                    self.base_output_dir.mkdir(parents=True, exist_ok=True)
                    print(f"✅ Папка изменена на: {self.base_output_dir}")
            
            elif choice == "5":
                print("👋 До свидания!")
                break
            
            else:
                print("❌ Неверный выбор")


def main():
    parser = argparse.ArgumentParser(description='Audio Extractor - Извлекает аудио из видео файлов')
    parser.add_argument('input', nargs='?', help='Путь к видео файлу или папке с видео')
    parser.add_argument('--format', '-f', default='mp3', choices=['mp3', 'wav', 'aac', 'ogg'], 
                       help='Формат аудио (по умолчанию: mp3)')
    parser.add_argument('--bitrate', '-b', default='192k', 
                       help='Битрейт для MP3 (по умолчанию: 192k)')
    parser.add_argument('--output', '-o', default='google_colab/audio', 
                       help='Базовая папка для сохранения аудио')
    parser.add_argument('--list', '-l', action='store_true', 
                       help='Показать список извлеченных аудио файлов')
    parser.add_argument('--interactive', '-i', action='store_true', 
                       help='Интерактивный режим')
    parser.add_argument('--overwrite', '-y', action='store_true', 
                       help='Принудительно перезаписывать существующие файлы')
    
    args = parser.parse_args()
    
    extractor = AudioExtractor(args.output)
    
    if args.list:
        extractor.list_extracted_audio()
    elif args.interactive or not args.input:
        extractor.interactive_mode()
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ Путь не найден: {input_path}")
            return
        
        if input_path.is_file():
            extractor.extract_audio_from_video(input_path, args.format, args.bitrate, args.overwrite)
        else:
            # Для пакетной обработки передаем флаг перезаписи в extract_audio_batch
            extractor.extract_audio_batch(input_path, args.format, args.bitrate, args.overwrite)


if __name__ == "__main__":
    main()
