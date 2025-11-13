#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис автоматизации Google Colab через Camoufox для выполнения транскрибации.
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
from camoufox.sync_api import NewBrowser
from web.services.profile_loader import load_profile_from_db, get_launch_options_from_profile

logger = logging.getLogger(__name__)


class ColabAutomation:
    """Класс для автоматизации работы с Google Colab через Camoufox."""
    
    def __init__(self, 
                 profile_path: Optional[Path] = None, 
                 headless: bool = False,
                 db_path: Optional[str] = None,
                 profile_id: Optional[int] = None,
                 profile_name: Optional[str] = None):
        """
        Инициализация автоматизации Colab.
        
        Args:
            profile_path: Путь к профилю Camoufox. Если None, используется профиль из БД или по умолчанию.
            headless: Запускать браузер в headless режиме (без GUI). Переопределяется параметрами из БД.
            db_path: Путь к базе данных с профилями.
            profile_id: ID профиля в БД (приоритетнее чем profile_name).
            profile_name: Имя профиля в БД.
        """
        self.profile_path = profile_path
        self.headless = headless
        self.db_path = db_path
        self.profile_id = profile_id
        self.profile_name = profile_name
        self.profile_data = None
        self.browser = None  # Будет объект браузера Playwright
        self.playwright = None  # Сохраняем объект Playwright
        self.page = None
        self.is_running = False
        
        # Загружаем профиль из БД, если указан путь к БД
        if self.db_path:
            self.profile_data = load_profile_from_db(
                self.db_path, 
                profile_id=self.profile_id, 
                profile_name=self.profile_name
            )
            if self.profile_data:
                # Используем user_data_dir из профиля
                user_data_dir = self.profile_data.get('user_data_dir')
                if user_data_dir and not self.profile_path:
                    self.profile_path = Path(user_data_dir)
                    logger.info(f"Используется user_data_dir из профиля: {self.profile_path}")
                # Переопределяем headless из профиля, если не указан явно
                if self.profile_data.get('headless') is not None:
                    self.headless = bool(self.profile_data['headless'])
        
    def start_browser(self) -> bool:
        """
        Запускает браузер Camoufox с указанным профилем.
        
        Returns:
            True если браузер успешно запущен, False иначе.
        """
        try:
            logger.info("Запуск браузера Camoufox...")
            
            # Получаем параметры запуска из профиля БД или используем базовые
            if self.profile_data:
                browser_args = get_launch_options_from_profile(self.profile_data)
                logger.info(f"Используются параметры из профиля: {self.profile_data.get('name', 'Unknown')}")
            else:
                browser_args = {
                    'headless': self.headless
                }
            
            # Убеждаемся, что headless установлен правильно
            if 'headless' not in browser_args:
                browser_args['headless'] = self.headless
            
            # Если указан профиль (user_data_dir), используем его для сохранения сессии
            if self.profile_path and self.profile_path.exists():
                logger.info(f"Используется профиль браузера: {self.profile_path}")
                # Camoufox использует user_data_dir через persistent_context
                # Но для Camoufox нужно использовать другой подход - через launch_options
                # Пока просто логируем, что профиль найден
            elif self.profile_path:
                logger.warning(f"Профиль указан, но не найден: {self.profile_path}")
            
            if browser_args.get('headless'):
                logger.info("Браузер запущен в headless режиме")
            else:
                logger.info("Браузер запущен в обычном режиме (с GUI)")
            
            # Инициализируем Playwright
            self.playwright = sync_playwright().start()
            
            # Если указан user_data_dir, используем launch_persistent_context напрямую
            if self.profile_path and self.profile_path.exists():
                # Используем launch_persistent_context для сохранения сессии
                # Получаем launch_options из Camoufox
                from camoufox import launch_options
                
                # Генерируем опции запуска из параметров профиля
                launch_opts = launch_options(**browser_args)
                launch_opts['user_data_dir'] = str(self.profile_path)
                
                logger.info(f"Используется persistent_context с user_data_dir: {self.profile_path}")
                
                # Запускаем браузер с persistent_context
                self.browser = self.playwright.firefox.launch_persistent_context(**launch_opts)
            else:
                # Используем NewBrowser без persistent_context
                self.browser = NewBrowser(self.playwright, **browser_args)
            
            self.page = self.browser.new_page()
            self.is_running = True
            
            logger.info("Браузер успешно запущен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при запуске браузера: {e}")
            return False
    
    def open_colab(self, url: str) -> bool:
        """
        Открывает Colab ноутбук по указанному URL.
        
        Args:
            url: URL Colab ноутбука.
            
        Returns:
            True если ноутбук успешно открыт, False иначе.
        """
        if not self.is_running or not self.page:
            logger.error("Браузер не запущен. Вызовите start_browser() сначала.")
            return False
        
        try:
            logger.info(f"Открытие Colab ноутбука: {url}")
            self.page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(3)  # Даем время на загрузку страницы
            logger.info("Colab ноутбук успешно открыт")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при открытии Colab ноутбука: {e}")
            return False
    
    def run_transcription_script(self, selectors: Dict[str, str]) -> bool:
        """
        Выполняет скрипт транскрибации в Colab, используя переданные селекторы.
        
        Args:
            selectors: Словарь с селекторами для навигации и запуска скрипта.
                      Формат: {
                          'run_button': 'селектор кнопки запуска',
                          'cell_id': 'ID ячейки (опционально)',
                          ...
                      }
        
        Returns:
            True если скрипт успешно запущен, False иначе.
        """
        if not self.is_running or not self.page:
            logger.error("Браузер не запущен. Вызовите start_browser() сначала.")
            return False
        
        try:
            logger.info("Запуск скрипта транскрибации...")
            
            # Определяем селектор кнопки запуска
            run_button_selector = selectors.get('run_button', 'colab-run-button')
            
            # Если указан ID ячейки, используем более точный селектор
            if 'cell_id' in selectors:
                cell_id = selectors['cell_id']
                # Ищем кнопку внутри конкретной ячейки
                run_button_selector = f'#{cell_id} colab-run-button'
                logger.info(f"Используется ячейка с ID: {cell_id}")
            
            logger.info(f"Поиск кнопки запуска: {run_button_selector}")
            
            # Ждем появления кнопки и нажимаем на неё
            try:
                # Ждем, пока страница полностью загрузится
                self.page.wait_for_load_state("networkidle", timeout=10000)
                time.sleep(2)  # Дополнительная пауза для полной загрузки Colab
                
                # Ищем кнопку запуска
                button = self.page.wait_for_selector(run_button_selector, timeout=15000, state="visible")
                
                if not button:
                    # Пробуем альтернативный селектор
                    logger.info("Пробуем альтернативный селектор...")
                    button = self.page.query_selector('colab-run-button')
                
                if button:
                    logger.info("Кнопка запуска найдена, нажимаем...")
                    # Прокручиваем к кнопке, если нужно
                    button.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    # Нажимаем на кнопку
                    button.click()
                    logger.info("Кнопка запуска нажата!")
                    time.sleep(2)  # Даем время на запуск ячейки
                    return True
                else:
                    logger.error("Кнопка запуска не найдена")
                    return False
                    
            except Exception as e:
                logger.error(f"Ошибка при поиске/нажатии кнопки: {e}")
                # Пробуем альтернативный способ - через JavaScript
                try:
                    logger.info("Пробуем запустить через JavaScript...")
                    self.page.evaluate("""
                        () => {
                            const button = document.querySelector('colab-run-button');
                            if (button) {
                                button.click();
                                return true;
                            }
                            return false;
                        }
                    """)
                    logger.info("Кнопка запущена через JavaScript")
                    time.sleep(2)
                    return True
                except Exception as js_error:
                    logger.error(f"Ошибка при запуске через JavaScript: {js_error}")
                    return False
            
        except Exception as e:
            logger.error(f"Ошибка при запуске скрипта транскрибации: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def wait_for_completion(self, selectors: Dict[str, str], timeout: int = 3600) -> bool:
        """
        Ожидает завершения транскрибации в Colab.
        
        Args:
            selectors: Словарь с селекторами для проверки завершения.
                      Может содержать:
                      - 'completion_text': текст, который появляется при завершении
                      - 'completion_selector': селектор элемента, который появляется при завершении
                      - 'cell_id': ID ячейки для проверки вывода
            timeout: Максимальное время ожидания в секундах (по умолчанию 1 час).
        
        Returns:
            True если транскрибация завершена успешно, False при таймауте или ошибке.
        """
        if not self.is_running or not self.page:
            logger.error("Браузер не запущен.")
            return False
        
        try:
            logger.info(f"Ожидание завершения транскрибации (таймаут: {timeout} сек)...")
            
            start_time = time.time()
            check_interval = 5  # Проверяем каждые 5 секунд
            
            # Текст, который появляется при завершении (по умолчанию)
            completion_text = selectors.get('completion_text', '=== Цикл завершен ===')
            cell_id = selectors.get('cell_id', '')
            
            logger.info(f"Ожидание текста завершения: '{completion_text}'")
            
            while time.time() - start_time < timeout:
                try:
                    # Проверяем наличие текста завершения в выводе
                    if cell_id:
                        # Ищем в конкретной ячейке
                        output_selector = f'#{cell_id} .output-content'
                    else:
                        # Ищем в любом выводе
                        output_selector = '.output-content'
                    
                    # Получаем текст из вывода
                    output_elements = self.page.query_selector_all(output_selector)
                    for output in output_elements:
                        text = output.inner_text()
                        if completion_text in text:
                            logger.info("Транскрибация завершена! Найден текст завершения.")
                            return True
                    
                    # Альтернативный способ - проверка через JavaScript
                    has_completion = self.page.evaluate(f"""
                        () => {{
                            const outputs = document.querySelectorAll('.output-content');
                            for (let output of outputs) {{
                                if (output.innerText.includes('{completion_text}')) {{
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """)
                    
                    if has_completion:
                        logger.info("Транскрибация завершена! Найден текст завершения (через JS).")
                        return True
                    
                    # Проверяем наличие селектора завершения, если указан
                    if 'completion_selector' in selectors:
                        element = self.page.query_selector(selectors['completion_selector'])
                        if element:
                            logger.info("Транскрибация завершена! Найден элемент завершения.")
                            return True
                    
                    # Показываем прогресс каждые 30 секунд
                    elapsed = int(time.time() - start_time)
                    if elapsed % 30 == 0 and elapsed > 0:
                        logger.info(f"Ожидание... Прошло {elapsed} секунд из {timeout}")
                    
                    time.sleep(check_interval)
                    
                except Exception as check_error:
                    logger.warning(f"Ошибка при проверке завершения: {check_error}")
                    time.sleep(check_interval)
                    continue
            
            logger.error(f"Таймаут ожидания завершения ({timeout} секунд)")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при ожидании завершения: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop_browser(self) -> bool:
        """
        Останавливает браузер и закрывает все вкладки.
        
        Returns:
            True если браузер успешно остановлен, False иначе.
        """
        try:
            if self.browser:
                logger.info("Остановка браузера...")
                # Закрываем страницу, если она открыта
                if self.page:
                    try:
                        self.page.close()
                    except:
                        pass
                # Закрываем браузер
                try:
                    if self.browser:
                        self.browser.close()
                except Exception:
                    pass
                # Останавливаем Playwright
                try:
                    if self.playwright:
                        self.playwright.stop()
                except Exception:
                    pass
                self.browser = None
                self.playwright = None
                self.page = None
                self.is_running = False
                logger.info("Браузер успешно остановлен")
                return True
            else:
                logger.warning("Браузер уже остановлен")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при остановке браузера: {e}")
            return False
    
    def cleanup(self):
        """
        Очистка ресурсов и закрытие браузера.
        """
        try:
            self.stop_browser()
            logger.info("Ресурсы очищены")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")
    
    def __enter__(self):
        """Поддержка контекстного менеджера."""
        self.start_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка контекстного менеджера."""
        self.cleanup()

