<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

import {
  ElButton,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElScrollbar
} from 'element-plus'
import { Switch } from '@element-plus/icons-vue'
import NodePalette from '@/components/workflow/NodePalette.vue'
import EditorToolbar from '@/components/workflow/EditorToolbar.vue'
import WorkflowNode from '@/components/workflow/nodes/WorkflowNode.vue'
import NodeConfigPanel from '@/components/workflow/NodeConfigPanel.vue'
import ExecutionPanel from '@/components/workflow/ExecutionPanel.vue'
import { useWorkflowsStore } from '@/stores/workflows'
import { useServersStore } from '@/stores/servers'
import { useServerValidation } from '@/composables/useServerValidation'
import { NODE_CONFIGS, REGION_OPTIONS } from '@/types'
import type { Execution, FlowNode, NodeExecution, NodeType } from '@/types'

const route = useRoute()
const router = useRouter()
const workflowsStore = useWorkflowsStore()
const serversStore = useServersStore()
const { isMissingServerId } = useServerValidation()

// Vue Flow instance
const {
  onConnect,
  onEdgeClick,
  onNodeDragStop,
  onPaneReady,
  onPaneClick,
  fitView,
  zoomIn,
  zoomOut,
  project
} = useVueFlow()

// Route params
const workflowId = computed(() => {
  const id = route.params.id
  return id ? Number(id) : null
})

// Workflow name and description
const workflowName = ref('')
const workflowDescription = ref('')
const isNewWorkflow = computed(() => !workflowId.value)

// Drag state
const isDragging = ref(false)
const draggedType = ref<NodeType | null>(null)

// Execution panel state
const showExecutionPanel = ref(false)
const executionRunRequestId = ref(0)
const executionPanelRef = ref<InstanceType<typeof ExecutionPanel> | null>(null)
const editorNodeExecutions = ref<NodeExecution[]>([])
const configDialogVisible = ref(false)
const nodeSwitcherDialogVisible = ref(false)

const selectedNodeConfig = computed(() => {
  const nodeType = workflowsStore.selectedNode?.data.nodeType
  return nodeType ? NODE_CONFIGS[nodeType] : null
})

const selectedNodeTitle = computed(() => selectedNodeConfig.value?.label || '编辑节点')
const selectedNodeCategory = computed(() => selectedNodeConfig.value?.category || '')
const selectedNodeDescription = computed(() => selectedNodeConfig.value?.description || '')
const selectedNodeColor = computed(() => selectedNodeConfig.value?.color || '#409eff')
const nodeCategoryLabels = {
  basic: '基础节点',
  iotdb: 'IoTDB 节点',
  control: '控制节点',
  result: '结果节点'
} as const
const nodeCategoryOrder = ['basic', 'iotdb', 'control', 'result'] as const

// 所有支持的卡片类型选项（用于卡片类型浏览）
const allNodeTypeOptions = computed(() => {
  return Object.values(NODE_CONFIGS).map(config => ({
    value: config.type,
    label: config.label,
    typeLabel: config.label,
    category: config.category,
    categoryLabel: nodeCategoryLabels[config.category],
    color: config.color,
    iconSymbol: config.label.charAt(0).toUpperCase()
  }))
})

// 所有卡片类型按类别分组
const allNodeTypeGroups = computed(() => {
  const groups = new Map<string, {
    categoryLabel: string
    color: string
    options: typeof allNodeTypeOptions.value
  }>()

  allNodeTypeOptions.value.forEach(option => {
    if (!groups.has(option.category)) {
      groups.set(option.category, {
        categoryLabel: option.categoryLabel,
        color: option.color,
        options: []
      })
    }
    groups.get(option.category)?.options.push(option)
  })

  return nodeCategoryOrder
    .map(category => groups.get(category))
    .filter((group): group is NonNullable<typeof group> => Boolean(group))
})
const fitViewOptions = { padding: 0.2, maxZoom: 2 }

const nodeExecutionStatusById = computed(() => {
  const statusById = new Map<string, 'running' | 'passed' | 'failed'>()

  editorNodeExecutions.value.forEach(nodeExecution => {
    if (nodeExecution.status === 'running') {
      statusById.set(nodeExecution.node_id, 'running')
    } else if (nodeExecution.status === 'success') {
      statusById.set(nodeExecution.node_id, 'passed')
    } else if (nodeExecution.status === 'failed') {
      statusById.set(nodeExecution.node_id, 'failed')
    }
  })

  return statusById
})

