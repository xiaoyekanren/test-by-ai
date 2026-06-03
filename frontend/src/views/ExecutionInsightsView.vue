<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCard,
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
  Edit
} from '@element-plus/icons-vue'
import { useExecutionsStore } from '@/stores/executions'
import { useWorkflowsStore } from '@/stores/workflows'
import { useServersStore } from '@/stores/servers'
import { NODE_CONFIGS } from '@/types'
import type { NodeDefinition, NodeExecution } from '@/types'

interface WorkflowStateSnapshotNode {
  id: string
  type: string
  config?: Record<string, unknown>
  position?: { x: number; y: number } | null
  sequence?: number
  status?: string
  duration?: number | null
  error_message?: string | null
}

interface WorkflowStateSnapshotEdge {
  from: string
  to: string
  label?: string | null
  status?: string
}

interface WorkflowStateSnapshot {
  version: number
  captured_at?: string
  nodes: WorkflowStateSnapshotNode[]
  edges: WorkflowStateSnapshotEdge[]
}

interface ExecutionNodeViewModel {
  nodeId: string
  label: string
  nodeType: string
  status: string
  sequence: string
  incomingCount: number
  outgoingCount: number
  definition: NodeDefinition | null
  execution: NodeExecution | null
}

interface ReadonlyGraphNode {
  node: ExecutionNodeViewModel
  x: number
  y: number
  width: number
  height: number
  layer: number
  lane: number
  hostLabel: string
}

interface ReadonlyGraphEdge {
  id: string
  path: string
  status: string
}

interface ReadonlyGraphPhase {
  key: number
  label: string
  x: number
  width: number
}

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

const readonlyGraphNodeWidth = 150
const readonlyGraphNodeHeight = 76
const readonlyGraphColumnGap = 68
const readonlyGraphRowGap = 34
const readonlyGraphPaddingX = 28
const readonlyGraphPaddingTop = 58
const readonlyGraphPaddingBottom = 34

const workflowNameMap = computed(() => {
  return new Map(workflowsStore.workflows.map(workflow => [workflow.id, workflow.name]))
})

const serverHostMap = computed(() => {
  return new Map(serversStore.servers.map(server => [server.id, server.host || server.name]))
})

const hasDisplayValue = (value: unknown) => value !== null && value !== undefined && value !== ''

const getDisplayString = (value: unknown) => {
  if (!hasDisplayValue(value)) return ''
  return String(value)
}

const getServerHostLabel = (serverId: unknown) => {
  if (!hasDisplayValue(serverId)) return ''
  const numericServerId = Number(serverId)
  if (!Number.isFinite(numericServerId)) return ''
  return serverHostMap.value.get(numericServerId) || `Server #${numericServerId}`
}

const getClusterHostLabels = (config: Record<string, unknown>) => {
  const hosts: string[] = []
  for (const field of ['config_nodes', 'data_nodes']) {
    const nodes = config[field]
    if (!Array.isArray(nodes)) continue
    for (const item of nodes) {
      if (!item || typeof item !== 'object') continue
      const node = item as Record<string, unknown>
      const host = getDisplayString(node.host) || getServerHostLabel(node.server_id)
      if (host && !hosts.includes(host)) {
        hosts.push(host)
      }
    }
  }
  return hosts
}

const getNodeSubtitle = (
  config: Record<string, unknown>,
  inputData: Record<string, unknown> | null | undefined
) => {
  const runtime = inputData || {}
  const directHost = (
    getDisplayString(runtime.server_name) ||
    getDisplayString(runtime.host) ||
    getDisplayString(runtime.target_host) ||
    getDisplayString(runtime.ain_rpc_address) ||
    getDisplayString(config.server_name) ||
    getDisplayString(config.host) ||
    getDisplayString(config.target_host) ||
    getDisplayString(config.ain_rpc_address) ||
    getDisplayString(config.ain_cluster_ingress_address)
  )
  if (directHost) return directHost

  const serverHost = getServerHostLabel(runtime.server_id) || getServerHostLabel(config.server_id)
  if (serverHost) return serverHost

  const clusterHosts = getClusterHostLabels(config)
  if (clusterHosts.length > 0) return clusterHosts.join(', ')

  return '无主机'
}

