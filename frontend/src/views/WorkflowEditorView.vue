<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

import {
  ElMessage,
  ElMessageBox
} from 'element-plus'
import NodePalette from '@/components/workflow/NodePalette.vue'
import EditorToolbar from '@/components/workflow/EditorToolbar.vue'
import WorkflowNode from '@/components/workflow/nodes/WorkflowNode.vue'
import { useWorkflowsStore } from '@/stores/workflows'
import type { NodeType } from '@/types'

const route = useRoute()
const router = useRouter()
const workflowsStore = useWorkflowsStore()

// Vue Flow instance
const {
  onConnect,
  onNodeDragStop,
  onPaneReady,
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

// Auto-save timer
let autoSaveTimer: ReturnType<typeof setInterval> | null = null

// Load workflow on mount
onMounted(async () => {
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
  fitView({ padding: 0.2 })
})

// Handle node click (selection)
const handleNodeClick = (nodeId: string) => {
  workflowsStore.selectNode(nodeId)
}

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
  } catch {
    ElMessage.error('Failed to save workflow')
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
  fitView({ padding: 0.2 })
}

// Handle run workflow
const handleRun = async () => {
  if (workflowId.value) {
    try {
      await ElMessageBox.confirm(
        'Are you sure you want to run this workflow?',
        'Run Workflow',
        {
          confirmButtonText: 'Run',
          cancelButtonText: 'Cancel',
          type: 'info'
        }
      )
      // TODO: Implement workflow execution (Phase2-9)
      ElMessage.info('Workflow execution will be implemented in Phase2-9')
    } catch {
      // User cancelled
    }
  }
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
          fit-view-on-init
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
              @click="handleNodeClick(nodeProps.id)"
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
    </div>
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
</style>