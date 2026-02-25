from flask import Blueprint, jsonify, request
import psutil
from datetime import datetime

# 创建蓝图
bp = Blueprint('server', __name__)

@bp.route('/status', methods=['GET'])
def get_server_status():
    """获取服务器基本状态信息"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
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


@bp.route('/processes', methods=['GET'])
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


@bp.route('/network', methods=['GET'])
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


@bp.route('/disk', methods=['GET'])
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
