@echo off
chcp 65001 >nul
title 高考化学题库

cd /d "%~dp0"

echo.
echo ================================
echo    高考化学题库 — 正在启动
echo ================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [1/3] 检查依赖...
pip install -r requirements.txt -q 2>nul
if errorlevel 1 (
    echo [警告] 依赖安装失败，尝试继续...
)

:: Initialize database
echo [2/3] 初始化数据库...
python -c "from models import init_db; init_db()" 2>nul

:: Start server
echo [3/3] 启动服务...
echo.
echo 服务已启动！浏览器将自动打开。
echo 如果未自动打开，请手动访问: http://localhost:5001
echo.
echo 按 Ctrl+C 或关闭此窗口即可停止服务。
echo ================================
echo.

:: Open browser after 2 seconds
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5001"

:: Start Flask
python app.py
pause
