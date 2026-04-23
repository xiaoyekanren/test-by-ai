<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElCard, ElButton, ElTable, ElTableColumn, ElDialog, ElForm, ElFormItem,
  ElInput, ElSelect, ElOption, ElMessageBox, ElMessage, ElEmpty, ElTag, ElTooltip
} from 'element-plus'
import { Plus, Edit, Delete, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { workflowsApi } from '@/api'
import type { Workflow, WorkflowCreate, Priority, TestType } from '@/types'
import { PRIORITY_OPTIONS, TEST_TYPE_OPTIONS } from '@/types'

const router = useRouter()

const workflows = ref<Workflow[]>([])
const loading = ref(false)
const filterPriority = ref<string>('')
const filterTestType = ref<string>('')

const isEmpty = computed(() => workflows.value.length === 0 && !loading.value)

const fetchTestCases = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = { is_test_case: true }
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterTestType.value) params.test_type = filterTestType.value
    workflows.value = await workflowsApi.list(params as { is_test_case?: boolean; priority?: string; test_type?: string })
  } catch {
    ElMessage.error('加载测试用例失败')
  } finally {
    loading.value = false
  }
}

// Create dialog
const createDialogVisible = ref(false)
const isCreating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  priority: 'P1' as Priority,
  test_type: '功能' as TestType,
  labels: '',
  source: '',
})

const resetCreateForm = () => {
  createForm.value = { name: '', description: '', priority: 'P1', test_type: '功能', labels: '', source: '' }
}

const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入用例名称')
    return
  }
  isCreating.value = true
  try {
    const data: WorkflowCreate = {
      name: createForm.value.name.trim(),
      description: createForm.value.description || undefined,
      priority: createForm.value.priority,
      test_type: createForm.value.test_type,
      labels: createForm.value.labels || undefined,
      source: createForm.value.source || undefined,
    }
    const wf = await workflowsApi.create(data)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    resetCreateForm()
    router.push(`/workflows/${wf.id}/edit`)
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '创建失败'
    ElMessage.error(msg)
  } finally {
    isCreating.value = false
  }
}

// Edit dialog
const editDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const editForm = ref({
  priority: '' as Priority | '',
  test_type: '' as TestType | '',
  labels: '',
  source: '',
})

const handleEdit = (row: Workflow) => {
  editingId.value = row.id
  editForm.value = {
    priority: row.priority || '',
    test_type: row.test_type || '',
    labels: row.labels || '',
    source: row.source || '',
  }
  editDialogVisible.value = true
}

const handleEditSubmit = async () => {
  if (!editingId.value) return
  isEditing.value = true
  try {
    await workflowsApi.update(editingId.value, {
      priority: (editForm.value.priority || undefined) as Priority | undefined,
      test_type: (editForm.value.test_type || undefined) as TestType | undefined,
      labels: editForm.value.labels || undefined,
      source: editForm.value.source || undefined,
    })
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    fetchTestCases()
  } catch {
    ElMessage.error('更新失败')
  } finally {
    isEditing.value = false
  }
}

const handleDelete = async (row: Workflow) => {
  try {
    await ElMessageBox.confirm(`确定删除测试用例「${row.name}」？此操作不可恢复。`, '确认删除', { type: 'warning' })
    await workflowsApi.delete(row.id)
    ElMessage.success('已删除')
    fetchTestCases()
  } catch { /* cancelled */ }
}

const handleRowClick = (row: Workflow) => {
  router.push(`/workflows/${row.id}/edit`)
}

const priorityColor = (p: string | null): 'danger' | 'warning' | 'info' => {
  const map: Record<string, 'danger' | 'warning' | 'info'> = { P0: 'danger', P1: 'warning', P2: 'info' }
  return (p && map[p]) || 'info'
}

const formatDate = (d: string) => {
  return new Date(d).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchTestCases)
</script>

