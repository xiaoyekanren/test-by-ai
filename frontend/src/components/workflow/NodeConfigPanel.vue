<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElSwitch,
  ElButton,
  ElEmpty
} from 'element-plus'
import { Edit, Plus, Delete } from '@element-plus/icons-vue'
import { useWorkflowsStore } from '@/stores/workflows'
import { useServersStore } from '@/stores/servers'
import { REGION_OPTIONS } from '@/types'
import type { NodeType } from '@/types'

interface KeyValueDraft {
  id: string
  key: string
  value: string
}

interface FieldDefinition {
  field: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'json' | 'keyValue' | 'server' | 'region' | 'clusterNodes'
  options?: Array<{ value: string | number | boolean; label: string }>
  placeholder?: string
  min?: number
  max?: number
}

interface FieldSection {
  key: string
  title: string
  fields: FieldDefinition[]
}

const workflowsStore = useWorkflowsStore()
const serversStore = useServersStore()

// Local edit state for node label
const editingLabel = ref('')
const isEditingLabel = ref(false)
const jsonDrafts = ref<Record<string, string>>({})
const jsonDraftNodeId = ref<string | null>(null)
const keyValueDrafts = ref<Record<string, KeyValueDraft[]>>({})
const keyValueDraftSnapshots = ref<Record<string, string>>({})

// Get selected node
const selectedNode = computed(() => workflowsStore.selectedNode)

const nodeHelpText = computed(() => {
  if (!selectedNode.value) return ''

  if (selectedNode.value.data.nodeType === 'iotdb_config') {
    return 'Use this node to declare the config items that should be written during workflow execution. It does not read the remote file while you are editing the workflow.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_deploy') {
    return 'Describe the cluster topology here. During execution, the workflow will upload the package, unpack it on each host, and write role-specific ConfigNode/DataNode settings.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_start') {
    return 'This node starts the first ConfigNode, then the remaining ConfigNodes, and finally all DataNodes.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_check') {
    return 'This node runs show cluster against the first DataNode and can execute extra validation SQL statements afterward.'
  }

  if (selectedNode.value.data.nodeType === 'iot_benchmark_start') {
    return 'Start one IoT Benchmark run in the background. Later nodes can continue while Wait IoT Benchmark polls the remote process.'
  }

  if (selectedNode.value.data.nodeType === 'iot_benchmark_wait') {
    return 'Wait for the benchmark_run produced by Start IoT Benchmark, then return the tail of its output log.'
  }

  return ''
})

// Server options for dropdown
const serverOptions = computed(() => {
  return serversStore.servers.map(server => ({
    value: server.id,
    label: `${server.name} (${server.host})`,
    region: server.region || '私有云'
  }))
})

const selectedRegion = computed(() => {
  const value = getConfigValue('region')
  return typeof value === 'string' && value ? value : null
})

const filteredServerOptions = computed(() => {
  if (!selectedRegion.value) return serverOptions.value
  return serverOptions.value.filter(option => option.region === selectedRegion.value)
})

// Fetch servers on mount
onMounted(async () => {
  if (serversStore.servers.length === 0) {
    try {
      await serversStore.fetchServers()
    } catch {
      // Silently fail - servers may not be configured
    }
  }
})

// Watch selected node to update local state
watch(selectedNode, (node) => {
  if (node) {
    editingLabel.value = node.data.label
    if (jsonDraftNodeId.value !== node.id) {
      jsonDrafts.value = {}
      keyValueDrafts.value = {}
      keyValueDraftSnapshots.value = {}
      jsonDraftNodeId.value = node.id
    }
  } else {
    jsonDrafts.value = {}
    keyValueDrafts.value = {}
    keyValueDraftSnapshots.value = {}
    jsonDraftNodeId.value = null
  }
}, { immediate: true })

// Start editing label
const startEditLabel = () => {
  if (selectedNode.value) {
    editingLabel.value = selectedNode.value.data.label
    isEditingLabel.value = true
  }
}

// Save label
const saveLabel = () => {
  if (selectedNode.value && editingLabel.value.trim()) {
    workflowsStore.updateNodeLabel(selectedNode.value.id, editingLabel.value.trim())
  }
  isEditingLabel.value = false
}

// Cancel label edit
const cancelEditLabel = () => {
  if (selectedNode.value) {
    editingLabel.value = selectedNode.value.data.label
  }
  isEditingLabel.value = false
}

