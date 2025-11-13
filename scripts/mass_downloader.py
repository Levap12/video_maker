#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HDRezka Mass Downloader
Массовое скачивание всех серий Рик и Морти
"""

import os
import sys
import requests
import time
from pathlib import Path
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from HdRezkaApi import HdRezkaApi
except ImportError:
    print("❌ Ошибка: Библиотека HdRezkaApi не установлена!")
    print("Установите её командой: pip install HdRezkaApi")
    sys.exit(1)

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MassDownloader:
    def __init__(self, output_dir="downloads"):
        """Инициализация массового загрузчика"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Настройка сессии
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Конфигурация сериала
        self.url = "http://hdrezka.kim/cartoons/comedy/2136-rik-i-morti-2013-latest.html"
        self.translator_id = 66  # Сыендук
        self.quality = "360p"
        
        # Информация о сезонах
        self.seasons_info = {
            1: {"year": "2013–2014", "episodes": 11},
            2: {"year": "2015", "episodes": 10},
            3: {"year": "2017", "episodes": 10},
            4: {"year": "2019–2020", "episodes": 10},
            5: {"year": "2021", "episodes": 10},
            6: {"year": "2022", "episodes": 10},
            7: {"year": "2023", "episodes": 10},
            8: {"year": "2025", "episodes": 10}
        }
    
    def download_file(self, url, filename, chunk_size=8192):
        """Скачивание файла"""
        try:
            print(f"📥 Скачиваю: {filename}")
            
            response = self.session.get(url, stream=True, verify=False, timeout=60)
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
    
    def download_episode(self, season, episode):
        """Скачивание одной серии"""
        try:
            print(f"\n🎬 Скачиваю S{season:02d}E{episode:02d}...")
            
            # Получаем информацию о видео
            rezka = HdRezkaApi(self.url)
            
            if not rezka.ok:
                print(f"❌ Ошибка получения информации: {rezka.exception}")
                return False
            
            # Получаем поток
            print(f"⏳ Получаю поток для сезон {season}, серия {episode}...")
            try:
                stream = rezka.getStream(season, episode, translation=self.translator_id)
                print(f"✅ Получен поток с озвучкой {self.translator_id}")
            except Exception as e:
                print(f"❌ Ошибка получения потока: {e}")
                return False
            
            if not stream:
                print("❌ Не удалось получить поток")
                return False
            
            # Проверяем наличие нужного качества
            if self.quality not in stream.videos:
                print(f"❌ Качество {self.quality} недоступно")
                available_qualities = list(stream.videos.keys())
                print(f"Доступные качества: {available_qualities}")
                return False
            
            # Получаем ссылки
            video_urls = stream.videos[self.quality]
            if not video_urls:
                print(f"❌ Нет ссылок для {self.quality}")
                return False
            
            # Создаем имя файла
            safe_name = "Рик и Морти"
            filename = f"{safe_name}_S{season:02d}E{episode:02d}_{self.quality}.mp4"
            
            # Проверяем, не скачан ли уже файл
            filepath = self.output_dir / filename
            if filepath.exists():
                print(f"⏭️ Файл уже существует: {filename}")
                return True
            
            # Скачиваем
            print(f"🎬 Скачиваю в качестве {self.quality}")
            for i, video_url in enumerate(video_urls):
                print(f"Попытка {i+1}/{len(video_urls)}")
                result = self.download_file(video_url, filename)
                if result:
                    print("✅ Серия успешно скачана!")
                    return True
                else:
                    print("Попытка неудачна, пробую следующую ссылку...")
                    time.sleep(3)  # Пауза между попытками
            
            print("❌ Не удалось скачать серию")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при скачивании серии: {e}")
            return False
    
    def download_season(self, season):
        """Скачивание всего сезона"""
        if season not in self.seasons_info:
            print(f"❌ Неизвестный сезон: {season}")
            return False
        
        season_info = self.seasons_info[season]
        episodes_count = season_info["episodes"]
        year = season_info["year"]
        
        print(f"\n📺 СЕЗОН {season} ({year}) - {episodes_count} серий")
        print("=" * 50)
        
        success_count = 0
        failed_episodes = []
        
        for episode in range(1, episodes_count + 1):
            print(f"\n🎬 Серия {episode}/{episodes_count}")
            
            if self.download_episode(season, episode):
                success_count += 1
            else:
                failed_episodes.append(episode)
                print(f"❌ Не удалось скачать серию {episode}")
            
            # Пауза между сериями
            if episode < episodes_count:
                print("⏳ Пауза 5 секунд...")
                time.sleep(5)
        
        # Итоги сезона
        print(f"\n📊 ИТОГИ СЕЗОНА {season}:")
        print(f"✅ Успешно скачано: {success_count}/{episodes_count}")
        if failed_episodes:
            print(f"❌ Не скачаны серии: {failed_episodes}")
        
        return success_count == episodes_count
    
    def download_all_seasons(self):
        """Скачивание всех сезонов"""
        print("🎬 HDRezka Mass Downloader - Рик и Морти")
        print("=" * 60)
        print(f"🌐 URL: {self.url}")
        print(f"🎭 Озвучка: Сыендук (ID: {self.translator_id})")
        print(f"📺 Качество: {self.quality}")
        print(f"📁 Папка: {self.output_dir}")
        print("=" * 60)
        
        total_episodes = sum(info["episodes"] for info in self.seasons_info.values())
        print(f"📊 Всего серий для скачивания: {total_episodes}")
        
        # Показываем план
        print("\n📋 ПЛАН СКАЧИВАНИЯ:")
        for season, info in self.seasons_info.items():
            print(f"  Сезон {season} ({info['year']}): {info['episodes']} серий")
        
        # Подтверждение
        print(f"\n⚠️ ВНИМАНИЕ: Будет скачано {total_episodes} серий!")
        print("Это может занять много времени и места на диске.")
        
        confirm = input("\nПродолжить? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes', 'да', 'д']:
            print("❌ Скачивание отменено")
            return
        
        # Начинаем скачивание
        print("\n🚀 НАЧИНАЕМ СКАЧИВАНИЕ...")
        start_time = time.time()
        
        all_success = True
        for season in self.seasons_info.keys():
            if not self.download_season(season):
                all_success = False
            
            # Пауза между сезонами
            if season < max(self.seasons_info.keys()):
                print(f"\n⏳ Пауза 10 секунд перед следующим сезоном...")
                time.sleep(10)
        
        # Итоги
        end_time = time.time()
        duration = end_time - start_time
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        
        print(f"\n🎉 СКАЧИВАНИЕ ЗАВЕРШЕНО!")
        print(f"⏱️ Время: {hours}ч {minutes}м")
        print(f"📁 Файлы сохранены в: {self.output_dir}")
        
        if all_success:
            print("✅ Все серии успешно скачаны!")
        else:
            print("⚠️ Некоторые серии не удалось скачать")
    
    def download_specific_season(self, season):
        """Скачивание конкретного сезона"""
        if season not in self.seasons_info:
            print(f"❌ Неизвестный сезон: {season}")
            print(f"Доступные сезоны: {list(self.seasons_info.keys())}")
            return
        
        print(f"🎬 Скачивание сезона {season}")
        self.download_season(season)
    
    def show_status(self):
        """Показать статус скачанных файлов"""
        print("📊 СТАТУС СКАЧАННЫХ ФАЙЛОВ:")
        print("=" * 50)
        
        for season, info in self.seasons_info.items():
            episodes_count = info["episodes"]
            downloaded_count = 0
            
            print(f"\nСезон {season} ({info['year']}):")
            for episode in range(1, episodes_count + 1):
                filename = f"Рик и Морти_S{season:02d}E{episode:02d}_{self.quality}.mp4"
                filepath = self.output_dir / filename
                
                if filepath.exists():
                    size_mb = filepath.stat().st_size / (1024 * 1024)
                    print(f"  ✅ E{episode:02d}: {filename} ({size_mb:.1f} MB)")
                    downloaded_count += 1
                else:
                    print(f"  ❌ E{episode:02d}: НЕ СКАЧАН")
            
            print(f"  📊 Скачано: {downloaded_count}/{episodes_count}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='HDRezka Mass Downloader - Рик и Морти')
    parser.add_argument('--season', '-s', type=int, help='Скачать конкретный сезон (1-8)')
    parser.add_argument('--all', '-a', action='store_true', help='Скачать все сезоны')
    parser.add_argument('--status', action='store_true', help='Показать статус скачанных файлов')
    parser.add_argument('--output', '-o', default='downloads', help='Папка для сохранения')
    
    args = parser.parse_args()
    
    downloader = MassDownloader(args.output)
    
    if args.status:
        downloader.show_status()
    elif args.season:
        downloader.download_specific_season(args.season)
    elif args.all:
        downloader.download_all_seasons()
    else:
        print("🎬 HDRezka Mass Downloader - Рик и Морти")
        print("\nВыберите действие:")
        print("1. Скачать все сезоны")
        print("2. Скачать конкретный сезон")
        print("3. Показать статус")
        print("4. Выход")
        
        choice = input("\nВведите номер (1-4): ").strip()
        
        if choice == "1":
            downloader.download_all_seasons()
        elif choice == "2":
            season = int(input("Введите номер сезона (1-8): "))
            downloader.download_specific_season(season)
        elif choice == "3":
            downloader.show_status()
        elif choice == "4":
            print("👋 До свидания!")
        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
