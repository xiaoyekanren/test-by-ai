from typing import FrozenSet


TOP_LEVEL_SERVER_NODE_TYPES: FrozenSet[str] = frozenset({
    "shell",
    "upload",
    "download",
    "config",
    "iotdb_config",
    "log_view",
    "iotdb_deploy",
    "iotdb_start",
    "iotdb_cli",
    "iotdb_stop",
    "iot_benchmark_deploy",
    "iot_benchmark_start",
    "iot_benchmark_wait",
})

CLUSTER_SERVER_NODE_TYPES: FrozenSet[str] = frozenset({
    "iotdb_cluster_deploy",
    "iotdb_cluster_start",
    "iotdb_cluster_check",
    "iotdb_cluster_stop",
})

SERVER_REQUIRED_NODE_TYPES: FrozenSet[str] = (
    TOP_LEVEL_SERVER_NODE_TYPES | CLUSTER_SERVER_NODE_TYPES
)


def node_requires_server(node_type: str) -> bool:
    return node_type in SERVER_REQUIRED_NODE_TYPES


def node_uses_top_level_server(node_type: str) -> bool:
    return node_type in TOP_LEVEL_SERVER_NODE_TYPES