const getNodeMissingServerIds = (node: FlowNode) => {
  const config = node.data.config || {}
  const ids = new Set<number>()

  if (isMissingServerId(config.server_id)) {
    ids.add(Number(config.server_id))
  }

  for (const field of ['config_nodes', 'data_nodes']) {
    const nodes = config[field]
    if (!Array.isArray(nodes)) continue
    for (const item of nodes) {
      if (
        item &&
        typeof item === 'object' &&
        'server_id' in item &&
        isMissingServerId(item.server_id)
      ) {
        ids.add(Number(item.server_id))
      }
    }
  }

  return [...ids]
}

const nodeTypesRequiringServer = new Set<NodeType>([
  'shell', 'upload', 'download', 'config', 'log_view',
  'iotdb_deploy', 'iotdb_start', 'iotdb_stop', 'iotdb_cli',
  'iotdb_config', 'iot_benchmark_deploy', 'iot_benchmark_start', 'iot_benchmark_wait'
])

const hasConfigValue = (value: unknown) => value !== null && value !== undefined && value !== ''

const getNodeScheduleError = (node: FlowNode) => {
  const config = node.data.config || {}

  if (workflowsStore.scheduleMode === 'random') {
    if (hasConfigValue(config.server_id)) {
      return '随机调度模式下不能选择固定服务器'
    }
    for (const field of ['config_nodes', 'data_nodes']) {
      const nodes = config[field]
      if (!Array.isArray(nodes)) continue
      if (nodes.some(item => typeof item === 'object' && item !== null && hasConfigValue(item.server_id))) {
        return '随机调度模式下集群节点不能选择固定服务器'
      }
    }
    return ''
  }

  if (nodeTypesRequiringServer.has(node.data.nodeType) && !hasConfigValue(config.server_id)) {
    return '固定主机模式下必须选择服务器'
  }

  for (const field of ['config_nodes', 'data_nodes']) {
    const nodes = config[field]
    if (!Array.isArray(nodes)) continue
    if (nodes.some(item => typeof item === 'object' && item !== null && !hasConfigValue(item.server_id))) {
      return '固定主机模式下集群节点必须选择服务器'
    }
  }

  return ''
}

const nodeValidationErrorsById = computed(() => {
  const errors = new Map<string, string>()
  for (const node of workflowsStore.editorNodes) {
    const scheduleError = getNodeScheduleError(node)
    if (scheduleError) {
      errors.set(node.id, scheduleError)
      continue
    }
    const missingServerIds = getNodeMissingServerIds(node)
    if (missingServerIds.length > 0) {
      errors.set(node.id, `缺少服务器 #${missingServerIds.join(', #')}`)
    }
  }
  return errors
})

const workflowValidationErrors = computed(() => {
  return [...nodeValidationErrorsById.value.entries()].map(([nodeId, message]) => {
    const node = workflowsStore.editorNodes.find(item => item.id === nodeId)
    return `${node?.data.label || nodeId}: ${message}`
  })
})

const canRunWorkflow = computed(() => workflowValidationErrors.value.length === 0)
const runBlockedReason = computed(() => workflowValidationErrors.value[0] || '')

// Auto-save timer
let autoSaveTimer: ReturnType<typeof setInterval> | null = null

const isEditableElement = (target: EventTarget | null) => {
  if (!(target instanceof HTMLElement)) return false
  const tagName = target.tagName.toLowerCase()
  return (
    tagName === 'input' ||
    tagName === 'textarea' ||
    target.isContentEditable ||
    Boolean(target.closest('.el-input')) ||
    Boolean(target.closest('.el-textarea'))
  )
}

const handleKeydown = (event: KeyboardEvent) => {
  if (configDialogVisible.value) {
    return
  }

  if ((event.key !== 'Delete' && event.key !== 'Backspace') || isEditableElement(event.target)) {
    return
  }

  if (workflowsStore.selectedEdgeId) {
    event.preventDefault()
    workflowsStore.deleteEdge(workflowsStore.selectedEdgeId)
    ElMessage.success('连线已删除')
    return
  }

  if (workflowsStore.selectedNodeId) {
    event.preventDefault()
    workflowsStore.deleteNode(workflowsStore.selectedNodeId)
    ElMessage.success('节点已删除')
  }
}

