@echo off
chcp 65001 > nul
title Upload Project to Git

echo ==================================================
echo  此脚本将把您的项目上传到指定的 Git 仓库。
echo ==================================================
echo.

REM 提示用户输入项目路径
set /p "PROJECT_PATH=请输入项目的完整路径: "

REM 验证路径是否存在
if not exist "%PROJECT_PATH%" (
    echo.
    echo 错误：指定的目录不存在。
    echo 路径: %PROJECT_PATH%
    pause
    exit /b
)

REM 提示用户输入 Git 仓库地址
set /p "GIT_URL=请输入远程 Git 仓库的 URL: "

REM 验证 URL 是否为空
if "%GIT_URL%"=="" (
    echo.
    echo 错误：Git 仓库 URL 不能为空。
    pause
    exit /b
)

echo.
echo ==================================================
echo  项目路径: %PROJECT_PATH%
echo  Git URL: %GIT_URL%
echo ==================================================
echo.
echo 按任意键开始上传...
pause >nul

REM 切换到项目目录
cd /d "%PROJECT_PATH%"

REM 如果 .git 目录不存在，则初始化仓库
if not exist ".git" (
    echo 正在初始化新的 Git 仓库...
    git init
    echo 切换到 main 分支...
    git branch -m main
) else (
    echo Git 仓库已存在。
)

echo.
echo 正在添加所有文件到暂存区...
git add .

echo.
echo 正在提交文件...
git commit -m "chore: 通过脚本进行初始项目上传"

echo.
echo 正在设置远程仓库 'origin'...
REM 如果远程 'origin' 已存在，先移除它，以避免冲突
(git remote remove origin >nul 2>&1)
git remote add origin "%GIT_URL%"

echo.
echo 正在推送到远程仓库...
REM 推送到 main 分支并设置上游跟踪
git push -u origin main

echo.
echo ==================================================
echo  上传过程已完成！
echo  请检查上面的输出日志以确认是否有错误。
echo ==================================================
echo.
pause
