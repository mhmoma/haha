@echo off
setlocal

:: 设置脚本标题
title XiaoHa Bot Launcher

:: 切换到脚本所在目录
cd /d "%~dp0"

echo ===================================
echo  Starting Discord Bot...
echo ===================================
echo.

:: 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in '.venv'.
    echo Please make sure you have created a virtual environment.
    pause
    exit /b
)

echo Activating virtual environment and running the bot...
echo If the bot fails to start, check your .env file and network connection.
echo Press Ctrl+C to stop the bot.
echo.

:: 运行机器人
".\.venv\Scripts\python.exe" bot.py

echo.
echo Bot script has been stopped.
endlocal
