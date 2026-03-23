@echo off
chcp 65001 >nul
echo ========================================
echo   SML AI Router - เริ่มระบบทั้งหมด
echo ========================================
echo.

echo [1/2] เริ่ม Proxy บน Docker...
docker compose up -d --build
echo.

echo [2/2] เริ่ม Dashboard (ใช้ Claude CLI)...
echo   Dashboard: http://127.0.0.1:8899
echo   Proxy:     http://127.0.0.1:8900
echo   Ctrl+C เพื่อหยุด Dashboard
echo.

set PYTHONIOENCODING=utf-8
python app.py
