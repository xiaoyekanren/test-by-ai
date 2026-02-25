from flask import Blueprint, jsonify, request

# 创建蓝图
bp = Blueprint('services', __name__)

@bp.route('', methods=['GET'])
def get_services():
    """获取服务列表（为后续功能预留）"""
    try:
        # 这里返回空列表，因为服务部署功能尚未实现
        return jsonify({
            'status': 'success',
            'data': []
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@bp.route('', methods=['POST'])
def create_service():
    """创建新服务（为后续功能预留）"""
    try:
        data = request.get_json()
        return jsonify({
            'status': 'success',
            'message': '服务创建功能尚未实现',
            'data': data
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
