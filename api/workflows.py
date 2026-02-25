from flask import Blueprint, jsonify, request
import sqlite3
import json
from .db import get_db_connection

# 创建蓝图
bp = Blueprint('workflows', __name__)

@bp.route('', methods=['GET'])
def get_workflows():
    """获取所有工作流"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id, name, description, created_at FROM workflows')
        workflows = c.fetchall()
        conn.close()
        
        # 将 sqlite3.Row 对象转换为字典
        workflows_list = [dict(row) for row in workflows]
        
        return jsonify({
            'status': 'success',
            'data': workflows_list
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('', methods=['POST'])
def create_workflow():
    """创建新工作流"""
    try:
        data = request.get_json()
        name = data.get('name')
        nodes = data.get('nodes', [])
        connections = data.get('connections', [])
        description = data.get('description', '')
        
        if not name:
            return jsonify({
                'status': 'error',
                'message': '工作流名称不能为空'
            }), 400
        
        # 合并 nodes 和 connections 到 data 字段
        workflow_data = {
            'nodes': nodes,
            'connections': connections
        }
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO workflows (name, description, data)
            VALUES (?, ?, ?)
        ''', (
            name,
            description,
            json.dumps(workflow_data)
        ))
        
        conn.commit()
        workflow_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '工作流创建成功',
            'data': {'id': workflow_id}
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:wf_id>', methods=['GET'])
def get_workflow(wf_id):
    """获取工作流详情"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM workflows WHERE id = ?', (wf_id,))
        workflow = c.fetchone()
        conn.close()
        
        if not workflow:
            return jsonify({
                'status': 'error',
                'message': '工作流不存在'
            }), 404
        
        # 将 sqlite3.Row 对象转换为字典
        workflow_dict = dict(workflow)
        
        # 解析 JSON 字段
        data = json.loads(workflow_dict['data'])
        workflow_dict['nodes'] = data.get('nodes', [])
        workflow_dict['connections'] = data.get('connections', [])
        
        return jsonify({
            'status': 'success',
            'data': workflow_dict
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:wf_id>', methods=['PUT'])
def update_workflow(wf_id):
    """更新工作流"""
    try:
        data = request.get_json()
        name = data.get('name')
        nodes = data.get('nodes')
        connections = data.get('connections')
        description = data.get('description')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # 检查工作流是否存在
        c.execute('SELECT id, data FROM workflows WHERE id = ?', (wf_id,))
        workflow = c.fetchone()
        if not workflow:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': '工作流不存在'
            }), 404
        
        # 构建更新语句
        update_fields = []
        update_values = []
        
        if name is not None:
            update_fields.append('name = ?')
            update_values.append(name)
        if description is not None:
            update_fields.append('description = ?')
            update_values.append(description)
        if nodes is not None or connections is not None:
            # 获取当前数据
            current_data = json.loads(workflow['data'])
            # 更新数据
            if nodes is not None:
                current_data['nodes'] = nodes
            if connections is not None:
                current_data['connections'] = connections
            # 添加到更新字段
            update_fields.append('data = ?')
            update_values.append(json.dumps(current_data))
        
        if update_fields:
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(wf_id)
            
            query = f"UPDATE workflows SET {', '.join(update_fields)} WHERE id = ?"
            c.execute(query, update_values)
            conn.commit()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '工作流更新成功'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:wf_id>', methods=['DELETE'])
def delete_workflow(wf_id):
    """删除工作流"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('DELETE FROM workflows WHERE id = ?', (wf_id,))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': '工作流不存在'
            }), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '工作流删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
