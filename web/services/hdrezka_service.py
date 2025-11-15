#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с HdRezkaApi
Основной сервис приложения для работы с HDRezka
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from pathlib import Path

try:
    from HdRezkaApi import HdRezkaApi, HdRezkaSession
    from HdRezkaApi.types import TVSeries, Movie
    from HdRezkaApi.search import HdRezkaSearch
except ImportError:
    raise ImportError("HdRezkaApi не установлен! Установите: pip install HdRezkaApi")

logger = logging.getLogger(__name__)


class HdRezkaService:
    """Сервис для работы с HDRezka через HdRezkaApi"""
    
    def __init__(self, proxy: Optional[str] = None, proxy_type: str = 'socks5'):
        """
        Инициализация сервиса
        
        Args:
            proxy: Прокси в формате 'user:pass@host:port' или None
            proxy_type: Тип прокси - 'socks5' или 'https' (по умолчанию 'socks5')
        """
        self.proxy = self._parse_proxy(proxy, proxy_type) if proxy else None
        self.sessions = {}  # Кэш сессий для разных доменов
    
    def _parse_proxy(self, proxy_string: str, proxy_type: str = 'socks5') -> Dict[str, str]:
        """
        Парсит прокси из формата 'user:pass@host:port'
        в формат для HdRezkaApi
        
        Args:
            proxy_string: Строка прокси в формате 'user:pass@host:port'
            proxy_type: Тип прокси - 'socks5' или 'https'
        """
        pattern = r'^([^:]+):([^@]+)@([^:]+):(\d+)$'
        match = re.match(pattern, proxy_string.strip())
        
        if not match:
            raise ValueError(f"Неверный формат прокси: {proxy_string}. Ожидается: user:pass@host:port")
        
        user, password, host, port = match.groups()
        
        # Формируем URL в зависимости от типа прокси
        if proxy_type.lower() == 'https':
            proxy_url = f'http://{user}:{password}@{host}:{port}'
        else:  # socks5 по умолчанию
            proxy_url = f'socks5://{user}:{password}@{host}:{port}'
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def _get_origin_from_url(self, url: str) -> str:
        """Извлекает origin (схему + домен) из URL."""
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    def get_session(self, url: str) -> HdRezkaSession:
        """Получает или создает сессию HdRezkaSession для указанного URL."""
        origin = self._get_origin_from_url(url)
        if origin not in self.sessions:
            self.sessions[origin] = HdRezkaSession(
                proxy=self.proxy,
                origin=origin
            )
        return self.sessions[origin]
    
    def analyze_content(self, url: str) -> Dict:
        """
        Анализирует контент по URL и возвращает информацию
        """
        try:
            logger.info(f"Начало анализа контента: {url}")
            logger.info(f"Используется прокси: {bool(self.proxy)} ({self.proxy if self.proxy else 'Нет'})")
            
            session = self.get_session(url)
            logger.info(f"Сессия создана для origin: {self._get_origin_from_url(url)}")
            
            logger.info(f"Выполнение session.get({url})...")
            rezka = session.get(url)
            logger.info(f"session.get завершен. rezka.ok = {rezka.ok}")
            
            if not rezka.ok:
                error_msg = str(rezka.exception)
                logger.error(f"Ошибка rezka.ok=False: {error_msg}")
                logger.error(f"Тип исключения: {type(rezka.exception).__name__}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            logger.info(f"Успешно получен контент: {rezka.name}")
            
            result = {
                'success': True,
                'name': str(rezka.name) if rezka.name else 'Неизвестно',
                'type': str(rezka.type) if rezka.type else 'movie',
                'category': str(rezka.category) if hasattr(rezka, 'category') and rezka.category else None,
                'thumbnail': str(rezka.thumbnail) if hasattr(rezka, 'thumbnail') and rezka.thumbnail else None,
                'rating': float(rezka.rating.value) if hasattr(rezka, 'rating') and rezka.rating else None,
                'rating_votes': int(rezka.rating.votes) if hasattr(rezka, 'rating') and rezka.rating else None,
                'translators': self._format_translators(rezka.translators) if hasattr(rezka, 'translators') else {},
            }
            
            rezka_type_str = str(rezka.type) if rezka.type else ''
            if rezka_type_str in ['tv_series', 'TVSeries'] or 'series' in rezka_type_str.lower() or rezka.type == TVSeries:
                logger.info(f"Начало извлечения информации о сезонах/эпизодах...")
                import time
                start_time = time.time()
                series_info = self._extract_series_info_from_api(rezka)
                elapsed = time.time() - start_time
                logger.info(f"Извлечение информации о сезонах завершено за {elapsed:.2f} секунд")
                result['series_info'] = series_info if series_info else {}
            
            logger.info(f"Анализ контента завершен успешно")
            return result
            
        except Exception as e:
            logger.exception(f"ИСКЛЮЧЕНИЕ в analyze_content: {e}")
            logger.error(f"Тип исключения: {type(e).__name__}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_translators(self, translators: Dict) -> Dict:
        """Форматирует список озвучек для удобного использования"""
        if not translators:
            return {}
        
        formatted = {}
        for tid, translator in translators.items():
            translator_id = str(tid) if tid else ''
            translator_name = str(translator.get('name', f'Озвучка {tid}')) if isinstance(translator, dict) else str(translator)
            
            formatted[translator_id] = {
                'id': translator_id,
                'name': translator_name
            }
        
        return formatted
    
    def _extract_series_info_from_api(self, rezka) -> Dict:
        """
        Извлекает информацию о сезонах и сериях из HdRezkaApi.
        Приоритет: episodesInfo > seriesInfo.
        """
        series_info = {}
        try:
            logger.debug("Проверка hasattr(rezka, 'episodesInfo')...")
            if hasattr(rezka, 'episodesInfo') and rezka.episodesInfo:
                logger.debug(f"episodesInfo найден, длина: {len(rezka.episodesInfo) if rezka.episodesInfo else 0}")
                for season_data in rezka.episodesInfo:
                    if isinstance(season_data, dict):
                        season_num = season_data.get('season')
                        episodes_list = season_data.get('episodes', [])
                        if season_num and isinstance(episodes_list, list):
                            ep_numbers = [int(ep.get('episode')) for ep in episodes_list if isinstance(ep, dict) and ep.get('episode')]
                            if ep_numbers:
                                max_episode = max(ep_numbers)
                                series_info[str(season_num)] = {
                                    'episodes': max_episode,
                                    'episode_list': list(range(1, max_episode + 1))
                                }
                if series_info:
                    logger.debug(f"seriesInfo извлечен из episodesInfo: {len(series_info)} сезонов")
                    return series_info

            logger.debug("Проверка hasattr(rezka, 'seriesInfo')...")
            if hasattr(rezka, 'seriesInfo') and rezka.seriesInfo:
                logger.debug(f"seriesInfo найден, количество переводов: {len(rezka.seriesInfo) if rezka.seriesInfo else 0}")
                seasons_data = {}
                for translator_info in rezka.seriesInfo.values():
                    if isinstance(translator_info, dict):
                        seasons = translator_info.get('seasons', {})
                        episodes = translator_info.get('episodes', {})
                        if isinstance(seasons, dict) and isinstance(episodes, dict):
                            for season_key, season_name in seasons.items():
                                season_num = int(season_key)
                                if season_num not in seasons_data:
                                    seasons_data[season_num] = set()
                                
                                if season_key in episodes and isinstance(episodes[season_key], dict):
                                    for ep_key in episodes[season_key].keys():
                                        seasons_data[season_num].add(int(ep_key))

                for season_num, episode_set in seasons_data.items():
                    if episode_set:
                        max_episode = max(episode_set)
                        series_info[str(season_num)] = {
                            'episodes': max_episode,
                            'episode_list': list(range(1, max_episode + 1))
                        }
                if series_info:
                    logger.debug(f"seriesInfo извлечен: {len(series_info)} сезонов")
                    return series_info

        except Exception as e:
            logger.warning(f"Ошибка при извлечении seriesInfo: {e}")
            return {}
            
        return series_info
    
    def get_available_qualities(self, url: str, season: Optional[int] = None, 
                                episode: Optional[int] = None, 
                                translator_id: Optional[int] = None) -> List[str]:
        """Получает список доступных качеств видео"""
        try:
            session = self.get_session(url)
            rezka = session.get(url)
            
            if not rezka.ok:
                return []
            
            stream = rezka.getStream(season, episode, translation=translator_id) if season and episode else rezka.getStream(translation=translator_id)
            
            if stream and hasattr(stream, 'videos'):
                return list(stream.videos.keys())
            
            return []
            
        except Exception:
            return []
    
    def download_video(self, url: str, output_path: Path, season: Optional[int] = None,
                      episode: Optional[int] = None, quality: str = '360p',
                      translator_id: Optional[int] = None,
                      progress_callback: Optional[callable] = None) -> Tuple[bool, Optional[str]]:
        """Скачивает видео с HDRezka"""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        try:
            session = self.get_session(url)
            rezka = session.get(url)
            
            if not rezka.ok:
                return False, str(rezka.exception)
            
            if progress_callback:
                progress_callback(10, "Получение потока видео...")
            
            try:
                stream = rezka.getStream(season, episode, translation=translator_id) if season and episode else rezka.getStream(translation=translator_id)
            except Exception as e:
                return False, f"Ошибка получения потока: {str(e)}"
            
            if not stream or not hasattr(stream, 'videos'):
                return False, "Не удалось получить поток видео"
            
            if quality not in stream.videos:
                available = list(stream.videos.keys())
                return False, f"Качество {quality} недоступно. Доступные: {', '.join(available)}"
            
            video_urls = stream.videos[quality]
            if not video_urls:
                return False, f"Нет ссылок для качества {quality}"
            
            if progress_callback:
                progress_callback(20, f"Начало скачивания из {len(video_urls)} источников...")
            
            download_session = requests.Session()
            if self.proxy:
                download_session.proxies = self.proxy
            
            retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry_strategy)
            download_session.mount("http://", adapter)
            download_session.mount("https://", adapter)
            download_session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            
            last_error = None
            for i, video_url in enumerate(video_urls):
                try:
                    if progress_callback:
                        progress_callback(20 + (i * 10), f"Попытка {i+1}/{len(video_urls)}: скачивание...")
                    
                    response = download_session.get(video_url, stream=True, timeout=60)
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0 and progress_callback:
                                    percent = 20 + (i * 10) + int((downloaded / total_size) * 10)
                                    progress_callback(percent, f"Скачивание: {downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB")
                    
                    if progress_callback:
                        progress_callback(100, "Скачивание завершено!")
                    return True, None
                    
                except Exception as e:
                    last_error = str(e)
                    continue
            
            return False, f"Не удалось скачать с всех источников. Последняя ошибка: {last_error}"
            
        except Exception as e:
            return False, str(e)
    
    def search_content(self, query: str, limit: int = 10, base_url: str = "https://hdrezka.ag/") -> List[Dict]:
        """Поиск контента на HDRezka"""
        try:
            search = HdRezkaSearch(base_url, proxy=self.proxy)
            results = search(query)
            
            if not results:
                return []
            
            formatted_results = []
            for result in results[:limit]:
                rating = result.get('rating')
                if rating is not None:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None
                
                formatted_results.append({
                    'title': str(result.get('title', '')),
                    'url': str(result.get('url', '')),
                    'rating': rating
                })
            
            return formatted_results
            
        except Exception:
            return []
