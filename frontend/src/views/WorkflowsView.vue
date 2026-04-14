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
import type { Execution, NodeExecution, Workflow } from '@/types'

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
  const completed = dialogNodeExecutions.value.filter(
    ne => ne.status === 'completed' || ne.status === 'failed' || ne.status === 'skipped'
  ).length
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
      if (execution.status === 'completed' || execution.status === 'failed') {
        stopExecutionPolling()
        if (execution.result === 'passed') {
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
        <ElButton
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
        <ElTableColumn label="Actions" width="160" align="center">
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
      title="Create Workflow"
      width="500px"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="createFormRef"
        :model="createForm"
        :rules="createFormRules"
        label-position="top"
        @submit.prevent="handleCreate"
      >
        <ElFormItem label="Name" prop="name">
          <ElInput
            v-model="createForm.name"
            placeholder="Enter workflow name"
            maxlength="100"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem label="Description" prop="description">
          <ElInput
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            placeholder="Enter workflow description (optional)"
            maxlength="500"
            show-word-limit
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createDialogVisible = false">Cancel</ElButton>
        <ElButton
          type="primary"
          @click="handleCreate"
          :loading="isCreating"
        >
          Create
        </ElButton>
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
      :title="`Execute: ${currentExecutionWorkflow?.name || ''}`"
      width="600px"
      :close-on-click-modal="false"
      @close="handleCloseExecutionDialog"
    >
      <div class="execution-content">
        <!-- Status Header -->
        <div class="execution-status-header">
          <div class="status-badge" :class="currentDialogExecution?.status || 'pending'">
            <ElIcon :class="{ 'is-loading': currentDialogExecution?.status === 'running' }">
              <component :is="currentDialogExecution?.status === 'completed' ? CircleCheck : currentDialogExecution?.status === 'failed' ? CircleClose : currentDialogExecution?.status === 'running' ? Loading : Clock" />
            </ElIcon>
            <span>{{ currentDialogExecution?.status || 'pending' }}</span>
          </div>
          <div class="execution-time">
            <ElIcon><Timer /></ElIcon>
            <span>{{ formatDuration(currentDialogExecution?.duration ?? null) }}</span>
          </div>
        </div>

        <!-- Progress -->
        <div class="execution-progress">
          <ElProgress
            :percentage="dialogExecutionProgress"
            :status="currentDialogExecution?.status === 'failed' ? 'exception' : currentDialogExecution?.status === 'completed' ? 'success' : undefined"
            :stroke-width="10"
          />
        </div>

        <!-- Node Executions -->
        <div class="node-executions-section">
          <h4>Node Executions</h4>
          <ElScrollbar class="node-executions-list">
            <div
              v-for="nodeExec in dialogNodeExecutions"
              :key="nodeExec.id"
              class="node-exec-item"
            >
              <div class="node-exec-info">
                <ElIcon
                  :class="{ 'is-loading': nodeExec.status === 'running' }"
                  :style="{ color: nodeExec.status === 'completed' ? '#67C23A' : nodeExec.status === 'failed' ? '#F56C6C' : '#909399' }"
                >
                  <component :is="nodeExec.status === 'completed' ? CircleCheck : nodeExec.status === 'failed' ? CircleClose : nodeExec.status === 'running' ? Loading : Clock" />
                </ElIcon>
                <span class="node-type">{{ nodeExec.node_type }}</span>
                <span class="node-id">{{ nodeExec.node_id.slice(0, 8) }}</span>
              </div>
              <div class="node-exec-meta">
                <span class="duration">{{ formatDuration(nodeExec.duration) }}</span>
                <ElTag
                  size="small"
                  :type="nodeExec.status === 'completed' ? 'success' : nodeExec.status === 'failed' ? 'danger' : 'info'"
                >
                  {{ nodeExec.status }}
                </ElTag>
              </div>
            </div>
          </ElScrollbar>
        </div>
      </div>

      <template #footer>
        <ElButton
          v-if="currentDialogExecution"
          @click="openExecutionInsights"
        >
          View Analysis
        </ElButton>
        <ElButton
          v-if="currentDialogExecution?.status === 'running' || currentDialogExecution?.status === 'pending'"
          type="danger"
          :icon="VideoPause"
          @click="handleStopExecution"
        >
          Stop
        </ElButton>
        <ElButton @click="handleCloseExecutionDialog">
          Close
        </ElButton>
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
</style>