// Update config field
const updateConfig = (field: string, value: unknown) => {
  if (!selectedNode.value) return
  workflowsStore.updateNodeConfig(selectedNode.value.id, { [field]: value })
}

const updateServerConfig = (value: number | string | null | undefined) => {
  if (!selectedNode.value) return
  const serverId = value === '' || value === null || value === undefined ? null : Number(value)
  const selectedServer = serversStore.servers.find(server => server.id === serverId)
  workflowsStore.updateNodeConfig(selectedNode.value.id, {
    server_id: serverId,
    region: selectedServer ? selectedServer.region || '私有云' : null
  })
}

const updateRegionConfig = (value: string | null | undefined) => {
  if (!selectedNode.value) return
  workflowsStore.updateNodeConfig(selectedNode.value.id, {
    region: value || null,
    server_id: null
  })
}

// Get config value
const getConfigValue = (field: string): unknown => {
  if (!selectedNode.value) return null
  return selectedNode.value.data.config[field]
}

const getClusterNodeRole = (field: string): 'confignode' | 'datanode' => {
  return field === 'config_nodes' ? 'confignode' : 'datanode'
}

const getClusterNodeList = (field: string): Record<string, unknown>[] => {
  const value = getConfigValue(field)
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    : []
}

const getClusterNodeServerIds = (field: string): number[] => {
  return getClusterNodeList(field)
    .map(item => Number(item.server_id))
    .filter(id => Number.isFinite(id))
}

const getServerRegion = (serverId: number) => {
  return serversStore.servers.find(server => server.id === serverId)?.region || '私有云'
}

const getClusterSelectedRegion = () => {
  const selectedIds = [
    ...getClusterNodeServerIds('config_nodes'),
    ...getClusterNodeServerIds('data_nodes')
  ]
  const firstId = selectedIds.find(id => serversStore.servers.some(server => server.id === id))
  return firstId === undefined ? null : getServerRegion(firstId)
}

const getClusterServerOptions = (field: string) => {
  const selectedRegion = getClusterSelectedRegion()
  const selectedIds = new Set(getClusterNodeServerIds(field))

  return serverOptions.value.filter(option => {
    if (!selectedRegion) return true
    return option.region === selectedRegion || selectedIds.has(Number(option.value))
  })
}

const buildClusterNode = (
  field: string,
  serverId: number,
  existingNodes: Record<string, unknown>[]
) => {
  const server = serversStore.servers.find(item => item.id === serverId)
  const existing = existingNodes.find(item => Number(item.server_id) === serverId) || {}
  return {
    ...existing,
    server_id: serverId,
    host: server?.host || existing.host,
    node_role: getClusterNodeRole(field)
  }
}

const filterClusterNodesByRegion = (field: string, region: string | null, nextValue?: Record<string, unknown>[]) => {
  const nodes = nextValue || getClusterNodeList(field)
  if (!region) return nodes
  return nodes.filter(node => getServerRegion(Number(node.server_id)) === region)
}

const updateClusterNodes = (field: string, value: unknown) => {
  if (!selectedNode.value) return

  const serverIds = Array.isArray(value) ? value.map(Number).filter(id => Number.isFinite(id)) : []
  const existingNodes = getClusterNodeList(field)
  const selectedRegion = serverIds.length > 0 ? getServerRegion(serverIds[0]) : getClusterSelectedRegion()
  const nextNodes = serverIds
    .filter(serverId => !selectedRegion || getServerRegion(serverId) === selectedRegion)
    .map(serverId => buildClusterNode(field, serverId, existingNodes))

  const otherField = field === 'config_nodes' ? 'data_nodes' : 'config_nodes'
  workflowsStore.updateNodeConfig(selectedNode.value.id, {
    [field]: nextNodes,
    [otherField]: filterClusterNodesByRegion(otherField, selectedRegion)
  })
}

const getFieldLayoutClass = (field: FieldDefinition) => {
  if (['textarea', 'json', 'keyValue'].includes(field.type)) return 'field-full'
  if (field.type === 'clusterNodes') return 'field-full'
  if (field.type === 'number') return 'field-compact field-inline'
  if (field.type === 'checkbox') return 'field-compact field-inline'
  if (['host', 'username', 'password', 'node_role', 'package_type', 'wait_strategy', 'sql_dialect', 'format', 'type', 'region'].includes(field.field)) return 'field-medium field-inline'
  if (['local_path', 'remote_path', 'file_path', 'iotdb_home', 'install_dir', 'artifact_local_path', 'remote_package_path'].includes(field.field)) return 'field-wide field-inline'
  if (field.type === 'server' || field.type === 'region') return 'field-wide field-inline'
  return 'field-wide field-inline'
}