const executionList = computed(() => {
  return executionsStore.executions.map(execution => ({
    ...execution,
    workflowName: workflowNameMap.value.get(execution.workflow_id) || `工作流 #${execution.workflow_id}`
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

const workflowStateSnapshot = computed<WorkflowStateSnapshot | null>(() => {
  const value = currentExecution.value?.summary?.workflow_state
  if (!value || typeof value !== 'object') return null
  const snapshot = value as Partial<WorkflowStateSnapshot>
  if (!Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.edges)) return null
  return {
    version: Number(snapshot.version || 1),
    captured_at: snapshot.captured_at,
    nodes: snapshot.nodes,
    edges: snapshot.edges
  }
})

const nodeExecutionMap = computed(() => {
  return new Map(nodeExecutions.value.map(node => [node.node_id, node]))
})

const workflowEdges = computed<WorkflowStateSnapshotEdge[]>(() => {
  return workflowStateSnapshot.value?.edges || []
})

const executionNodeViewModels = computed<ExecutionNodeViewModel[]>(() => {
  const snapshotNodes = workflowStateSnapshot.value?.nodes || []
  return snapshotNodes
    .map((node, index) => {
      const execution = nodeExecutionMap.value.get(node.id) || null
      const sequence = String(node.sequence || index + 1)
      return {
        nodeId: node.id,
        label: NODE_CONFIGS[node.type as keyof typeof NODE_CONFIGS]?.label || node.type,
        nodeType: node.type,
        status: node.status || execution?.status || 'not-run',
        sequence,
        incomingCount: workflowEdges.value.filter(edge => edge.to === node.id).length,
        outgoingCount: workflowEdges.value.filter(edge => edge.from === node.id).length,
        definition: {
          id: node.id,
          type: node.type as NodeDefinition['type'],
          config: node.config || {},
          position: node.position || null
        },
        execution
      }
    })
    .sort((left, right) => compareSequence(left.sequence, right.sequence))
})

const selectedNodeExecution = computed(() => {
  if (!rawNodeId.value) return null
  return nodeExecutions.value.find(node => node.node_id === rawNodeId.value) || null
})

const selectedNodeView = computed(() => {
  if (!rawNodeId.value) return null
  return executionNodeViewModels.value.find(node => node.nodeId === rawNodeId.value) || null
})

const completedNodeCount = computed(() => {
  return executionNodeViewModels.value.filter(node => ['success', 'failed', 'skipped'].includes(node.status)).length
})

const progressPercent = computed(() => {
  if (executionNodeViewModels.value.length === 0) return 0
  return Math.round((completedNodeCount.value / executionNodeViewModels.value.length) * 100)
})

const notRunNodeCount = computed(() => {
  return executionNodeViewModels.value.filter(node => node.status === 'not-run').length
})

const failedNodeCount = computed(() => {
  return executionNodeViewModels.value.filter(node => node.status === 'failed').length
})

const executionSummaryDisplay = computed(() => {
  const summary = currentExecution.value?.summary
  if (!summary) return null
  const { workflow_state: _workflowState, ...rest } = summary
  return rest
})

const readonlyGraphLayout = computed(() => {
  const parsedNodes = executionNodeViewModels.value.map(node => ({
    node,
    sequence: parseSequenceParts(node.sequence)
  }))
  const layerValues = Array.from(new Set(parsedNodes.map(item => item.sequence.layer))).sort((a, b) => a - b)
  const maxLane = Math.max(1, ...parsedNodes.map(item => item.sequence.lane))
  const centeredLane = maxLane > 1 ? (maxLane + 1) / 2 : 1

  const graphNodes: ReadonlyGraphNode[] = parsedNodes.map(item => {
    const layerIndex = Math.max(0, layerValues.indexOf(item.sequence.layer))
    const lane = item.sequence.hasExplicitLane ? item.sequence.lane : centeredLane
    return {
      node: item.node,
      x: readonlyGraphPaddingX + layerIndex * (readonlyGraphNodeWidth + readonlyGraphColumnGap),
      y: readonlyGraphPaddingTop + (lane - 1) * (readonlyGraphNodeHeight + readonlyGraphRowGap),
      width: readonlyGraphNodeWidth,
      height: readonlyGraphNodeHeight,
      layer: item.sequence.layer,
      lane,
      hostLabel: getTimelineHostLabel(item.node)
    }
  })

  const width = Math.max(
    620,
    readonlyGraphPaddingX * 2 +
      layerValues.length * readonlyGraphNodeWidth +
      Math.max(0, layerValues.length - 1) * readonlyGraphColumnGap
  )
  const height = Math.max(
    320,
    readonlyGraphPaddingTop +
      maxLane * readonlyGraphNodeHeight +
      Math.max(0, maxLane - 1) * readonlyGraphRowGap +
      readonlyGraphPaddingBottom
  )

  const nodeMap = new Map(graphNodes.map(item => [item.node.nodeId, item]))
  const edges: ReadonlyGraphEdge[] = workflowEdges.value
    .map(edge => {
      const source = nodeMap.get(edge.from)
      const target = nodeMap.get(edge.to)
      const from = executionNodeViewModels.value.find(node => node.nodeId === edge.from)
      const to = executionNodeViewModels.value.find(node => node.nodeId === edge.to)
      if (!source || !target || !from || !to) return null

      const startX = source.x + source.width
      const startY = source.y + source.height / 2
      const endX = target.x
      const endY = target.y + target.height / 2
      const controlGap = Math.max(42, Math.abs(endX - startX) * 0.45)
      const path = endX >= startX
        ? `M ${startX} ${startY} C ${startX + controlGap} ${startY}, ${endX - controlGap} ${endY}, ${endX} ${endY}`
        : `M ${startX} ${startY} C ${startX + 54} ${startY}, ${endX - 54} ${endY}, ${endX} ${endY}`
      const status = edge.status || getWorkflowEdgeStatus(from, to)

      return {
        id: `${edge.from}-${edge.to}`,
        path,
        status
      }
    })
    .filter((edge): edge is ReadonlyGraphEdge => edge !== null)

  const phases: ReadonlyGraphPhase[] = layerValues.map((layer, index) => ({
    key: layer,
    label: `阶段 ${layer}`,
    x: readonlyGraphPaddingX + index * (readonlyGraphNodeWidth + readonlyGraphColumnGap),
    width: readonlyGraphNodeWidth
  }))

  return {
    nodes: graphNodes,
    edges,
    phases,
    width,
    height
  }
})

const readonlyGraphStyle = computed(() => ({
  width: `${readonlyGraphLayout.value.width}px`,
  height: `${readonlyGraphLayout.value.height}px`
}))

const readonlyGraphViewBox = computed(() => {
  return `0 0 ${readonlyGraphLayout.value.width} ${readonlyGraphLayout.value.height}`
})

const timelinePhaseGroups = computed(() => {
  const groups = new Map<number, ExecutionNodeViewModel[]>()
  for (const node of executionNodeViewModels.value) {
    const layer = parseSequenceParts(node.sequence).layer
    const group = groups.get(layer) || []
    group.push(node)
    groups.set(layer, group)
  }

  return Array.from(groups.entries())
    .sort(([left], [right]) => left - right)
    .map(([phase, nodes]) => ({
      phase,
      nodes: nodes.sort((left, right) => compareSequence(left.sequence, right.sequence))
    }))
})

const displayExecutionStatus = computed(() => {
  const execution = currentExecution.value
  if (!execution) return ''

  if (execution.status === 'failed' && execution.result === 'partial') {
    return '失败（部分完成）'
  }

  if (execution.status === 'failed') return '失败'
  if (execution.status === 'completed') return '成功'
  if (execution.status === 'stopped') return '已停止'
  if (execution.status === 'running') return '运行中'
  if (execution.status === 'pending') return '等待中'
  if (execution.status === 'paused') return '已暂停'
  return execution.status
})

function stringifyData(value: unknown) {
  if (value === null || value === undefined) return '无'
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
  if (value === null || value === undefined) return '无'
  if (typeof value === 'string') return normalizeLogText(value)

  if (typeof value === 'object' && !Array.isArray(value)) {
    const record = value as Record<string, unknown>
    const logSections: string[] = []

    if (typeof record.stdout === 'string' && record.stdout) {
      logSections.push(normalizeLogText(record.stdout))
    }
    if (typeof record.stderr === 'string' && record.stderr) {
      logSections.push(`标准错误：\n${normalizeLogText(record.stderr)}`)
    }
    if (typeof record.error === 'string' && record.error) {
      logSections.push(`错误：\n${normalizeLogText(record.error)}`)
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

function getWorkflowEdgeStatus(from: ExecutionNodeViewModel, to: ExecutionNodeViewModel) {
  if (from.status === 'failed') return 'failed'
  if (from.status === 'success' && to.status !== 'not-run') return 'passed'
  if (to.status === 'running') return 'running'
  return 'pending'
}

function parseSequenceParts(value: string) {
  const [layerText, branchText] = value.split('-', 2)
  const layer = Number(layerText)
  const lane = Number(branchText)

  return {
    layer: Number.isFinite(layer) ? layer : 0,
    lane: Number.isFinite(lane) && lane > 0 ? lane : 1,
    hasExplicitLane: branchText !== undefined
  }
}

function compareSequence(left: string, right: string) {
  const leftParts = parseSequenceParts(left)
  const rightParts = parseSequenceParts(right)
  return leftParts.layer - rightParts.layer || leftParts.lane - rightParts.lane
}

function getGraphNodeStyle(node: ReadonlyGraphNode) {
  return {
    left: `${node.x}px`,
    top: `${node.y}px`,
    width: `${node.width}px`,
    height: `${node.height}px`
  }
}

function getGraphPhaseStyle(phase: ReadonlyGraphPhase) {
  return {
    left: `${phase.x}px`,
    width: `${phase.width}px`
  }
}

function getNodeStatusClass(status: string) {
  if (['success', 'failed', 'running', 'skipped', 'not-run', 'pending'].includes(status)) {
    return status
  }
  return 'pending'
}

function getEdgeStatusClass(status: string) {
  if (['passed', 'failed', 'running', 'pending'].includes(status)) return status
  return 'pending'
}

function getStatusTone(status: string) {
  switch (status) {
    case 'completed':
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'stopped':
    case 'running':
      return 'warning'
    case 'not-run':
    case 'skipped':
      return 'info'
    default:
      return 'info'
  }
}

function getNodeStatusLabel(status: string) {
  switch (status) {
    case 'success':
      return '成功'
    case 'failed':
      return '失败'
    case 'running':
      return '运行中'
    case 'pending':
      return '等待中'
    case 'skipped':
      return '已跳过'
    case 'not-run':
      return '未执行'
    default:
      return status
  }
}

function getTimelineHostLabel(node: ExecutionNodeViewModel) {
  return getNodeSubtitle(node.definition?.config || {}, node.execution?.input_data)
}

function goToWorkflowEditor() {
  if (!currentExecution.value) return
  router.push(`/workflows/${currentExecution.value.workflow_id}/edit`)
}

async function loadExecution(executionId: number, syncRoute = true) {
  loadingDetail.value = true
  const previousNodeId = rawNodeId.value
  try {
    selectedExecutionId.value = executionId
    const execution = await executionsStore.fetchExecution(executionId)
    await executionsStore.fetchNodeExecutions(execution.id)

    const nextNodes = executionNodeViewModels.value
    rawNodeId.value = nextNodes.some(node => node.nodeId === previousNodeId)
      ? previousNodeId
      : nextNodes[0]?.nodeId || null

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
    ? workflowNameMap.value.get(execution.workflow_id) || `工作流 #${execution.workflow_id}`
    : `执行 #${executionId}`

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
        <ElOption label="stopped" value="stopped" />
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
                <div class="execution-subtitle">执行 #{{ execution.id }}</div>
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
              <span>{{ execution.result || '无' }}</span>
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

          <div class="overview-layout">
            <div class="overview-main">
              <div class="overview-grid">
                <div class="metric-card">
                  <div class="metric-label">工作流</div>
                  <div class="metric-value">{{ workflowNameMap.get(currentExecution.workflow_id) || `工作流 #${currentExecution.workflow_id}` }}</div>
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
                <div class="metric-card">
                  <div class="metric-label">未执行节点</div>
                  <div class="metric-value">{{ notRunNodeCount }}</div>
                </div>
                <div class="metric-card">
                  <div class="metric-label">失败节点</div>
                  <div class="metric-value">{{ failedNodeCount }}</div>
                </div>
              </div>

              <div class="overview-time-grid">
                <div class="overview-info-card">
                  <div class="overview-info-label">创建时间</div>
                  <div class="overview-info-value">{{ formatDate(currentExecution.created_at) }}</div>
                </div>
                <div class="overview-info-card">
                  <div class="overview-info-label">开始时间</div>
                  <div class="overview-info-value">{{ formatDate(currentExecution.started_at) }}</div>
                </div>
                <div class="overview-info-card">
                  <div class="overview-info-label">结束时间</div>
                  <div class="overview-info-value">{{ formatDate(currentExecution.finished_at) }}</div>
                </div>
              </div>
            </div>

            <div class="overview-summary-card">
              <div class="overview-summary-header">
                <div>
                  <div class="overview-summary-title">执行摘要 JSON</div>
                  <div class="overview-summary-subtitle">summary</div>
                </div>
              </div>
              <pre class="overview-summary-pre">{{ stringifyData(executionSummaryDisplay) }}</pre>
            </div>
          </div>
        </ElCard>

        <div v-if="currentExecution" class="detail-grid">
          <ElCard class="panel" shadow="never">
            <template #header>
              <div class="panel-title">
                <span>工作流运行状态图</span>
                <ElTag type="info" effect="plain">{{ executionNodeViewModels.length }} 节点</ElTag>
              </div>
            </template>

            <div v-if="executionNodeViewModels.length === 0" class="panel-empty">
              <span class="empty-text">该执行没有工作流状态快照，请重新运行工作流生成状态图</span>
            </div>

            <div
              v-else
              class="workflow-status-canvas"
            >
              <div class="readonly-graph-inner" :style="readonlyGraphStyle">
                <div
                  v-for="phase in readonlyGraphLayout.phases"
                  :key="phase.key"
                  class="readonly-graph-phase"
                  :style="getGraphPhaseStyle(phase)"
                >
                  {{ phase.label }}
                </div>

                <svg
                  class="readonly-graph-svg"
                  :viewBox="readonlyGraphViewBox"
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <path
                    v-for="edge in readonlyGraphLayout.edges"
                    :key="edge.id"
                    class="readonly-graph-edge"
                    :class="`readonly-graph-edge-${getEdgeStatusClass(edge.status)}`"
                    :d="edge.path"
                  />
                </svg>

                <button
                  v-for="graphNode in readonlyGraphLayout.nodes"
                  :key="graphNode.node.nodeId"
                  type="button"
                  class="readonly-graph-node"
                  :class="[
                    `readonly-graph-node-${getNodeStatusClass(graphNode.node.status)}`,
                    { active: rawNodeId === graphNode.node.nodeId }
                  ]"
                  :style="getGraphNodeStyle(graphNode)"
                  @click="rawNodeId = graphNode.node.nodeId"
                >
                  <div class="readonly-node-top">
                    <span class="readonly-node-sequence">{{ graphNode.node.sequence }}</span>
                    <span class="readonly-node-status-dot" />
                    <span class="readonly-node-status">{{ getNodeStatusLabel(graphNode.node.status) }}</span>
                  </div>
                  <div class="readonly-node-title">{{ graphNode.node.label }}</div>
                  <div class="readonly-node-meta">{{ graphNode.hostLabel }}</div>
                </button>
              </div>
            </div>

            <div v-if="executionNodeViewModels.length > 0" class="timeline-board">
              <div class="timeline-header">
                <div class="timeline-heading-group">
                  <span class="timeline-heading">事件流</span>
                  <span class="timeline-subtitle">{{ completedNodeCount }} / {{ executionNodeViewModels.length }} 已结束</span>
                </div>
                <div class="timeline-progress" aria-label="节点进度">
                  <span class="timeline-progress-track">
                    <span class="timeline-progress-fill" :style="{ width: `${progressPercent}%` }" />
                  </span>
                  <span class="timeline-progress-text">{{ progressPercent }}%</span>
                </div>
              </div>

              <div class="timeline-list">
                <div
                  v-for="group in timelinePhaseGroups"
                  :key="group.phase"
                  class="timeline-phase-row"
                >
                  <div class="timeline-phase-label">阶段 {{ group.phase }}</div>
                  <div class="timeline-phase-nodes">
                    <button
                      v-for="node in group.nodes"
                      :key="node.nodeId"
                      type="button"
                      class="timeline-item"
                      :class="[
                        `status-${node.status}`,
                        { active: rawNodeId === node.nodeId, 'not-run': node.status === 'not-run' }
                      ]"
                      :title="`${node.sequence} ${node.label} · ${getTimelineHostLabel(node)}`"
                      @click="rawNodeId = node.nodeId"
                    >
                      <span class="timeline-dot" :class="node.status" />
                      <span class="timeline-sequence">{{ node.sequence }}</span>
                      <span class="timeline-title">{{ node.label }}</span>
                    </button>
                  </div>
                </div>
              </div>
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
                    :class="{ 'is-empty': !selectedNodeView }"
                  >
                    {{ selectedNodeView?.label || 'placeholder-node' }}
                  </ElTag>
                </div>
              </div>
            </template>

            <div v-if="!selectedNodeView" class="panel-empty">
              <span class="empty-text">选择左侧节点查看原始信息</span>
            </div>

            <template v-else>
              <div class="node-detail-grid">
                <div>
                  <div class="raw-label">节点</div>
                  <div class="detail-value">{{ selectedNodeView.label }}</div>
                </div>
                <div>
                  <div class="raw-label">类型</div>
                  <div class="detail-value">{{ selectedNodeView.nodeType }}</div>
                </div>
                <div>
                  <div class="raw-label">状态</div>
                  <ElTag :type="getStatusTone(selectedNodeView.status)" effect="plain">
                    {{ selectedNodeView.status }}
                  </ElTag>
                </div>
                <div>
                  <div class="raw-label">拓扑</div>
                  <div class="detail-value">{{ selectedNodeView.incomingCount }} 入 / {{ selectedNodeView.outgoingCount }} 出</div>
                </div>
              </div>

              <div class="raw-summary">
                <ElAlert
                  v-if="selectedNodeExecution?.error_message"
                  :title="selectedNodeExecution.error_message"
                  type="error"
                  :closable="false"
                  show-icon
                />
                <ElAlert
                  v-else-if="!selectedNodeExecution"
                  title="该节点还没有执行记录，通常表示执行尚未到达这里，或前序节点失败后工作流已停止。"
                  type="info"
                  :closable="false"
                  show-icon
                />
              </div>

              <details v-if="selectedNodeView.definition" class="raw-block raw-detail" open>
                <summary class="raw-detail-summary">工作流配置</summary>
                <pre class="raw-pre">{{ stringifyData(selectedNodeView.definition.config) }}</pre>
              </details>

              <details class="raw-block raw-detail" open>
                <summary class="raw-detail-summary">输入</summary>
                <pre class="raw-pre">{{ stringifyData(selectedNodeExecution?.input_data) }}</pre>
              </details>

              <details class="raw-block raw-detail" open>
                <summary class="raw-detail-summary">输出</summary>
                <pre class="raw-pre">{{ formatRawOutput(selectedNodeExecution?.output_data) }}</pre>
              </details>
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
.metric-label {
  color: #94a3b8;
  font-size: 10px;
}

.execution-row-meta {
  margin-top: 4px;
}

.overview-layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.72fr) minmax(460px, 1.28fr);
  gap: 10px;
}

.overview-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.overview-time-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.metric-card {
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #edf2f7;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.metric-value {
  margin-top: 2px;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-info-card {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  background: #fff;
}

.overview-info-label {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
}

.overview-info-value {
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-summary-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.overview-summary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #edf2f7;
  background: #f8fafc;
}

.overview-summary-title {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
}

.overview-summary-subtitle {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.2;
}

.overview-summary-pre {
  height: 154px;
  overflow: auto;
  margin: 0;
  padding: 10px 12px;
  background: #fff;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 10px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-label {
  margin-bottom: 4px;
  color: #64748b;
  font-size: 10px;
  font-weight: 600;
}

.node-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  border-radius: 6px;
  background: #f8fafc;
}

.detail-value {
  color: #1e293b;
  font-size: 12px;
  font-weight: 600;
  word-break: break-word;
}

.workflow-status-canvas {
  margin-bottom: 14px;
  overflow: auto;
  border-radius: 8px;
  border: 1px solid #dbe4ee;
  background:
    radial-gradient(circle at 1px 1px, rgba(148, 163, 184, 0.18) 1px, transparent 0) 0 0 / 14px 14px,
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.readonly-graph-inner {
  position: relative;
  margin: 0 auto;
}

.readonly-graph-phase {
  position: absolute;
  top: 18px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.88);
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.readonly-graph-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.readonly-graph-edge {
  fill: none;
  stroke: #cbd5e1;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.readonly-graph-edge-passed {
  stroke: #10b981;
}

.readonly-graph-edge-failed {
  stroke: #ef4444;
}

.readonly-graph-edge-running {
  stroke: #f59e0b;
  stroke-dasharray: 7 5;
}

.readonly-graph-edge-pending {
  stroke: #cbd5e1;
  stroke-dasharray: 5 5;
}

.readonly-graph-node {
  position: absolute;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 5px;
  padding: 9px 10px 8px;
  overflow: hidden;
  border: 1px solid #dbe4ee;
  border-left: 4px solid #94a3b8;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 7px 18px rgba(15, 23, 42, 0.08);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.readonly-graph-node:hover {
  border-color: #bfdbfe;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  transform: translateY(-1px);
}

.readonly-graph-node:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.2),
    0 10px 24px rgba(15, 23, 42, 0.12);
}

.readonly-graph-node.active {
  border-color: #93c5fd;
  background: #f8fbff;
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.16),
    0 12px 24px rgba(59, 130, 246, 0.14);
}

.readonly-graph-node-success {
  border-left-color: #10b981;
}

.readonly-graph-node-failed {
  border-color: #fecaca;
  border-left-color: #ef4444;
  background: #fffafa;
}

.readonly-graph-node-running {
  border-left-color: #f59e0b;
}

.readonly-graph-node-skipped,
.readonly-graph-node-not-run,
.readonly-graph-node-pending {
  border-left-color: #cbd5e1;
  background: rgba(248, 250, 252, 0.96);
}

.readonly-node-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.readonly-node-sequence {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 28px;
  height: 20px;
  padding: 0 6px;
  border-radius: 6px;
  background: #eef2f7;
  color: #334155;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.readonly-node-status-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
}

.readonly-graph-node-success .readonly-node-status-dot {
  background: #10b981;
}

.readonly-graph-node-failed .readonly-node-status-dot {
  background: #ef4444;
}

.readonly-graph-node-running .readonly-node-status-dot {
  background: #f59e0b;
}

.readonly-node-status {
  overflow: hidden;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readonly-node-title {
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readonly-node-meta {
  overflow: hidden;
  color: #64748b;
  font-size: 10px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readonly-node-error {
  overflow: hidden;
  padding-top: 1px;
  color: #dc2626;
  font-size: 10px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-board {
  padding: 10px;
  border: 1px solid #edf2f7;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.timeline-heading-group {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.timeline-heading {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
}

.timeline-subtitle {
  color: #64748b;
  font-size: 10px;
  white-space: nowrap;
}

.timeline-progress {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.timeline-progress-track {
  display: block;
  width: 84px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.timeline-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #10b981 0%, #3b82f6 100%);
  transition: width 0.2s ease;
}

.timeline-progress-text {
  color: #475569;
  font-size: 10px;
  font-weight: 700;
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.timeline-phase-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.timeline-phase-label {
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.timeline-phase-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.timeline-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 170px;
  min-height: 30px;
  padding: 0 9px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  background: #fff;
  color: #475569;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.timeline-item:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.timeline-item:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.18),
    0 4px 12px rgba(15, 23, 42, 0.06);
}

.timeline-item.active {
  background: #f8fbff;
  border-color: #bfdbfe;
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.14),
    0 4px 12px rgba(59, 130, 246, 0.08);
}

.timeline-sequence {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 26px;
  height: 20px;
  padding: 0 5px;
  border-radius: 6px;
  background: #eef2f7;
  color: #334155;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.timeline-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
}

.timeline-dot.success {
  background: #10b981;
}

.timeline-dot.failed {
  background: #ef4444;
}

.timeline-dot.running {
  background: #f59e0b;
}

.timeline-dot.not-run,
.timeline-dot.skipped {
  background: #cbd5e1;
}

.timeline-title {
  overflow: hidden;
  color: #334155;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.raw-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 420px;
}

.raw-block {
  display: flex;
  flex-direction: column;
}

.raw-detail {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  background: #fff;
}

.raw-detail-summary {
  padding: 9px 10px;
  color: #334155;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
}

.raw-detail-summary:hover {
  background: #f8fafc;
}

.raw-detail[open] .raw-detail-summary {
  border-bottom: 1px solid #edf2f7;
  background: #f8fafc;
}

.raw-pre {
  max-height: 200px;
  overflow: auto;
  margin: 0;
  padding: 10px;
  background: #fff;
  color: #475569;
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1200px) {
  .page-grid,
  .detail-grid,
  .overview-layout,
  .overview-grid,
  .overview-time-grid,
  .node-detail-grid {
    grid-template-columns: 1fr;
  }

  .overview-summary-pre {
    height: 150px;
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

  .overview-summary-header {
    flex-direction: column;
  }

  .timeline-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .timeline-heading-group {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }

  .timeline-progress {
    width: 100%;
  }

  .timeline-progress-track {
    flex: 1;
    width: auto;
  }

  .timeline-phase-row {
    grid-template-columns: 1fr;
    align-items: flex-start;
    gap: 6px;
  }

  .timeline-sequence {
    min-width: 28px;
    height: 24px;
    font-size: 10px;
  }
}
</style>
