#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для доступа к файлам (скачивание клипов, shorts и т.д.)
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
if Path(__file__).parent.parent.parent not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Blueprint, send_file, jsonify
from web.config import Config

files_bp = Blueprint('files', __name__, url_prefix='/api/files')


@files_bp.route('/clip/<filename>')
def download_clip(filename):
    """Скачивание клипа"""
    clip_path = Config.CLIPS_DIR / filename
    
    if not clip_path.exists():
        return jsonify({'error': 'Файл не найден'}), 404
    
    return send_file(
        str(clip_path),
        as_attachment=True,
        download_name=filename,
        mimetype='video/mp4'
    )


@files_bp.route('/short/<filename>')
def download_short(filename):
    """Скачивание Shorts"""
    short_path = Config.SHORTS_OUTPUT_DIR / filename
    
    if not short_path.exists():
        return jsonify({'error': 'Файл не найден'}), 404
    
    return send_file(
        str(short_path),
        as_attachment=True,
        download_name=filename,
        mimetype='video/mp4'
    )


@files_bp.route('/video/<filename>')
def download_video(filename):
    """Скачивание исходного видео"""
    video_path = Config.DOWNLOADS_DIR / filename
    
    if not video_path.exists():
        return jsonify({'error': 'Файл не найден'}), 404
    
    return send_file(
        str(video_path),
        as_attachment=True,
        download_name=filename,
        mimetype='video/mp4'
    )


@files_bp.route('/audio/<filename>')
def download_audio(filename):
    """Скачивание аудио файла для транскрибации"""
    audio_path = Config.AUDIO_DIR / filename
    
    if not audio_path.exists():
        return jsonify({'error': 'Аудио файл не найден'}), 404
    
    return send_file(
        str(audio_path),
        as_attachment=True,
        download_name=filename,
        mimetype='audio/mpeg'
    )


@files_bp.route('/list/clips')
def list_clips():
    """Список всех клипов"""
    clips = []
    for clip_file in sorted(Config.CLIPS_DIR.glob('*.mp4')):
        size_mb = clip_file.stat().st_size / (1024 * 1024)
        clips.append({
            'name': clip_file.name,
            'size_mb': round(size_mb, 2),
            'path': f'/api/files/clip/{clip_file.name}'
        })
    
    return jsonify({
        'success': True,
        'clips': clips,
        'count': len(clips)
    })


@files_bp.route('/transcription/<filename>')
def download_transcription(filename):
    """Скачивание файла транскрипции"""
    # Путь к транскрипциям может быть вложенным, поэтому ищем в data/transcriptions
    transcription_path = Config.DATA_DIR / 'transcriptions' / filename
    
    if not transcription_path.exists():
        return jsonify({'error': 'Файл транскрипции не найден'}), 404
    
    return send_file(
        str(transcription_path),
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )


@files_bp.route('/list/shorts')
def list_shorts():
    """Список всех Shorts"""
    shorts = []
    for short_file in sorted(Config.SHORTS_OUTPUT_DIR.glob('*.mp4')):
        size_mb = short_file.stat().st_size / (1024 * 1024)
        shorts.append({
            'name': short_file.name,
            'size_mb': round(size_mb, 2),
            'path': f'/api/files/short/{short_file.name}'
        })
    
    return jsonify({
        'success': True,
        'shorts': shorts,
        'count': len(shorts)
    })


@files_bp.route('/list/banners')
def list_banners():
    """Список всех баннеров"""
    banners = []
    if not Config.BANER_DIR.exists():
        return jsonify({'success': True, 'banners': [], 'count': 0})

    for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        for banner_file in sorted(Config.BANER_DIR.glob(f'*{ext}')):
            banners.append({
                'name': banner_file.name,
                'path': str(banner_file)
            })
    
    return jsonify({
        'success': True,
        'banners': banners,
        'count': len(banners)
    })


@files_bp.route('/ai-clips/<filename>')
def get_ai_clips(filename):
    """Отдает содержимое JSON файла с AI нарезкой"""
    import json
    file_path = Config.DATA_DIR / 'ai_clips' / filename
    
    if not file_path.exists():
        return jsonify({'success': False, 'error': 'Файл не найден'}), 404
    
    with open(file_path, 'r', encoding='utf-8') as f:
        clips_data = json.load(f)
        
    return jsonify({'success': True, 'clips': clips_data})


@files_bp.route('/any/<filename>')
def download_any(filename):
    """Универсальный endpoint для скачивания файлов из разных директорий"""
    # Пробуем найти файл в разных директориях
    search_dirs = [
        Config.SHORTS_OUTPUT_DIR,
        Config.CLIPS_DIR,
        Config.DOWNLOADS_DIR,
        Config.OUTPUT_DIR,
        Config.DATA_DIR / 'transcriptions',
        Config.DATA_DIR / 'ai_clips'
    ]
    
    for directory in search_dirs:
        file_path = directory / filename
        if file_path.exists():
            # Определяем MIME тип по расширению
            mimetype = 'application/octet-stream'
            if filename.endswith('.mp4'):
                mimetype = 'video/mp4'
            elif filename.endswith('.mp3'):
                mimetype = 'audio/mpeg'
            elif filename.endswith('.json'):
                mimetype = 'application/json'
            elif filename.endswith('.txt'):
                mimetype = 'text/plain'
            
            return send_file(
                str(file_path),
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )
    
    return jsonify({'error': 'Файл не найден'}), 404