// Load workflow on mount
onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  if (serversStore.servers.length === 0) {
    try {
      await serversStore.fetchServers()
    } catch {
      ElMessage.error('加载服务器列表失败')
    }
  }
  if (workflowId.value) {
    try {
      const workflow = await workflowsStore.fetchWorkflow(workflowId.value)
      if (workflow) {
        workflowName.value = workflow.name
        workflowDescription.value = workflow.description || ''
        workflowsStore.initEditor(workflow)
      }
    } catch {
      ElMessage.error('加载工作流失败')
      router.push('/workflows')
    }
  } else {
    // New workflow
    workflowName.value = '新建工作流'
    workflowDescription.value = ''
    workflowsStore.initEditor(null)
  }
})

// Cleanup on unmount
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer)
  }
  workflowsStore.clearEditor()
})

// Watch for auto-save changes
watch(
  () => workflowsStore.autoSave,
  (enabled) => {
    if (enabled) {
      // Start auto-save timer (save every 30 seconds if dirty)
      autoSaveTimer = setInterval(async () => {
        if (workflowsStore.isDirty && !workflowsStore.isSaving) {
          await handleSave(true)
        }
      }, 30000)
    } else {
      if (autoSaveTimer) {
        clearInterval(autoSaveTimer)
        autoSaveTimer = null
      }
    }
  },
  { immediate: true }
)

// Vue Flow event handlers

// Handle connection (edge creation)
onConnect((params) => {
  const { source, target, sourceHandle, targetHandle } = params
  workflowsStore.addEdge(
    source,
    target,
    sourceHandle || undefined,
    targetHandle || undefined
  )
})

// Handle node drag stop (position update)
onNodeDragStop((event) => {
  const node = event.node
  workflowsStore.updateNodePosition(node.id, node.position)
  workflowsStore.saveHistory()
})

// Handle pane ready (fit view on init)
onPaneReady(() => {
  fitView(fitViewOptions)
})

// Handle pane click (deselect node)
onPaneClick(() => {
  if (configDialogVisible.value) {
    return
  }
  workflowsStore.selectNode(null)
  workflowsStore.selectEdge(null)
})

// Handle node click (selection)
const handleNodeClick = (nodeId: string) => {
  workflowsStore.selectNode(nodeId)
}

// Handle node double click (configuration)
const handleNodeDoubleClick = (nodeId: string) => {
  workflowsStore.selectNode(nodeId)
  configDialogVisible.value = true
}

const handleConfigDialogClosed = () => {
  configDialogVisible.value = false
  nodeSwitcherDialogVisible.value = false
}

// 点击卡片类型后的处理 - 替换当前节点的类型
const handleNodeTypeClick = (nodeType: string) => {
  if (!workflowsStore.selectedNodeId) return

  const newNodeType = nodeType as NodeType
  const currentNodeType = workflowsStore.selectedNode?.data.nodeType

  if (currentNodeType === newNodeType) {
    // 类型相同，直接关闭弹窗
    nodeSwitcherDialogVisible.value = false
    return
  }

  // 替换节点类型
  workflowsStore.replaceNodeType(workflowsStore.selectedNodeId, newNodeType)
  nodeSwitcherDialogVisible.value = false
  ElMessage.success(`已替换为「${NODE_CONFIGS[newNodeType]?.label || nodeType}」`)
}

// Handle edge click (selection)
onEdgeClick(({ event, edge }) => {
  event.preventDefault()
  event.stopPropagation()
  workflowsStore.selectEdge(edge.id)
})

// Handle drag start from palette
const handleDragStart = (nodeType: NodeType) => {
  isDragging.value = true
  draggedType.value = nodeType
}

// Handle drop on canvas
const handleDrop = (event: DragEvent) => {
  if (!draggedType.value) return

  // Get drop position relative to the flow container
  const bounds = event.currentTarget as HTMLElement
  const rect = bounds.getBoundingClientRect()

  // Calculate position in Vue Flow coordinates
  const position = project({
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  })

  // Add node at the drop position
  workflowsStore.addNode(draggedType.value, position)

  isDragging.value = false
  draggedType.value = null

  ElMessage.success('节点已添加')
}

// Handle drag over (prevent default to allow drop)
const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

