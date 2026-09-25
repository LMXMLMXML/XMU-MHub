@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python。请安装 Python 3.10 或更高版本，安装时勾选 Add python.exe to PATH。
  pause
  exit /b 1
)
echo 正在启动 厦大统一门户 ...
%PY% app.py
if errorlevel 1 pause
