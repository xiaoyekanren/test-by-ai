from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psutil
from datetime import datetime
import os
import tempfile
import json
import sqlite3
from pathlib import Path
import requests
import paramiko

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# ==================== 数据库初始化 ====================

from api.db import init_db, get_db_connection

init_db()

# ==================== 辅助函数 ====================

# 导入辅助函数
from api.utils import ssh_run_command, fetch_remote_api, sftp_upload

# ==================== API 路由 ====================

# 导入并注册 API 蓝图
from api import api_bp
app.register_blueprint(api_bp)

# ==================== 前端路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/integrated')
def integrated():
    """集成监控面板"""
    return render_template('integrated.html')


@app.route('/servers')
def servers():
    """服务器管理页面"""
    return render_template('servers.html')

@app.route('/workflow')
def workflow():
    return render_template('workflow.html')


@app.route('/sql')
def sql():
    """SQL 工具页面"""
    return render_template('sql.html')


@app.route('/api-page')
def api_page():
    """API 接口管理页面"""
    return render_template('api.html')


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Resource not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)