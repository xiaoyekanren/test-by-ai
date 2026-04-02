import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MonitoringStatus, ProcessInfo, RemoteMonitoringStatus, RemoteProcessesResponse, KillProcessResult } from '@/types'
import { monitoringApi } from '@/api'

export const useMonitoringStore = defineStore('monitoring', () => {
  const localStatus = ref<MonitoringStatus | null>(null)
  const localProcesses = ref<ProcessInfo[]>([])
  const remoteStatus = ref<RemoteMonitoringStatus | null>(null)
  const remoteProcesses = ref<RemoteProcessesResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchLocalStatus() {
    loading.value = true
    error.value = null
    try {
      localStatus.value = await monitoringApi.localStatus()
      return localStatus.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch local status'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchLocalProcesses(params?: { limit?: number; sort_by?: 'cpu' | 'memory' }) {
    loading.value = true
    error.value = null
    try {
      localProcesses.value = await monitoringApi.localProcesses(params)
      return localProcesses.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch local processes'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchRemoteStatus(serverId: number) {
    loading.value = true
    error.value = null
    try {
      remoteStatus.value = await monitoringApi.remoteStatus(serverId)
      return remoteStatus.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch remote status'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchRemoteProcesses(serverId: number, params?: { limit?: number; sort_by?: 'cpu' | 'memory' }) {
    loading.value = true
    error.value = null
    try {
      remoteProcesses.value = await monitoringApi.remoteProcesses(serverId, params)
      return remoteProcesses.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch remote processes'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function killProcess(pid: number): Promise<KillProcessResult> {
    loading.value = true
    error.value = null
    try {
      const result = await monitoringApi.killProcess(pid)
      // Remove the killed process from local processes list
      if (result.success) {
        localProcesses.value = localProcesses.value.filter(p => p.pid !== pid)
      }
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to kill process'
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearRemoteData() {
    remoteStatus.value = null
    remoteProcesses.value = null
  }

  return {
    localStatus,
    localProcesses,
    remoteStatus,
    remoteProcesses,
    loading,
    error,
    fetchLocalStatus,
    fetchLocalProcesses,
    fetchRemoteStatus,
    fetchRemoteProcesses,
    killProcess,
    clearRemoteData
  }
})