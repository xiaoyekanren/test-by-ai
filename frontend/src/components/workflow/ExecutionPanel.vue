<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import {
  ElButton,
  ElProgress,
  ElCollapse,
  ElCollapseItem,
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
  Document,
  Timer
} from '@element-plus/icons-vue'
import { useExecutionsStore } from '@/stores/executions'
import type { Execution, ExecutionStatus } from '@/types'

const props = defineProps<{
  workflowId: number | null
  runRequestId?: number
}>()

const emit = defineEmits<{
  (e: 'executionStarted', execution: Execution): void
  (e: 'executionCompleted', execution: Execution): void
}>()

const executionsStore = useExecutionsStore()

// Local state
const isStarting = ref(false)
const isStopping = ref(false)
const logsExpanded = ref(['logs'])
const selectedNodeFilter = ref<string | null>(null)
const handledRunRequestId = ref(0)

// Polling timer
let pollTimer: ReturnType<typeof setInterval> | null = null

// Computed
const currentExecution = computed(() => executionsStore.currentExecution)
const nodeExecutions = computed(() => executionsStore.nodeExecutions)

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

// Run workflow
const handleRun = async () => {
  if (!props.workflowId || !canRun.value) return

  isStarting.value = true
  selectedNodeFilter.value = null
  stopPolling()
  executionsStore.clearCurrentExecution()

  try {
    const execution = await executionsStore.createExecution({
      workflow_id: props.workflowId,
      trigger_type: 'manual'
    })

    // Fetch node executions
    await executionsStore.fetchNodeExecutions(execution.id)

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
    await executionsStore.stopExecution(currentExecution.value.id)
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
      const execution = await executionsStore.fetchExecution(executionId)
      await executionsStore.fetchNodeExecutions(executionId)

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

// Clear execution
const handleClear = () => {
  stopPolling()
  executionsStore.clearCurrentExecution()
}

// Filter logs
const filteredNodeExecutions = computed(() => {
  if (!selectedNodeFilter.value) return nodeExecutions.value
  return nodeExecutions.value.filter(ne => ne.node_id === selectedNodeFilter.value)
})

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
        <p class="hint">Click "Run Workflow" to start execution</p>
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
        </div>

        <ElScrollbar class="node-list">
          <div
            v-for="nodeExec in nodeExecutions"
            :key="nodeExec.id"
            class="node-item"
            :class="{ active: selectedNodeFilter === nodeExec.node_id }"
            @click="selectedNodeFilter = selectedNodeFilter === nodeExec.node_id ? null : nodeExec.node_id"
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

      <!-- Execution Logs -->
      <ElCollapse v-model="logsExpanded" class="logs-collapse">
        <ElCollapseItem name="logs">
          <template #title>
            <div class="logs-title">
              <ElIcon><Document /></ElIcon>
              <span>Execution Logs</span>
            </div>
          </template>

          <div class="logs-content">
            <ElScrollbar class="logs-scroll">
              <div v-if="filteredNodeExecutions.length === 0" class="no-logs">
                No logs available
              </div>
              <div v-else class="log-entries">
                <div
                  v-for="nodeExec in filteredNodeExecutions"
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
                    <pre class="log-data">{{ JSON.stringify(nodeExec.input_data, null, 2) }}</pre>
                  </div>
                  <div v-if="nodeExec.output_data" class="log-section">
                    <span class="log-label">Output:</span>
                    <pre class="log-data">{{ JSON.stringify(nodeExec.output_data, null, 2) }}</pre>
                  </div>
                  <div v-if="nodeExec.error_message" class="log-section error">
                    <span class="log-label">Error:</span>
                    <pre class="log-data error">{{ nodeExec.error_message }}</pre>
                  </div>
                </div>
              </div>
            </ElScrollbar>
          </div>
        </ElCollapseItem>
      </ElCollapse>

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

.logs-collapse {
  border: none;
  margin-top: auto;
}

.logs-collapse :deep(.el-collapse-item__header) {
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 16px;
  height: 40px;
}

.logs-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.logs-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.logs-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.logs-content {
  height: 200px;
  border-top: 1px solid #e4e7ed;
  overflow: hidden;
}

.logs-scroll {
  height: 200px;
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
