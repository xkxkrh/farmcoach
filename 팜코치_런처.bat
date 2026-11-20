@echo off
cd /d "%~dp0"
where pyw > nul 2> nul
if %errorlevel%==0 (
  start "" pyw "%~dp0launcher.pyw"
) else (
  start "" pythonw "%~dp0launcher.pyw"
)