// Field definitions by node type
const getFieldDefinitions = (nodeType: NodeType): FieldDefinition[] => {
  const definitions: Record<NodeType, FieldDefinition[]> = {
    // Basic nodes
    shell: [
      { field: 'command', label: 'Command', type: 'textarea', placeholder: 'Enter shell command...' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 },
      { field: 'retry', label: 'Retry Count', type: 'number', min: 0, max: 10 }
    ],
    upload: [
      { field: 'local_path', label: 'Local Path', type: 'text', placeholder: '/path/to/local/file' },
      { field: 'remote_path', label: 'Remote Path', type: 'text', placeholder: '/path/to/remote/file' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    download: [
      { field: 'remote_path', label: 'Remote Path', type: 'text', placeholder: '/path/to/remote/file' },
      { field: 'local_path', label: 'Local Path', type: 'text', placeholder: '/path/to/local/file' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' }
    ],
    config: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/config/file' },
      { field: 'config_items', label: 'Config Items', type: 'keyValue', placeholder: 'e.g. key = value' },
      { field: 'backup_before_write', label: 'Backup Before Write', type: 'checkbox', placeholder: 'Create a .bak file before writing' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    log_view: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/log/file' },
      { field: 'lines', label: 'Lines', type: 'number', min: 1, max: 10000 },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' }
    ],

    // IoTDB nodes
    iotdb_deploy: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'artifact_local_path', label: 'Artifact Local Path', type: 'text', placeholder: '/path/to/apache-iotdb-bin.zip' },
      { field: 'remote_package_path', label: 'Remote Package Path', type: 'text', placeholder: '/tmp/apache-iotdb-bin.zip' },
      { field: 'install_dir', label: 'Install Directory', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'package_type', label: 'Package Type', type: 'select', options: [
        { value: 'auto', label: 'Auto Detect' },
        { value: 'zip', label: 'ZIP' },
        { value: 'tar.gz', label: 'tar.gz' }
      ]},
      { field: 'extract_subdir', label: 'Extract Subdirectory', type: 'text', placeholder: 'Optional inner directory name' },
      { field: 'overwrite', label: 'Overwrite Install Dir', type: 'checkbox', placeholder: 'Delete existing install directory first' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_start: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'host', label: 'Host', type: 'text', placeholder: 'Optional, defaults to server host' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'wait_port', label: 'Wait Port', type: 'number', min: 1, max: 65535 },
      { field: 'wait_strategy', label: 'Wait Strategy', type: 'select', options: [
        { value: 'port', label: 'Port Check' },
        { value: 'cli', label: 'CLI Check' }
      ]},
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_stop: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'graceful', label: 'Graceful Shutdown', type: 'checkbox', placeholder: 'Use graceful shutdown script' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_cli: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'host', label: 'Host', type: 'text', placeholder: 'Optional, defaults to server host' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'username', label: 'Username', type: 'text', placeholder: 'root' },
      { field: 'password', label: 'Password', type: 'text', placeholder: 'root' },
      { field: 'sql_dialect', label: 'SQL Dialect', type: 'select', options: [
        { value: 'tree', label: 'Tree' },
        { value: 'table', label: 'Table' }
      ]},
      { field: 'sqls', label: 'SQL Statements', type: 'textarea', placeholder: 'Enter one SQL statement per line...' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_config: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'file_path', label: 'Target Config File', type: 'text', placeholder: 'Optional, defaults to {iotdb_home}/conf/iotdb-system.properties' },
      { field: 'config_items', label: 'Override Items', type: 'keyValue', placeholder: 'e.g. dn_rpc_port = 6667' },
      { field: 'backup_before_write', label: 'Backup Before Write', type: 'checkbox', placeholder: 'Create a backup before applying overrides' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_cluster_deploy: [
      { field: 'artifact_local_path', label: 'Artifact Local Path', type: 'text', placeholder: '/path/to/apache-iotdb-bin.zip' },
      { field: 'remote_package_path', label: 'Remote Package Path', type: 'text', placeholder: '/tmp/apache-iotdb-cluster-bin.zip' },
      { field: 'install_dir', label: 'Base Install Directory', type: 'text', placeholder: '/opt/iotdb-cluster' },
      { field: 'package_type', label: 'Package Type', type: 'select', options: [
        { value: 'auto', label: 'Auto Detect' },
        { value: 'zip', label: 'ZIP' },
        { value: 'tar.gz', label: 'tar.gz' }
      ]},
      { field: 'extract_subdir', label: 'Extract Subdirectory', type: 'text', placeholder: 'Optional inner directory name' },
      { field: 'overwrite', label: 'Overwrite Install Dir', type: 'checkbox', placeholder: 'Delete existing install directory first' },
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'defaultCluster' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'clusterNodes', placeholder: 'Select ConfigNode servers' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'clusterNodes', placeholder: 'Select DataNode servers' },
      { field: 'common_config', label: 'Common Config', type: 'json', placeholder: '{"schema_replication_factor":"1","data_replication_factor":"1"}' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_cluster_start: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy node' },
      { field: 'wait_strategy', label: 'Wait Strategy', type: 'select', options: [
        { value: 'port', label: 'Port Check' },
        { value: 'cli', label: 'CLI Check (DataNode only)' }
      ]},
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
    ],
    iotdb_cluster_check: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy/start node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy/start node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy/start node' },
      { field: 'username', label: 'Username', type: 'text', placeholder: 'root' },
      { field: 'password', label: 'Password', type: 'text', placeholder: 'root' },
      { field: 'sql_dialect', label: 'SQL Dialect', type: 'select', options: [
        { value: 'tree', label: 'Tree' },
        { value: 'table', label: 'Table' }
      ]},
      { field: 'validation_sqls', label: 'Validation SQLs', type: 'textarea', placeholder: 'Optional extra SQL statements, one per line...' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
    ],
    iotdb_cluster_stop: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy/start node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy/start node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'clusterNodes', placeholder: 'Inherited from deploy/start node' },
      { field: 'graceful', label: 'Graceful Shutdown', type: 'checkbox', placeholder: 'Stop nodes gracefully before forcing' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
    ],
    iot_benchmark_start: [
      { field: 'server_id', label: 'Benchmark Server', type: 'server' },
      { field: 'region', label: 'Region', type: 'region' },
      { field: 'benchmark_home', label: 'Benchmark Home', type: 'text', placeholder: '/opt/iot-benchmark-iotdb-2.0' },
      { field: 'target_host', label: 'Target Host', type: 'text', placeholder: 'IoTDB host, inherited when possible' },
      { field: 'rpc_port', label: 'Target RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'db_switch', label: 'DB Switch', type: 'select', options: [
        { value: 'IoTDB-200-SESSION_BY_TABLET', label: 'IoTDB 2.0 Session Tablet' },
        { value: 'IoTDB-200-SESSION_BY_RECORD', label: 'IoTDB 2.0 Session Record' },
        { value: 'IoTDB-200-SESSION_BY_RECORDS', label: 'IoTDB 2.0 Session Records' },
        { value: 'IoTDB-200-JDBC', label: 'IoTDB 2.0 JDBC' },
        { value: 'IoTDB-200-REST', label: 'IoTDB 2.0 REST' }
      ]},
      { field: 'dialect', label: 'Dialect', type: 'select', options: [
        { value: 'tree', label: 'Tree' },
        { value: 'table', label: 'Table' }
      ]},
      { field: 'username', label: 'Username', type: 'text', placeholder: 'root' },
      { field: 'password', label: 'Password', type: 'text', placeholder: 'root' },
      { field: 'db_name', label: 'DB Name', type: 'text', placeholder: 'test' },
      { field: 'work_mode', label: 'Work Mode', type: 'select', options: [
        { value: 'testWithDefaultPath', label: 'Default Test' },
        { value: 'generateDataMode', label: 'Generate Data' },
        { value: 'verificationWriteMode', label: 'Verification Write' },
        { value: 'verificationQueryMode', label: 'Verification Query' }
      ]},
      { field: 'loop', label: 'Loop', type: 'number', min: 1, max: 100000000 },
      { field: 'operation_proportion', label: 'Operation Proportion', type: 'text', placeholder: '1:0:0:0:0:0:0:0:0:0:0:0' },
      { field: 'config_items', label: 'Extra Config Items', type: 'keyValue', placeholder: 'Override config.properties item' },
      { field: 'timeout', label: 'Start Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iot_benchmark_wait: [
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 86400 },
      { field: 'poll_interval_seconds', label: 'Poll Interval (seconds)', type: 'number', min: 1, max: 300 },
      { field: 'tail_lines', label: 'Tail Lines', type: 'number', min: 1, max: 5000 },
      { field: 'kill_on_timeout', label: 'Kill On Timeout', type: 'checkbox', placeholder: 'Try to kill the remote benchmark process if waiting times out' }
    ],

    // Control nodes
    condition: [
      { field: 'expression', label: 'Expression', type: 'textarea', placeholder: 'Enter condition expression...' }
    ],
    loop: [
      { field: 'loop_type', label: 'Loop Type', type: 'select', options: [
        { value: 'for', label: 'For Loop' },
        { value: 'while', label: 'While Loop' }
      ]},
      { field: 'iterations', label: 'Iterations', type: 'number', min: 1, max: 10000 },
      { field: 'condition', label: 'Condition', type: 'text', placeholder: 'Loop condition (for while)' }
    ],
    wait: [
      { field: 'condition', label: 'Wait Condition', type: 'textarea', placeholder: 'Condition to wait for...' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 },
      { field: 'interval', label: 'Check Interval (seconds)', type: 'number', min: 1, max: 300 }
    ],
    parallel: [
      { field: 'max_concurrent', label: 'Max Concurrent', type: 'number', min: 1, max: 100 }
    ],
    assert: [
      { field: 'assert_type', label: 'Assert Type', type: 'select', options: [
        { value: 'log_contains', label: 'Log Contains' },
        { value: 'file_exists', label: 'File Exists' },
        { value: 'process_running', label: 'Process Running' },
        { value: 'port_open', label: 'Port Open' },
        { value: 'custom', label: 'Custom' }
      ]},
      { field: 'params', label: 'Parameters', type: 'json', placeholder: '{"param": "value"}' },
      { field: 'expected', label: 'Expected Value', type: 'text', placeholder: 'Expected result' }
    ],

    // Result nodes
    report: [
      { field: 'format', label: 'Format', type: 'select', options: [
        { value: 'html', label: 'HTML' },
        { value: 'json', label: 'JSON' },
        { value: 'markdown', label: 'Markdown' }
      ]},
      { field: 'include_logs', label: 'Include Logs', type: 'checkbox' }
    ],
    summary: [],
    notify: [
      { field: 'type', label: 'Notification Type', type: 'select', options: [
        { value: 'email', label: 'Email' },
        { value: 'slack', label: 'Slack' },
        { value: 'webhook', label: 'Webhook' }
      ]},
      { field: 'recipient', label: 'Recipient', type: 'text', placeholder: 'Email address or channel' },
      { field: 'template', label: 'Template', type: 'text', placeholder: 'Message template name' }
    ]
  }

  return definitions[nodeType] || []
}

