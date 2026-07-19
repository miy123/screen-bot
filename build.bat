@echo off
setlocal
set NAME=ScreenBot
set DIST=dist\%NAME%

echo ========================================
echo  %NAME% 打包腳本
echo ========================================

:: 安裝依賴
echo [1/3] 安裝依賴...
pip install -r requirements.txt
if errorlevel 1 (echo 安裝失敗，請確認 Python 和 pip 已安裝 & pause & exit /b 1)

:: 打包 exe（onedir 模式：啟動快、易除錯）
echo [2/3] 打包 exe...
pyinstaller --noconfirm --onedir --noconsole --uac-admin ^
    --name %NAME% ^
    --add-data "images;images" ^
    bot.py
if errorlevel 1 (echo 打包失敗 & pause & exit /b 1)

:: 把 config.py 和 images/ 複製到 dist 旁（讓使用者可以直接編輯）
echo [3/3] 整理輸出資料夾...
copy /Y config.py "%DIST%\config.py"
xcopy /E /I /Y images "%DIST%\images"

:: 建立使用說明
(
echo ScreenBot 使用說明
echo ==================
echo 1. 編輯 config.py 設定素材圖片和採集按鍵
echo 2. 把素材圖片放入 images\ 資料夾
echo 3. 用「以系統管理員身分執行」開啟 ScreenBot.exe
echo 4. F1 啟動 / F2 停止
echo.
echo 注意：必須以系統管理員身分執行，否則熱鍵無法作用
) > "%DIST%\README.txt"

echo.
echo 完成！輸出在：%DIST%\
echo 整個 %NAME%\ 資料夾可以直接複製到其他電腦使用。
echo.
pause
