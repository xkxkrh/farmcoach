@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where py > nul 2> nul
if %errorlevel%==0 (
  py manager\app.py
) else (
  python manager\app.py
)
pause
