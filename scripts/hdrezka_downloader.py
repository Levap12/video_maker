#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HDRezka Video Downloader
Простой загрузчик видео с HDRezka
"""

import os
import sys
import requests
import argparse
from pathlib import Path
import time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from HdRezkaApi import HdRezkaApi
    from HdRezkaApi.search import HdRezkaSearch
except ImportError:
    print("❌ Ошибка: Библиотека HdRezkaApi не установлена!")
    print("Установите её командой: pip install HdRezkaApi")
    sys.exit(1)

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HDRezkaDownloader:
    def __init__(self, output_dir="downloads"):
        """Инициализация загрузчика"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Настройка сессии
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def download_file(self, url, filename, chunk_size=8192):
        """Скачивание файла"""
        try:
            print(f"📥 Скачиваю: {filename}")
            
            response = self.session.get(url, stream=True, verify=False, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            filepath = self.output_dir / filename
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rПрогресс: {progress:.1f}%", end='')
            
            print(f"\n✅ Файл скачан: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Ошибка скачивания: {e}")
            return None
    
    def search_content(self, query):
        """Поиск контента"""
        try:
            print(f"🔍 Ищу: {query}")
            search = HdRezkaSearch("https://hdrezka.ag/")
            results = search(query)
            
            if results:
                print(f"✅ Найдено: {len(results)} результатов")
                return results
            else:
                print("❌ Ничего не найдено")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return []
    
    def show_quality_menu(self, available_qualities):
        """Показывает меню выбора качества"""
        print("\n📋 Выберите качество:")
        for i, quality in enumerate(available_qualities, 1):
            print(f"{i}. {quality}")
        
        while True:
            try:
                choice = int(input("Введите номер качества: "))
                if 1 <= choice <= len(available_qualities):
                    return available_qualities[choice - 1]
                else:
                    print("❌ Неверный номер")
            except ValueError:
                print("❌ Введите число")
    
    def show_translator_menu(self, translators):
        """Показывает меню выбора озвучки"""
        if not translators:
            return None
            
        print("\n🎭 Выберите озвучку:")
        translator_list = list(translators.items())
        for i, (tid, translator) in enumerate(translator_list, 1):
            print(f"{i}. {translator['name']} (ID: {tid})")
        
        while True:
            try:
                choice = int(input("Введите номер озвучки (0 - пропустить): "))
                if choice == 0:
                    print("⚠️ Озвучка не выбрана, будет использована по умолчанию")
                    return None
                elif 1 <= choice <= len(translator_list):
                    selected_translator = translator_list[choice - 1]
                    print(f"✅ Выбрана озвучка: {selected_translator[1]['name']} (ID: {selected_translator[0]})")
                    return selected_translator[0]
                else:
                    print("❌ Неверный номер")
            except ValueError:
                print("❌ Введите число")
    
    def download_video(self, url, season=1, episode=1, quality=None, translator_id=None):
        """Скачивание видео"""
        try:
            print(f"\n🎬 Получаю информацию о видео...")
            rezka = HdRezkaApi(url)
            
            if not rezka.ok:
                print(f"❌ Ошибка: {rezka.exception}")
                return False
            
            print(f"📺 Название: {rezka.name}")
            print(f"🎭 Тип: {rezka.type}")
            
            if hasattr(rezka, 'rating') and rezka.rating:
                print(f"⭐ Рейтинг: {rezka.rating.value}")
            
            # Показываем доступных переводчиков
            if hasattr(rezka, 'translators') and rezka.translators and not translator_id:
                translator_id = self.show_translator_menu(rezka.translators)
            
            # Получаем поток
            print(f"\n🎬 Получаю поток...")
            
            try:
                if rezka.type == "tv_series":
                    print(f"📺 Получаю поток для сезон {season}, серия {episode}")
                    print("⏳ Пожалуйста, подождите... (может занять до 30 секунд)")
                    
                    if translator_id:
                        stream = rezka.getStream(season, episode, translation=translator_id)
                        print(f"✅ Получен поток с озвучкой {translator_id}")
                    else:
                        stream = rezka.getStream(season, episode)
                        print("✅ Получен поток")
                else:
                    print("🎬 Получаю поток для фильма")
                    print("⏳ Пожалуйста, подождите... (может занять до 30 секунд)")
                    
                    if translator_id:
                        stream = rezka.getStream(translation=translator_id)
                        print(f"✅ Получен поток с озвучкой {translator_id}")
                    else:
                        stream = rezka.getStream()
                        print("✅ Получен поток")
            except KeyboardInterrupt:
                print("\n❌ Операция прервана пользователем")
                return False
            except Exception as e:
                print(f"❌ Ошибка при получении потока: {e}")
                print("💡 Попробуйте:")
                print("   - Проверить интернет-соединение")
                print("   - Попробовать другую озвучку")
                print("   - Попробовать позже")
                return False
            
            if not stream:
                print("❌ Не удалось получить поток")
                return False
            
            # Показываем доступные качества
            available_qualities = list(stream.videos.keys())
            if not quality:
                quality = self.show_quality_menu(available_qualities)
            
            # Получаем ссылки
            video_urls = stream.videos[quality]
            if not video_urls:
                print(f"❌ Нет ссылок для {quality}")
                return False
            
            # Создаем имя файла
            safe_name = "".join(c for c in rezka.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if rezka.type == "tv_series":
                filename = f"{safe_name}_S{season:02d}E{episode:02d}_{quality}.mp4"
            else:
                filename = f"{safe_name}_{quality}.mp4"
            
            # Скачиваем
            print(f"\n🎬 Скачиваю в качестве {quality}")
            for i, video_url in enumerate(video_urls):
                print(f"Попытка {i+1}/{len(video_urls)}")
                result = self.download_file(video_url, filename)
                if result:
                    print("🎉 Видео успешно скачано!")
                    return True
                else:
                    print("Попытка неудачна, пробую следующую ссылку...")
                    time.sleep(2)
            
            print("❌ Не удалось скачать видео")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False
    
    def interactive_mode(self):
        """Интерактивный режим"""
        print("🎮 HDRezka Video Downloader")
        print("=" * 40)
        
        while True:
            print("\nВыберите действие:")
            print("1. Поиск и скачивание")
            print("2. Скачивание по URL")
            print("3. Выход")
            
            choice = input("\nВведите номер (1-3): ").strip()
            
            if choice == "1":
                # Поиск контента
                query = input("Введите поисковый запрос: ").strip()
                if not query:
                    continue
                    
                results = self.search_content(query)
                if not results:
                    continue
                
                print("\nРезультаты поиска:")
                for i, result in enumerate(results[:10], 1):
                    print(f"{i}. {result['title']}")
                    if 'rating' in result:
                        print(f"   Рейтинг: {result['rating']}")
                
                try:
                    choice_idx = int(input("\nВыберите номер для скачивания (0 - отмена): "))
                    if choice_idx == 0:
                        continue
                    elif 1 <= choice_idx <= len(results):
                        selected = results[choice_idx - 1]
                        print(f"\nВыбрано: {selected['title']}")
                        
                        # Всегда спрашиваем сезон и серию для сериалов
                        print("📺 Это сериал, укажите параметры:")
                        try:
                            season = int(input("Номер сезона (1): ") or "1")
                            episode = int(input("Номер серии (1): ") or "1")
                        except ValueError:
                            print("Использую значения по умолчанию: сезон 1, серия 1")
                            season = episode = 1
                        
                        # Скачиваем
                        self.download_video(selected['url'], season, episode)
                        
                except ValueError:
                    print("❌ Неверный номер")
            
            elif choice == "2":
                # Прямое скачивание по URL
                url = input("Введите URL: ").strip()
                if not url:
                    continue
                
                try:
                    season = int(input("Номер сезона (1): ") or "1")
                    episode = int(input("Номер серии (1): ") or "1")
                except ValueError:
                    season = episode = 1
                
                self.download_video(url, season, episode)
            
            elif choice == "3":
                print("👋 До свидания!")
                break
            
            else:
                print("❌ Неверный выбор")


def main():
    parser = argparse.ArgumentParser(description='HDRezka Video Downloader')
    parser.add_argument('--search', help='Поиск контента')
    parser.add_argument('--url', help='URL для скачивания')
    parser.add_argument('--season', '-s', type=int, default=1, help='Номер сезона')
    parser.add_argument('--episode', '-e', type=int, default=1, help='Номер серии')
    parser.add_argument('--quality', '-q', help='Качество видео')
    parser.add_argument('--translator', '-t', help='ID озвучки (номер из списка)')
    parser.add_argument('--output', '-o', default='downloads', help='Папка для сохранения')
    parser.add_argument('--interactive', '-i', action='store_true', help='Интерактивный режим')
    
    args = parser.parse_args()
    
    downloader = HDRezkaDownloader(args.output)
    
    if args.interactive or (not args.search and not args.url):
        downloader.interactive_mode()
    elif args.search:
        results = downloader.search_content(args.search)
        if results:
            print("\nРезультаты:")
            for i, result in enumerate(results[:5], 1):
                print(f"{i}. {result['title']}")
    elif args.url:
        downloader.download_video(args.url, args.season, args.episode, args.quality, args.translator)


if __name__ == "__main__":
    main()