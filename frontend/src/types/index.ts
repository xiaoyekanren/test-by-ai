// Server related types
export interface Server {
  id: string
  name: string
  host: string
  port: number
  status: 'online' | 'offline' | 'unknown'
  createdAt: string
  updatedAt: string
}

// Workflow related types
export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
}

export interface Workflow {
  id: string
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  status: 'draft' | 'active' | 'inactive'
  createdAt: string
  updatedAt: string
}

// Execution related types
export interface Execution {
  id: string
  workflowId: string
  status: 'pending' | 'running' | 'success' | 'failed'
  startedAt: string
  finishedAt?: string
  logs: ExecutionLog[]
}

export interface ExecutionLog {
  timestamp: string
  level: 'info' | 'warn' | 'error'
  message: string
  nodeId?: string
}