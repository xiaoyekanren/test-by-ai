<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import {
  ElButton,
  ElProgress,
  ElDialog,
  ElTag,
  ElEmpty,
  ElIcon,
  ElScrollbar
} from 'element-plus'
import {
  VideoPlay,
  VideoPause,
  CircleCheck,
  CircleClose,
  Clock,
  Loading,
  Timer
} from '@element-plus/icons-vue'
import { executionsApi } from '@/api'
import type { Execution, ExecutionStatus, NodeExecution } from '@/types'

const props = defineProps<{
  workflowId: number | null
  runRequestId?: number
}>()

const emit = defineEmits<{
  (e: 'executionStarted', execution: Execution): void
  (e: 'executionCompleted', execution: Execution): void
  (e: 'executionCleared'): void
  (e: 'nodeExecutionsUpdated', nodeExecutions: NodeExecution[]): void
}>()

// Local state
const isStarting = ref(false)
const isStopping = ref(false)
const logDialogVisible = ref(false)
const selectedLogNodeId = ref<string | null>(null)
const handledRunRequestId = ref(0)
const currentExecution = ref<Execution | null>(null)
const nodeExecutions = ref<NodeExecution[]>([])

// Polling timer
let pollTimer: ReturnType<typeof setInterval> | null = null

const executionStatus = computed(() => currentExecution.value?.status || null)
const displayExecutionStatus = computed(() => executionStatus.value || (isStarting.value ? 'running' : null))
const displayDuration = computed(() => currentExecution.value?.duration ?? null)
const hasExecutionView = computed(() => Boolean(currentExecution.value) || isStarting.value)

const isRunning = computed(() =>
  executionStatus.value === 'running' || executionStatus.value === 'pending'
)

const canRun = computed(() =>
  props.workflowId !== null && !isRunning.value && !isStarting.value
)

const canStop = computed(() =>
  isRunning.value && !isStopping.value
)

// Progress calculation
const progressPercent = computed(() => {
  if (!nodeExecutions.value.length) return 0
  const completed = nodeExecutions.value.filter(
    ne => ne.status === 'completed' || ne.status === 'failed' || ne.status === 'skipped'
  ).length
  return Math.round((completed / nodeExecutions.value.length) * 100)
})

// Status color and icon mapping
const statusConfig: Record<ExecutionStatus | string, { color: string; bgColor: string; icon: typeof VideoPlay; label: string }> = {
  pending: { color: '#909399', bgColor: '#f4f4f5', icon: Clock, label: 'Pending' },
  running: { color: '#409EFF', bgColor: '#ecf5ff', icon: Loading, label: 'Running' },
  paused: { color: '#E6A23C', bgColor: '#fdf6ec', icon: VideoPause, label: 'Paused' },
  completed: { color: '#67C23A', bgColor: '#f0f9eb', icon: CircleCheck, label: 'Completed' },
  failed: { color: '#F56C6C', bgColor: '#fef0f0', icon: CircleClose, label: 'Failed' }
}

// Node status config
const nodeStatusConfig: Record<string, { color: string; icon: typeof Clock; label: string }> = {
  pending: { color: '#909399', icon: Clock, label: 'Pending' },
  running: { color: '#409EFF', icon: Loading, label: 'Running' },
  completed: { color: '#67C23A', icon: CircleCheck, label: 'Success' },
  failed: { color: '#F56C6C', icon: CircleClose, label: 'Failed' },
  skipped: { color: '#909399', icon: VideoPause, label: 'Skipped' }
}

// Format duration
const formatDuration = (seconds: number | null): string => {
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

// Get status info
const getStatusInfo = (status: string) => {
  return statusConfig[status] || statusConfig.pending
}

const getNodeStatusInfo = (status: string) => {
  return nodeStatusConfig[status] || nodeStatusConfig.pending
}

const normalizeLogText = (value: string): string => {
  return value
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
}

const formatLogData = (value: unknown): string => {
  if (value === null || value === undefined) return ''
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

  return normalizeLogText(JSON.stringify(value, null, 2))
}

// Run workflow
const handleRun = async () => {
  if (!props.workflowId || !canRun.value) return

  isStarting.value = true
  selectedLogNodeId.value = null
  stopPolling()
  clearExecutionState()

  try {
    const execution = await executionsApi.create({
      workflow_id: props.workflowId,
      trigger_type: 'manual'
    })
    currentExecution.value = execution

    // Fetch node executions
    nodeExecutions.value = await executionsApi.getNodes(execution.id)
    emit('nodeExecutionsUpdated', nodeExecutions.value)

    // Start polling
    startPolling(execution.id)

    emit('executionStarted', execution)
  } catch (error) {
    console.error('Failed to start execution:', error)
  } finally {
    isStarting.value = false
  }
}

// Stop execution
const handleStop = async () => {
  if (!currentExecution.value) return

  isStopping.value = true
  try {
    currentExecution.value = await executionsApi.stop(currentExecution.value.id)
    stopPolling()
  } catch (error) {
    console.error('Failed to stop execution:', error)
  } finally {
    isStopping.value = false
  }
}

// Polling logic
const startPolling = (executionId: number) => {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const execution = await executionsApi.get(executionId)
      currentExecution.value = execution
      nodeExecutions.value = await executionsApi.getNodes(executionId)
      emit('nodeExecutionsUpdated', nodeExecutions.value)

      // Check if execution is finished
      if (execution.status === 'completed' || execution.status === 'failed') {
        stopPolling()
        emit('executionCompleted', execution)
      }
    } catch (error) {
      console.error('Polling error:', error)
      stopPolling()
    }
  }, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearExecutionState = () => {
  currentExecution.value = null
  nodeExecutions.value = []
  emit('nodeExecutionsUpdated', [])
}