// Toolbar actions

// Handle save
const handleSave = async (silent = false) => {
  try {
    const workflow = await workflowsStore.saveWorkflowToBackend(
      workflowId.value,
      workflowName.value,
      workflowDescription.value
    )

    if (isNewWorkflow.value && workflow.id) {
      // Navigate to the edit route for the new workflow
      router.replace(`/workflows/${workflow.id}/edit`)
    }

    if (!silent) {
      ElMessage.success('工作流已保存')
    }
    return true
  } catch {
    ElMessage.error('保存工作流失败')
    return false
  }
}

// Handle auto-save change
const handleAutoSaveChange = (value: boolean) => {
  workflowsStore.setAutoSave(value)
}

const handleScheduleModeChange = (value: 'fixed' | 'random') => {
  workflowsStore.setScheduleMode(value)
}

const handleScheduleRegionChange = (value: string) => {
  workflowsStore.setScheduleRegion(value)
}

// Handle undo
const handleUndo = () => {
  workflowsStore.undo()
}

// Handle redo
const handleRedo = () => {
  workflowsStore.redo()
}

// Handle zoom in
const handleZoomIn = () => {
  zoomIn()
}

// Handle zoom out
const handleZoomOut = () => {
  zoomOut()
}

// Handle fit view
const handleFitView = () => {
  fitView(fitViewOptions)
}

