import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TestSuite, TestSuiteDetail, TestSuiteCreate, TestSuiteUpdate } from '@/types'
import { testSuitesApi } from '@/api'

export const useTestSuitesStore = defineStore('testSuites', () => {
  const suites = ref<TestSuite[]>([])
  const currentSuite = ref<TestSuiteDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSuites(suiteType?: string) {
    loading.value = true
    error.value = null
    try {
      suites.value = await testSuitesApi.list(suiteType ? { suite_type: suiteType } : undefined)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载测试套件失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchSuite(id: number) {
    loading.value = true
    error.value = null
    try {
      currentSuite.value = await testSuitesApi.get(id)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载测试套件详情失败'
    } finally {
      loading.value = false
    }
  }

  async function createSuite(data: TestSuiteCreate) {
    const suite = await testSuitesApi.create(data)
    suites.value.unshift(suite)
    return suite
  }

  async function updateSuite(id: number, data: TestSuiteUpdate) {
    const suite = await testSuitesApi.update(id, data)
    const idx = suites.value.findIndex(s => s.id === id)
    if (idx !== -1) suites.value[idx] = suite
    return suite
  }

  async function deleteSuite(id: number) {
    await testSuitesApi.delete(id)
    suites.value = suites.value.filter(s => s.id !== id)
  }

  async function addCase(suiteId: number, workflowId: number) {
    const detail = await testSuitesApi.addCase(suiteId, workflowId)
    currentSuite.value = detail
    const idx = suites.value.findIndex(s => s.id === suiteId)
    if (idx !== -1) suites.value[idx] = { ...suites.value[idx], case_count: detail.cases.length }
    return detail
  }

  async function removeCase(suiteId: number, workflowId: number) {
    const detail = await testSuitesApi.removeCase(suiteId, workflowId)
    currentSuite.value = detail
    const idx = suites.value.findIndex(s => s.id === suiteId)
    if (idx !== -1) suites.value[idx] = { ...suites.value[idx], case_count: detail.cases.length }
    return detail
  }

  return {
    suites, currentSuite, loading, error,
    fetchSuites, fetchSuite, createSuite, updateSuite, deleteSuite,
    addCase, removeCase,
  }
})
