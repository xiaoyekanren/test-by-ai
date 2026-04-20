export type NodeExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export const isNodeSuccess = (status: string): boolean => status === 'success'

export const isNodeFinished = (status: string): boolean =>
  status === 'success' || status === 'failed' || status === 'skipped'
