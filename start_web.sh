#!/bin/bash
# Скрипт запуска веб-интерфейса Video Maker для Linux/Mac

cd "$(dirname "$0")"
source venv/bin/activate
python run_web.py
