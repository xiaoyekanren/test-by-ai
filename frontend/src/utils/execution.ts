export type NodeExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export const isNodeSuccess = (status: string): boolean => status === 'success'

export const isNodeFinished = (status: string): boolean =>
  status === 'success' || status === 'failed' || status === 'skipped'

export const isExecutionActive = (status: string | null | undefined): boolean =>
  status === 'pending' || status === 'running'
