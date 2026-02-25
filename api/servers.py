from flask import Blueprint, jsonify, request
import sqlite3
import os
import tempfile
from .db import get_db_connection
from .utils import ssh_run_command, fetch_remote_api, sftp_upload

# 创建蓝图
bp = Blueprint('servers', __name__)

@bp.route('', methods=['GET'])
def list_servers():
    """获取所有服务器列表"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id, name, host, port, username, description, tags, status, created_at FROM servers ORDER BY created_at DESC')
        servers = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': servers
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('', methods=['POST'])
def add_server():
    """添加新服务器"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('name') or not data.get('host'):
            return jsonify({
                'status': 'error',
                'message': '服务器名称和主机地址为必填项'
            }), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO servers (name, host, port, username, password, description, tags, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['host'],
            data.get('port', 5000),
            data.get('username', ''),
            data.get('password', ''),
            data.get('description', ''),
            data.get('tags', ''),
            'offline'
        ))
        
        conn.commit()
        server_id = c.lastrowid
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '服务器添加成功',
            'data': {'id': server_id}
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({
            'status': 'error',
            'message': '服务器名称已存在'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:server_id>', methods=['GET'])
def get_server(server_id):
    """获取服务器详情"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM servers WHERE id = ?', (server_id,))
        server = c.fetchone()
        conn.close()
        
        if not server:
            return jsonify({
                'status': 'error',
                'message': '服务器不存在'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': dict(server)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    """更新服务器信息"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        c = conn.cursor()
        
        # 检查服务器是否存在
        c.execute('SELECT id FROM servers WHERE id = ?', (server_id,))
        if not c.fetchone():
            conn.close()
            return jsonify({
                'status': 'error',
                'message': '服务器不存在'
            }), 404
        
        # 更新字段
        update_fields = []
        update_values = []
        
        if 'name' in data:
            update_fields.append('name = ?')
            update_values.append(data['name'])
        if 'host' in data:
            update_fields.append('host = ?')
            update_values.append(data['host'])
        if 'port' in data:
            update_fields.append('port = ?')
            update_values.append(data['port'])
        if 'username' in data:
            update_fields.append('username = ?')
            update_values.append(data['username'])
        # 只有当密码不为空时才更新密码
        if 'password' in data and data['password']:
            update_fields.append('password = ?')
            update_values.append(data['password'])
        if 'description' in data:
            update_fields.append('description = ?')
            update_values.append(data['description'])
        if 'tags' in data:
            update_fields.append('tags = ?')
            update_values.append(data['tags'])
        
        if update_fields:
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(server_id)
            
            query = f"UPDATE servers SET {', '.join(update_fields)} WHERE id = ?"
            c.execute(query, update_values)
            conn.commit()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '服务器更新成功'
        }), 200
    except sqlite3.IntegrityError:
        return jsonify({
            'status': 'error',
            'message': '服务器名称已存在'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    """删除服务器"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('DELETE FROM servers WHERE id = ?', (server_id,))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': '服务器不存在'
            }), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '服务器删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:server_id>/test', methods=['POST'])
def test_server_connection(server_id):
    """测试服务器连接"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        server = c.fetchone()
        conn.close()
        
        if not server:
            return jsonify({
                'status': 'error',
                'message': '服务器不存在'
            }), 404
        
        # 测试 SSH 连接: 尝试在远端执行简单命令
        srv = {'host': server['host'], 'port': server['port'], 'username': server['username'], 'password': server['password']}
        res = ssh_run_command(srv, "echo OK", timeout=3)
        if res.get('error'):
            error_msg = res.get('error')
            return jsonify({
                'status': 'error',
                'message': '服务器连接失败: ' + error_msg,
                'server_status': 'offline'
            }), 400

        # 如果 SSH 成功（不关心 stdout 内容），更新数据库状态
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE servers SET status = ? WHERE id = ?', ('online', server_id))
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'message': '服务器连接成功',
            'server_status': 'online'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('/<int:server_id>/upload', methods=['POST'])
def upload_file_to_server(server_id):
    try:
        remote_path = request.form.get('remote_path', '')
        file = request.files.get('file')
        
        # 只要有文件即可，remote_path 可以为空（后端会自动生成默认路径）
        if not file:
            return jsonify({'status': 'error', 'message': '缺少文件'}), 400
        
        # 验证文件名安全
        if not file.filename:
            return jsonify({'status': 'error', 'message': '文件名为空'}), 400

        # 处理远程路径：如果以 / 结尾或为空，则追加原始文件名
        if remote_path.endswith('/'):
            remote_path = os.path.join(remote_path, file.filename)
        
        # 另外，如果 remote_path 完全为空，我们可以默认使用 /tmp/filename
        if not remote_path:
             remote_path = f"/tmp/{file.filename}"
             
        # 再次确保路径分隔符是正斜杠（Linux/Unix）
        remote_path = remote_path.replace('\\', '/')
            
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        server = c.fetchone()
        conn.close()
        
        if not server:
            return jsonify({'status': 'error', 'message': '服务器不存在'}), 404
            
        # 使用更稳健的临时文件处理
        try:
            # 确保临时文件名保留原始扩展名（有些系统或场景可能需要）
            suffix = os.path.splitext(file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
                
            server_dict = {'host': server['host'], 'port': server['port'], 'username': server['username'], 'password': server['password']}
            
            # 执行 SFTP 上传
            res = sftp_upload(server_dict, tmp_path, remote_path)
            
            # 清理临时文件
            try:
                os.remove(tmp_path)
            except Exception as e:
                pass
                
            if res.get('status') != 'success':
                return jsonify({'status': 'error', 'message': res.get('message', '上传失败')}), 400
                
            return jsonify({'status': 'success', 'message': '文件上传成功'}), 200
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'上传处理错误: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/execute', methods=['POST'])
def execute_command_on_server(server_id):
    try:
        data = request.get_json()
        command = data.get('command', '')
        if not command:
            return jsonify({'status': 'error', 'message': '命令不能为空'}), 400
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        server = c.fetchone()
        conn.close()
        if not server:
            return jsonify({'status': 'error', 'message': '服务器不存在'}), 404
        server_dict = {'host': server['host'], 'port': server['port'], 'username': server['username'], 'password': server['password']}
        result = ssh_run_command(server_dict, command, timeout=30)
        if 'error' in result:
            return jsonify({'status': 'error', 'message': result['error'], 'data': {'output': '', 'error': result['error'], 'exit_status': -1}}), 400
        return jsonify({'status': 'success', 'message': '命令执行成功', 'data': {'output': result.get('stdout', ''), 'error': result.get('stderr', ''), 'exit_status': result.get('exit_status')}}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/proxy/server/status', methods=['GET'])
def proxy_server_status(server_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        resp = fetch_remote_api(server, '/api/server/status')
        status_code = 200 if resp.get('status') == 'success' else 502
        return jsonify(resp), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/proxy/server/processes', methods=['GET'])
def proxy_server_processes(server_id):
    try:
        limit = request.args.get('limit', 20, type=int)
        sort_by = request.args.get('sort_by', 'memory', type=str)
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        resp = fetch_remote_api(server, '/api/server/processes', params={'limit': limit, 'sort_by': sort_by})
        status_code = 200 if resp.get('status') == 'success' else 502
        return jsonify(resp), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/proxy/server/process/<int:pid>/kill', methods=['POST'])
def proxy_kill_process(server_id, pid):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        resp = fetch_remote_api(server, f'/api/process/{pid}/kill', method='POST')
        status_code = 200 if resp.get('status') == 'success' else 502
        return jsonify(resp), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/proxy/server/network', methods=['GET'])
def proxy_server_network(server_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        resp = fetch_remote_api(server, '/api/server/network')
        status_code = 200 if resp.get('status') == 'success' else 502
        return jsonify(resp), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/<int:server_id>/proxy/server/disk', methods=['GET'])
def proxy_server_disk(server_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        resp = fetch_remote_api(server, '/api/server/disk')
        status_code = 200 if resp.get('status') == 'success' else 502
        return jsonify(resp), status_code
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
