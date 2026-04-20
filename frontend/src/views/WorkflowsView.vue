<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElCard,
  ElButton,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElMessage,
  ElEmpty,
  ElTag,
  ElTooltip,
  ElProgress,
  ElIcon,
  ElScrollbar
} from 'element-plus'
import {
  Refresh,
  Plus,
  Edit,
  Delete,
  CopyDocument,
  Download,
  Upload,
  VideoPlay,
  VideoPause,
  CircleCheck,
  CircleClose,
  Clock,
  Loading,
  Timer
} from '@element-plus/icons-vue'
import { executionsApi } from '@/api'
import { useWorkflowsStore } from '@/stores/workflows'
import { isNodeSuccess, isNodeFinished } from '@/utils/execution'
import type { EdgeDefinition, Execution, NodeDefinition, NodeExecution, Workflow, WorkflowCreate } from '@/types'

const router = useRouter()
const workflowsStore = useWorkflowsStore()

// Dialog state
const createDialogVisible = ref(false)
const createFormRef = ref()
const createForm = ref({
  name: '',
  description: ''
})
const createFormRules = {
  name: [
    { required: true, message: 'Please enter workflow name', trigger: 'blur' },
    { min: 1, max: 100, message: 'Name must be 1-100 characters', trigger: 'blur' }
  ]
}
const isCreating = ref(false)
const importInputRef = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)

interface WorkflowExportFile {
  format: 'test-by-ai.workflow'
  version: 1
  exported_at: string
  workflow: WorkflowCreate
}

// Rename dialog state
const renameDialogVisible = ref(false)
const renameFormRef = ref()
const renameWorkflowId = ref<number | null>(null)
const renameForm = ref({
  name: '',
  description: ''
})
const renameFormRules = createFormRules
const isRenaming = ref(false)

// Execution dialog state
const executionDialogVisible = ref(false)
const currentExecutionWorkflow = ref<Workflow | null>(null)
const currentDialogExecution = ref<Execution | null>(null)
const dialogNodeExecutions = ref<NodeExecution[]>([])
let executionPollTimer: ReturnType<typeof setInterval> | null = null

// Computed
const isEmpty = computed(() => workflowsStore.workflows.length === 0 && !workflowsStore.loading)
const dialogExecutionProgress = computed(() => {
  if (dialogNodeExecutions.value.length === 0) return 0
  const completed = dialogNodeExecutions.value.filter(ne => isNodeFinished(ne.status)).length
  return Math.round((completed / dialogNodeExecutions.value.length) * 100)
})

// Methods
const fetchWorkflows = async () => {
  try {
    await workflowsStore.fetchWorkflows()
  } catch (error) {
    ElMessage.error('Failed to load workflows')
  }
}

const handleRowClick = (row: Workflow) => {
  router.push(`/workflows/${row.id}/edit`)
}

const handleEdit = (row: Workflow) => {
  renameWorkflowId.value = row.id
  renameForm.value = {
    name: row.name,
    description: row.description || ''
  }
  renameDialogVisible.value = true
}

