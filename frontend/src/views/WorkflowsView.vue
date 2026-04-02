<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
  ElTooltip
} from 'element-plus'
import { Refresh, Plus, Edit, Delete, CopyDocument } from '@element-plus/icons-vue'
import { useWorkflowsStore } from '@/stores/workflows'
import type { Workflow } from '@/types'

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

// Lifecycle
onMounted(() => {
  fetchWorkflows()
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
        <ElTableColumn label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons" @click.stop>
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
</style>