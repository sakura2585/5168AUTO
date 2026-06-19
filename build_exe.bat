@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [5168AUTO] 安裝依賴...
python -m pip install -r requirements.txt pyinstaller>=6.0.0
if errorlevel 1 goto :fail
echo [5168AUTO] 開始 PyInstaller 打包...
python -m PyInstaller --noconfirm 5168AUTO.spec
if errorlevel 1 goto :fail
echo.
echo 完成：dist\5168AUTO_v*.exe（檔名含 app.py 版號）
exit /b 0
:fail
echo 打包失敗。
pause
exit /b 1