const fieldSectionTitles: Record<string, string> = {
  connection: 'Connection',
  package: 'Package',
  paths: 'Paths',
  runtime: 'Runtime',
  configuration: 'Configuration',
  command: 'Command',
  checks: 'Checks',
  notification: 'Notification',
  output: 'Output',
  general: 'General'
}

const getFieldSection = (field: FieldDefinition) => {
  if (['server_id', 'host', 'target_host', 'username', 'password', 'region'].includes(field.field)) return 'connection'
  if (['db_switch', 'dialect', 'db_name'].includes(field.field)) return 'connection'
  if (['artifact_local_path', 'remote_package_path', 'package_type', 'extract_subdir', 'overwrite'].includes(field.field)) return 'package'
  if (['local_path', 'remote_path', 'file_path', 'iotdb_home', 'install_dir', 'benchmark_home'].includes(field.field)) return 'paths'
  if (['timeout', 'timeout_seconds', 'retry', 'rpc_port', 'wait_port', 'node_role', 'wait_strategy', 'graceful'].includes(field.field)) return 'runtime'
  if (['poll_interval_seconds', 'tail_lines', 'kill_on_timeout', 'loop'].includes(field.field)) return 'runtime'
  if (['config_items', 'config_nodes', 'data_nodes', 'common_config', 'cluster_name', 'backup_before_write', 'work_mode', 'operation_proportion'].includes(field.field)) return 'configuration'
  if (['command', 'commands', 'sqls', 'validation_sqls', 'expression', 'condition'].includes(field.field)) return 'command'
  if (['assert_type', 'params', 'expected', 'iterations', 'interval', 'max_concurrent'].includes(field.field)) return 'checks'
  if (['recipient', 'template'].includes(field.field)) return 'notification'
  if (['format', 'include_logs'].includes(field.field)) return 'output'
  return 'general'
}

