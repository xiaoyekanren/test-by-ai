<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElScrollbar,
  ElTag
} from 'element-plus'
import {
  Delete as DeleteIcon,
  Refresh,
  Clock,
  Monitor,
  Edit
} from '@element-plus/icons-vue'
import { useExecutionsStore } from '@/stores/executions'
import { useWorkflowsStore } from '@/stores/workflows'
import { useServersStore } from '@/stores/servers'

const route = useRoute()
const router = useRouter()
const executionsStore = useExecutionsStore()
const workflowsStore = useWorkflowsStore()
const serversStore = useServersStore()

const selectedExecutionId = ref<number | null>(null)
const workflowFilter = ref<number | null>(null)
const statusFilter = ref<string | null>(null)
const searchKeyword = ref('')
const rawNodeId = ref<string | null>(null)
const loadingDetail = ref(false)
const deletingExecutionId = ref<number | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const workflowNameMap = computed(() => {
  return new Map(workflowsStore.workflows.map(workflow => [workflow.id, workflow.name]))
})

const serverNameMap = computed(() => {
  return new Map(serversStore.servers.map(server => [server.id, `${server.name} (${server.host})`]))
})

const executionList = computed(() => {
  return executionsStore.executions.map(execution => ({
    ...execution,
    workflowName: workflowNameMap.value.get(execution.workflow_id) || `Workflow #${execution.workflow_id}`
  }))
})

const filteredExecutions = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  return executionList.value.filter(execution => {
    if (workflowFilter.value && execution.workflow_id !== workflowFilter.value) return false
    if (statusFilter.value && execution.status !== statusFilter.value) return false
    if (!keyword) return true

    const haystack = [
      execution.workflowName,
      execution.status,
      execution.result || '',
      execution.id.toString()
    ].join(' ').toLowerCase()

    return haystack.includes(keyword)
  })
})

const currentExecution = computed(() => executionsStore.currentExecution)
const nodeExecutions = computed(() => executionsStore.nodeExecutions)

const selectedNodeExecution = computed(() => {
  if (!rawNodeId.value) return null
  return nodeExecutions.value.find(node => node.node_id === rawNodeId.value) || null
})

const completedNodeCount = computed(() => {
  return nodeExecutions.value.filter(node => ['success', 'completed', 'failed', 'skipped'].includes(node.status)).length
})

const progressPercent = computed(() => {
  if (nodeExecutions.value.length === 0) return 0
  return Math.round((completedNodeCount.value / nodeExecutions.value.length) * 100)
})

const displayExecutionStatus = computed(() => {
  const execution = currentExecution.value
  if (!execution) return ''

  if (execution.status === 'failed' && execution.result === 'partial') {
    return '失败（部分完成）'
  }

  if (execution.status === 'failed') return '失败'
  if (execution.status === 'completed') return '成功'
  if (execution.status === 'running') return '运行中'
  if (execution.status === 'pending') return '等待中'
  if (execution.status === 'paused') return '已暂停'
  return execution.status
})

function stringifyData(value: unknown) {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function normalizeLogText(value: string): string {
  return value
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
}

function formatRawOutput(value: unknown): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'string') return normalizeLogText(value)

  if (typeof value === 'object' && !Array.isArray(value)) {
    const record = value as Record<string, unknown>
    const logSections: string[] = []

    if (typeof record.stdout === 'string' && record.stdout) {
      logSections.push(normalizeLogText(record.stdout))
    }
    if (typeof record.stderr === 'string' && record.stderr) {
      logSections.push(`stderr:\n${normalizeLogText(record.stderr)}`)
    }
    if (typeof record.error === 'string' && record.error) {
      logSections.push(`error:\n${normalizeLogText(record.error)}`)
    }
    if (logSections.length > 0) {
      return logSections.join('\n\n')
    }

    const entries = Object.entries(record)
    if (entries.length === 1 && typeof entries[0][1] === 'string') {
      return normalizeLogText(entries[0][1])
    }
  }

  try {
    return normalizeLogText(JSON.stringify(value, null, 2))
  } catch {
    return normalizeLogText(String(value))
  }
}

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatDuration(seconds: number | null) {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return remain === 0 ? `${minutes}m` : `${minutes}m ${remain}s`
}

function getStatusTone(status: string) {
  switch (status) {
    case 'completed':
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'warning'
    default:
      return 'info'
  }
}

function getServerLabel(serverId: unknown) {
  if (typeof serverId !== 'number') return 'Unknown server'
  return serverNameMap.value.get(serverId) || `Server #${serverId}`
}

function goToWorkflowEditor() {
  if (!currentExecution.value) return
  router.push(`/workflows/${currentExecution.value.workflow_id}/edit`)
}

