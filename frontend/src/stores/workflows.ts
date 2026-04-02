import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Workflow, WorkflowCreate, WorkflowUpdate } from '@/types'
import { workflowsApi } from '@/api'

export const useWorkflowsStore = defineStore('workflows', () => {
  const workflows = ref<Workflow[]>([])
  const currentWorkflow = ref<Workflow | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchWorkflows() {
    loading.value = true
    error.value = null
    try {
      workflows.value = await workflowsApi.list()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch workflows'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkflow(id: number) {
    loading.value = true
    error.value = null
    try {
      currentWorkflow.value = await workflowsApi.get(id)
      return currentWorkflow.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch workflow'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function createWorkflow(data: WorkflowCreate) {
    loading.value = true
    error.value = null
    try {
      const workflow = await workflowsApi.create(data)
      workflows.value.push(workflow)
      return workflow
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create workflow'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateWorkflow(id: number, data: WorkflowUpdate) {
    loading.value = true
    error.value = null
    try {
      const updated = await workflowsApi.update(id, data)
      const index = workflows.value.findIndex(w => w.id === id)
      if (index !== -1) {
        workflows.value[index] = updated
      }
      if (currentWorkflow.value?.id === id) {
        currentWorkflow.value = updated
      }
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update workflow'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteWorkflow(id: number) {
    loading.value = true
    error.value = null
    try {
      await workflowsApi.delete(id)
      workflows.value = workflows.value.filter(w => w.id !== id)
      if (currentWorkflow.value?.id === id) {
        currentWorkflow.value = null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete workflow'
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearCurrentWorkflow() {
    currentWorkflow.value = null
  }

  return {
    workflows,
    currentWorkflow,
    loading,
    error,
    fetchWorkflows,
    fetchWorkflow,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    clearCurrentWorkflow
  }
})