const handleDelete = async (row: Workflow) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete workflow "${row.name}"?`,
      'Delete Workflow',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
    await workflowsStore.deleteWorkflow(row.id)
    ElMessage.success('Workflow deleted successfully')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete workflow')
    }
  }
}

const handleDuplicate = async (row: Workflow) => {
  try {
    const newWorkflow = await workflowsStore.createWorkflow({
      name: `${row.name} (Copy)`,
      description: row.description,
      nodes: row.nodes,
      edges: row.edges,
      variables: row.variables
    })
    ElMessage.success('Workflow duplicated successfully')
    router.push(`/workflows/${newWorkflow.id}/edit`)
  } catch (error) {
    ElMessage.error('Failed to duplicate workflow')
  }
}

const buildExportFileName = (workflow: Workflow) => {
  return `workflow-${workflow.id}.json`
}

const workflowNameExists = (name: string) => {
  return workflowsStore.workflows.some(workflow => workflow.name === name)
}

const fitWorkflowName = (name: string, suffix = '') => {
  const fallback = 'Imported Workflow'
  const base = (name.trim() || fallback).slice(0, Math.max(1, 100 - suffix.length)).trim()
  return `${base || fallback.slice(0, Math.max(1, 100 - suffix.length))}${suffix}`
}

const createImportTimestamp = () => {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds())
  ].join('')
}

const getUniqueImportedWorkflowName = (name: string) => {
  const fittedName = fitWorkflowName(name)
  if (!workflowNameExists(fittedName)) {
    return fittedName
  }

  const timestamp = createImportTimestamp()
  const maxAttempts = 1000
  for (let index = 0; index < maxAttempts; index += 1) {
    const suffix = index === 0 ? `-${timestamp}` : `-${timestamp}-${index}`
    const candidate = fitWorkflowName(name, suffix)
    if (!workflowNameExists(candidate)) {
      return candidate
    }
  }
  return fitWorkflowName(name, `-${timestamp}-${Date.now()}`)
}

const handleExport = (row: Workflow) => {
  const payload: WorkflowExportFile = {
    format: 'test-by-ai.workflow',
    version: 1,
    exported_at: new Date().toISOString(),
    workflow: {
      name: row.name,
      description: row.description,
      nodes: row.nodes || [],
      edges: row.edges || [],
      variables: row.variables || {}
    }
  }

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = buildExportFileName(row)
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  ElMessage.success('工作流已导出')
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const isValidNodeDefinition = (value: unknown): value is NodeDefinition => {
  if (!isRecord(value)) return false
  return typeof value.id === 'string' && typeof value.type === 'string'
}

const isValidEdgeDefinition = (value: unknown): value is EdgeDefinition => {
  if (!isRecord(value)) return false
  return typeof value.from === 'string' && typeof value.to === 'string'
}

const normalizeImportedWorkflow = (value: unknown): WorkflowCreate => {
  const root = isRecord(value) && isRecord(value.workflow) ? value.workflow : value
  if (!isRecord(root)) {
    throw new Error('Invalid workflow file')
  }

  const name = typeof root.name === 'string' ? root.name.trim() : ''
  if (!name) {
    throw new Error('Workflow name is required')
  }

  const nodes = Array.isArray(root.nodes) ? root.nodes.filter(isValidNodeDefinition) : []
  const edges = Array.isArray(root.edges) ? root.edges.filter(isValidEdgeDefinition) : []
  const variables = isRecord(root.variables)
    ? Object.fromEntries(Object.entries(root.variables).map(([key, item]) => [key, String(item)]))
    : {}

  return {
    name,
    description: typeof root.description === 'string' ? root.description : null,
    nodes,
    edges,
    variables
  }
}

const openImportPicker = () => {
  importInputRef.value?.click()
}

const handleImport = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  try {
    isImporting.value = true
    const workflow = normalizeImportedWorkflow(JSON.parse(await file.text()))
    const importedName = getUniqueImportedWorkflowName(workflow.name)
    workflow.name = importedName
    const created = await workflowsStore.createWorkflow(workflow)
    ElMessage.success(`工作流已导入：${created.name}`)
    router.push(`/workflows/${created.id}/edit`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导入工作流失败')
  } finally {
    isImporting.value = false
  }
}

const openCreateDialog = () => {
  createForm.value = { name: '', description: '' }
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createFormRef.value) return

  try {
    await createFormRef.value.validate()
    isCreating.value = true
    const workflow = await workflowsStore.createWorkflow({
      name: createForm.value.name,
      description: createForm.value.description || null
    })
    createDialogVisible.value = false
    ElMessage.success('Workflow created successfully')
    router.push(`/workflows/${workflow.id}/edit`)
  } catch (error) {
    // Form validation error or API error
    if (error !== 'Validation failed') {
      ElMessage.error('Failed to create workflow')
    }
  } finally {
    isCreating.value = false
  }
}

const handleRename = async () => {
  if (!renameFormRef.value || !renameWorkflowId.value) return

  try {
    await renameFormRef.value.validate()
    isRenaming.value = true
    await workflowsStore.updateWorkflow(renameWorkflowId.value, {
      name: renameForm.value.name,
      description: renameForm.value.description || null
    })
    renameDialogVisible.value = false
    ElMessage.success('Workflow renamed successfully')
  } catch (error) {
    if (error !== 'Validation failed') {
      ElMessage.error('Failed to rename workflow')
    }
  } finally {
    isRenaming.value = false
  }
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

// Execute workflow
const handleExecute = async (row: Workflow) => {
  try {
    await ElMessageBox.confirm(
      `Start execution for workflow "${row.name}"?`,
      'Execute Workflow',
      {
        confirmButtonText: 'Execute',
        cancelButtonText: 'Cancel',
        type: 'info'
      }
    )

    // Create execution
    const execution = await executionsApi.create({
      workflow_id: row.id,
      trigger_type: 'manual'
    })

    // Show execution dialog
    currentDialogExecution.value = execution
    currentExecutionWorkflow.value = row
    executionDialogVisible.value = true

    // Fetch node executions
    dialogNodeExecutions.value = await executionsApi.getNodes(execution.id)

    // Start polling for updates
    startExecutionPolling(execution.id)

    ElMessage.success(`Execution #${execution.id} started`)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to start execution')
    }
  }
}

