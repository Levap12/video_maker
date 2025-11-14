#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для взаимодействия с AI моделями (DeepSeek, OpenAI и др.)
"""

import requests
import json
import logging
from web.config import Config

logger = logging.getLogger(__name__)

class AIService:
    """Класс для работы с DeepSeek API."""

    def __init__(self, api_key=None):
        # Используем переданный ключ, или из настроек, или из переменной окружения
        self.api_key = api_key or Config.get_deepseek_api_key()
        self.api_url = "https://api.deepseek.com/chat/completions"

    def _get_prompt_by_id(self, prompt_type: str, prompt_id: str) -> str:
        file_path = Config.SYSTEM_PROMPTS_FILE if prompt_type == 'system' else Config.USER_PROMPTS_FILE
        if not file_path.exists():
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        for p in prompts:
            if p['id'] == prompt_id:
                return p['text']
        return None

    def generate_clips_from_transcription(self, transcription: str, system_prompt_id: str, user_prompt_id: str, video_duration_seconds: float) -> dict:
        """
        Генерирует JSON с нарезкой клипов на основе транскрипции и ID промптов.
        """
        if not self.api_key:
            return {'success': False, 'error': 'API ключ для DeepSeek не настроен в config.py'}

        system_prompt_text = self._get_prompt_by_id('system', system_prompt_id)
        user_prompt_text = self._get_prompt_by_id('user', user_prompt_id)

        if not system_prompt_text or not user_prompt_text:
            return {'success': False, 'error': 'Один из выбранных промптов не найден.'}

        # Подставляем длительность видео в системный промпт безопасным способом
        system_prompt_text = system_prompt_text.replace('{video_duration_seconds:.2f}', f'{video_duration_seconds:.2f}')

        logger.info(f"Итоговый системный промпт: {system_prompt_text}")
        logger.info(f"Итоговый пользовательский промпт: {user_prompt_text}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        full_prompt = f"""Вот транскрибация видео:
---
{transcription}
---

Запрос пользователя: "{user_prompt_text}"""

        payload = {
            "model": "deepseek-chat", # Или другая модель DeepSeek
            "messages": [
                {"role": "system", "content": system_prompt_text},
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.5,
            "stream": False,
            "response_format": {"type": "json_object"} # Четко указываем, что ждем JSON
        }

        try:
            logger.info("Отправка запроса в DeepSeek API...")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=180) # Таймаут 3 минуты
            response.raise_for_status() # Вызовет исключение для кодов 4xx/5xx

            logger.info("Ответ от DeepSeek API получен.")
            content = response.json()['choices'][0]['message']['content']
            logger.info(f"Получен успешный ответ от AI: {content}")

            # Теперь модель должна возвращать чистый JSON
            clips_json = json.loads(content)
            
            # TODO: Добавить валидацию полученного JSON (проверка полей, форматов времени и т.д.)

            return {'success': True, 'clips': clips_json}

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при обращении к DeepSeek API: {e}")
            return {'success': False, 'error': f"Ошибка сети: {e}"}
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Ошибка парсинга или структуры ответа от DeepSeek API: {e}")
            logger.error(f"Полученный ответ: {content}")
            return {'success': False, 'error': 'AI вернул некорректный формат данных. Попробуйте изменить промпт.'}
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при работе с DeepSeek API: {e}")
            return {'success': False, 'error': f"Непредвиденная ошибка: {e}"}