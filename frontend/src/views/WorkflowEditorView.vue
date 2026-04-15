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
import { NODE_CONFIGS } from '@/types'
import type { Execution, NodeExecution, NodeType } from '@/types'

const route = useRoute()
const router = useRouter()
const workflowsStore = useWorkflowsStore()

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

const selectedNodeTitle = computed(() => selectedNodeConfig.value?.label || 'Edit Node')
const selectedNodeCategory = computed(() => selectedNodeConfig.value?.category || '')
const selectedNodeDescription = computed(() => selectedNodeConfig.value?.description || '')
const selectedNodeColor = computed(() => selectedNodeConfig.value?.color || '#409eff')
const configDialogNodeOptions = computed(() => {
  return workflowsStore.editorNodes.map(node => {
    const config = NODE_CONFIGS[node.data.nodeType]
    return {
      value: node.id,
      label: node.data.label || config?.label || node.id,
      typeLabel: config?.label || node.data.nodeType,
      shortId: node.id.slice(0, 12)
    }
  })
})
const configDialogOtherNodeOptions = computed(() => {
  return configDialogNodeOptions.value.filter(option => option.value !== workflowsStore.selectedNodeId)
})
const fitViewOptions = { padding: 0.2, maxZoom: 2 }

const nodeExecutionStatusById = computed(() => {
  const statusById = new Map<string, 'running' | 'passed' | 'failed'>()

  editorNodeExecutions.value.forEach(nodeExecution => {
    if (nodeExecution.status === 'running') {
      statusById.set(nodeExecution.node_id, 'running')
    } else if (['completed', 'success', 'passed'].includes(nodeExecution.status)) {
      statusById.set(nodeExecution.node_id, 'passed')
    } else if (['failed', 'error'].includes(nodeExecution.status)) {
      statusById.set(nodeExecution.node_id, 'failed')
    }
  })

  return statusById
})

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
    ElMessage.success('Connection deleted')
    return
  }

  if (workflowsStore.selectedNodeId) {
    event.preventDefault()
    workflowsStore.deleteNode(workflowsStore.selectedNodeId)
    ElMessage.success('Node deleted')
  }
}

// Load workflow on mount
onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  if (workflowId.value) {
    try {
      const workflow = await workflowsStore.fetchWorkflow(workflowId.value)
      if (workflow) {
        workflowName.value = workflow.name
        workflowDescription.value = workflow.description || ''
        workflowsStore.initEditor(workflow)
      }
    } catch {
      ElMessage.error('Failed to load workflow')
      router.push('/workflows')
    }
  } else {
    // New workflow
    workflowName.value = 'New Workflow'
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

const handleConfigNodeSwitch = (nodeId: string) => {
  workflowsStore.selectNode(nodeId)
  nodeSwitcherDialogVisible.value = false
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

  ElMessage.success('Node added successfully')
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
      ElMessage.success('Workflow saved successfully')
    }
    return true
  } catch {
    ElMessage.error('Failed to save workflow')
    return false
  }
}

// Handle auto-save change
const handleAutoSaveChange = (value: boolean) => {
  workflowsStore.setAutoSave(value)
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
    // Check if workflow has unsaved changes
    if (workflowsStore.isDirty) {
      try {
        await ElMessageBox.confirm(
          'The workflow has unsaved changes. Please save before running.',
          'Unsaved Changes',
          {
            confirmButtonText: 'Save & Run',
            cancelButtonText: 'Cancel',
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
  ElMessage.success(`Execution #${execution.id} started`)
}

// Handle execution completed
const handleExecutionCompleted = (execution: Execution) => {
  if (execution.result === 'passed') {
    ElMessage.success('Workflow execution completed successfully')
  } else if (execution.result === 'failed') {
    ElMessage.error('Workflow execution failed')
  } else {
    ElMessage.info('Workflow execution completed with partial results')
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
      @save="handleSave"
      @auto-save-change="handleAutoSaveChange"
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
              @click="handleNodeClick(nodeProps.id)"
              @dblclick="handleNodeDoubleClick(nodeProps.id)"
              @execution-status-dblclick="handleExecutionStatusDblclick"
            />
          </template>
        </VueFlow>

        <!-- Empty state -->
        <div v-if="workflowsStore.editorNodes.length === 0" class="empty-canvas">
          <div class="empty-message">
            <p>Drag nodes from the palette to start building your workflow</p>
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
            <div class="config-dialog-meta-enhanced">{{ selectedNodeCategory || 'Workflow Node' }}</div>
            <div class="config-dialog-title-enhanced">{{ selectedNodeTitle }}</div>
            <div v-if="selectedNodeDescription" class="config-dialog-description-enhanced">
              {{ selectedNodeDescription }}
            </div>
          </div>
          <ElButton
            v-if="configDialogOtherNodeOptions.length > 0"
            class="config-dialog-switch-button"
            :icon="Switch"
            circle
            title="切换其他卡片"
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
      width="420px"
      top="16vh"
      append-to-body
      class="node-switch-dialog"
      title="切换卡片"
    >
      <div class="node-switch-dialog-body">
        <div class="node-switch-dialog-hint">选择要编辑的其他卡片</div>
        <ElScrollbar class="node-switch-list">
          <button
            v-for="option in configDialogOtherNodeOptions"
            :key="option.value"
            class="node-switch-card"
            type="button"
            @click="handleConfigNodeSwitch(option.value)"
          >
            <span class="node-switch-card-title">{{ option.label }}</span>
            <span class="node-switch-card-meta">{{ option.typeLabel }} · {{ option.shortId }}</span>
          </button>
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
  top: 16px;
  right: 48px;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: #475569;
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
  max-height: min(52vh, 420px);
}

.node-switch-card {
  width: 100%;
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.node-switch-card:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.node-switch-card-title {
  max-width: 100%;
  overflow: hidden;
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-switch-card-meta {
  max-width: 100%;
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
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
}
</style>