// Polling for execution updates
const startExecutionPolling = (executionId: number) => {
  stopExecutionPolling()
  executionPollTimer = setInterval(async () => {
    try {
      const execution = await executionsApi.get(executionId)
      currentDialogExecution.value = execution
      dialogNodeExecutions.value = await executionsApi.getNodes(executionId)

      // Stop polling if execution is finished
      if (execution.status === 'completed' || execution.status === 'failed' || execution.status === 'stopped') {
        stopExecutionPolling()
        if (execution.status === 'stopped') {
          ElMessage.info('Execution stopped')
        } else if (execution.result === 'passed') {
          ElMessage.success('Workflow execution completed successfully')
        } else {
          ElMessage.error('Workflow execution failed')
        }
      }
    } catch (error) {
      console.error('Polling error:', error)
      stopExecutionPolling()
    }
  }, 2000)
}

const stopExecutionPolling = () => {
  if (executionPollTimer) {
    clearInterval(executionPollTimer)
    executionPollTimer = null
  }
}

// Stop execution
const handleStopExecution = async () => {
  if (!currentDialogExecution.value) return

  try {
    currentDialogExecution.value = await executionsApi.stop(currentDialogExecution.value.id)
    dialogNodeExecutions.value = await executionsApi.getNodes(currentDialogExecution.value.id)
    stopExecutionPolling()
    ElMessage.info('Execution stopped')
  } catch (error) {
    ElMessage.error('Failed to stop execution')
  }
}

// Close execution dialog
const handleCloseExecutionDialog = () => {
  stopExecutionPolling()
  executionDialogVisible.value = false
  currentExecutionWorkflow.value = null
  currentDialogExecution.value = null
  dialogNodeExecutions.value = []
}

const openExecutionInsights = () => {
  if (!currentDialogExecution.value) return
  router.push(`/executions?executionId=${currentDialogExecution.value.id}`)
}

