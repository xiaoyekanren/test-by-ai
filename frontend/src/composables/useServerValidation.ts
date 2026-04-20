import { computed } from 'vue'
import { useServersStore } from '@/stores/servers'

export interface MissingServerOption {
  value: number
  label: string
  region: string
  disabled: boolean
}

export function useServerValidation() {
  const serversStore = useServersStore()

  const serverIds = computed(() => {
    return new Set(serversStore.servers.map(server => server.id))
  })

  const isMissingServerId = (serverId: unknown): boolean => {
    if (serverId === null || serverId === undefined || serverId === '') return false
    const numericId = Number(serverId)
    return Number.isFinite(numericId) && !serverIds.value.has(numericId)
  }

  const missingServerOption = (serverId: unknown): MissingServerOption => {
    const numericId = Number(serverId)
    return {
      value: numericId,
      label: `Missing server #${numericId}`,
      region: 'missing',
      disabled: true
    }
  }

  return { serverIds, isMissingServerId, missingServerOption }
}
