#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Shorts Creator
Простой скрипт для конвертации видео в формат 9:16 для YouTube Shorts
"""

import os
import sys
import numpy as np
from pathlib import Path
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, TextClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
import tempfile

# Попытка импортировать OpenCV для оптимизированного размытия
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ShortsCreator:
    def __init__(self, input_dir="clips", output_dir="shorts_output", height_scale=2.0, banner_path=None, banner_offset=100, watermark_text=None, watermark_font_size=72, watermark_bottom_offset=180, watermark_color="gray"):
        """Инициализация создателя Shorts"""
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.height_scale = height_scale  # Коэффициент увеличения высоты
        self.banner_path = banner_path  # Путь к баннеру
        self.banner_offset = banner_offset  # Отступ сверху для баннера
        self.watermark_text = watermark_text  # Текст водяного знака
        self.watermark_font_size = watermark_font_size  # Размер шрифта водяного знака
        self.watermark_bottom_offset = watermark_bottom_offset  # Отступ снизу для водяного знака
        self.watermark_color = watermark_color  # Цвет водяного знака
        
        # Создаем папку для выходных файлов
        self.output_dir.mkdir(exist_ok=True)
        
        # Целевое разрешение для YouTube Shorts (9:16) - 720p
        self.target_width = 720
        self.target_height = 1280
    
    def create_text_image(self, text, font_size, color):
        """Создает изображение с текстом используя PIL"""
        try:
            # Создаем изображение с прозрачным фоном
            img_width = len(text) * (font_size // 2) + 40
            img_height = font_size + 20
            
            # Создаем изображение с альфа-каналом
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Определяем цвет текста
            color_map = {
                "white": (255, 255, 255, 128),
                "black": (0, 0, 0, 128),
                "red": (255, 0, 0, 128),
                "blue": (0, 0, 255, 128),
                "green": (0, 255, 0, 128),
                "yellow": (255, 255, 0, 128),
                "orange": (255, 165, 0, 128),
                "purple": (128, 0, 128, 128),
                "gray": (128, 128, 128, 128),
                "grey": (128, 128, 128, 128)
            }
            
            text_color = color_map.get(color.lower(), (255, 255, 255, 255))
            
            # Пробуем загрузить шрифт
            try:
                # Пробуем использовать системный шрифт
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    # Пробуем другой системный шрифт
                    font = ImageFont.truetype("calibri.ttf", font_size)
                except:
                    # Используем стандартный шрифт
                    font = ImageFont.load_default()
            
            # Получаем размеры текста
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Центрируем текст
            x = (img_width - text_width) // 2
            y = (img_height - text_height) // 2
            
            # Рисуем черную обводку
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
            
            # Рисуем основной текст
            draw.text((x, y), text, font=font, fill=text_color)
            
            return img
            
        except Exception as e:
            print(f"   ⚠️ Ошибка создания текстового изображения: {e}")
            return None
    
    def create_watermark(self, duration):
        """Создает водяной знак в виде текста используя PIL"""
        if not self.watermark_text:
            return None
        
        try:
            # Создаем текстовое изображение с помощью PIL
            text_img = self.create_text_image(self.watermark_text, self.watermark_font_size, self.watermark_color)
            
            if text_img is None:
                print(f"   ❌ Не удалось создать текстовое изображение")
                return None
            
            # Сохраняем временное изображение
            temp_img_path = tempfile.mktemp(suffix='.png')
            text_img.save(temp_img_path, 'PNG')
            
            # Создаем ImageClip из временного файла
            watermark = ImageClip(temp_img_path).set_duration(duration)
            
            # Позиционируем водяной знак снизу с отступом
            watermark_y = self.target_height - self.watermark_bottom_offset - watermark.h
            watermark_positioned = watermark.set_position(("center", watermark_y))
            
            print(f"   🏷️ Добавлен текстовый водяной знак: '{self.watermark_text}'")
            print(f"   📏 Размер шрифта: {self.watermark_font_size}")
            print(f"   🎨 Цвет: {self.watermark_color}")
            print(f"   📍 Позиция: y={watermark_y} (отступ снизу: {self.watermark_bottom_offset}px)")
            
            # Удаляем временный файл после создания клипа
            try:
                os.unlink(temp_img_path)
            except:
                pass
            
            return watermark_positioned
            
        except Exception as e:
            print(f"   ❌ Ошибка создания текстового водяного знака: {e}")
            return None
    
    def convert_to_shorts_format(self, input_path, output_path):
        """Конвертирует видео в формат 9:16 для YouTube Shorts с размытым фоном
        
        Args:
            input_path: Путь к входному видео файлу
            output_path: Путь к выходному файлу
            
        Returns:
            Path: путь к созданному файлу при успехе, None при ошибке
        """
        def get_optimal_codec_for_amd():
            """Определяет оптимальный кодек - использует libx264 с оптимизацией"""
            # Используем libx264 с оптимизированными параметрами
            return 'libx264', 'fast', 8, "4000k"  # H.264 программный с 8 потоками
        
        try:
            print(f"🎬 Обрабатываю: {input_path.name}")
            
            # Загружаем видео
            video = VideoFileClip(str(input_path))
            original_width, original_height = video.size
            aspect_ratio = original_width / original_height
            
            print(f"   📐 Исходное разрешение: {original_width}x{original_height}")
            print(f"   📊 Соотношение сторон: {aspect_ratio:.2f}")
            
            # Размытый фон (на весь кадр 9:16) - оптимизированная версия
            background_video = video.resize((self.target_width, self.target_height))
            
            if CV2_AVAILABLE:
                # Оптимизированный вариант с OpenCV и downscale-blur-upscale техникой
                # Коэффициент уменьшения: 2x (720x1280 → 360x640) - сохраняем больше деталей для качества как в старой версии
                DOWNSCALE_FACTOR = 2
                TARGET_W, TARGET_H = self.target_width, self.target_height
                SMALL_W, SMALL_H = TARGET_W // DOWNSCALE_FACTOR, TARGET_H // DOWNSCALE_FACTOR
                BLUR_KERNEL = (21, 21)  # Эквивалент radius=20 на полном разрешении
                
                def fast_blur_frame(frame):
                    """
                    Оптимизированная функция размытия с использованием OpenCV и downscaling.
                    Ожидает frame как numpy array.
                    """
                    # 1. Уменьшаем кадр (очень быстрая операция)
                    small_frame = cv2.resize(frame, (SMALL_W, SMALL_H), interpolation=cv2.INTER_LINEAR)
                    
                    # 2. Размываем маленький кадр (очень быстрая операция)
                    # Используем sigma для более точного контроля размытия (эквивалент radius=20)
                    blurred_small = cv2.GaussianBlur(small_frame, BLUR_KERNEL, sigmaX=7, sigmaY=7)
                    
                    # 3. Увеличиваем размытый кадр до оригинала (очень быстрая операция)
                    # Используем INTER_CUBIC для более плавного результата
                    blurred_frame = cv2.resize(blurred_small, (TARGET_W, TARGET_H), interpolation=cv2.INTER_CUBIC)
                    
                    return blurred_frame
                
                blurred_background = background_video.fl_image(fast_blur_frame)
                
            else:
                # Fallback на оптимизированный PIL вариант (если OpenCV недоступен)
                # Уменьшаем разрешение для размытия (в 2 раза)
                small_width = self.target_width // 2
                small_height = self.target_height // 2
                background_video_small = video.resize((small_width, small_height))
                
                def blur_frame_pil(frame):
                    """
                    Оптимизированная функция размытия с PIL (fallback вариант).
                    Работает быстрее оригинала за счет уменьшения разрешения.
                    """
                    from PIL import Image, ImageFilter
                    
                    # Конвертируем numpy array в PIL Image
                    pil_image = Image.fromarray(frame)
                    
                    # Применяем размытие с радиусом близким к оригинальному (radius=20)
                    # На уменьшенном разрешении используем radius=18 для эквивалентного эффекта
                    blurred_pil = pil_image.filter(ImageFilter.GaussianBlur(radius=18))
                    
                    # Конвертируем обратно в numpy array
                    blurred_frame = np.array(blurred_pil)
                    
                    return blurred_frame
                
                # Размываем в маленьком разрешении
                blurred_small = background_video_small.fl_image(blur_frame_pil)
                
                # Увеличиваем обратно до полного размера (быстрая операция)
                blurred_background = blurred_small.resize((self.target_width, self.target_height))
            
            # Масштабируем видео по ширине кадра (чтобы не было отступов по бокам)
            new_width = self.target_width
            new_height = int(new_width / aspect_ratio)
            
            # Применяем коэффициент увеличения высоты
            if self.height_scale != 1.0:
                new_height = int(new_height * self.height_scale)
                new_width = int(new_height * aspect_ratio)
                resized_video = video.resize(height=new_height)
                print(f"   🔍 Увеличение высоты: {self.height_scale}x")
            else:
                resized_video = video.resize(width=new_width)
            
            # Если видео стало выше, чем нужно — центрируем его
            y_offset = (self.target_height - new_height) // 2
            
            print(f"   📏 Размер видео: {new_width}x{new_height}")
            print(f"   📍 Смещение по Y: {y_offset}")
            
            # Подготавливаем слои для композиции
            layers = [blurred_background, resized_video.set_position(("center", y_offset))]
            
            # Добавляем водяной знак, если указан
            watermark = self.create_watermark(video.duration)
            if watermark:
                layers.append(watermark)
            
            # Добавляем баннер, если указан
            if self.banner_path and Path(self.banner_path).exists():
                try:
                    banner_video = VideoFileClip(str(self.banner_path))
                    
                    # Масштабируем баннер по ширине кадра
                    banner_width = self.target_width
                    banner_height = int(banner_width * (banner_video.h / banner_video.w))
                    banner_resized = banner_video.resize(width=banner_width)
                    
                    # Растягиваем баннер на всю длительность основного видео
                    video_duration = video.duration
                    banner_duration = banner_resized.duration
                    
                    print(f"   📊 Длительность видео: {video_duration:.2f} сек")
                    print(f"   📊 Длительность баннера: {banner_duration:.2f} сек")
                    
                    # Создаем баннер нужной длительности
                    if banner_duration < video_duration:
                        # Зацикливаем баннер через повторение
                        loops_needed = int(video_duration / banner_duration) + 1
                        banner_clips = []
                        for i in range(loops_needed):
                            banner_clips.append(banner_resized)
                        from moviepy.editor import concatenate_videoclips
                        banner_stretched = concatenate_videoclips(banner_clips).subclip(0, video_duration)
                        print(f"   🔄 Баннер зациклен через конкатенацию ({loops_needed} раз)")
                    else:
                        # Если баннер длиннее, обрезаем его
                        banner_stretched = banner_resized.subclip(0, video_duration)
                        print(f"   ✂️ Баннер обрезан до {video_duration:.2f} сек")
                    
                    # Создаем задержку в 5 секунд и обрезаем точно по длительности видео
                    banner_delayed = banner_stretched.set_start(5).subclip(5, video_duration)
                    
                    # Позиционируем баннер сверху с отступом
                    banner_y = self.banner_offset
                    layers.append(banner_delayed.set_position(("center", banner_y)))
                    
                    print(f"   🏷️ Добавлен баннер: {Path(self.banner_path).name}")
                    print(f"   📍 Позиция баннера: y={banner_y}")
                    print(f"   ⏱️ Баннер появляется через 5 секунд")
                    print(f"   🔄 Баннер растянут на всю длительность видео")
                    
                except Exception as e:
                    print(f"   ⚠️ Ошибка загрузки баннера: {e}")
            
            # Компоновка: фон, основное видео, водяной знак (если есть), баннер (если есть)
            final_video = CompositeVideoClip(layers, size=(self.target_width, self.target_height))
            
            print(f"   🎯 Финальное разрешение: {self.target_width}x{self.target_height}")
            print(f"   🌫️ Добавлен размытый фон из самого видео")
            
            # Сохраняем результат
            print(f"   💾 Сохраняю: {output_path}")
            
            # Определяем оптимальный кодек для системы
            codec, preset, threads, bitrate = get_optimal_codec_for_amd()
            print(f"   🎬 Используется кодек: {codec}, preset: {preset}, bitrate: {bitrate}")
            
            final_video.write_videofile(
                str(output_path),
                codec=codec,
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None,
                bitrate=bitrate,
                preset=preset,
                threads=threads
            )
            
            # Закрываем клипы
            video.close()
            resized_video.close()
            background_video.close()
            blurred_background.close()
            if watermark:
                watermark.close()
            if self.banner_path and Path(self.banner_path).exists():
                try:
                    banner_video.close()
                    banner_resized.close()
                    banner_stretched.close()
                    banner_delayed.close()
                except:
                    pass
            final_video.close()
            
            print(f"   ✅ Готово: {output_path}")
            
            # Проверяем, что файл действительно создан
            if output_path.exists():
                return output_path
            else:
                print(f"   ⚠️ Файл не был создан: {output_path}")
                return None
            
        except Exception as e:
            print(f"   ❌ Ошибка при обработке {input_path.name}: {e}")
            return None


    
    def process_single_file(self, input_file):
        """Обрабатывает один файл
        
        Returns:
            Path: путь к созданному файлу при успехе, None при ошибке
        """
        if not input_file.exists():
            print(f"❌ Файл не найден: {input_file}")
            return None
        
        # Создаем имя выходного файла
        output_filename = f"shorts_{input_file.stem}.mp4"
        output_path = self.output_dir / output_filename
        
        result = self.convert_to_shorts_format(input_file, output_path)
        # convert_to_shorts_format теперь возвращает Path или None
        return result
    
    def process_all_clips(self):
        """Обрабатывает все видео файлы в папке clips"""
        if not self.input_dir.exists():
            print(f"❌ Папка с клипами не найдена: {self.input_dir}")
            return False
        
        # Находим все видео файлы
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(self.input_dir.glob(f"*{ext}"))
        
        if not video_files:
            print(f"❌ Не найдено видео файлов в {self.input_dir}")
            return False
        
        print(f"📁 Найдено {len(video_files)} видео файлов")
        print(f"📂 Выходная папка: {self.output_dir}")
        print("-" * 50)
        
        successful = 0
        failed = 0
        
        # Обрабатываем каждый файл
        for i, video_file in enumerate(sorted(video_files), 1):
            print(f"\n[{i}/{len(video_files)}]")
            result = self.process_single_file(video_file)
            if result is not None:  # Если вернулся путь к файлу
                successful += 1
            else:
                failed += 1
        
        # Итоговая статистика
        print("\n" + "=" * 50)
        print(f"📊 Результаты обработки:")
        print(f"✅ Успешно обработано: {successful}")
        print(f"❌ Ошибок: {failed}")
        print(f"📁 Результаты сохранены в: {self.output_dir}")
        
        return successful > 0


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='YouTube Shorts Creator - конвертация в формат 9:16')
    parser.add_argument('--input', '-i', help='Путь к входному видео файлу (если не указан, обрабатывает все из папки clips)')
    parser.add_argument('--output', '-o', default='shorts_output', help='Папка для сохранения результатов')
    parser.add_argument('--input-dir', '-d', default='clips', help='Папка с исходными клипами')
    parser.add_argument('--height-scale', '-s', type=float, default=2.0, help='Коэффициент увеличения высоты видео (по умолчанию 2.0)')
    parser.add_argument('--banner', '-b', help='Путь к баннеру (видео файл)')
    parser.add_argument('--banner-offset', '-bo', type=int, default=100, help='Отступ сверху для баннера в пикселях (по умолчанию 100)')
    parser.add_argument('--watermark-text', '-wt', help='Текст водяного знака')
    parser.add_argument('--watermark-font-size', '-wfs', type=int, default=72, help='Размер шрифта водяного знака (по умолчанию 72)')
    parser.add_argument('--watermark-bottom-offset', '-wbo', type=int, default=180, help='Отступ снизу для водяного знака в пикселях (по умолчанию 180)')
    parser.add_argument('--watermark-color', '-wc', default='gray', help='Цвет водяного знака: white, black, red, blue, green, yellow, orange, purple, gray (по умолчанию gray)')
    
    args = parser.parse_args()
    
    # Создаем экземпляр создателя Shorts
    creator = ShortsCreator(
        args.input_dir, 
        args.output, 
        args.height_scale, 
        args.banner, 
        args.banner_offset,
        args.watermark_text,
        args.watermark_font_size,
        args.watermark_bottom_offset,
        args.watermark_color
    )
    
    if args.input:
        # Обрабатываем конкретный файл
        input_path = Path(args.input)
        if not input_path.is_file():
            print(f"❌ Указанный путь не является файлом: {args.input}")
            sys.exit(1)
        result = creator.process_single_file(input_path)
        success = result is not None  # Проверяем, что вернулся путь к файлу
    else:
        # Обрабатываем все файлы из папки clips
        success = creator.process_all_clips()
    
    if success:
        print("\n🎉 Обработка завершена успешно!")
    else:
        print("\n❌ Обработка завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
