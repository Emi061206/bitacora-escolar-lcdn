@echo off
chcp 65001 > nul
title Bitácora del Semestre - Servidor y Recordatorios

echo =========================================================
echo    Iniciando Bitácora del Semestre (Semestre 4)
echo =========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    if exist "C:\Python314\python.exe" (
        set PYTHON_CMD="C:\Python314\python.exe"
    ) else (
        echo [ERROR] No se encontro Python en el sistema.
        echo Por favor instala Python o agregalo a las variables de entorno.
        pause
        exit /b 1
    )
) else (
    set PYTHON_CMD=python
)

echo [1/2] Abriendo la aplicación en tu navegador...
start http://localhost:8000/horarios.html

echo [2/2] Iniciando el servidor local con base de datos SQLite...
echo.
echo Presiona Ctrl + C en cualquier momento para detener el servidor.
echo.

%PYTHON_CMD% server.py

pause
