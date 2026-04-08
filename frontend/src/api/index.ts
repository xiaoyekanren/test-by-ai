import axios from 'axios'
import type {
  Server,
  ServerCreate,
  ServerUpdate,
  ServerTestResult,
  ServerExecuteResult,
  Workflow,
  WorkflowCreate,
  WorkflowUpdate,
  Execution,
  ExecutionCreate,
  NodeExecution,
  MonitoringStatus,
  ProcessInfo,
  RemoteMonitoringStatus,
  RemoteProcessesResponse,
  KillProcessResult,
  IoTDBFileInfo,
  IoTDBLogContent,
  IoTDBConfigContent,
  IoTDBRestartResult
} from '@/types'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// Servers API
export const serversApi = {
  list: (): Promise<Server[]> =>
    apiClient.get('/servers'),

  get: (id: number): Promise<Server> =>
    apiClient.get(`/servers/${id}`),

  create: (data: ServerCreate): Promise<Server> =>
    apiClient.post('/servers', data),

  update: (id: number, data: ServerUpdate): Promise<Server> =>
    apiClient.put(`/servers/${id}`, data),

  delete: (id: number): Promise<void> =>
    apiClient.delete(`/servers/${id}`),

  test: (id: number): Promise<ServerTestResult> =>
    apiClient.post(`/servers/${id}/test`),

  execute: (id: number, command: string, timeout?: number): Promise<ServerExecuteResult> =>
    apiClient.post(`/servers/${id}/execute`, { command, timeout })
}

// Workflows API
export const workflowsApi = {
  list: (): Promise<Workflow[]> =>
    apiClient.get('/workflows'),

  get: (id: number): Promise<Workflow> =>
    apiClient.get(`/workflows/${id}`),

  create: (data: WorkflowCreate): Promise<Workflow> =>
    apiClient.post('/workflows', data),

  update: (id: number, data: WorkflowUpdate): Promise<Workflow> =>
    apiClient.put(`/workflows/${id}`, data),

  delete: (id: number): Promise<void> =>
    apiClient.delete(`/workflows/${id}`)
}

// Executions API
export const executionsApi = {
  list: (params?: { workflow_id?: number; status?: string; limit?: number }): Promise<Execution[]> =>
    apiClient.get('/executions', { params }),

  get: (id: number): Promise<Execution> =>
    apiClient.get(`/executions/${id}`),

  create: (data: ExecutionCreate): Promise<Execution> =>
    apiClient.post('/executions', data),

  stop: (id: number): Promise<Execution> =>
    apiClient.post(`/executions/${id}/stop`),

  delete: (id: number): Promise<void> =>
    apiClient.delete(`/executions/${id}`),

  getNodes: (id: number): Promise<NodeExecution[]> =>
    apiClient.get(`/executions/${id}/nodes`)
}

// Monitoring API
export const monitoringApi = {
  localStatus: (): Promise<MonitoringStatus> =>
    apiClient.get('/monitoring/local/status'),

  localProcesses: (params?: { limit?: number; sort_by?: 'cpu' | 'memory' }): Promise<ProcessInfo[]> =>
    apiClient.get('/monitoring/local/processes', { params }),

  remoteStatus: (serverId: number): Promise<RemoteMonitoringStatus> =>
    apiClient.get(`/monitoring/remote/${serverId}/status`),

  remoteProcesses: (serverId: number, params?: { limit?: number; sort_by?: 'cpu' | 'memory' }): Promise<RemoteProcessesResponse> =>
    apiClient.get(`/monitoring/remote/${serverId}/processes`, { params }),

  killProcess: (pid: number): Promise<KillProcessResult> =>
    apiClient.post(`/monitoring/local/process/${pid}/kill`)
}

export interface MonitorSettingsPayload {
  refreshInterval: number
}

export interface ObservabilitySettingsPayload {
  prometheusUrl: string | null
  grafanaUrl: string | null
  grafanaDashboardUid: string | null
  grafanaDatasource: string | null
  grafanaOrgId: string | null
  grafanaTimeRange: string
  grafanaEmbedEnabled: boolean
}

export interface SettingsPayload {
  monitor: MonitorSettingsPayload
  observability: ObservabilitySettingsPayload
}

export const settingsApi = {
  get: (): Promise<SettingsPayload> =>
    apiClient.get('/settings'),

  update: (data: Partial<SettingsPayload>): Promise<SettingsPayload> =>
    apiClient.put('/settings', data),

  getObservability: (): Promise<ObservabilitySettingsPayload> =>
    apiClient.get('/settings/observability'),

  updateObservability: (data: ObservabilitySettingsPayload): Promise<ObservabilitySettingsPayload> =>
    apiClient.put('/settings/observability', data)
}

// IoTDB API
export const iotdbApi = {
  listLogs: (serverId: number, iotdbHome: string): Promise<IoTDBFileInfo[]> =>
    apiClient.post('/iotdb/logs/list', { server_id: serverId, iotdb_home: iotdbHome }),

  readLog: (serverId: number, iotdbHome: string, path: string, tail?: number): Promise<IoTDBLogContent> =>
    apiClient.post('/iotdb/logs/read', { server_id: serverId, iotdb_home: iotdbHome, path, tail }),

  listConfigs: (serverId: number, iotdbHome: string): Promise<IoTDBFileInfo[]> =>
    apiClient.post('/iotdb/configs/list', { server_id: serverId, iotdb_home: iotdbHome }),

  readConfig: (serverId: number, iotdbHome: string, path: string): Promise<IoTDBConfigContent> =>
    apiClient.post('/iotdb/configs/read', { server_id: serverId, iotdb_home: iotdbHome, path }),

  writeConfig: (serverId: number, iotdbHome: string, path: string, content: string): Promise<{ success: boolean; message: string }> =>
    apiClient.post('/iotdb/configs/write', { server_id: serverId, iotdb_home: iotdbHome, path, content }),

  restart: (serverId: number, iotdbHome: string, restartScope = 'all'): Promise<IoTDBRestartResult> =>
    apiClient.post('/iotdb/restart', { server_id: serverId, iotdb_home: iotdbHome, restart_scope: restartScope })
}

export default apiClient
