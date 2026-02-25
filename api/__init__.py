from flask import Blueprint

# 创建 API 蓝图
api_bp = Blueprint('api', __name__, url_prefix='/api')

# 导入各个模块的路由
from . import local_server, process, servers, services, globals, workflows

# 注册路由
api_bp.register_blueprint(local_server.bp, url_prefix='/server')
api_bp.register_blueprint(process.bp, url_prefix='/process')
api_bp.register_blueprint(servers.bp, url_prefix='/servers')
api_bp.register_blueprint(services.bp, url_prefix='/services')
api_bp.register_blueprint(globals.bp, url_prefix='/globals')
api_bp.register_blueprint(workflows.bp, url_prefix='/workflows')
