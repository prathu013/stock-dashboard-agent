@echo off
title Push to GitHub
color 0A
cd /d "%~dp0"

echo ============================================
echo   PUSH YOUR DASHBOARD TO GITHUB
echo ============================================
echo.

REM ---- check git ----
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed.
    echo 1. Download it from: https://git-scm.com/download/win
    echo 2. Install it (keep all default options).
    echo 3. Run this file again.
    echo.
    pause
    exit /b 1
)

REM ---- initialize git if needed ----
if not exist ".git" (
    echo [1/4] Initializing git repository...
    git init
) else (
    echo [1/4] Git repository already initialized.
)

REM ---- set remote if needed ----
git remote get-url origin >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [2/4] Paste your GitHub repository URL and press Enter.
    echo       Example: https://github.com/YOUR-USERNAME/stock-dashboard-agent.git
    set /p GITURL="Repo URL: "
    git remote add origin %GITURL%
) else (
    echo [2/4] Remote 'origin' already set.
)

echo [3/4] Adding and committing all changes...
git add .
git commit -m "Stock Dashboard Agent update"

echo [4/4] Pushing to GitHub (main branch)...
git branch -M main
git push -u origin main

echo.
echo ============================================
echo   DONE! Your code is now on GitHub.
echo ============================================
pause
