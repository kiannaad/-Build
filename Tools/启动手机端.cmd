@echo off
chcp 65001 >nul
set "PATH=%APPDATA%\npm;%PATH%"
cd /d D:\大肥鱼
echo 正在启动手机端 DSH（dsh web + dshgo）...
echo 关闭这个窗口就会停止手机端的服务。
echo.
dsh web --no-open
pause
