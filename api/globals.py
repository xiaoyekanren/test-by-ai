from flask import Blueprint, jsonify, request
import sqlite3
from .db import get_db_connection

# 创建蓝图
bp = Blueprint('globals', __name__)

@bp.route('', methods=['GET'])
def get_globals():
    """获取所有全局变量"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT key, value FROM globals')
        items = c.fetchall()
        conn.close()
        
        data = {item['key']: json.loads(item['value']) for item in items}
        
        return jsonify({
            'status': 'success',
            'data': data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('', methods=['POST'])
def set_global():
    """创建或更新全局变量"""
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        
        if not key:
            return jsonify({
                'status': 'error',
                'message': 'key 不能为空'
            }), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # 检查是否已存在
        c.execute('SELECT id FROM globals WHERE key = ?', (key,))
        existing = c.fetchone()
        
        if existing:
            # 更新
            c.execute('UPDATE globals SET value = ? WHERE key = ?', (json.dumps(value), key))
        else:
            # 插入
            c.execute('INSERT INTO globals (key, value) VALUES (?, ?)', (key, json.dumps(value)))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '全局变量保存成功'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<key>', methods=['DELETE'])
def delete_global(key):
    """删除全局变量"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM globals WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '全局变量删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
