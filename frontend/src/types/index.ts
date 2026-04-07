// Node type configurations for the workflow editor

export type NodeCategory = 'basic' | 'iotdb' | 'control' | 'result'

export interface NodeTypeConfig {
  type: NodeType
  label: string
  category: NodeCategory
  icon: string
  color: string
  description: string
  defaultConfig: Record<string, unknown>
  inputs: number // number of input ports (0, 1, or -1 for any)
  outputs: number // number of output ports (0, 1, or -1 for any)
}

export const NODE_CONFIGS: Record<NodeType, NodeTypeConfig> = {
  // Basic nodes
  shell: {
    type: 'shell',
    label: 'Shell',
    category: 'basic',
    icon: 'Monitor',
    color: '#409EFF',
    description: 'Execute shell command',
    defaultConfig: { command: '', server_id: null, timeout: 300, retry: 0 },
    inputs: 1,
    outputs: 1
  },
  upload: {
    type: 'upload',
    label: 'Upload',
    category: 'basic',
    icon: 'Upload',
    color: '#67C23A',
    description: 'Upload file via SFTP',
    defaultConfig: { local_path: '', remote_path: '', server_id: null, timeout: 300 },
    inputs: 1,
    outputs: 1
  },
  download: {
    type: 'download',
    label: 'Download',
    category: 'basic',
    icon: 'Download',
    color: '#E6A23C',
    description: 'Download file via SFTP',
    defaultConfig: { remote_path: '', local_path: '', server_id: null },
    inputs: 1,
    outputs: 1
  },
  config: {
    type: 'config',
    label: 'Config',
    category: 'basic',
    icon: 'Setting',
    color: '#909399',
    description: 'Modify configuration file',
    defaultConfig: { file_path: '', config_items: {}, backup_before_write: true, server_id: null, timeout: 60 },
    inputs: 1,
    outputs: 1
  },
  log_view: {
    type: 'log_view',
    label: 'Log View',
    category: 'basic',
    icon: 'Document',
    color: '#909399',
    description: 'View log content',
    defaultConfig: { file_path: '', lines: 100, server_id: null },
    inputs: 1,
    outputs: 1
  },

  // IoTDB nodes
  iotdb_deploy: {
    type: 'iotdb_deploy',
    label: 'IoTDB Deploy',
    category: 'iotdb',
    icon: 'Download',
    color: '#9B59B6',
    description: 'Deploy IoTDB instance',
    defaultConfig: {
      server_id: null,
      artifact_local_path: '',
      remote_package_path: '/tmp/apache-iotdb-bin.zip',
      install_dir: '/opt/iotdb',
      package_type: 'auto',
      extract_subdir: '',
      overwrite: false,
      rpc_port: 6667,
      timeout: 600
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_start: {
    type: 'iotdb_start',
    label: 'IoTDB Start',
    category: 'iotdb',
    icon: 'VideoPlay',
    color: '#27AE60',
    description: 'Start IoTDB service',
    defaultConfig: {
      server_id: null,
      node_role: 'standalone',
      iotdb_home: '',
      host: '',
      rpc_port: 6667,
      wait_port: 6667,
      timeout_seconds: 60,
      wait_strategy: 'port'
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_stop: {
    type: 'iotdb_stop',
    label: 'IoTDB Stop',
    category: 'iotdb',
    icon: 'VideoPause',
    color: '#E74C3C',
    description: 'Stop IoTDB service',
    defaultConfig: { server_id: null, node_role: 'standalone', iotdb_home: '', graceful: true, timeout_seconds: 60 },
    inputs: 1,
    outputs: 1
  },
  iotdb_cli: {
    type: 'iotdb_cli',
    label: 'IoTDB CLI',
    category: 'iotdb',
    icon: 'Tools',
    color: '#3498DB',
    description: 'Execute IoTDB CLI commands',
    defaultConfig: {
      server_id: null,
      iotdb_home: '',
      host: '',
      rpc_port: 6667,
      username: 'root',
      password: 'root',
      sqls: [],
      sql_dialect: 'tree',
      timeout_seconds: 300
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_config: {
    type: 'iotdb_config',
    label: 'IoTDB Config Override',
    category: 'iotdb',
    icon: 'Setting',
    color: '#8E44AD',
    description: 'Declare config overrides for deployed IoTDB',
    defaultConfig: {
      server_id: null,
      node_role: 'standalone',
      iotdb_home: '',
      file_path: '',
      config_items: {},
      backup_before_write: true,
      timeout: 60
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_cluster_deploy: {
    type: 'iotdb_cluster_deploy',
    label: 'IoTDB Cluster Deploy',
    category: 'iotdb',
    icon: 'Grid',
    color: '#6c5ce7',
    description: 'Deploy ConfigNode and DataNode hosts for a cluster',
    defaultConfig: {
      artifact_local_path: '',
      remote_package_path: '/tmp/apache-iotdb-cluster-bin.zip',
      install_dir: '/opt/iotdb-cluster',
      package_type: 'auto',
      extract_subdir: '',
      overwrite: false,
      cluster_name: 'defaultCluster',
      config_nodes: [],
      data_nodes: [],
      common_config: {},
      timeout: 900
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_cluster_start: {
    type: 'iotdb_cluster_start',
    label: 'IoTDB Cluster Start',
    category: 'iotdb',
    icon: 'VideoPlay',
    color: '#16a085',
    description: 'Start cluster nodes in ConfigNode then DataNode order',
    defaultConfig: {
      cluster_name: '',
      config_nodes: [],
      data_nodes: [],
      wait_strategy: 'port',
      timeout_seconds: 180
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_cluster_check: {
    type: 'iotdb_cluster_check',
    label: 'IoTDB Cluster Check',
    category: 'iotdb',
    icon: 'CircleCheck',
    color: '#0984e3',
    description: 'Run show cluster and optional validation SQLs',
    defaultConfig: {
      cluster_name: '',
      config_nodes: [],
      data_nodes: [],
      username: 'root',
      password: 'root',
      sql_dialect: 'tree',
      validation_sqls: [],
      timeout_seconds: 300
    },
    inputs: 1,
    outputs: 1
  },
  iotdb_cluster_stop: {
    type: 'iotdb_cluster_stop',
    label: 'IoTDB Cluster Stop',
    category: 'iotdb',
    icon: 'VideoPause',
    color: '#c0392b',
    description: 'Stop DataNodes first and ConfigNodes last',
    defaultConfig: {
      cluster_name: '',
      config_nodes: [],
      data_nodes: [],
      graceful: true,
      timeout_seconds: 180
    },
    inputs: 1,
    outputs: 1
  },

  // Control nodes
  condition: {
    type: 'condition',
    label: 'Condition',
    category: 'control',
    icon: 'Share',
    color: '#F39C12',
    description: 'If/else branch',
    defaultConfig: { expression: '' },
    inputs: 1,
    outputs: 2
  },
  loop: {
    type: 'loop',
    label: 'Loop',
    category: 'control',
    icon: 'Refresh',
    color: '#1ABC9C',
    description: 'Loop execution',
    defaultConfig: { loop_type: 'for', iterations: 1, condition: '' },
    inputs: 1,
    outputs: 1
  },
  wait: {
    type: 'wait',
    label: 'Wait',
    category: 'control',
    icon: 'Timer',
    color: '#F1C40F',
    description: 'Wait for condition',
    defaultConfig: { condition: '', timeout: 60, interval: 5 },
    inputs: 1,
    outputs: 1
  },
  parallel: {
    type: 'parallel',
    label: 'Parallel',
    category: 'control',
    icon: 'Grid',
    color: '#2ECC71',
    description: 'Parallel execution',
    defaultConfig: { max_concurrent: 5 },
    inputs: 1,
    outputs: -1 // dynamic outputs
  },
  assert: {
    type: 'assert',
    label: 'Assert',
    category: 'control',
    icon: 'CircleCheck',
    color: '#E67E22',
    description: 'Assertion check',
    defaultConfig: { assert_type: 'log_contains', params: {}, expected: '' },
    inputs: 1,
    outputs: 1
  },

  // Result nodes
  report: {
    type: 'report',
    label: 'Report',
    category: 'result',
    icon: 'Document',
    color: '#3498DB',
    description: 'Generate test report',
    defaultConfig: { format: 'html', include_logs: true },
    inputs: 1,
    outputs: 0
  },
  summary: {
    type: 'summary',
    label: 'Summary',
    category: 'result',
    icon: 'DataAnalysis',
    color: '#2980B9',
    description: 'Summarize test results',
    defaultConfig: {},
    inputs: 1,
    outputs: 0
  },
  notify: {
    type: 'notify',
    label: 'Notify',
    category: 'result',
    icon: 'Bell',
    color: '#8E44AD',
    description: 'Send notification',
    defaultConfig: { type: 'email', recipient: '', template: '' },
    inputs: 1,
    outputs: 0
  }
}

// Vue Flow types
export interface FlowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: {
    label: string
    nodeType: NodeType
    config: Record<string, unknown>
  }
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
  animated?: boolean
}

// Server related types (matching backend Pydantic schemas)

export interface Server {
  id: number
  name: string
  host: string
  port: number
  username: string | null
  description: string | null
  tags: string | null
  role: string
  status: string
  created_at: string
  updated_at: string
}

export interface ServerCreate {
  name: string
  host: string
  port?: number
  username?: string | null
  password?: string | null
  description?: string | null
  tags?: string | null
  role?: string
}

export interface ServerUpdate {
  name?: string
  host?: string
  port?: number
  username?: string | null
  password?: string | null
  description?: string | null
  tags?: string | null
  role?: string
}

export interface ServerTestResult {
  success: boolean
  message: string
  server_id: number
  server_name: string
  ssh_port?: number
}

export interface ServerExecuteResult {
  server_id: number
  server_name: string
  command: string
  exit_status: number | null
  stdout: string
  stderr: string
  error: string | null
  ssh_port: number
}

// Workflow related types

export type NodeType =
  | "shell"
  | "upload"
  | "download"
  | "config"
  | "log_view"
  | "iotdb_deploy"
  | "iotdb_start"
  | "iotdb_stop"
  | "iotdb_cli"
  | "iotdb_config"
  | "iotdb_cluster_deploy"
  | "iotdb_cluster_start"
  | "iotdb_cluster_check"
  | "iotdb_cluster_stop"
  | "condition"
  | "loop"
  | "wait"
  | "parallel"
  | "assert"
  | "report"
  | "summary"
  | "notify"

export interface NodeDefinition {
  id: string
  type: NodeType
  config: Record<string, unknown>
  position?: { x: number; y: number } | null
}

export interface EdgeDefinition {
  from: string
  to: string
  label?: string | null
}

export interface Workflow {
  id: number
  name: string
  description: string | null
  nodes: NodeDefinition[]
  edges: EdgeDefinition[]
  variables: Record<string, string>
  created_at: string
  updated_at: string
}

export interface WorkflowCreate {
  name: string
  description?: string | null
  nodes?: NodeDefinition[]
  edges?: EdgeDefinition[]
  variables?: Record<string, string>
}

export interface WorkflowUpdate {
  name?: string
  description?: string | null
  nodes?: NodeDefinition[]
  edges?: EdgeDefinition[]
  variables?: Record<string, string>
}

// Execution related types

export type ExecutionStatus = "pending" | "running" | "paused" | "completed" | "failed"
export type TriggerType = "manual" | "scheduled" | "api"
export type ExecutionResult = "passed" | "failed" | "partial"

export interface Execution {
  id: number
  workflow_id: number
  status: ExecutionStatus
  trigger_type: TriggerType
  triggered_by: string | null
  started_at: string | null
  finished_at: string | null
  duration: number | null
  result: ExecutionResult | null
  summary: Record<string, unknown> | null
  created_at: string
}

export interface ExecutionCreate {
  workflow_id: number
  trigger_type?: TriggerType
  triggered_by?: string | null
}

export interface NodeExecution {
  id: number
  execution_id: number
  node_id: string
  node_type: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration: number | null
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  log_path: string | null
  error_message: string | null
  retry_count: number
}

// Monitoring related types

export interface MemoryInfo {
  total: number
  available: number
  percent: number
  used: number
  free: number
}

export interface DiskInfo {
  total: number
  used: number
  free: number
  percent: number
}

export interface MonitoringStatus {
  cpu_percent: number
  memory: MemoryInfo
  disk: DiskInfo
}

export interface ProcessInfo {
  pid: number
  name: string
  cpu_percent: number
  memory_percent: number
}

export interface RemoteMonitoringStatus extends MonitoringStatus {
  server_id: number | null
  server_name: string | null
  host: string
}

export interface RemoteProcessesResponse {
  server_id: number | null
  server_name: string | null
  host: string
  processes: ProcessInfo[]
}

export interface KillProcessResult {
  success: boolean
  pid: number
  name?: string
  error?: string
}
