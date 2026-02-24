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

DB_PATH = 'servers.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 5000,
            username TEXT,
            password TEXT,
            description TEXT,
            tags TEXT,
            status TEXT DEFAULT 'offline',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 检查 tags 列是否存在（针对旧数据库）
    try:
        c.execute('SELECT tags FROM servers LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE servers ADD COLUMN tags TEXT')
        
    # 创建工作流表
    c.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建全局变量表
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_variables (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
    conn.commit()
    conn.close()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

init_db()

# ==================== 系统信息接口 ====================

@app.route('/api/server/status', methods=['GET'])
def get_server_status():
    """获取服务器基本状态信息"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0)  # 设置 interval=0，避免等待
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return jsonify({
            'status': 'success',
            'data': {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'usage': cpu_percent,
                    'count': psutil.cpu_count()
                },
                'memory': {
                    'total': memory.total,
                    'used': memory.used,
                    'available': memory.available,
                    'percent': memory.percent
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/server/processes', methods=['GET'])
def get_processes():
    """获取运行中的进程列表"""
    try:
        limit = request.args.get('limit', 20, type=int)
        sort_by = request.args.get('sort_by', 'memory', type=str)  # 'memory' 或 'cpu'
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu': proc.info['cpu_percent'] or 0.0,
                    'memory': proc.info['memory_percent'] or 0.0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 按指定字段排序
        if sort_by == 'cpu':
            processes.sort(key=lambda x: x['cpu'], reverse=True)
        else:
            processes.sort(key=lambda x: x['memory'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': processes[:limit]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/server/network', methods=['GET'])
def get_network_info():
    """获取网络信息"""
    try:
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        net_io = psutil.net_io_counters()
        
        interfaces = []
        for interface_name, addrs in net_if_addrs.items():
            ip_addresses = []
            for addr in addrs:
                ip_addresses.append({
                    'family': str(addr.family),
                    'address': addr.address,
                    'netmask': addr.netmask
                })
            
            stats = net_if_stats.get(interface_name)
            interfaces.append({
                'name': interface_name,
                'ips': ip_addresses,
                'is_up': stats.isup if stats else False,
                'mtu': stats.mtu if stats else 0
            })
        
        return jsonify({
            'status': 'success',
            'data': {
                'interfaces': interfaces,
                'stats': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                    'errin': net_io.errin,
                    'errout': net_io.errout
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/server/disk', methods=['GET'])
def get_disk_partitions():
    """获取磁盘分区信息"""
    try:
        partitions = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                })
            except PermissionError:
                pass
        
        return jsonify({
            'status': 'success',
            'data': partitions
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ==================== 进程管理接口（为后续功能预留） ====================

@app.route('/api/process/<int:pid>', methods=['GET'])
def get_process_detail(pid):
    """获取进程详细信息"""
    try:
        proc = psutil.Process(pid)
        return jsonify({
            'status': 'success',
            'data': {
                'pid': proc.pid,
                'name': proc.name(),
                'status': proc.status(),
                'cpu_percent': proc.cpu_percent(),
                'memory_info': {
                    'rss': proc.memory_info().rss,
                    'vms': proc.memory_info().vms
                },
                'create_time': proc.create_time()
            }
        }), 200
    except psutil.NoSuchProcess:
        return jsonify({
            'status': 'error',
            'message': f'Process {pid} not found'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/process/<int:pid>/kill', methods=['POST'])
def kill_process(pid):
    """终止进程（为后续功能预留）"""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        return jsonify({
            'status': 'success',
            'message': f'Process {pid} terminated'
        }), 200
    except psutil.NoSuchProcess:
        return jsonify({
            'status': 'error',
            'message': f'Process {pid} not found'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ==================== 服务器管理接口 ====================

@app.route('/api/servers', methods=['GET'])
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


@app.route('/api/servers', methods=['POST'])
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


@app.route('/api/servers/<int:server_id>', methods=['GET'])
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


@app.route('/api/servers/<int:server_id>', methods=['PUT'])
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


@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
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


@app.route('/api/servers/<int:server_id>/test', methods=['POST'])
def test_server_connection(server_id):
    """测试服务器连接"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        server = c.fetchone()
        conn.close()
        
        if not server:
            app.logger.warning(f"🔍 Test connection: Server {server_id} not found")
            return jsonify({
                'status': 'error',
                'message': '服务器不存在'
            }), 404
        
        app.logger.info(f"🔍 Testing SSH connection to server {server_id} ({server['host']})")
        # 测试 SSH 连接: 尝试在远端执行简单命令
        srv = {'host': server['host'], 'port': server['port'], 'username': server['username'], 'password': server['password']}
        res = ssh_run_command(srv, "echo OK", timeout=3)
        if res.get('error'):
            error_msg = res.get('error')
            app.logger.warning(f"🔍 SSH test failed: {error_msg}")
            return jsonify({
                'status': 'error',
                'message': '服务器连接失败: ' + error_msg,
                'server_status': 'offline'
            }), 400

        # 如果 SSH 成功（不关心 stdout 内容），更新数据库状态
        app.logger.info(f"✅ SSH test passed for server {server_id}, updating status to online")
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
        app.logger.error(f"❌ Error in test_server_connection: {type(e).__name__}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ==================== 服务部署接口（为后续功能预留） ====================

@app.route('/api/services', methods=['GET'])
def get_services():
    """获取服务列表（为后续功能预留）"""
    return jsonify({
        'status': 'success',
        'data': [],
        'message': 'Service management feature coming soon'
    }), 200


@app.route('/api/services', methods=['POST'])
def create_service():
    """创建新服务（为后续功能预留）"""
    return jsonify({
        'status': 'error',
        'message': 'Service deployment feature coming soon'
    }), 501


# ==================== 远程服务器代理接口 ====================

def ssh_run_command(server, command, timeout=5):
    """通过 SSH 在远程主机上运行命令，返回字典包含 stdout/stderr/exit_status 或 error."""
    host = server.get('host')
    username = server.get('username') or None
    password = server.get('password') or None
    
    ports_to_try = [22]
    # 如果数据库里保存了端口，尝试备用端口（兼容旧字段）
    try:
        if server.get('port'):
            ports_to_try.append(int(server.get('port')))
    except Exception:
        pass

    app.logger.info(f"🔐 Attempting SSH to {host} with username={username}, ports={ports_to_try}")
    last_exc = None
    for ssh_port in ports_to_try:
        try:
            app.logger.debug(f"  Trying SSH port {ssh_port}...")
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            client.connect(hostname=host, port=ssh_port, username=username, password=password, timeout=timeout)
            app.logger.info(f"  ✓ SSH connected on port {ssh_port}. Executing: {command[:80]}...")
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            exit_status = stdout.channel.recv_exit_status()
            client.close()
            app.logger.info(f"  ✓ SSH command succeeded with exit_status={exit_status}")
            return {'exit_status': exit_status, 'stdout': out, 'stderr': err, 'ssh_port': ssh_port}
        except paramiko.AuthenticationException as e:
            last_exc = e
            app.logger.warning(f"❌ SSH auth failed to {host}:{ssh_port}: {str(e)[:100]}")
            continue
        except paramiko.SSHException as e:
            last_exc = e
            app.logger.warning(f"❌ SSH protocol error to {host}:{ssh_port}: {str(e)[:100]}")
            continue
        except Exception as e:
            last_exc = e
            app.logger.warning(f"❌ SSH error to {host}:{ssh_port}: {type(e).__name__}: {str(e)[:100]}")
            continue

    error_msg = str(last_exc) if last_exc else 'SSH connection failed'
    app.logger.error(f"❌ SSH all ports failed for {host}: {error_msg}")
    return {'error': error_msg}


def fetch_remote_api(server, path, params=None, method='GET', json_data=None, timeout=5):
    """使用 SSH 从远程主机收集监控数据或执行操作；直接使用 shell 命令收集，不尝试远程 psutil。
    返回与原先 API 兼容的 JSON-like dict。"""
    app.logger.info(f"🔌 SSH proxy request to {server.get('host')} path={path} method={method}")
    app.logger.debug(f"   Server details: host={server.get('host')}, port={server.get('port')}, user={server.get('username')}")

    # 获取系统状态
    if path == '/api/server/status':
        # 使用一组 shell 命令来获取CPU、内存、磁盘信息
        fallback_cmd = (
            "(nproc || echo '1') && "
            "(average=$(uptime | grep -oP 'average: \\K[0-9.]+' || echo '0'); echo $average) && "
            "(free -b | awk '/^Mem:/ {print $2, $3}' || echo '0 0') && "
            "(df -B1 / | tail -1 | awk '{print $2, $3, $(NF-1)}' || echo '0 0 0')"
        )
        res2 = ssh_run_command(server, fallback_cmd, timeout=timeout)
        if res2.get('error') or res2.get('exit_status', 1) != 0:
            app.logger.error(f"  ❌ Fallback failed: {res2.get('error')}")
            return {'status': 'error', 'message': res2.get('error'), 'diagnosis': 'SSHFail'}
        
        # 解析 shell 输出
        try:
            lines = res2.get('stdout', '').strip().split('\n')
            cpu_count = int(lines[0].strip()) if len(lines) > 0 else 1
            cpu_usage = float(lines[1].strip()) if len(lines) > 1 else 0
            
            mem_data = lines[2].strip().split() if len(lines) > 2 else ['0', '0']
            mem_total = int(mem_data[0]) if len(mem_data) > 0 else 0
            mem_used = int(mem_data[1]) if len(mem_data) > 1 else 0
            mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
            
            disk_data = lines[3].strip().split() if len(lines) > 3 else ['0', '0', '0']
            disk_total = int(disk_data[0]) if len(disk_data) > 0 else 0
            disk_used = int(disk_data[1]) if len(disk_data) > 1 else 0
            disk_percent_str = disk_data[2] if len(disk_data) > 2 else '0%'
            disk_percent = float(disk_percent_str.rstrip('%')) if disk_percent_str.endswith('%') else 0
            
            app.logger.info(f"  ✓ Parsed shell fallback: cpu_count={cpu_count}, mem={mem_percent:.1f}%, disk={disk_percent:.1f}%")
            
            return {
                'status': 'success',
                'data': {
                    'cpu': {'count': cpu_count, 'usage': cpu_usage},
                    'memory': {'total': mem_total, 'used': mem_used, 'available': mem_total - mem_used, 'percent': mem_percent},
                    'disk': {'total': disk_total, 'used': disk_used, 'free': disk_total - disk_used, 'percent': disk_percent}
                },
                'diagnosis': 'Limited'
            }
        except Exception as e:
            app.logger.warning(f"  ⚠️  Failed to parse shell fallback: {str(e)[:80]}, returning raw output")
            return {'status': 'success', 'data': {'raw': res2.get('stdout', '')}, 'diagnosis': 'Limited'}

    # 列表进程
    if path.startswith('/api/server/processes'):
        limit = int(params.get('limit', 20)) if params else 20
        # 直接使用 ps 命令
        cmd2 = f"ps -eo pid,comm,%cpu,%mem --sort=-%mem | head -n {limit+1}"
        res2 = ssh_run_command(server, cmd2, timeout=timeout)
        if res2.get('error') or res2.get('exit_status', 1) != 0:
            app.logger.error(f"  ❌ ps command failed: {res2.get('error')}")
            return {'status': 'error', 'message': res2.get('error'), 'diagnosis': 'SSHFail'}
        lines = res2.get('stdout','').strip().splitlines()
        procs = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                pid = parts[0]
                name = parts[1]
                cpu = parts[2]
                mem = parts[3]
                try:
                    procs.append({'pid': int(pid), 'name': name, 'cpu': float(cpu), 'memory': float(mem)})
                except Exception:
                    continue
        app.logger.info(f"  ✓ Parsed {len(procs)} processes from ps output")
        return {'status':'success','data':procs}

    # 强制 kill
    if path.startswith('/api/process/') and path.endswith('/kill'):

        # path format: /api/process/{pid}/kill
        try:
            pid = int(path.split('/')[3])
        except Exception:
            app.logger.warning(f"  Invalid pid in path: {path}")
            return {'status':'error','message':'Invalid pid', 'diagnosis':'BadRequest'}
        app.logger.debug(f"  Executing kill command for pid {pid}")
        cmd = f"kill -TERM {pid} && echo OK || echo FAIL"
        res = ssh_run_command(server, cmd, timeout=timeout)
        if res.get('error') or res.get('exit_status', 1) != 0:
            app.logger.error(f"  Kill command failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        out = res.get('stdout','')
        if 'OK' in out:
            app.logger.info(f"  Successfully killed process {pid}")
            return {'status':'success','message':f'Process {pid} terminated'}
        else:
            app.logger.warning(f"  Kill process returned: {out}")
            return {'status':'error','message':out or res.get('stderr',''), 'diagnosis':'KillFailed'}

    # 网络信息 / 磁盘等：尝试简单命令并返回原始输出，前端可根据诊断简化显示
    if path == '/api/server/network':
        app.logger.debug(f"  Fetching network info using ip/ifconfig")
        cmd = "ip -j addr || ifconfig"
        res = ssh_run_command(server, cmd, timeout=timeout)
        if res.get('error') or res.get('exit_status', 1) != 0:
            app.logger.warning(f"  Network fetch failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        app.logger.info(f"  Successfully fetched network info")
        return {'status':'success','data':{'raw': res.get('stdout','')}, 'diagnosis':'Limited'}

    if path == '/api/server/disk':
        app.logger.debug(f"  Fetching disk info using df")
        cmd = "df -B1 -h || df -h"
        res = ssh_run_command(server, cmd, timeout=timeout)
        if res.get('error') or res.get('exit_status', 1) != 0:
            app.logger.warning(f"  Disk fetch failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        app.logger.info(f"  Successfully fetched disk info")
        return {'status':'success','data':{'raw': res.get('stdout','')}, 'diagnosis':'Limited'}

    return {'status':'error','message':'Unsupported path for SSH proxy', 'diagnosis':'NotImplemented'}

def sftp_upload(server, local_path, remote_path, timeout=10):
    host = server.get('host')
    username = server.get('username') or None
    password = server.get('password') or None
    ports = [22]
    try:
        if server.get('port'):
            ports.append(int(server.get('port')))
    except Exception:
        pass
    last_exc = None
    for p in ports:
        try:
            transport = paramiko.Transport((host, p))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.put(local_path, remote_path)
            sftp.close()
            transport.close()
            return {'status': 'success'}
        except Exception as e:
            last_exc = e
            try:
                transport.close()
            except Exception:
                pass
            continue
    return {'status': 'error', 'message': str(last_exc) if last_exc else 'SFTP failed'}

@app.route('/api/servers/<int:server_id>/upload', methods=['POST'])
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
        # 注意：这里简单判断是否为目录路径。更严谨的做法可能需要检查远程文件系统，但这里做个约定即可。
        # 如果 remote_path 为空，默认上传到当前用户主目录或临时目录可能不合适，这里假设用户至少指定了目录。
        # 如果 remote_path 以 / 结尾，或者看起来像个目录（虽然无法完全确定），我们追加文件名。
        # 为简单起见，如果 remote_path 以 / 结尾，就追加文件名。
        if remote_path.endswith('/'):
            remote_path = os.path.join(remote_path, file.filename)
        # 另一种情况：用户可能只写了 "/tmp"，意图是目录。
        # 但我们无法区分 "/tmp" 是文件还是目录。
        # 我们可以约定：如果 remote_path 是目录，请以 / 结尾。
        # 或者，我们可以在 SFTP 上传前尝试探测，但这会增加延迟。
        # 
        # 改进策略：如果 remote_path 没有扩展名，且 file.filename 有扩展名，
        # 这种判断也不完全准确（Linux 文件可以无扩展名）。
        # 
        # 最稳妥的方式：遵循用户输入。但为了方便，支持以 / 结尾的自动拼接。
        
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
            app.logger.info(f"📤 Uploading {file.filename} to {server['host']}:{remote_path}")
            res = sftp_upload(server_dict, tmp_path, remote_path)
            
            # 清理临时文件
            try:
                os.remove(tmp_path)
            except Exception as e:
                app.logger.warning(f"⚠️ Failed to remove temp file {tmp_path}: {e}")
                
            if res.get('status') != 'success':
                app.logger.error(f"❌ SFTP upload failed: {res.get('message')}")
                return jsonify({'status': 'error', 'message': res.get('message', '上传失败')}), 400
                
            return jsonify({'status': 'success', 'message': '文件上传成功'}), 200
            
        except Exception as e:
            app.logger.error(f"❌ Upload process error: {e}")
            return jsonify({'status': 'error', 'message': f'上传处理错误: {str(e)}'}), 500
            
    except Exception as e:
        app.logger.error(f"❌ Unhandled upload error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/servers/<int:server_id>/execute', methods=['POST'])
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

@app.route('/api/servers/<int:server_id>/proxy/server/status', methods=['GET'])
def proxy_server_status(server_id):
    try:
        app.logger.info(f"📊 [PROXY] GET /api/servers/{server_id}/proxy/server/status")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            app.logger.warning(f"⚠️  Server {server_id} not found in database")
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        app.logger.debug(f"  Fetched server from DB: {server['host']}")
        resp = fetch_remote_api(server, '/api/server/status')
        status_code = 200 if resp.get('status') == 'success' else 502
        if status_code != 200:
            app.logger.warning(f"  Response status failed: {resp}")
        return jsonify(resp), status_code
    except Exception as e:
        app.logger.error(f"❌ Error in proxy_server_status: {type(e).__name__}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/servers/<int:server_id>/proxy/server/processes', methods=['GET'])
def proxy_server_processes(server_id):
    try:
        limit = request.args.get('limit', 20, type=int)
        sort_by = request.args.get('sort_by', 'memory', type=str)
        
        app.logger.info(f"📊 [PROXY] GET /api/servers/{server_id}/proxy/server/processes?limit={limit}&sort_by={sort_by}")

        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            app.logger.warning(f"⚠️  Server {server_id} not found in database")
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        app.logger.debug(f"  Fetched server from DB: {server['host']}")
        resp = fetch_remote_api(server, '/api/server/processes', params={'limit': limit, 'sort_by': sort_by})
        status_code = 200 if resp.get('status') == 'success' else 502
        if status_code != 200:
            app.logger.warning(f"  Response status failed: {resp}")
        return jsonify(resp), status_code
    except Exception as e:
        app.logger.error(f"❌ Error in proxy_server_processes: {type(e).__name__}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/servers/<int:server_id>/proxy/server/process/<int:pid>/kill', methods=['POST'])
def proxy_kill_process(server_id, pid):
    try:
        app.logger.info(f"🔪 [PROXY] POST /api/servers/{server_id}/proxy/server/process/{pid}/kill")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            app.logger.warning(f"⚠️  Server {server_id} not found in database")
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        app.logger.debug(f"  Attempting to kill process {pid} on {server['host']}")
        resp = fetch_remote_api(server, f'/api/process/{pid}/kill', method='POST')
        status_code = 200 if resp.get('status') == 'success' else 502
        if status_code != 200:
            app.logger.warning(f"  Kill process failed: {resp}")
        return jsonify(resp), status_code
    except Exception as e:
        app.logger.error(f"❌ Error in proxy_kill_process: {type(e).__name__}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/servers/<int:server_id>/proxy/server/network', methods=['GET'])
def proxy_server_network(server_id):
    try:
        app.logger.info(f"🌐 [PROXY] GET /api/servers/{server_id}/proxy/server/network")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            app.logger.warning(f"⚠️  Server {server_id} not found in database")
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        app.logger.debug(f"  Fetching network info from {server['host']}")
        resp = fetch_remote_api(server, '/api/server/network')
        status_code = 200 if resp.get('status') == 'success' else 502
        if status_code != 200:
            app.logger.warning(f"  Network info fetch failed: {resp}")
        return jsonify(resp), status_code
    except Exception as e:
        app.logger.error(f"❌ Error in proxy_server_network: {type(e).__name__}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/servers/<int:server_id>/proxy/server/disk', methods=['GET'])
def proxy_server_disk(server_id):
    try:
        app.logger.info(f"💾 [PROXY] GET /api/servers/{server_id}/proxy/server/disk")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT host, port, username, password FROM servers WHERE id = ?', (server_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            app.logger.warning(f"⚠️  Server {server_id} not found in database")
            return jsonify({'status': 'error', 'message': 'Server not found'}), 404

        server = {'host': row['host'], 'port': row['port'], 'username': row['username'], 'password': row['password']}
        app.logger.debug(f"  Fetching disk info from {server['host']}")
        resp = fetch_remote_api(server, '/api/server/disk')
        status_code = 200 if resp.get('status') == 'success' else 502
        if status_code != 200:
            app.logger.warning(f"  Disk info fetch failed: {resp}")
        return jsonify(resp), status_code
    except Exception as e:
        app.logger.error(f"❌ Error in proxy_server_disk: {type(e).__name__}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500






# ==================== 全局变量接口 ====================

@app.route('/api/globals', methods=['GET'])
def list_globals():
    """获取所有全局变量"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT key, value, description, updated_at FROM global_variables ORDER BY key')
        variables = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'status': 'success', 'data': variables}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/globals', methods=['POST'])
def create_global():
    """创建或更新全局变量"""
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        description = data.get('description', '')
        
        if not key:
            return jsonify({'status': 'error', 'message': '变量名不能为空'}), 400
            
        conn = get_db_connection()
        c = conn.cursor()
        
        # 使用 REPLACE INTO 实现 upsert
        c.execute('REPLACE INTO global_variables (key, value, description, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                 (key, value, description))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': '变量保存成功'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/globals/<key>', methods=['DELETE'])
def delete_global(key):
    """删除全局变量"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM global_variables WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': '变量已删除'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== 工作流管理接口 ====================

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    """获取工作流列表"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id, name, description, updated_at FROM workflows ORDER BY updated_at DESC')
        workflows = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'status': 'success', 'data': workflows}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/workflows', methods=['POST'])
def create_workflow():
    """创建新工作流"""
    try:
        data = request.get_json()
        name = data.get('name')
        workflow_data = data.get('data') # JSON string
        description = data.get('description', '')
        
        if not name or not workflow_data:
            return jsonify({'status': 'error', 'message': '名称和数据不能为空'}), 400
            
        # 验证 data 是否为有效 JSON
        try:
            if isinstance(workflow_data, str):
                json.loads(workflow_data)
            else:
                workflow_data = json.dumps(workflow_data)
        except json.JSONDecodeError:
            return jsonify({'status': 'error', 'message': '数据格式错误'}), 400

        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO workflows (name, data, description) VALUES (?, ?, ?)',
                     (name, workflow_data, description))
            conn.commit()
            wf_id = c.lastrowid
            conn.close()
            return jsonify({'status': 'success', 'message': '工作流保存成功', 'data': {'id': wf_id}}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'status': 'error', 'message': '工作流名称已存在'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/workflows/<int:wf_id>', methods=['GET'])
def get_workflow(wf_id):
    """获取指定工作流"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM workflows WHERE id = ?', (wf_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'status': 'error', 'message': '工作流不存在'}), 404
            
        return jsonify({'status': 'success', 'data': dict(row)}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/workflows/<int:wf_id>', methods=['PUT'])
def update_workflow(wf_id):
    """更新工作流"""
    try:
        data = request.get_json()
        workflow_data = data.get('data')
        description = data.get('description')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        update_fields = []
        params = []
        
        if workflow_data:
            if not isinstance(workflow_data, str):
                workflow_data = json.dumps(workflow_data)
            update_fields.append('data = ?')
            params.append(workflow_data)
            
        if description is not None:
            update_fields.append('description = ?')
            params.append(description)
            
        if not update_fields:
            return jsonify({'status': 'success', 'message': '无变更'}), 200
            
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        params.append(wf_id)
        
        c.execute(f'UPDATE workflows SET {", ".join(update_fields)} WHERE id = ?', params)
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': '工作流更新成功'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/workflows/<int:wf_id>', methods=['DELETE'])
def delete_workflow(wf_id):
    """删除工作流"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM workflows WHERE id = ?', (wf_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': '工作流已删除'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