<template>
  <div class="test-cases-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <h2 class="toolbar-title">测试用例</h2>
        <ElTag type="info" size="small" round>{{ workflows.length }}</ElTag>
      </div>
      <div class="toolbar-actions">
        <ElSelect v-model="filterPriority" placeholder="优先级" clearable size="small" style="width: 100px" @change="fetchTestCases">
          <ElOption v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </ElSelect>
        <ElSelect v-model="filterTestType" placeholder="测试类型" clearable size="small" style="width: 100px" @change="fetchTestCases">
          <ElOption v-for="o in TEST_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </ElSelect>
        <ElTooltip content="刷新">
          <ElButton :icon="Refresh" circle size="small" @click="fetchTestCases" />
        </ElTooltip>
        <ElButton type="primary" :icon="Plus" size="small" @click="createDialogVisible = true">新建用例</ElButton>
      </div>
    </div>

    <!-- Table -->
    <ElCard shadow="never" :body-style="{ padding: 0 }">
      <ElTable
        v-if="!isEmpty"
        :data="workflows"
        v-loading="loading"
        row-class-name="clickable-row"
        @row-click="handleRowClick"
        style="width: 100%"
      >
        <ElTableColumn label="用例名称" prop="name" min-width="240">
          <template #default="{ row }">
            <div class="cell-name">
              <span class="name-text">{{ row.name }}</span>
              <span v-if="row.description" class="name-desc">{{ row.description }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="优先级" width="80" align="center">
          <template #default="{ row }">
            <ElTag :type="priorityColor(row.priority)" size="small">{{ row.priority }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="类型" width="80" align="center">
          <template #default="{ row }">
            <span>{{ row.test_type || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="来源" prop="source" width="160">
          <template #default="{ row }">
            <span class="text-muted">{{ row.source || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="标签" width="160">
          <template #default="{ row }">
            <template v-if="row.labels">
              <ElTag v-for="tag in row.labels.split(',')" :key="tag" size="small" class="label-tag">{{ tag.trim() }}</ElTag>
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="节点数" width="70" align="center">
          <template #default="{ row }">{{ row.nodes?.length || 0 }}</template>
        </ElTableColumn>
        <ElTableColumn label="更新时间" width="120" align="center">
          <template #default="{ row }">
            <span class="text-muted">{{ formatDate(row.updated_at) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="140" align="center">
          <template #default="{ row }">
            <ElTooltip content="编辑工作流">
              <ElButton link :icon="VideoPlay" @click.stop="router.push(`/workflows/${row.id}/edit`)" />
            </ElTooltip>
            <ElTooltip content="修改属性">
              <ElButton link :icon="Edit" @click.stop="handleEdit(row)" />
            </ElTooltip>
            <ElTooltip content="删除">
              <ElButton link :icon="Delete" type="danger" @click.stop="handleDelete(row)" />
            </ElTooltip>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty v-else description="暂无测试用例，点击「新建用例」创建" />
    </ElCard>

    <!-- Create Dialog -->
    <ElDialog v-model="createDialogVisible" title="新建测试用例" width="480px" :close-on-click-modal="false">
      <ElForm label-width="80px" label-position="left">
        <ElFormItem label="用例名称" required>
          <ElInput v-model="createForm.name" placeholder="如：表模型-查询系统表基本功能" maxlength="100" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="createForm.description" type="textarea" :rows="2" placeholder="可选" />
        </ElFormItem>
        <ElFormItem label="优先级">
          <ElSelect v-model="createForm.priority" style="width: 100%">
            <ElOption v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="测试类型">
          <ElSelect v-model="createForm.test_type" style="width: 100%">
            <ElOption v-for="o in TEST_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="来源">
          <ElInput v-model="createForm.source" placeholder="如：v2091 磁盘空间占用" />
        </ElFormItem>
        <ElFormItem label="标签">
          <ElInput v-model="createForm.labels" placeholder="逗号分隔，如：表模型,核心功能" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="isCreating" @click="handleCreate">创建并编排</ElButton>
      </template>
    </ElDialog>

    <!-- Edit Dialog -->
    <ElDialog v-model="editDialogVisible" title="修改测试属性" width="420px" :close-on-click-modal="false">
      <ElForm label-width="80px" label-position="left">
        <ElFormItem label="优先级">
          <ElSelect v-model="editForm.priority" style="width: 100%">
            <ElOption v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="测试类型">
          <ElSelect v-model="editForm.test_type" style="width: 100%">
            <ElOption v-for="o in TEST_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="来源">
          <ElInput v-model="editForm.source" />
        </ElFormItem>
        <ElFormItem label="标签">
          <ElInput v-model="editForm.labels" placeholder="逗号分隔" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="isEditing" @click="handleEditSubmit">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.test-cases-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background-color: #f8fafc;
}

.cell-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-text {
  font-weight: 500;
  color: #1e293b;
  font-size: 13px;
}

.name-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.text-muted {
  color: #94a3b8;
  font-size: 12px;
}

.label-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
</style>
