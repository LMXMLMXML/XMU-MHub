@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=pythonw"
where pythonw >nul 2>nul || set "PY=python"
start "" %PY% app.py
