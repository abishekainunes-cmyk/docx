@echo off
setlocal
cd /d "%~dp0"
title NUNES ALL CATALOGUE GENERATOR

echo ============================================================
echo  NUNES ALL CATALOGUE GENERATOR - DRIVE TO PDF
echo ============================================================
echo  Source: Google Drive - total price list
echo  Output 1: Catalogue\
echo  Output 2: Mini Catalogue\
echo  Resume: automatic
echo ============================================================

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py -3
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set PY=python
  ) else (
    echo Python 3 was not found.
    echo Install Python 3.11 or newer, then run this file again.
    pause
    exit /b 1
  )
)

%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Dependency installation failed.
  pause
  exit /b 1
)

%PY% generator.py
pause