const fieldSections = computed<FieldSection[]>(() => {
  if (!selectedNode.value) return []

  const sections: FieldSection[] = []
  for (const field of getFieldDefinitions(selectedNode.value.data.nodeType as NodeType)) {
    const key = getFieldSection(field)
    let section = sections.find(item => item.key === key)
    if (!section) {
      section = { key, title: fieldSectionTitles[key] || 'General', fields: [] }
      sections.push(section)
    }
    section.fields.push(field)
  }

  return sections
})

// Handle JSON input
const handleJsonInput = (field: string, value: string) => {
  if (!selectedNode.value) return

  const draftKey = `${selectedNode.value.id}:${field}`
  jsonDrafts.value[draftKey] = value

  try {
    const parsed = JSON.parse(value)
    updateConfig(field, parsed)
  } catch {
    // Invalid JSON - keep the current value
  }
}

const getJsonFieldString = (field: string): string => {
  if (!selectedNode.value) return ''

  const draftKey = `${selectedNode.value.id}:${field}`
  if (!(draftKey in jsonDrafts.value)) {
    jsonDrafts.value[draftKey] = JSON.stringify(getConfigValue(field) || {}, null, 2)
  }

  return jsonDrafts.value[draftKey]
}

const getDraftKey = (field: string): string => selectedNode.value ? `${selectedNode.value.id}:${field}` : field

