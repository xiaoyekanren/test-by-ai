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
  | "iotdb_deploy"
  | "iotdb_start"
  | "iotdb_stop"
  | "iotdb_cli"
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