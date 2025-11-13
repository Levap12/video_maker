@echo off
REM Скрипт запуска веб-интерфейса Video Maker для Windows

cd /d %~dp0
call venv\Scripts\activate.bat

REM Устанавливаем все зависимости из requirements.txt
python -m pip install -r requirements.txt

python run_web.py
pause