// Clear execution
const handleClear = () => {
  stopPolling()
  logDialogVisible.value = false
  selectedLogNodeId.value = null
  clearExecutionState()
  emit('executionCleared')
}

const openLogsForNode = (nodeId: string | null = null) => {
  selectedLogNodeId.value = nodeId
  logDialogVisible.value = true
}

const logDialogNodeExecutions = computed(() => {
  if (!selectedLogNodeId.value) return nodeExecutions.value
  return nodeExecutions.value.filter(ne => ne.node_id === selectedLogNodeId.value)
})

const logDialogTitle = computed(() => {
  if (!selectedLogNodeId.value) return 'Execution Logs'
  const nodeExecution = nodeExecutions.value.find(ne => ne.node_id === selectedLogNodeId.value)
  return `Execution Logs - ${nodeExecution?.node_type || selectedLogNodeId.value}`
})

defineExpose({ openLogsForNode })

watch(() => props.runRequestId, (requestId) => {
  const nextRequestId = requestId ?? 0
  if (nextRequestId <= handledRunRequestId.value) return

  handledRunRequestId.value = nextRequestId
  void handleRun()
}, { immediate: true })

// Watch workflow ID changes
watch(() => props.workflowId, () => {
  handleClear()
})

// Cleanup on unmount
onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="execution-panel">
    <!-- Header -->
    <div class="panel-header">
      <h3>Execution Panel</h3>
      <div class="header-actions">
        <ElButton
          v-if="currentExecution"
          text
          size="small"
          @click="handleClear"
        >
          Clear
        </ElButton>
      </div>
    </div>

    <!-- Execution Controls -->
    <div v-if="canStop" class="execution-controls">
      <ElButton
        type="danger"
        :icon="VideoPause"
        :loading="isStopping"
        @click="handleStop"
      >
        {{ isStopping ? 'Stopping...' : 'Stop' }}
      </ElButton>
    </div>

    <!-- No Execution State -->
    <div v-if="!hasExecutionView" class="no-execution">
      <ElEmpty description="No execution running">
        <template #image>
          <ElIcon :size="48" color="#c0c4cc">
            <VideoPlay />
          </ElIcon>
        </template>
        <p class="hint">Use the toolbar Run button to start execution</p>
      </ElEmpty>
    </div>

    <!-- Execution Status -->
    <div v-else class="execution-status">
      <!-- Status Header -->
      <div class="status-header">
        <div class="status-badge" :style="{
          backgroundColor: getStatusInfo(displayExecutionStatus || 'pending').bgColor,
          color: getStatusInfo(displayExecutionStatus || 'pending').color
        }">
          <ElIcon class="status-icon" :class="{ 'is-loading': displayExecutionStatus === 'running' }">
            <component :is="getStatusInfo(displayExecutionStatus || 'pending').icon" />
          </ElIcon>
          <span>{{ isStarting && !currentExecution ? 'Starting' : getStatusInfo(displayExecutionStatus || 'pending').label }}</span>
        </div>

        <div class="execution-time">
          <ElIcon><Timer /></ElIcon>
          <span>{{ formatDuration(displayDuration) }}</span>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="progress-section">
        <div class="progress-label">
          <span>Progress</span>
          <span>{{ progressPercent }}%</span>
        </div>
        <ElProgress
          :percentage="progressPercent"
          :status="displayExecutionStatus === 'failed' ? 'exception' : displayExecutionStatus === 'completed' ? 'success' : undefined"
          :stroke-width="8"
        />
      </div>

      <!-- Node Execution List -->
      <div class="node-executions">
        <div class="section-header">
          <h4>Node Executions</h4>
          <span class="count">{{ nodeExecutions.length }} nodes</span>
          <span class="section-hint">Double-click for logs</span>
        </div>

        <ElScrollbar class="node-list">
          <div
            v-for="nodeExec in nodeExecutions"
            :key="nodeExec.id"
            class="node-item"
            :class="{ active: selectedLogNodeId === nodeExec.node_id }"
            @dblclick.stop="openLogsForNode(nodeExec.node_id)"
          >
            <div class="node-info">
              <ElIcon
                :color="getNodeStatusInfo(nodeExec.status).color"
                :class="{ 'is-loading': nodeExec.status === 'running' }"
              >
                <component :is="getNodeStatusInfo(nodeExec.status).icon" />
              </ElIcon>
              <span class="node-type">{{ nodeExec.node_type }}</span>
              <span class="node-id">{{ nodeExec.node_id.slice(0, 8) }}</span>
            </div>
            <div class="node-meta">
              <span class="duration">{{ formatDuration(nodeExec.duration) }}</span>
              <ElTag
                size="small"
                :type="nodeExec.status === 'completed' ? 'success' : nodeExec.status === 'failed' ? 'danger' : 'info'"
              >
                {{ getNodeStatusInfo(nodeExec.status).label }}
              </ElTag>
            </div>
          </div>
        </ElScrollbar>
      </div>

      <!-- Execution Result Summary -->
      <div v-if="currentExecution?.result" class="result-summary">
        <div class="result-header">
          <ElIcon :size="20" :color="currentExecution.result === 'passed' ? '#67C23A' : '#F56C6C'">
            <component :is="currentExecution.result === 'passed' ? CircleCheck : CircleClose" />
          </ElIcon>
          <span class="result-text" :class="currentExecution.result">
            {{ currentExecution.result === 'passed' ? 'All tests passed' : 'Some tests failed' }}
          </span>
        </div>
      </div>
    </div>

    <ElDialog
      v-model="logDialogVisible"
      :title="logDialogTitle"
      width="760px"
      top="8vh"
      append-to-body
    >
      <div class="logs-dialog-content">
        <ElScrollbar class="logs-dialog-scroll">
          <div v-if="logDialogNodeExecutions.length === 0" class="no-logs">
            No logs available
          </div>
          <div v-else class="log-entries">
            <div
              v-for="nodeExec in logDialogNodeExecutions"
              :key="nodeExec.id"
              class="log-entry"
            >
              <div class="log-header">
                <span class="log-node">{{ nodeExec.node_type }}</span>
                <ElTag size="small" :type="nodeExec.status === 'completed' ? 'success' : nodeExec.status === 'failed' ? 'danger' : 'info'">
                  {{ nodeExec.status }}
                </ElTag>
              </div>
              <div v-if="nodeExec.input_data" class="log-section">
                <span class="log-label">Input:</span>
                <pre class="log-data">{{ formatLogData(nodeExec.input_data) }}</pre>
              </div>
              <div v-if="nodeExec.output_data" class="log-section">
                <span class="log-label">Output:</span>
                <pre class="log-data">{{ formatLogData(nodeExec.output_data) }}</pre>
              </div>
              <div v-if="nodeExec.error_message" class="log-section error">
                <span class="log-label">Error:</span>
                <pre class="log-data error">{{ nodeExec.error_message }}</pre>
              </div>
            </div>
          </div>
        </ElScrollbar>
      </div>
    </ElDialog>
  </div>