// Handle run workflow
const handleRun = async () => {
  if (workflowId.value) {
    if (workflowValidationErrors.value.length > 0) {
      const firstInvalidNodeId = nodeValidationErrorsById.value.keys().next().value
      if (firstInvalidNodeId) {
        workflowsStore.selectNode(firstInvalidNodeId)
      }
      ElMessage.error(`无法运行工作流：${workflowValidationErrors.value[0]}`)
      return
    }

    // Check if workflow has unsaved changes
    if (workflowsStore.isDirty) {
      try {
        await ElMessageBox.confirm(
          '工作流有未保存的修改，请先保存再运行。',
          '未保存的修改',
          {
            confirmButtonText: '保存并运行',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        // Save first then run
        const saved = await handleSave(false)
        if (!saved) return
      } catch {
        return
      }
    }
    // Ask the panel to start a run as soon as it opens.
    executionRunRequestId.value += 1
    showExecutionPanel.value = true
  }
}

// Handle execution started
const handleExecutionStarted = (execution: Execution) => {
  ElMessage.success(`执行 #${execution.id} 已启动`)
}

// Handle execution completed
const handleExecutionCompleted = (execution: Execution) => {
  if (execution.result === 'passed') {
    ElMessage.success('工作流执行成功')
  } else if (execution.result === 'failed') {
    ElMessage.error('工作流执行失败')
  } else {
    ElMessage.info('工作流执行完成，部分结果异常')
  }
}

const handleNodeExecutionsUpdated = (nodeExecutions: NodeExecution[]) => {
  editorNodeExecutions.value = nodeExecutions
}

const handleExecutionCleared = () => {
  editorNodeExecutions.value = []
}

const handleExecutionStatusDblclick = async (nodeId: string) => {
  showExecutionPanel.value = true
  await nextTick()
  executionPanelRef.value?.openLogsForNode(nodeId)
}
</script>

<template>
  <div class="workflow-editor">
    <!-- Toolbar -->
    <EditorToolbar
      :workflow-id="workflowId"
      :workflow-name="workflowName"
      :is-saving="workflowsStore.isSaving"
      :is-dirty="workflowsStore.isDirty"
      :auto-save="workflowsStore.autoSave"
      :can-undo="workflowsStore.canUndo"
      :can-redo="workflowsStore.canRedo"
      :can-run="canRunWorkflow"
      :run-blocked-reason="runBlockedReason"
      :schedule-mode="workflowsStore.scheduleMode"
      :schedule-region="workflowsStore.scheduleRegion"
      :region-options="REGION_OPTIONS"
      @save="handleSave"
      @auto-save-change="handleAutoSaveChange"
      @schedule-mode-change="handleScheduleModeChange"
      @schedule-region-change="handleScheduleRegionChange"
      @undo="handleUndo"
      @redo="handleRedo"
      @zoom-in="handleZoomIn"
      @zoom-out="handleZoomOut"
      @fit-view="handleFitView"
      @run="handleRun"
    />

    <!-- Main Editor Area -->
    <div class="editor-main">
      <!-- Node Palette -->
      <NodePalette @dragstart="handleDragStart" />

      <!-- Flow Canvas -->
      <div
        class="flow-canvas"
        @drop="handleDrop"
        @dragover="handleDragOver"
      >
        <VueFlow
          v-model:nodes="workflowsStore.editorNodes"
          v-model:edges="workflowsStore.editorEdges"
          :edges-selectable="true"
          :min-zoom="0.2"
          :max-zoom="4"
          snap-to-grid
          :snap-grid="[15, 15]"
          class="vue-flow-container"
        >
          <Background pattern-color="#aaa" :gap="20" />
          <Controls position="bottom-left" />

          <!-- Custom node template with click handling -->
          <template #node-workflowNode="nodeProps">
            <WorkflowNode
              :id="nodeProps.id"
              :data="nodeProps.data"
              :selected="nodeProps.selected"
              :execution-status="nodeExecutionStatusById.get(nodeProps.id) || null"
              :validation-error="nodeValidationErrorsById.get(nodeProps.id) || null"
              @click="handleNodeClick(nodeProps.id)"
              @dblclick="handleNodeDoubleClick(nodeProps.id)"
              @execution-status-dblclick="handleExecutionStatusDblclick"
            />
          </template>
        </VueFlow>

        <!-- Empty state -->
        <div v-if="workflowsStore.editorNodes.length === 0" class="empty-canvas">
          <div class="empty-message">
            <p>从左侧面板拖拽节点到画布开始编排工作流</p>
          </div>
        </div>
      </div>

      <!-- Execution Panel (right side, toggleable) -->
      <ExecutionPanel
        v-if="showExecutionPanel"
        ref="executionPanelRef"
        :workflow-id="workflowId"
        :run-request-id="executionRunRequestId"
        @execution-started="handleExecutionStarted"
        @execution-completed="handleExecutionCompleted"
        @execution-cleared="handleExecutionCleared"
        @node-executions-updated="handleNodeExecutionsUpdated"
      />
    </div>

    <ElDialog
      v-model="configDialogVisible"
      width="860px"
      top="8vh"
      append-to-body
      destroy-on-close
      :close-on-click-modal="true"
      :close-on-press-escape="false"
      @closed="handleConfigDialogClosed"
      class="config-dialog-enhanced"
    >
      <template #header>
        <div class="config-dialog-header-enhanced" :style="{ '--node-color': selectedNodeColor }">
          <div class="config-dialog-accent-enhanced"></div>
          <div class="config-dialog-icon-wrapper">
            <div class="config-dialog-icon" :style="{ background: selectedNodeColor }">
              <span class="icon-symbol">{{ selectedNodeCategory?.charAt(0)?.toUpperCase() || 'N' }}</span>
            </div>
          </div>
          <div class="config-dialog-title-block-enhanced">
            <div class="config-dialog-meta-enhanced">{{ selectedNodeCategory || '工作流节点' }}</div>
            <div class="config-dialog-title-enhanced">{{ selectedNodeTitle }}</div>
            <div v-if="selectedNodeDescription" class="config-dialog-description-enhanced">
              {{ selectedNodeDescription }}
            </div>
          </div>
          <ElButton
            class="config-dialog-switch-button"
            :icon="Switch"
            circle
            title="查看全部卡片类型"
            @click="nodeSwitcherDialogVisible = true"
          />
        </div>
      </template>
      <NodeConfigPanel />
      <template #footer>
        <div class="config-dialog-footer-enhanced">
          <span class="footer-hint">
            <ElIcon><span class="hint-icon">💡</span></ElIcon>
            点击弹窗外区域保存并关闭
          </span>
        </div>
      </template>
    </ElDialog>

    <ElDialog
      v-model="nodeSwitcherDialogVisible"
      width="680px"
      top="16vh"
      append-to-body
      class="node-switch-dialog"
      title="卡片类型"
    >
      <div class="node-switch-dialog-body">
        <div class="node-switch-dialog-hint">全部支持的卡片类型（共 {{ allNodeTypeOptions.length }} 种）</div>
        <ElScrollbar class="node-switch-list">
          <section
            v-for="group in allNodeTypeGroups"
            :key="group.categoryLabel"
            class="node-switch-group"
          >
            <div class="node-switch-group-title">
              <span class="node-switch-group-mark" :style="{ background: group.color }"></span>
              <span>{{ group.categoryLabel }}</span>
              <span class="node-switch-group-count">{{ group.options.length }}</span>
            </div>
            <div class="node-switch-grid">
              <button
                v-for="option in group.options"
                :key="option.value"
                class="node-switch-card"
                type="button"
                @click="handleNodeTypeClick(option.value)"
              >
                <span class="node-switch-card-icon" :style="{ background: option.color }">
                  {{ option.iconSymbol }}
                </span>
                <span class="node-switch-card-main">
                  <span class="node-switch-card-title">{{ option.label }}</span>
                  <span class="node-switch-card-meta">{{ option.typeLabel }}</span>
                </span>
              </button>
            </div>
          </section>
        </ElScrollbar>
      </div>
    </ElDialog>
  </div>
</template>

<style scoped>
.workflow-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.editor-main {
  flex: 1;
  display: flex;
  min-height: 0;
}

.flow-canvas {
  flex: 1;
  min-width: 0;
  position: relative;
  background: #fff;
}

.vue-flow-container {
  width: 100%;
  height: 100%;
}

.empty-canvas {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  pointer-events: none;
}

.empty-message {
  background: rgba(255, 255, 255, 0.9);
  padding: 24px 32px;
  border-radius: 8px;
  text-align: center;
  border: 1px dashed #dcdfe6;
}

.empty-message p {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.config-dialog-footer {
  color: #909399;
  font-size: 12px;
}

.config-dialog-footer-enhanced {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
}

.hint-icon {
  font-size: 14px;
}

:deep(.el-dialog) {
  max-width: calc(100vw - 32px);
  border-radius: 16px !important;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15) !important;
}

:deep(.el-dialog__header) {
  margin-right: 0;
  padding: 0;
  border-bottom: none;
}

:deep(.el-dialog__body) {
  padding: 0;
}

:deep(.el-dialog__footer) {
  padding: 0;
}

.config-dialog-header-enhanced {
  position: relative;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 24px 96px 24px 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  border-bottom: 1px solid #e2e8f0;
}

.config-dialog-accent-enhanced {
  width: 4px;
  height: 60px;
  background: linear-gradient(180deg, var(--node-color) 0%, color-mix(in srgb, var(--node-color) 70%, white) 100%);
  border-radius: 2px;
  flex-shrink: 0;
}

.config-dialog-icon-wrapper {
  display: flex;
  align-items: center;
}

.config-dialog-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: white;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.icon-symbol {
  font-size: 20px;
}

.config-dialog-title-block-enhanced {
  min-width: 0;
  flex: 1;
}

.config-dialog-meta-enhanced {
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-dialog-title-enhanced {
  color: #0f172a;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.35;
  margin-top: 4px;
}

.config-dialog-description-enhanced {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.config-dialog-switch-button {
  position: absolute;
  top: 20px;
  right: 52px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #475569;
  background: transparent;
  border: none;
}

.config-dialog-switch-button:hover {
  color: var(--node-color);
}

.node-switch-dialog :deep(.el-dialog) {
  border-radius: 8px !important;
}

.node-switch-dialog :deep(.el-dialog__body) {
  padding: 0 20px 20px;
}

.node-switch-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.node-switch-dialog-hint {
  color: #64748b;
  font-size: 12px;
}

.node-switch-list {
  height: min(58vh, 520px);
}

.node-switch-group {
  padding-right: 8px;
  margin-bottom: 18px;
}

.node-switch-group:last-child {
  margin-bottom: 0;
}

.node-switch-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.node-switch-group-mark {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex-shrink: 0;
}

.node-switch-group-count {
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  border-radius: 8px;
  background: #eef2f7;
  color: #64748b;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

.node-switch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.node-switch-card {
  width: 100%;
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.node-switch-card:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.node-switch-card-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  color: #fff;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
}

.node-switch-card-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.node-switch-card-title {
  max-width: 100%;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-switch-card-meta {
  max-width: 100%;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .config-dialog-header-enhanced {
    padding-right: 64px;
    flex-wrap: wrap;
  }

  .config-dialog-switch-button {
    top: 14px;
    right: 44px;
  }

  .node-switch-grid {
    grid-template-columns: 1fr;
  }
}
</style>
