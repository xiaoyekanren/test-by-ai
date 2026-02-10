@echo off
cd /d %~dp0

echo 正在检查 Python 依赖...
pip install -r requirements.txt

echo.
echo 启动服务器...
python app.py

pause
