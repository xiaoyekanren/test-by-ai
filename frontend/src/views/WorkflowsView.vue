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
import { useWorkflowsStore } from '@/stores/workflows'
import { useExecutionsStore } from '@/stores/executions'
import type { Workflow } from '@/types'

const router = useRouter()
const workflowsStore = useWorkflowsStore()
const executionsStore = useExecutionsStore()

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

// Execution dialog state
const executionDialogVisible = ref(false)
const currentExecutionWorkflow = ref<Workflow | null>(null)
let executionPollTimer: ReturnType<typeof setInterval> | null = null

// Computed
const isEmpty = computed(() => workflowsStore.workflows.length === 0 && !workflowsStore.loading)

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
  router.push(`/workflows/${row.id}/edit`)
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
    const execution = await executionsStore.createExecution({
      workflow_id: row.id,
      trigger_type: 'manual'
    })

    // Show execution dialog
    currentExecutionWorkflow.value = row
    executionDialogVisible.value = true

    // Fetch node executions
    await executionsStore.fetchNodeExecutions(execution.id)

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
      const execution = await executionsStore.fetchExecution(executionId)
      await executionsStore.fetchNodeExecutions(executionId)

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
  if (!executionsStore.currentExecution) return

  try {
    await executionsStore.stopExecution(executionsStore.currentExecution.id)
    stopExecutionPolling()
    ElMessage.info('Execution stopped')
  } catch (error) {
    ElMessage.error('Failed to stop execution')
  }
}

// Close execution dialog
const handleCloseExecutionDialog = () => {
  stopExecutionPolling()
  executionsStore.clearCurrentExecution()
  executionDialogVisible.value = false
  currentExecutionWorkflow.value = null
}

const openExecutionInsights = () => {
  if (!executionsStore.currentExecution) return
  router.push(`/executions?executionId=${executionsStore.currentExecution.id}`)
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
    <ElCard>
      <template #header>
        <div class="card-header">
          <span class="title">Workflows</span>
          <div class="toolbar">
            <ElTooltip content="Refresh" placement="top">
              <ElButton
                :icon="Refresh"
                circle
                @click="fetchWorkflows"
                :loading="workflowsStore.loading"
              />
            </ElTooltip>
            <ElButton @click="router.push('/workflows/new')">
              Create Blank
            </ElButton>
            <ElButton type="primary" :icon="Plus" @click="openCreateDialog">
              Create Workflow
            </ElButton>
          </div>
        </div>
      </template>

      <!-- Empty State -->
      <div v-if="isEmpty" class="empty-state">
        <ElEmpty description="No workflows yet">
          <ElButton type="primary" :icon="Plus" @click="openCreateDialog">
            Create your first workflow
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
        highlight-current-row
      >
        <ElTableColumn prop="name" label="Name" min-width="180">
          <template #default="{ row }">
            <span class="workflow-name">{{ row.name }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="description" label="Description" min-width="200">
          <template #default="{ row }">
            <span class="description">{{ row.description || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Nodes" width="100" align="center">
          <template #default="{ row }">
            <ElTag type="info" size="small">
              {{ row.nodes?.length || 0 }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="Created At" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="Actions" width="250" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons" @click.stop>
              <ElTooltip content="Execute" placement="top">
                <ElButton
                  type="success"
                  :icon="VideoPlay"
                  circle
                  size="small"
                  @click="handleExecute(row)"
                />
              </ElTooltip>
              <ElTooltip content="Edit" placement="top">
                <ElButton
                  type="primary"
                  :icon="Edit"
                  circle
                  size="small"
                  @click="handleEdit(row)"
                />
              </ElTooltip>
              <ElTooltip content="Duplicate" placement="top">
                <ElButton
                  type="info"
                  :icon="CopyDocument"
                  circle
                  size="small"
                  @click="handleDuplicate(row)"
                />
              </ElTooltip>
              <ElTooltip content="Delete" placement="top">
                <ElButton
                  type="danger"
                  :icon="Delete"
                  circle
                  size="small"
                  @click="handleDelete(row)"
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
          <div class="status-badge" :class="executionsStore.currentExecution?.status || 'pending'">
            <ElIcon :class="{ 'is-loading': executionsStore.currentExecution?.status === 'running' }">
              <component :is="executionsStore.currentExecution?.status === 'completed' ? CircleCheck : executionsStore.currentExecution?.status === 'failed' ? CircleClose : executionsStore.currentExecution?.status === 'running' ? Loading : Clock" />
            </ElIcon>
            <span>{{ executionsStore.currentExecution?.status || 'pending' }}</span>
          </div>
          <div class="execution-time">
            <ElIcon><Timer /></ElIcon>
            <span>{{ formatDuration(executionsStore.currentExecution?.duration ?? null) }}</span>
          </div>
        </div>

        <!-- Progress -->
        <div class="execution-progress">
          <ElProgress
            :percentage="Math.round((executionsStore.nodeExecutions.filter(ne => ne.status === 'completed' || ne.status === 'failed' || ne.status === 'skipped').length / Math.max(executionsStore.nodeExecutions.length, 1)) * 100)"
            :status="executionsStore.currentExecution?.status === 'failed' ? 'exception' : executionsStore.currentExecution?.status === 'completed' ? 'success' : undefined"
            :stroke-width="10"
          />
        </div>

        <!-- Node Executions -->
        <div class="node-executions-section">
          <h4>Node Executions</h4>
          <ElScrollbar class="node-executions-list">
            <div
              v-for="nodeExec in executionsStore.nodeExecutions"
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
          v-if="executionsStore.currentExecution"
          @click="openExecutionInsights"
        >
          View Analysis
        </ElButton>
        <ElButton
          v-if="executionsStore.currentExecution?.status === 'running' || executionsStore.currentExecution?.status === 'pending'"
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 18px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.empty-state {
  padding: 40px 0;
}

.workflow-table {
  cursor: pointer;
}

.workflow-table :deep(.el-table__row) {
  cursor: pointer;
}

.workflow-table :deep(.el-table__row:hover) {
  background-color: var(--el-fill-color-light);
}

.workflow-name {
  font-weight: 500;
}

.description {
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 280px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: flex-start;
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
