#!/bin/bash

echo "正在检查 Python 依赖..."
pip install -r requirements.txt

echo ""
echo "启动服务器..."
python3 app.py
