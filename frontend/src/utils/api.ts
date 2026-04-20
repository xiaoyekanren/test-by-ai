import axios from 'axios'

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = String(detail.message)
    const workflows = Array.isArray(detail.workflows)
      ? detail.workflows
          .map((item: unknown) => item && typeof item === 'object' && 'name' in item ? String(item.name) : '')
          .filter(Boolean)
      : []
    return workflows.length ? `${message}: ${workflows.join(', ')}` : message
  }
  return fallback
}
