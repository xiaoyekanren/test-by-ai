import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Execution, ExecutionCreate, NodeExecution } from '@/types'
import { executionsApi } from '@/api'

export const useExecutionsStore = defineStore('executions', () => {
  const executions = ref<Execution[]>([])
  const currentExecution = ref<Execution | null>(null)
  const nodeExecutions = ref<NodeExecution[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchExecutions(params?: { workflow_id?: number; status?: string; limit?: number }) {
    loading.value = true
    error.value = null
    try {
      executions.value = await executionsApi.list(params)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch executions'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchExecution(id: number) {
    loading.value = true
    error.value = null
    try {
      currentExecution.value = await executionsApi.get(id)
      return currentExecution.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch execution'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createExecution(data: ExecutionCreate) {
    loading.value = true
    error.value = null
    try {
      const execution = await executionsApi.create(data)
      executions.value.unshift(execution)
      return execution
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create execution'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function stopExecution(id: number) {
    loading.value = true
    error.value = null
    try {
      const updated = await executionsApi.stop(id)
      const index = executions.value.findIndex(e => e.id === id)
      if (index !== -1) {
        executions.value[index] = updated
      }
      if (currentExecution.value?.id === id) {
        currentExecution.value = updated
      }
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to stop execution'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchNodeExecutions(executionId: number) {
    loading.value = true
    error.value = null
    try {
      nodeExecutions.value = await executionsApi.getNodes(executionId)
      return nodeExecutions.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch node executions'
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearCurrentExecution() {
    currentExecution.value = null
    nodeExecutions.value = []
  }

  return {
    executions,
    currentExecution,
    nodeExecutions,
    loading,
    error,
    fetchExecutions,
    fetchExecution,
    createExecution,
    stopExecution,
    fetchNodeExecutions,
    clearCurrentExecution
  }
})