const createEmptyKeyValueRow = (): KeyValueDraft => ({
  id: `row-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  key: '',
  value: ''
})

const getKeyValueSignature = (value: unknown): string => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return '{}'
  return JSON.stringify(value)
}

const getKeyValueRows = (field: string): KeyValueDraft[] => {
  if (!selectedNode.value) return []

  const draftKey = getDraftKey(field)
  const value = getConfigValue(field)
  const signature = getKeyValueSignature(value)
  if (!(draftKey in keyValueDrafts.value) || keyValueDraftSnapshots.value[draftKey] !== signature) {
    const rows = typeof value === 'object' && value !== null && !Array.isArray(value)
      ? Object.entries(value).map(([key, itemValue], index) => ({
        id: `${draftKey}-${index}`,
        key,
        value: String(itemValue ?? '')
      }))
      : []

    keyValueDrafts.value[draftKey] = rows.length > 0 ? rows : [createEmptyKeyValueRow()]
    keyValueDraftSnapshots.value[draftKey] = signature
  }

  return keyValueDrafts.value[draftKey]
}

const syncKeyValueConfig = (field: string) => {
  const rows = keyValueDrafts.value[getDraftKey(field)] || []
  const nextConfigItems: Record<string, string> = {}

  for (const row of rows) {
    const key = row.key.trim()
    if (key) {
      nextConfigItems[key] = row.value
    }
  }

  updateConfig(field, nextConfigItems)
  keyValueDraftSnapshots.value[getDraftKey(field)] = JSON.stringify(nextConfigItems)
}

const updateKeyValueRow = (field: string, rowId: string, prop: 'key' | 'value', value: string) => {
  const rows = getKeyValueRows(field)
  const row = rows.find(item => item.id === rowId)
  if (!row) return

  row[prop] = value
  syncKeyValueConfig(field)
}

const addKeyValueRow = (field: string) => {
  getKeyValueRows(field).push(createEmptyKeyValueRow())
}

const removeKeyValueRow = (field: string, rowId: string) => {
  const draftKey = getDraftKey(field)
  const nextRows = (keyValueDrafts.value[draftKey] || []).filter(row => row.id !== rowId)
  keyValueDrafts.value[draftKey] = nextRows.length > 0 ? nextRows : [createEmptyKeyValueRow()]
  syncKeyValueConfig(field)
}

// Handle commands array (for iotdb_cli)
const handleListInput = (field: string, value: string) => {
  const items = value.split('\n').filter(item => item.trim())
  updateConfig(field, items)
}

// Get list field as string for display
const getListFieldString = (field: string): string => {
  const value = getConfigValue(field)
  if (Array.isArray(value)) {
    return value.join('\n')
  }
  return ''
}

// Handle textarea with line-based array fields
const isListField = (field: string): boolean => {
  return ['commands', 'sqls', 'validation_sqls'].includes(field)
}
</script>

<template>
  <div class="node-config-dialog-content">
    <div v-if="!selectedNode" class="no-selection">
      <ElEmpty description="Select a node to configure" :image-size="80" />
    </div>

    <div v-else class="settings-page">
      <div class="node-name-section">
        <div class="setting-label">Node Name</div>
        <div v-if="!isEditingLabel" class="node-name-display">
          <span class="node-name">{{ selectedNode.data.label }}</span>
          <ElButton
            text
            size="small"
            :icon="Edit"
            @click="startEditLabel"
          />
        </div>
        <div v-else class="node-name-edit">
          <ElInput
            v-model="editingLabel"
            size="small"
            placeholder="Enter node name"
            @keyup.enter="saveLabel"
            @keyup.escape="cancelEditLabel"
          />
          <ElButton size="small" type="primary" @click="saveLabel">Save</ElButton>
          <ElButton size="small" @click="cancelEditLabel">Cancel</ElButton>
        </div>
      </div>

      <div v-if="nodeHelpText" class="node-help">
        {{ nodeHelpText }}
      </div>

      <ElForm label-position="top" class="settings-form">
        <section
          v-for="section in fieldSections"
          :key="section.key"
          class="settings-section"
        >
          <div class="section-title">{{ section.title }}</div>
          <ElFormItem
            v-for="field in section.fields"
            :key="field.field"
            :label="field.label"
            :class="['setting-item', getFieldLayoutClass(field)]"
          >
            <template v-if="field.type === 'server'">
              <ElSelect
                :model-value="(getConfigValue(field.field) as number | null | undefined)"
                placeholder="Select server"
                clearable
                size="small"
                style="width: 100%"
                @update:model-value="updateServerConfig($event)"
              >
                <ElOption
                  v-for="option in filteredServerOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </template>

            <template v-else-if="field.type === 'region'">
              <ElSelect
                :model-value="(getConfigValue(field.field) as string | null | undefined)"
                placeholder="Select region"
                clearable
                size="small"
                style="width: 100%"
                @update:model-value="updateRegionConfig($event)"
              >
                <ElOption
                  v-for="region in REGION_OPTIONS"
                  :key="region"
                  :label="region"
                  :value="region"
                />
              </ElSelect>
            </template>

            <template v-else-if="field.type === 'select'">
              <ElSelect
                :model-value="(getConfigValue(field.field) as string | number | null | undefined)"
                placeholder="Select option"
                size="small"
                style="width: 100%"
                @update:model-value="updateConfig(field.field, $event)"
              >
                <ElOption
                  v-for="option in field.options"
                  :key="String(option.value)"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </template>

            <template v-else-if="field.type === 'checkbox'">
              <div class="switch-field">
                <ElSwitch
                  :model-value="Boolean(getConfigValue(field.field))"
                  size="small"
                  @update:model-value="updateConfig(field.field, $event)"
                />
                <span class="switch-label">{{ field.placeholder || 'Enabled' }}</span>
              </div>
            </template>

            <template v-else-if="field.type === 'number'">
              <ElInputNumber
                :model-value="(getConfigValue(field.field) as number) || field.min || 0"
                :min="field.min"
                :max="field.max"
                size="small"
                :controls="false"
                style="width: 100%"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>

            <template v-else-if="field.type === 'textarea'">
              <ElInput
                v-if="isListField(field.field)"
                :model-value="getListFieldString(field.field)"
                type="textarea"
                :rows="3"
                :placeholder="field.placeholder"
                @update:model-value="handleListInput(field.field, $event)"
              />
              <ElInput
                v-else
                :model-value="(getConfigValue(field.field) as string) || ''"
                type="textarea"
                :rows="3"
                :placeholder="field.placeholder"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>

            <template v-else-if="field.type === 'json'">
              <ElInput
                :model-value="getJsonFieldString(field.field)"
                type="textarea"
                :rows="4"
                :placeholder="field.placeholder"
                @update:model-value="handleJsonInput(field.field, $event)"
              />
            </template>

            <template v-else-if="field.type === 'clusterNodes'">
              <div class="cluster-node-select">
                <ElSelect
                  :model-value="getClusterNodeServerIds(field.field)"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  :placeholder="field.placeholder"
                  size="small"
                  style="width: 100%"
                  @update:model-value="updateClusterNodes(field.field, $event)"
                >
                  <ElOption
                    v-for="option in getClusterServerOptions(field.field)"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  >
                    <div class="cluster-server-option">
                      <span>{{ option.label }}</span>
                      <span>{{ option.region }}</span>
                    </div>
                  </ElOption>
                </ElSelect>
                <div class="cluster-region-hint">
                  {{ getClusterSelectedRegion() ? `已限制为 ${getClusterSelectedRegion()} 区域` : '选择任意服务器后，另一组节点会限制在同一区域' }}
                </div>
              </div>
            </template>

            <template v-else-if="field.type === 'keyValue'">
              <div class="key-value-editor">
                <div class="key-value-heading">
                  <span>Key</span>
                  <span>Value</span>
                </div>
                <div
                  v-for="row in getKeyValueRows(field.field)"
                  :key="row.id"
                  class="key-value-row"
                >
                  <ElInput
                    :model-value="row.key"
                    placeholder="Config key"
                    size="small"
                    @update:model-value="updateKeyValueRow(field.field, row.id, 'key', $event)"
                  />
                  <ElInput
                    :model-value="row.value"
                    placeholder="Value"
                    size="small"
                    @update:model-value="updateKeyValueRow(field.field, row.id, 'value', $event)"
                  />
                  <ElButton
                    circle
                    text
                    type="danger"
                    size="small"
                    :icon="Delete"
                    @click="removeKeyValueRow(field.field, row.id)"
                  />
                </div>
                <ElButton
                  class="add-key-value-row"
                  size="small"
                  :icon="Plus"
                  @click="addKeyValueRow(field.field)"
                >
                  Add Item
                </ElButton>
              </div>
            </template>

            <template v-else>
              <ElInput
                :model-value="(getConfigValue(field.field) as string) || ''"
                :placeholder="field.placeholder"
                size="small"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>
          </ElFormItem>
        </section>
      </ElForm>

      <div class="node-id-section">
        <span class="node-id-label">Node ID:</span>
        <span class="node-id-value">{{ selectedNode.id }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-config-dialog-content {
  width: 100%;
  height: min(70vh, 720px);
  background: #fff;
  color: #1f2937;
  font-size: 13px;
  overflow: hidden;
}

.no-selection {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.settings-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.node-name-section {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid #e5e7eb;
}

.setting-label {
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.45;
}

.node-name-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  flex: 1;
}

.node-name-edit {
  display: flex;
  gap: 8px;
  align-items: center;
}

.settings-form {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px 18px;
  align-content: start;
  padding: 16px 18px;
}

.settings-section {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 10px 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.section-title {
  grid-column: 1 / -1;
  color: #111827;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
}

.setting-item {
  grid-column: span 6;
  margin-bottom: 0;
}

.field-compact {
  grid-column: span 3;
}

.field-medium {
  grid-column: span 4;
}

.field-wide {
  grid-column: span 6;
}

.field-full {
  grid-column: 1 / -1;
}

.field-inline {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  column-gap: 14px;
  align-items: center;
}

.node-help {
  margin: 12px 18px 0;
  padding: 8px 10px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-color: #e2e8f0;
  border-radius: 8px;
}

.setting-item :deep(.el-form-item__label) {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
  line-height: 1.45;
  padding-bottom: 6px;
}

.setting-item :deep(.el-form-item__content) {
  line-height: 1.45;
  min-width: 0;
}

.field-inline :deep(.el-form-item__label) {
  overflow: hidden;
  padding-bottom: 0;
  margin-bottom: 0;
  color: #475569;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.setting-item :deep(.el-input__inner),
.setting-item :deep(.el-textarea__inner),
.setting-item :deep(.el-select__selected-item) {
  font-size: 13px;
  line-height: 1.45;
}

.switch-field {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
}

.switch-label {
  color: #606266;
  display: none;
  font-size: 12px;
  line-height: 1.45;
}

.key-value-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cluster-node-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.cluster-server-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.cluster-server-option span:last-child {
  color: #94a3b8;
  font-size: 12px;
}

.cluster-region-hint {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.key-value-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 28px;
  gap: 8px;
  padding: 0 2px;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
}

.key-value-row {
  display: grid;
  grid-template-columns: minmax(160px, 260px) minmax(0, 1fr) 28px;
  gap: 8px;
  align-items: center;
}

.add-key-value-row {
  align-self: flex-start;
}

.node-id-section {
  padding: 8px 18px;
  background: #f5f7fa;
  border-top: 1px solid #e5e7eb;
  font-size: 12px;
}

@media (max-width: 760px) {
  .settings-form,
  .settings-section {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .field-compact,
  .field-medium {
    grid-column: span 3;
  }

  .field-wide,
  .field-full,
  .setting-item {
    grid-column: 1 / -1;
  }
}

.node-id-label {
  color: #909399;
  margin-right: 8px;
}

.node-id-value {
  color: #606266;
  font-family: monospace;
}
</style>