// Format duration helper
const formatDuration = (seconds: number | null): string => {
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

// Lifecycle
onMounted(() => {
  fetchWorkflows()
})

onUnmounted(() => {
  stopExecutionPolling()
})
</script>

<template>
  <div class="workflows-view">
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>⚙️ 工作流管理</h2>
        <span class="workflow-count">{{ workflowsStore.workflows.length }} 个</span>
        <span class="refresh-info">{{ workflowsStore.loading ? '加载中' : '点击行编辑' }}</span>
      </div>
      <div class="toolbar-actions">
        <input
          ref="importInputRef"
          class="import-input"
          type="file"
          accept="application/json,.json,.workflow.json"
          @change="handleImport"
        />
        <ElButton
          :icon="Upload"
          :loading="isImporting"
          size="small"
          @click="openImportPicker"
        >
          导入
        </ElButton>
        <ElButton
          class="refresh-action"
          @click="fetchWorkflows"
          :icon="Refresh"
          :loading="workflowsStore.loading"
          size="small"
        >
          刷新
        </ElButton>
        <ElButton type="primary" :icon="Plus" size="small" @click="openCreateDialog">
          新建工作流
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="workflows-card">
      <!-- Empty State -->
      <div v-if="isEmpty" class="empty-state">
        <ElEmpty description="暂无工作流">
          <ElButton type="primary" :icon="Plus" size="small" @click="openCreateDialog">
            创建第一个工作流
          </ElButton>
        </ElEmpty>
      </div>

      <!-- Workflow Table -->
      <ElTable
        v-else
        :data="workflowsStore.workflows"
        style="width: 100%"
        v-loading="workflowsStore.loading"
        @row-click="handleRowClick"
        class="workflow-table"
        stripe
        :fit="false"
        highlight-current-row
      >
        <ElTableColumn prop="name" label="Workflow" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="workflow-info">
              <ElTag type="info" size="small" class="workflow-type-tag">FLOW</ElTag>
              <span class="workflow-name">{{ row.name }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="description" label="Description" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="description">{{ row.description || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Nodes" width="90" align="center">
          <template #default="{ row }">
            <span class="node-count">
              {{ row.nodes?.length || 0 }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="Created At" width="180">
          <template #default="{ row }">
            <span class="created-at">{{ formatDate(row.created_at) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Actions" width="190" align="center">
          <template #default="{ row }">
            <div class="action-buttons" @click.stop>
              <ElTooltip content="Execute" placement="top">
                <ElButton
                  type="success"
                  :icon="VideoPlay"
                  size="small"
                  @click="handleExecute(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Rename" placement="top">
                <ElButton
                  type="primary"
                  :icon="Edit"
                  size="small"
                  @click="handleEdit(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Duplicate" placement="top">
                <ElButton
                  type="info"
                  :icon="CopyDocument"
                  size="small"
                  @click="handleDuplicate(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="导出" placement="top">
                <ElButton
                  type="info"
                  :icon="Download"
                  size="small"
                  @click="handleExport(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Delete" placement="top">
                <ElButton
                  type="danger"
                  :icon="Delete"
                  size="small"
                  @click="handleDelete(row)"
                  link
                />
              </ElTooltip>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- Create Workflow Dialog -->
    <ElDialog
      v-model="createDialogVisible"
      width="520px"
      :close-on-click-modal="false"
      class="enhanced-dialog"
    >
      <template #header>
        <div class="dialog-header-enhanced">
          <div class="dialog-header-accent"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon">
              <ElIcon :size="20"><Plus /></ElIcon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">新建工作流</h3>
              <p class="dialog-subtitle">创建一个新的工作流配置</p>
            </div>
          </div>
        </div>
      </template>
      <ElForm
        ref="createFormRef"
        :model="createForm"
        :rules="createFormRules"
        label-position="top"
        @submit.prevent="handleCreate"
        class="dialog-form-enhanced"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput
            v-model="createForm.name"
            placeholder="请输入工作流名称"
            maxlength="100"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="描述" prop="description">
          <ElInput
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入工作流描述（可选）"
            maxlength="500"
            show-word-limit
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton @click="createDialogVisible = false" class="btn-cancel">取消</ElButton>
          <ElButton
            type="primary"
            @click="handleCreate"
            :loading="isCreating"
            class="btn-primary"
          >
            <ElIcon><Plus /></ElIcon>
            创建
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- Rename Workflow Dialog -->
    <ElDialog
      v-model="renameDialogVisible"
      title="Rename Workflow"
      width="500px"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="renameFormRef"
        :model="renameForm"
        :rules="renameFormRules"
        label-position="top"
        @submit.prevent="handleRename"
      >
        <ElFormItem label="Name" prop="name">
          <ElInput
            v-model="renameForm.name"
            placeholder="Enter workflow name"
            maxlength="100"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="Description" prop="description">
          <ElInput
            v-model="renameForm.description"
            type="textarea"
            :rows="4"
            placeholder="Enter workflow description (optional)"
            maxlength="500"
            show-word-limit
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="renameDialogVisible = false">Cancel</ElButton>
        <ElButton
          type="primary"
          @click="handleRename"
          :loading="isRenaming"
        >
          Save
        </ElButton>
      </template>
    </ElDialog>

    <!-- Execution Dialog -->
    <ElDialog
      v-model="executionDialogVisible"
      width="640px"
      :close-on-click-modal="false"
      @close="handleCloseExecutionDialog"
      class="enhanced-dialog execution-dialog"
    >
      <template #header>
        <div class="dialog-header-enhanced execution-header">
          <div class="dialog-header-accent" :class="currentDialogExecution?.status || 'pending'"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon execution-icon">
              <ElIcon :size="20">
                <component :is="currentDialogExecution?.status === 'completed' ? CircleCheck : currentDialogExecution?.status === 'failed' ? CircleClose : currentDialogExecution?.status === 'stopped' ? VideoPause : currentDialogExecution?.status === 'running' ? Loading : Clock" />
              </ElIcon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">{{ currentExecutionWorkflow?.name || '工作流执行' }}</h3>
              <p class="dialog-subtitle">
                <ElTag size="small" effect="plain" class="execution-id-tag">#{{ currentDialogExecution?.id }}</ElTag>
                执行详情监控
              </p>
            </div>
          </div>
        </div>
      </template>
      <div class="execution-content-enhanced">
        <!-- Status Header -->
        <div class="execution-status-header-enhanced">
          <div class="status-badge-enhanced" :class="currentDialogExecution?.status || 'pending'">
            <ElIcon :class="{ 'is-loading': currentDialogExecution?.status === 'running' }">
              <component :is="currentDialogExecution?.status === 'completed' ? CircleCheck : currentDialogExecution?.status === 'failed' ? CircleClose : currentDialogExecution?.status === 'stopped' ? VideoPause : currentDialogExecution?.status === 'running' ? Loading : Clock" />
            </ElIcon>
            <span class="status-text">{{ currentDialogExecution?.status || 'pending' }}</span>
          </div>
          <div class="execution-time-enhanced">
            <ElIcon><Timer /></ElIcon>
            <span>{{ formatDuration(currentDialogExecution?.duration ?? null) }}</span>
          </div>
        </div>

        <!-- Progress -->
        <div class="execution-progress-enhanced">
          <div class="progress-label">
            <span>执行进度</span>
            <span class="progress-value">{{ dialogExecutionProgress }}%</span>
          </div>
          <ElProgress
            :percentage="dialogExecutionProgress"
            :status="currentDialogExecution?.status === 'failed' ? 'exception' : currentDialogExecution?.status === 'completed' ? 'success' : currentDialogExecution?.status === 'stopped' ? 'warning' : undefined"
            :stroke-width="8"
          />
        </div>

        <!-- Node Executions -->
        <div class="node-executions-section-enhanced">
          <div class="section-header">
            <h4>节点执行状态</h4>
            <span class="section-count">{{ dialogNodeExecutions.length }} 个节点</span>
          </div>
          <ElScrollbar class="node-executions-list-enhanced">
            <div
              v-for="nodeExec in dialogNodeExecutions"
              :key="nodeExec.id"
              class="node-exec-item-enhanced"
            >
              <div class="node-exec-info-enhanced">
                <div class="node-exec-icon" :class="nodeExec.status">
                  <ElIcon :class="{ 'is-loading': nodeExec.status === 'running' }">
                    <component :is="isNodeSuccess(nodeExec.status) ? CircleCheck : nodeExec.status === 'failed' ? CircleClose : nodeExec.status === 'running' ? Loading : Clock" />
                  </ElIcon>
                </div>
                <div class="node-exec-details">
                  <span class="node-type-enhanced">{{ nodeExec.node_type }}</span>
                  <span class="node-id-enhanced">{{ nodeExec.node_id.slice(0, 8) }}</span>
                </div>
              </div>
              <div class="node-exec-meta-enhanced">
                <span class="duration-enhanced">{{ formatDuration(nodeExec.duration) }}</span>
                <ElTag
                  size="small"
                  :type="isNodeSuccess(nodeExec.status) ? 'success' : nodeExec.status === 'failed' ? 'danger' : 'info'"
                  effect="plain"
                >
                  {{ nodeExec.status }}
                </ElTag>
              </div>
            </div>
          </ElScrollbar>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton
            v-if="currentDialogExecution"
            @click="openExecutionInsights"
            class="btn-secondary"
          >
            <ElIcon><Timer /></ElIcon>
            查看分析
          </ElButton>
          <ElButton
            v-if="currentDialogExecution?.status === 'running' || currentDialogExecution?.status === 'pending'"
            type="danger"
            :icon="VideoPause"
            @click="handleStopExecution"
            class="btn-danger"
          >
            停止执行
          </ElButton>
          <ElButton @click="handleCloseExecutionDialog" class="btn-cancel">
            关闭
          </ElButton>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.workflows-view {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.workflow-count {
  font-size: 10px;
  color: #3b82f6;
  background: #eff6ff;
  padding: 2px 6px;
  border-radius: 6px;
  font-weight: 500;
}

.refresh-info {
  font-size: 10px;
  color: #94a3b8;
  margin-left: 4px;
}

.toolbar-actions {
  display: flex;
  gap: 6px;
}

.import-input {
  display: none;
}

.refresh-action {
  order: 3;
}

.workflows-card {
  width: 100%;
  margin: 0;
}

.empty-state {
  padding: 32px 0;
}

.workflow-table {
  cursor: pointer;
}

.workflow-table :deep(.el-table__cell) {
  padding: 4px 0;
}

.workflow-table :deep(.el-table__header-cell) {
  padding: 4px 0;
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
}

.workflow-table :deep(.el-table__row) {
  cursor: pointer;
}

.workflow-table :deep(.el-table__row:hover) {
  background-color: var(--el-fill-color-light);
}

.workflow-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
}

.workflow-name {
  font-weight: 500;
  color: #1e293b;
  font-size: 12px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workflow-type-tag {
  flex: 0 0 auto;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

.description {
  color: #94a3b8;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.node-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 18px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #eff6ff;
  color: #3b82f6;
  font-size: 10px;
  font-weight: 500;
}

.created-at {
  font-size: 10px;
  color: #94a3b8;
}

.action-buttons {
  display: flex;
  gap: 6px;
  justify-content: center;
  align-items: center;
}

/* Execution Dialog Styles */
.execution-content {
  padding: 10px 0;
}

.execution-status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
}

.status-badge.pending {
  background: #f4f4f5;
  color: #909399;
}

.status-badge.running {
  background: #ecf5ff;
  color: #409EFF;
}

.status-badge.completed {
  background: #f0f9eb;
  color: #67C23A;
}

.status-badge.failed {
  background: #fef0f0;
  color: #F56C6C;
}

.status-badge.stopped {
  background: #fdf6ec;
  color: #E6A23C;
}

.status-badge .is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.execution-time {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
}

.execution-progress {
  margin-bottom: 20px;
}

.node-executions-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.node-executions-list {
  max-height: 300px;
}

.node-exec-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 8px;
}

.node-exec-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-type {
  font-weight: 500;
  color: #303133;
}

.node-id {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.node-exec-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.duration {
  font-size: 12px;
  color: #909399;
}

/* Enhanced Dialog Styles */
.dialog-header-enhanced {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  border-bottom: 1px solid #e2e8f0;
  margin: -20px -20px 0 -20px;
}

.dialog-header-accent {
  width: 4px;
  height: 48px;
  background: linear-gradient(180deg, #3b82f6 0%, #60a5fa 100%);
  border-radius: 2px;
  flex-shrink: 0;
}

.dialog-header-accent.completed {
  background: linear-gradient(180deg, #10b981 0%, #34d399 100%);
}

.dialog-header-accent.failed {
  background: linear-gradient(180deg, #ef4444 0%, #f87171 100%);
}

.dialog-header-accent.stopped {
  background: linear-gradient(180deg, #f59e0b 0%, #fbbf24 100%);
}

.dialog-header-accent.running {
  background: linear-gradient(180deg, #f59e0b 0%, #fbbf24 100%);
}

.dialog-header-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.dialog-header-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 10px;
  color: #3b82f6;
}

.execution-icon {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.dialog-header-text {
  flex: 1;
}

.dialog-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
}

.dialog-subtitle {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
}

.execution-id-tag {
  font-size: 10px;
  padding: 1px 6px;
}

.dialog-form-enhanced {
  padding: 8px 0;
}

.dialog-footer-enhanced {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 24px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  margin: 0 -20px -20px -20px;
}

.btn-cancel {
  background: #ffffff !important;
  border: 1px solid #dcdfe6 !important;
  color: #606266 !important;
}

.btn-primary {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
  border: none !important;
  color: #ffffff !important;
}

.btn-secondary {
  background: #ffffff !important;
  border: 1px solid #e2e8f0 !important;
  color: #64748b !important;
}

.btn-danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
  border: none !important;
}

/* Enhanced Execution Dialog */
.execution-content-enhanced {
  padding: 20px 24px;
}

.execution-status-header-enhanced {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.status-badge-enhanced {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
}

.status-badge-enhanced .is-loading {
  animation: spin 1s linear infinite;
}

.status-text {
  text-transform: capitalize;
}

.status-badge-enhanced.pending {
  background: linear-gradient(135deg, #f4f4f5 0%, #e4e7ed 100%);
  color: #909399;
}

.status-badge-enhanced.running {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.status-badge-enhanced.completed {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #059669;
}

.status-badge-enhanced.failed {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #dc2626;
}

.status-badge-enhanced.stopped {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #d97706;
}

.execution-time-enhanced {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.execution-progress-enhanced {
  margin-bottom: 24px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #64748b;
}

.progress-value {
  font-weight: 600;
  color: #1e293b;
}

.node-executions-section-enhanced {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  border-radius: 12px 12px 0 0;
}

.section-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.section-count {
  font-size: 11px;
  color: #64748b;
  padding: 2px 8px;
  background: #e2e8f0;
  border-radius: 6px;
}

.node-executions-list-enhanced {
  max-height: 280px;
  padding: 8px;
}

.node-exec-item-enhanced {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 8px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.node-exec-item-enhanced:last-child {
  margin-bottom: 0;
}

.node-exec-item-enhanced:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.node-exec-info-enhanced {
  display: flex;
  align-items: center;
  gap: 12px;
}

.node-exec-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 16px;
}

.node-exec-icon.success {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.node-exec-icon.failed {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.node-exec-icon.running {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.node-exec-icon.pending {
  background: rgba(100, 116, 139, 0.1);
  color: #64748b;
}

.node-exec-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-type-enhanced {
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
}

.node-id-enhanced {
  font-size: 11px;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', monospace;
}

.node-exec-meta-enhanced {
  display: flex;
  align-items: center;
  gap: 12px;
}

.duration-enhanced {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}
</style>
