@echo off
rem Launch ASTERISM from source (Windows). First time: py -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
cd /d "%~dp0"
.venv\Scripts\python -m asterism %*