async function loadExecution(executionId: number, syncRoute = true) {
  loadingDetail.value = true
  try {
    selectedExecutionId.value = executionId
    rawNodeId.value = null
    await executionsStore.fetchExecution(executionId)
    await executionsStore.fetchNodeExecutions(executionId)
    rawNodeId.value = executionsStore.nodeExecutions[0]?.node_id || null

    if (syncRoute) {
      await router.replace({
        path: '/executions',
        query: { executionId: String(executionId) }
      })
    }
  } finally {
    loadingDetail.value = false
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPollingIfNeeded() {
  stopPolling()
  if (!currentExecution.value || !selectedExecutionId.value) return
  if (!['pending', 'running'].includes(currentExecution.value.status)) return

  pollTimer = setInterval(async () => {
    if (!selectedExecutionId.value) return
    await loadExecution(selectedExecutionId.value, false)

    if (!currentExecution.value || !['pending', 'running'].includes(currentExecution.value.status)) {
      stopPolling()
    }
  }, 3000)
}

async function refreshPage() {
  await Promise.all([
    workflowsStore.fetchWorkflows(),
    serversStore.fetchServers(),
    executionsStore.fetchExecutions({ limit: 100 })
  ])

  const queryExecutionId = Number(route.query.executionId)
  const initialExecutionId = Number.isFinite(queryExecutionId) && queryExecutionId > 0
    ? queryExecutionId
    : filteredExecutions.value[0]?.id

  if (initialExecutionId) {
    await loadExecution(initialExecutionId, false)
  } else {
    executionsStore.clearCurrentExecution()
    rawNodeId.value = null
    selectedExecutionId.value = null
  }

  startPollingIfNeeded()
}

async function deleteExecution(executionId: number) {
  const execution = executionsStore.executions.find(item => item.id === executionId)
  const workflowName = execution
    ? workflowNameMap.value.get(execution.workflow_id) || `Workflow #${execution.workflow_id}`
    : `Execution #${executionId}`

  try {
    await ElMessageBox.confirm(
      `确定要删除「${workflowName}」的执行记录 #${executionId} 吗？删除后节点执行信息也会一起移除。`,
      '删除执行记录',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return
  }

  const listBeforeDelete = filteredExecutions.value
  const deletedIndex = listBeforeDelete.findIndex(item => item.id === executionId)
  const nextExecution = listBeforeDelete[deletedIndex + 1] || listBeforeDelete[deletedIndex - 1] || null
  const wasSelected = selectedExecutionId.value === executionId

  deletingExecutionId.value = executionId
  try {
    if (wasSelected) {
      stopPolling()
    }

    await executionsStore.deleteExecution(executionId)
    ElMessage.success('执行记录已删除')

    if (!wasSelected) return

    if (nextExecution) {
      await loadExecution(nextExecution.id)
    } else {
      executionsStore.clearCurrentExecution()
      rawNodeId.value = null
      selectedExecutionId.value = null
      await router.replace({ path: '/executions' })
    }
  } catch {
    ElMessage.error('删除执行记录失败')
  } finally {
    deletingExecutionId.value = null
  }
}

watch(() => currentExecution.value?.status, () => {
  startPollingIfNeeded()
})

watch(() => route.query.executionId, async (value) => {
  const nextId = Number(value)
  if (Number.isFinite(nextId) && nextId > 0 && nextId !== selectedExecutionId.value) {
    await loadExecution(nextId, false)
  }
})

onMounted(async () => {
  await refreshPage()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="execution-insights-page">
    <div class="toolbar">
      <ElButton type="primary" :icon="Refresh" @click="refreshPage">刷新</ElButton>

      <ElSelect v-model="workflowFilter" clearable placeholder="筛选工作流" class="toolbar-select">
        <ElOption
          v-for="workflow in workflowsStore.workflows"
          :key="workflow.id"
          :label="workflow.name"
          :value="workflow.id"
        />
      </ElSelect>

      <ElSelect v-model="statusFilter" clearable placeholder="筛选状态" class="toolbar-select">
        <ElOption label="pending" value="pending" />
        <ElOption label="running" value="running" />
        <ElOption label="completed" value="completed" />
        <ElOption label="failed" value="failed" />
      </ElSelect>

      <ElInput
        v-model="searchKeyword"
        placeholder="搜索执行 ID / 工作流 / 状态"
        clearable
        class="toolbar-search"
      />
    </div>

    <div class="page-grid">
      <ElCard class="panel execution-list-panel" shadow="never">
        <template #header>
          <div class="panel-title">
            <span>执行记录</span>
            <ElTag type="info" effect="plain">{{ filteredExecutions.length }}</ElTag>
          </div>
        </template>

        <ElScrollbar max-height="780px">
          <div v-if="filteredExecutions.length === 0" class="panel-empty">
            <span class="empty-text">暂无执行记录</span>
          </div>

          <div
            v-for="execution in filteredExecutions"
            :key="execution.id"
            class="execution-row"
            role="button"
            tabindex="0"
            :class="{ active: selectedExecutionId === execution.id }"
            @click="loadExecution(execution.id)"
            @keydown.enter="loadExecution(execution.id)"
            @keydown.space.prevent="loadExecution(execution.id)"
          >
            <div class="execution-row-top">
              <div>
                <div class="execution-title">{{ execution.workflowName }}</div>
                <div class="execution-subtitle">Execution #{{ execution.id }}</div>
              </div>
              <div class="execution-row-actions">
                <ElTag :type="getStatusTone(execution.status)" effect="dark">
                  {{ execution.status }}
                </ElTag>
                <ElButton
                  circle
                  plain
                  type="danger"
                  size="small"
                  :icon="DeleteIcon"
                  :loading="deletingExecutionId === execution.id"
                  aria-label="删除执行记录"
                  @click.stop="deleteExecution(execution.id)"
                  @keydown.stop
                />
              </div>
            </div>
            <div class="execution-row-meta">
              <span>{{ formatDate(execution.created_at) }}</span>
              <span>{{ execution.result || 'n/a' }}</span>
              <span>{{ formatDuration(execution.duration) }}</span>
            </div>
          </div>
        </ElScrollbar>
      </ElCard>

      <div class="detail-stack">
        <ElCard v-if="currentExecution" class="panel" shadow="never">
          <template #header>
            <div class="panel-title">
              <div class="panel-title-main">
                <span>执行概览</span>
                <ElTag :type="getStatusTone(currentExecution.status)" effect="dark">
                  {{ displayExecutionStatus }}
                </ElTag>
              </div>
              <div class="panel-actions">
                <ElButton size="small" :icon="Edit" @click="goToWorkflowEditor">编辑工作流</ElButton>
              </div>
            </div>
          </template>

          <div class="overview-grid">
            <div class="metric-card">
              <div class="metric-label">工作流</div>
              <div class="metric-value">{{ workflowNameMap.get(currentExecution.workflow_id) || `Workflow #${currentExecution.workflow_id}` }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">触发方式</div>
              <div class="metric-value">{{ currentExecution.trigger_type }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">总耗时</div>
              <div class="metric-value">{{ formatDuration(currentExecution.duration) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">节点进度</div>
              <div class="metric-value">{{ progressPercent }}%</div>
            </div>
          </div>

          <ElDescriptions :column="2" border class="execution-descriptions">
            <ElDescriptionsItem label="创建时间">{{ formatDate(currentExecution.created_at) }}</ElDescriptionsItem>
            <ElDescriptionsItem label="开始时间">{{ formatDate(currentExecution.started_at) }}</ElDescriptionsItem>
            <ElDescriptionsItem label="结束时间">{{ formatDate(currentExecution.finished_at) }}</ElDescriptionsItem>
            <ElDescriptionsItem label="摘要">{{ stringifyData(currentExecution.summary) }}</ElDescriptionsItem>
          </ElDescriptions>
        </ElCard>

        <div v-if="currentExecution" class="detail-grid">
          <ElCard class="panel" shadow="never">
            <template #header>
              <div class="panel-title">
                <span>节点时间线</span>
                <ElTag type="info" effect="plain">{{ nodeExecutions.length }} 节点</ElTag>
              </div>
            </template>

            <div v-if="nodeExecutions.length === 0" class="panel-empty">
              <span class="empty-text">该执行尚未产生节点记录</span>
            </div>

            <div v-else class="timeline-list">
              <button
                v-for="node in nodeExecutions"
                :key="node.node_id"
                type="button"
                class="timeline-item"
                :class="{ active: rawNodeId === node.node_id }"
                @click="rawNodeId = node.node_id"
              >
                <div class="timeline-dot" :class="node.status" />
                <div class="timeline-main">
                  <div class="timeline-title-row">
                    <div>
                      <div class="timeline-title">{{ node.node_type }}</div>
                      <div class="timeline-id">{{ node.node_id }}</div>
                    </div>
                    <ElTag :type="getStatusTone(node.status)" effect="plain">
                      {{ node.status }}
                    </ElTag>
                  </div>

                  <div class="timeline-meta">
                    <span><Clock class="inline-icon" /> {{ formatDuration(node.duration) }}</span>
                    <span><Monitor class="inline-icon" /> {{ getServerLabel(node.input_data?.server_id) }}</span>
                  </div>

                  <div v-if="node.error_message" class="timeline-error">
                    {{ node.error_message }}
                  </div>
                </div>
              </button>
            </div>
          </ElCard>

          <ElCard class="panel raw-panel" shadow="never">
            <template #header>
              <div class="panel-title">
                <span>节点原始信息</span>
                <div class="panel-title-side">
                  <ElTag
                    type="info"
                    effect="plain"
                    class="panel-node-tag"
                    :class="{ 'is-empty': !selectedNodeExecution }"
                  >
                    {{ selectedNodeExecution?.node_type || 'placeholder-node' }}
                  </ElTag>
                </div>
              </div>
            </template>

            <div v-if="!selectedNodeExecution" class="panel-empty">
              <span class="empty-text">选择左侧节点查看原始信息</span>
            </div>

            <template v-else>
              <div class="raw-summary">
                <ElAlert
                  v-if="selectedNodeExecution.error_message"
                  :title="selectedNodeExecution.error_message"
                  type="error"
                  :closable="false"
                  show-icon
                />
              </div>

              <div class="raw-block">
                <div class="raw-label">Input</div>
                <pre class="raw-pre">{{ stringifyData(selectedNodeExecution.input_data) }}</pre>
              </div>

              <div class="raw-block">
                <div class="raw-label">Output</div>
                <pre class="raw-pre">{{ formatRawOutput(selectedNodeExecution.output_data) }}</pre>
              </div>
            </template>
          </ElCard>
        </div>

        <ElCard v-else class="panel" shadow="never">
          <div class="panel-empty">
            <span class="empty-text">从左侧选择一条执行记录开始分析</span>
          </div>
        </ElCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.execution-insights-page {
  min-height: 100%;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.toolbar-select {
  width: 180px;
}

.toolbar-search {
  flex: 1;
  max-width: 300px;
}

.page-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 10px;
}

.detail-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.panel {
  border: 1px solid #e2e8f0 !important;
  border-radius: 8px !important;
}

.panel :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfc;
}

.panel :deep(.el-card__body) {
  padding: 12px 16px;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 12px;
  color: #1e293b;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.panel-title-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title-side {
  display: flex;
  justify-content: flex-end;
}

.panel-node-tag {
  max-width: 140px;
  overflow: hidden;
}

.panel-empty {
  padding: 20px 0;
}

.empty-text {
  color: #94a3b8;
  font-size: 12px;
}

.execution-row {
  width: 100%;
  margin-bottom: 6px;
  padding: 10px;
  border-radius: 6px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
  transition: background-color 0.15s;
}

.execution-row:hover {
  background: #f1f5f9;
}

.execution-row.active {
  background: #eff6ff;
}

.execution-row-top,
.execution-row-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.execution-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.execution-title,
.timeline-title,
.metric-value {
  color: #1e293b;
  font-weight: 600;
  font-size: 12px;
}

.execution-subtitle,
.execution-row-meta,
.timeline-id,
.timeline-meta,
.metric-label {
  color: #94a3b8;
  font-size: 10px;
}

.execution-row-meta {
  margin-top: 4px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}

.metric-card {
  padding: 10px;
  border-radius: 6px;
  background: #f8fafc;
}

.metric-value {
  margin-top: 2px;
  font-size: 14px;
}

.raw-label {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 10px;
  font-weight: 600;
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s, background-color 0.15s;
}

.timeline-item:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.timeline-item.active {
  background: #eff6ff;
  border-color: #3b82f6;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 50%;
  background: #94a3b8;
}

.timeline-dot.success,
.timeline-dot.completed {
  background: #10b981;
}

.timeline-dot.failed {
  background: #ef4444;
}

.timeline-dot.running {
  background: #f59e0b;
}

.timeline-main {
  flex: 1;
}

.timeline-title-row,
.timeline-meta {
  display: flex;
  justify-content: space-between;
  gap: 6px;
}

.timeline-error {
  margin-top: 6px;
  color: #ef4444;
  font-size: 10px;
}

.inline-icon {
  width: 14px;
  margin-right: 4px;
  vertical-align: -2px;
}

.raw-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.raw-block {
  display: flex;
  flex-direction: column;
}

.raw-pre {
  max-height: 200px;
  overflow: auto;
  padding: 10px;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1200px) {
  .page-grid,
  .detail-grid,
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-hero,
  .toolbar {
    flex-direction: column;
  }

  .toolbar-select,
  .toolbar-search {
    width: 100%;
    max-width: none;
  }
}
</style>
