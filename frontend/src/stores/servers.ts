import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Server, ServerCreate, ServerUpdate, ServerTestResult, ServerExecuteResult } from '@/types'
import { serversApi } from '@/api'

export const useServersStore = defineStore('servers', () => {
  const servers = ref<Server[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchServers() {
    loading.value = true
    error.value = null
    try {
      servers.value = await serversApi.list()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch servers'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function addServer(data: ServerCreate) {
    loading.value = true
    error.value = null
    try {
      const server = await serversApi.create(data)
      servers.value.push(server)
      return server
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create server'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateServer(id: number, data: ServerUpdate) {
    loading.value = true
    error.value = null
    try {
      const updated = await serversApi.update(id, data)
      const index = servers.value.findIndex(s => s.id === id)
      if (index !== -1) {
        servers.value[index] = updated
      }
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update server'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteServer(id: number) {
    loading.value = true
    error.value = null
    try {
      await serversApi.delete(id)
      servers.value = servers.value.filter(s => s.id !== id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete server'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function testConnection(id: number): Promise<ServerTestResult> {
    loading.value = true
    error.value = null
    try {
      const result = await serversApi.test(id)
      // Update server status if connection successful
      if (result.success) {
        const index = servers.value.findIndex(s => s.id === id)
        if (index !== -1) {
          servers.value[index].status = 'online'
        }
      }
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to test connection'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function executeCommand(id: number, command: string, timeout?: number): Promise<ServerExecuteResult> {
    loading.value = true
    error.value = null
    try {
      return await serversApi.execute(id, command, timeout)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to execute command'
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    servers,
    loading,
    error,
    fetchServers,
    addServer,
    updateServer,
    deleteServer,
    testConnection,
    executeCommand
  }
})