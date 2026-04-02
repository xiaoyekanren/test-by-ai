import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Workflow, WorkflowCreate, WorkflowUpdate, NodeType, FlowNode, FlowEdge } from '@/types'
import { NODE_CONFIGS } from '@/types'
import { workflowsApi } from '@/api'

// History state for undo/redo
interface HistoryState {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export const useWorkflowsStore = defineStore('workflows', () => {
  // Workflow list state
  const workflows = ref<Workflow[]>([])
  const currentWorkflow = ref<Workflow | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Editor state
  const editorNodes = ref<FlowNode[]>([])
  const editorEdges = ref<FlowEdge[]>([])
  const selectedNodeId = ref<string | null>(null)
  const isDirty = ref(false)
  const autoSave = ref(true)
  const isSaving = ref(false)

  // History for undo/redo
  const history = ref<HistoryState[]>([])
  const historyIndex = ref(-1)
  const maxHistorySize = 50

  // Computed properties for undo/redo
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)

  // Workflow list operations
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

  // Editor operations

  // Initialize editor with workflow data
  function initEditor(workflow: Workflow | null) {
    if (workflow) {
      // Convert workflow nodes to flow nodes
      editorNodes.value = workflow.nodes.map(n => ({
        id: n.id,
        type: 'workflowNode',
        position: n.position || { x: 0, y: 0 },
        data: {
          label: NODE_CONFIGS[n.type]?.label || n.type,
          nodeType: n.type,
          config: n.config
        }
      }))

      // Convert workflow edges to flow edges
      editorEdges.value = workflow.edges.map(e => ({
        id: `edge-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        label: e.label || undefined
      }))
    } else {
      // New workflow - start with empty canvas
      editorNodes.value = []
      editorEdges.value = []
    }

    // Reset history
    history.value = []
    historyIndex.value = -1
    saveHistory()
    isDirty.value = false
    selectedNodeId.value = null
  }

  // Save current state to history
  function saveHistory() {
    const currentState: HistoryState = {
      nodes: JSON.parse(JSON.stringify(editorNodes.value)),
      edges: JSON.parse(JSON.stringify(editorEdges.value))
    }

    // Remove any future states if we're not at the end
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    history.value.push(currentState)
    historyIndex.value = history.value.length - 1

    // Limit history size
    if (history.value.length > maxHistorySize) {
      history.value.shift()
      historyIndex.value--
    }

    isDirty.value = true
  }

  // Undo
  function undo() {
    if (canUndo.value) {
      historyIndex.value--
      const state = history.value[historyIndex.value]
      editorNodes.value = JSON.parse(JSON.stringify(state.nodes))
      editorEdges.value = JSON.parse(JSON.stringify(state.edges))
    }
  }

  // Redo
  function redo() {
    if (canRedo.value) {
      historyIndex.value++
      const state = history.value[historyIndex.value]
      editorNodes.value = JSON.parse(JSON.stringify(state.nodes))
      editorEdges.value = JSON.parse(JSON.stringify(state.edges))
    }
  }

  // Add node
  function addNode(nodeType: NodeType, position: { x: number; y: number }) {
    const id = `node-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const config = NODE_CONFIGS[nodeType]

    const newNode: FlowNode = {
      id,
      type: 'workflowNode',
      position,
      data: {
        label: config.label,
        nodeType,
        config: config.defaultConfig
      }
    }

    editorNodes.value.push(newNode)
    saveHistory()
    return newNode
  }

  // Update node position
  function updateNodePosition(nodeId: string, position: { x: number; y: number }) {
    const node = editorNodes.value.find(n => n.id === nodeId)
    if (node) {
      node.position = position
      isDirty.value = true
    }
  }

  // Update node config
  function updateNodeConfig(nodeId: string, config: Record<string, unknown>) {
    const node = editorNodes.value.find(n => n.id === nodeId)
    if (node) {
      node.data.config = { ...node.data.config, ...config }
      saveHistory()
    }
  }

  // Delete node
  function deleteNode(nodeId: string) {
    editorNodes.value = editorNodes.value.filter(n => n.id !== nodeId)
    editorEdges.value = editorEdges.value.filter(e => e.source !== nodeId && e.target !== nodeId)
    if (selectedNodeId.value === nodeId) {
      selectedNodeId.value = null
    }
    saveHistory()
  }

  // Add edge
  function addEdge(source: string, target: string, sourceHandle?: string, targetHandle?: string) {
    // Check if edge already exists
    const exists = editorEdges.value.some(
      e => e.source === source && e.target === target
    )
    if (exists) return null

    const id = `edge-${source}-${target}-${Date.now()}`
    const newEdge: FlowEdge = {
      id,
      source,
      target,
      sourceHandle,
      targetHandle,
      animated: true
    }

    editorEdges.value.push(newEdge)
    saveHistory()
    return newEdge
  }

  // Delete edge
  function deleteEdge(edgeId: string) {
    editorEdges.value = editorEdges.value.filter(e => e.id !== edgeId)
    saveHistory()
  }

  // Select node
  function selectNode(nodeId: string | null) {
    selectedNodeId.value = nodeId
  }

  // Get selected node
  const selectedNode = computed(() => {
    if (!selectedNodeId.value) return null
    return editorNodes.value.find(n => n.id === selectedNodeId.value)
  })

  // Save workflow to backend
  async function saveWorkflowToBackend(workflowId: number | null, name: string, description: string | null) {
    isSaving.value = true

    // Convert flow nodes to workflow nodes
    const nodes = editorNodes.value.map(n => ({
      id: n.id,
      type: n.data.nodeType,
      config: n.data.config,
      position: n.position
    }))

    // Convert flow edges to workflow edges
    const edges = editorEdges.value.map(e => ({
      from: e.source,
      to: e.target,
      label: e.label || null
    }))

    try {
      let workflow: Workflow
      if (workflowId) {
        workflow = await updateWorkflow(workflowId, {
          name,
          description,
          nodes,
          edges
        })
      } else {
        workflow = await createWorkflow({
          name,
          description,
          nodes,
          edges
        })
      }

      isDirty.value = false
      return workflow
    } catch (e) {
      throw e
    } finally {
      isSaving.value = false
    }
  }

  // Set auto save
  function setAutoSave(value: boolean) {
    autoSave.value = value
  }

  // Clear editor
  function clearEditor() {
    editorNodes.value = []
    editorEdges.value = []
    selectedNodeId.value = null
    history.value = []
    historyIndex.value = -1
    isDirty.value = false
  }

  return {
    // Workflow list state
    workflows,
    currentWorkflow,
    loading,
    error,

    // Editor state
    editorNodes,
    editorEdges,
    selectedNodeId,
    selectedNode,
    isDirty,
    autoSave,
    isSaving,
    canUndo,
    canRedo,

    // Workflow list operations
    fetchWorkflows,
    fetchWorkflow,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    clearCurrentWorkflow,

    // Editor operations
    initEditor,
    saveHistory,
    undo,
    redo,
    addNode,
    updateNodePosition,
    updateNodeConfig,
    deleteNode,
    addEdge,
    deleteEdge,
    selectNode,
    saveWorkflowToBackend,
    setAutoSave,
    clearEditor
  }
})