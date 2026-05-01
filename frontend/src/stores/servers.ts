import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Server, ServerCreate, ServerUpdate, ServerTestResult, ServerExecuteResult } from '@/types'
import { serversApi } from '@/api'

export const useServersStore = defineStore('servers', () => {
  const servers = ref<Server[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const testingServerIds = ref<Set<number>>(new Set())

  function setServerTesting(id: number, isTesting: boolean) {
    const next = new Set(testingServerIds.value)
    if (isTesting) {
      next.add(id)
    } else {
      next.delete(id)
    }
    testingServerIds.value = next
  }

  function isTestingServer(id: number) {
    return testingServerIds.value.has(id)
  }

  function updateServerStatus(id: number, status: string) {
    const index = servers.value.findIndex(s => s.id === id)
    if (index !== -1) {
      servers.value[index] = {
        ...servers.value[index],
        status
      }
    }
  }

  async function fetchServers() {
    loading.value = true
    error.value = null
    try {
      servers.value = await serversApi.list()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取服务器列表失败'
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
      error.value = e instanceof Error ? e.message : '创建服务器失败'
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
      error.value = e instanceof Error ? e.message : '更新服务器失败'
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
      error.value = e instanceof Error ? e.message : '删除服务器失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function testConnection(id: number, options: { useGlobalLoading?: boolean } = {}): Promise<ServerTestResult> {
    const useGlobalLoading = options.useGlobalLoading ?? true
    if (useGlobalLoading) {
      loading.value = true
    }
    setServerTesting(id, true)
    error.value = null
    try {
      const result = await serversApi.test(id)
      updateServerStatus(id, result.success ? 'online' : 'offline')
      return result
    } catch (e) {
      updateServerStatus(id, 'offline')
      error.value = e instanceof Error ? e.message : '测试连接失败'
      throw e
    } finally {
      setServerTesting(id, false)
      if (useGlobalLoading) {
        loading.value = false
      }
    }
  }

  async function executeCommand(id: number, command: string, timeout?: number): Promise<ServerExecuteResult> {
    loading.value = true
    error.value = null
    try {
      return await serversApi.execute(id, command, timeout)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '执行命令失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    servers,
    loading,
    error,
    testingServerIds,
    fetchServers,
    addServer,
    updateServer,
    deleteServer,
    isTestingServer,
    testConnection,
    executeCommand
  }
})
