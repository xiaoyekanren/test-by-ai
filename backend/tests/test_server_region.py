# backend/tests/test_server_region.py
import sys
sys.path.insert(0, 'backend')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Server

def test_server_region_field():
    """Test Server model has region field with default value"""
    server = Server(
        name="test-region-server",
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret"
    )
    # 默认值应为 私有云
    assert server.region == "私有云"

    server2 = Server(
        name="test-region-server-2",
        host="192.168.1.2",
        port=22,
        username="admin",
        password="secret",
        region="公司"
    )
    assert server2.region == "公司"

def test_server_region_valid_values():
    """Test Server model accepts valid region values"""
    valid_regions = ["私有云", "公司-上层", "公司", "Fit楼", "公有云", "异构"]
    for region in valid_regions:
        server = Server(
            name=f"server-{region}",
            host="192.168.1.1",
            port=22,
            username="admin",
            password="secret",
            region=region
        )
        assert server.region == region