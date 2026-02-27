import json
import requests

# 工作流数据
workflow_data = {
    'nodes': [
        {
            'id': 1,
            'type': 'server',
            'x': 100,
            'y': 100,
            'serverId': 1,
            'serverName': '目标服务器',
            'serverHost': '127.0.0.1'
        },
        {
            'id': 2,
            'type': 'command',
            'x': 300,
            'y': 50,
            'title': '环境准备',
            'command': 'sudo apt update && sudo apt install -y openjdk-11-jdk && sudo mkdir -p /opt/iotdb && sudo chmod 755 /opt/iotdb',
            'refName': 'prepare_env'
        },
        {
            'id': 3,
            'type': 'command',
            'x': 300,
            'y': 150,
            'title': '下载 IoTDB',
            'command': 'cd /tmp && wget -O iotdb.zip https://github.com/apache/iotdb/releases/download/v1.1.0/apache-iotdb-1.1.0-all-bin.zip',
            'refName': 'download_iotdb'
        },
        {
            'id': 4,
            'type': 'command',
            'x': 300,
            'y': 250,
            'title': '解压安装包',
            'command': 'sudo unzip /tmp/iotdb.zip -d /opt/iotdb && sudo mv /opt/iotdb/apache-iotdb-1.1.0-all-bin /opt/iotdb/iotdb',
            'refName': 'unzip_iotdb'
        },
        {
            'id': 5,
            'type': 'command',
            'x': 300,
            'y': 350,
            'title': '配置 IoTDB',
            'command': 'sudo cp /opt/iotdb/iotdb/conf/iotdb-engine.properties /opt/iotdb/iotdb/conf/iotdb-engine.properties.bak && sudo sed -i \'s|#data_dirs=./data|data_dirs=/opt/iotdb/iotdb/data|g\' /opt/iotdb/iotdb/conf/iotdb-engine.properties && sudo sed -i \'s|#system_dir=./system|system_dir=/opt/iotdb/iotdb/system|g\' /opt/iotdb/iotdb/conf/iotdb-engine.properties',
            'refName': 'configure_iotdb'
        },
        {
            'id': 6,
            'type': 'command',
            'x': 300,
            'y': 450,
            'title': '启动 IoTDB 服务',
            'command': 'cd /opt/iotdb/iotdb && sudo ./sbin/start-server.sh && sleep 10',
            'refName': 'start_iotdb'
        },
        {
            'id': 7,
            'type': 'command',
            'x': 300,
            'y': 550,
            'title': '验证服务状态',
            'command': 'cd /opt/iotdb/iotdb && sudo ./sbin/status-server.sh && echo "show databases;" | sudo ./sbin/start-cli.sh -h 127.0.0.1 -p 6667 -u root -pw root',
            'refName': 'verify_iotdb'
        }
    ],
    'connections': [
        {'from': 1, 'to': 2, 'type': 'default'},
        {'from': 2, 'to': 3, 'type': 'success'},
        {'from': 3, 'to': 4, 'type': 'success'},
        {'from': 4, 'to': 5, 'type': 'success'},
        {'from': 5, 'to': 6, 'type': 'success'},
        {'from': 6, 'to': 7, 'type': 'success'}
    ]
}

# 构建请求数据
data = {
    'name': 'IoTDB 部署工作流',
    'description': '自动化部署 IoTDB 数据库服务',
    'nodes': workflow_data['nodes'],
    'connections': workflow_data['connections']
}

# 发送请求
try:
    response = requests.post('http://localhost:5001/api/workflows', json=data)
    print('Response:', response.json())
except Exception as e:
    print('Error:', str(e))
