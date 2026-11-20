@echo off
chcp 65001 > nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title 팜코치 런처 준비

rem ==================================================================
rem  팜코치 런처 시작 파일
rem  1) 파이썬 / Git 이 있는지 확인
rem  2) 없으면 물어보고 자동 설치 (윈도우 기본 설치 도구 winget 사용)
rem  3) 런처 창 열기
rem ==================================================================

call :find_python
call :find_git

if /i "%~1"=="--check" (
  echo PYTHON=!PYW!
  echo GIT=!GITOK!
  exit /b 0
)

if not defined PYW call :setup_python
if not defined PYW goto :manual

if not defined GITOK call :setup_git
if not defined GITOK goto :manual

rem 설치 후에는 업데이트로 함께 새로워지는 farmcoach 폴더 안의 런처를 씀
set "LAUNCHER=%~dp0launcher.pyw"
if exist "%~dp0farmcoach\launcher.pyw" set "LAUNCHER=%~dp0farmcoach\launcher.pyw"
start "" "!PYW!" "!LAUNCHER!"
exit /b 0


rem ------------------------------------------------------------------
:setup_python
echo.
echo  ============================================================
echo   [준비] 파이썬 Python 프로그램이 없어서 먼저 설치해야 해요.
echo  ============================================================
choice /c YN /n /m "  지금 자동으로 설치할까요?  Y = 예 / N = 아니오 : "
if errorlevel 2 exit /b
call :winget Python.Python.3.12
call :add_python_paths
call :find_python
if defined PYW (echo   파이썬 설치 완료.) else (echo   파이썬을 찾지 못했어요.)
exit /b

:setup_git
echo.
echo  ============================================================
echo   [준비] Git 프로그램이 없어서 먼저 설치해야 해요.
echo  ============================================================
choice /c YN /n /m "  지금 자동으로 설치할까요?  Y = 예 / N = 아니오 : "
if errorlevel 2 exit /b
call :winget Git.Git
call :find_git
if defined GITOK (echo   Git 설치 완료.) else (echo   Git 을 찾지 못했어요.)
exit /b

:winget
where winget > nul 2> nul
if errorlevel 1 (
  echo   이 컴퓨터에는 자동 설치 도구 winget 이 없어요.
  exit /b 1
)
echo.
echo   설치하는 중이에요. 몇 분 걸릴 수 있어요.
echo   중간에 "이 앱이 디바이스를 변경하도록 허용..." 창이 뜨면 [예] 를 눌러 주세요.
echo.
winget install --id %1 -e --silent --accept-package-agreements --accept-source-agreements
exit /b

rem ------------------------------------------------------------------
:find_python
set "PYW="
where py > nul 2> nul
if not errorlevel 1 (
  py -c "import tkinter" > nul 2> nul
  if not errorlevel 1 (
    for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
  )
)
if not defined PYW (
  for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
    if not defined PYW if exist "%%~d\pythonw.exe" (
      "%%~d\python.exe" -c "import tkinter" > nul 2> nul
      if not errorlevel 1 set "PYW=%%~d\pythonw.exe"
    )
  )
)
if not defined PYW (
  for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYW if exist "%%~dpipythonw.exe" (
      "%%i" -c "import tkinter" > nul 2> nul
      if not errorlevel 1 set "PYW=%%~dpipythonw.exe"
    )
  )
)
exit /b

:add_python_paths
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do set "PATH=%%~d;%%~d\Scripts;!PATH!"
if exist "%LOCALAPPDATA%\Programs\Python\Launcher" set "PATH=%LOCALAPPDATA%\Programs\Python\Launcher;!PATH!"
exit /b

:find_git
set "GITOK="
where git > nul 2> nul
if not errorlevel 1 set "GITOK=1"
if not defined GITOK if exist "%ProgramFiles%\Git\cmd\git.exe" (
  set "PATH=%ProgramFiles%\Git\cmd;!PATH!"
  set "GITOK=1"
)
exit /b

rem ------------------------------------------------------------------
:manual
echo.
echo  ============================================================
echo   자동 준비를 끝내지 못했어요.
echo   같은 폴더의 [실행전_가이드라인.txt] 를 열어 드릴게요.
echo   거기 적힌 순서대로 설치한 뒤, 이 파일을 다시 더블클릭해 주세요.
echo  ============================================================
start "" notepad "%~dp0실행전_가이드라인.txt"
echo.
pause
exit /b 1
