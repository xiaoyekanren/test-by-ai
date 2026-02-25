from flask import Blueprint, jsonify
import psutil

# 创建蓝图
bp = Blueprint('process', __name__)

@bp.route('/<int:pid>', methods=['GET'])
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


@bp.route('/<int:pid>/kill', methods=['POST'])
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