</template>

<style scoped>
.execution-panel {
  height: 100%;
  width: 380px;
  min-width: 380px;
  flex: 0 0 380px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid #e4e7ed;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.execution-controls {
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  gap: 8px;
}

.no-execution {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.no-execution .hint {
  color: #909399;
  font-size: 13px;
  margin-top: 8px;
}

.execution-status {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}

.status-icon.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.execution-time {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #606266;
  font-size: 13px;
}

.progress-section {
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #909399;
}

.node-executions {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-bottom: 1px solid #e4e7ed;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.section-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.section-header .count {
  font-size: 12px;
  color: #909399;
}

.section-hint {
  margin-left: auto;
  font-size: 11px;
  color: #909399;
}

.node-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.node-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.node-item:hover {
  background: #f5f7fa;
}

.node-item.active {
  background: #ecf5ff;
}

.node-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-type {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.node-id {
  font-size: 11px;
  color: #909399;
  font-family: monospace;
}

.node-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.duration {
  font-size: 12px;
  color: #909399;
}

.logs-dialog-content {
  height: min(60vh, 560px);
  overflow: hidden;
}

.logs-dialog-scroll {
  height: 100%;
}

.no-logs {
  padding: 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.log-entries {
  padding: 8px;
}

.log-entry {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.log-entry:last-child {
  margin-bottom: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-node {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
}

.log-section {
  margin-bottom: 6px;
}

.log-section:last-child {
  margin-bottom: 0;
}

.log-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
  display: block;
}

.log-data {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 11px;
  background: #fff;
  padding: 8px;
  border-radius: 4px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  color: #303133;
}

.log-data.error {
  color: #f56c6c;
  background: #fef0f0;
}

.result-summary {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-text {
  font-size: 14px;
  font-weight: 500;
}

.result-text.passed {
  color: #67c23a;
}

.result-text.failed {
  color: #f56c6c;
}
</style>
