#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с транскрипциями
Форматирование, парсинг временных меток
"""

import re
from typing import List, Dict, Tuple


class TranscriptionService:
    """Сервис для обработки транскрипций"""
    
    @staticmethod
    def format_transcription(raw_transcription: str, format_type: str = 'whisper') -> str:
        """
        Форматирует транскрипцию, удаляя лишние детали
        
        Args:
            raw_transcription: Сырая транскрипция от Whisper
            format_type: Тип формата ('whisper' или 'plain')
            
        Returns:
            Отформатированная транскрипция
        """
        if format_type == 'plain':
            return raw_transcription
        
        # Для Whisper формата удаляем детализацию слов
        # Формат: [0:00:11.020000 - 0:00:12.800000] Текст
        #   Слова: У(0:00:11.020000-0:00:11.140000) ...
        
        lines = raw_transcription.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Если строка содержит временную метку в начале
            if re.match(r'\[\d+:\d+:\d+', line):
                # Берем только основную строку с временем и текстом
                # Удаляем детализацию слов (строки начинающиеся с "Слова:")
                if 'Слова:' not in line:
                    formatted_lines.append(line)
            elif not line.startswith('Слова:') and not line.startswith('  '):
                # Сохраняем другие строки если они не детализация
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    @staticmethod
    def parse_transcription(transcription: str) -> List[Dict]:
        """
        Парсит транскрипцию и возвращает список сегментов
        
        Args:
            transcription: Отформатированная транскрипция
            
        Returns:
            Список словарей:
            [
                {
                    'start': 11.02,  # секунды
                    'end': 12.8,
                    'text': 'Текст'
                },
                ...
            ]
        """
        segments = []
        
        # Паттерн для временных меток: [0:00:11.020000 - 0:00:12.800000] Текст
        pattern = r'\[(\d+):(\d+):([\d.]+)\s*-\s*(\d+):(\d+):([\d.]+)\]\s*(.+)'
        
        for match in re.finditer(pattern, transcription):
            start_h, start_m, start_s = match.groups()[:3]
            end_h, end_m, end_s = match.groups()[3:6]
            text = match.group(7).strip()
            
            start_seconds = int(start_h) * 3600 + int(float(start_m)) * 60 + float(start_s)
            end_seconds = int(end_h) * 3600 + int(float(end_m)) * 60 + float(end_s)
            
            segments.append({
                'start': start_seconds,
                'end': end_seconds,
                'text': text
            })
        
        return segments
    
    @staticmethod
    def time_to_string(seconds: float) -> str:
        """Конвертирует секунды в строку HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def string_to_time(time_str: str) -> float:
        """Конвертирует строку HH:MM:SS в секунды"""
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        else:
            return float(parts[0])
