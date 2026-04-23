<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  ElCard, ElButton, ElTable, ElTableColumn, ElDialog, ElForm, ElFormItem,
  ElInput, ElSelect, ElOption, ElMessageBox, ElMessage, ElEmpty, ElTag,
  ElTooltip, ElDrawer, ElTransfer
} from 'element-plus'
import { Plus, Edit, Delete, Refresh, Setting } from '@element-plus/icons-vue'
import { useTestSuitesStore } from '@/stores/testSuites'
import { workflowsApi } from '@/api'
import type { TestSuite, TestSuiteCreate, Workflow } from '@/types'
import { SUITE_TYPE_OPTIONS } from '@/types'

import type { TransferKey } from 'element-plus'

const store = useTestSuitesStore()

const allTestCases = ref<Workflow[]>([])

const isEmpty = computed(() => store.suites.length === 0 && !store.loading)

const fetchAll = async () => {
  await store.fetchSuites()
}

const fetchTestCases = async () => {
  try {
    allTestCases.value = await workflowsApi.list({ is_test_case: true })
  } catch {
    ElMessage.error('加载测试用例列表失败')
  }
}

// Create dialog
const createDialogVisible = ref(false)
const isCreating = ref(false)
const createForm = ref<TestSuiteCreate>({
  name: '',
  description: '',
  suite_type: 'feature',
  artifact_version: '',
})

const resetCreateForm = () => {
  createForm.value = { name: '', description: '', suite_type: 'feature', artifact_version: '' }
}

const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入模块名称')
    return
  }
  isCreating.value = true
  try {
    await store.createSuite({
      ...createForm.value,
      name: createForm.value.name.trim(),
      artifact_version: createForm.value.artifact_version || undefined,
    })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    resetCreateForm()
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
const editForm = ref({ name: '', description: '', suite_type: 'feature' as string, artifact_version: '' })

const handleEdit = (row: TestSuite) => {
  editingId.value = row.id
  editForm.value = {
    name: row.name,
    description: row.description || '',
    suite_type: row.suite_type,
    artifact_version: row.artifact_version || '',
  }
  editDialogVisible.value = true
}

const handleEditSubmit = async () => {
  if (!editingId.value) return
  isEditing.value = true
  try {
    await store.updateSuite(editingId.value, {
      name: editForm.value.name.trim(),
      description: editForm.value.description || undefined,
      suite_type: editForm.value.suite_type as TestSuiteCreate['suite_type'],
      artifact_version: editForm.value.artifact_version || undefined,
    })
    ElMessage.success('更新成功')
    editDialogVisible.value = false
  } catch {
    ElMessage.error('更新失败')
  } finally {
    isEditing.value = false
  }
}

const handleDelete = async (row: TestSuite) => {
  try {
    await ElMessageBox.confirm(`确定删除功能模块「${row.name}」？`, '确认删除', { type: 'warning' })
    await store.deleteSuite(row.id)
    ElMessage.success('已删除')
  } catch { /* cancelled */ }
}

// Manage cases drawer
const drawerVisible = ref(false)
const managingSuite = ref<TestSuite | null>(null)
const isLoadingDetail = ref(false)
const transferValue = ref<number[]>([])

interface TransferItem {
  key: number
  label: string
  disabled: boolean
}

const transferData = computed<TransferItem[]>(() => {
  return allTestCases.value.map(wf => ({
    key: wf.id,
    label: `${wf.name}${wf.priority ? ` [${wf.priority}]` : ''}`,
    disabled: false,
  }))
})

const handleManageCases = async (row: TestSuite) => {
  managingSuite.value = row
  isLoadingDetail.value = true
  drawerVisible.value = true
  try {
    await Promise.all([store.fetchSuite(row.id), fetchTestCases()])
    transferValue.value = store.currentSuite?.cases.map(c => c.workflow_id) || []
  } catch {
    ElMessage.error('加载详情失败')
  } finally {
    isLoadingDetail.value = false
  }
}

const handleTransferChange = async (newVal: TransferKey[]) => {
  if (!managingSuite.value) return
  const suiteId = managingSuite.value.id
  const oldVal = store.currentSuite?.cases.map(c => c.workflow_id) || []
  const numVal = newVal.map(v => Number(v))
  const added = numVal.filter(id => !oldVal.includes(id))
  const removed = oldVal.filter(id => !numVal.includes(id))

  try {
    for (const wid of added) {
      await store.addCase(suiteId, wid)
    }
    for (const wid of removed) {
      await store.removeCase(suiteId, wid)
    }
  } catch {
    ElMessage.error('操作失败')
    await store.fetchSuite(suiteId)
    transferValue.value = store.currentSuite?.cases.map(c => c.workflow_id) || []
  }
}

const suiteTypeLabel = (t: string) => {
  const map: Record<string, string> = { feature: '功能测试', regression: '回归测试', smoke: '冒烟测试', performance: '性能测试' }
  return map[t] || t
}

const suiteTypeColor = (t: string): 'success' | 'warning' | 'danger' | undefined => {
  const map: Record<string, 'success' | 'warning' | 'danger'> = { regression: 'warning', smoke: 'success', performance: 'danger' }
  return map[t] || undefined
}

const formatDate = (d: string) => {
  return new Date(d).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchAll)
</script>

<template>
  <div class="test-modules-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <h2 class="toolbar-title">功能模块</h2>
        <ElTag type="info" size="small" round>{{ store.suites.length }}</ElTag>
      </div>
      <div class="toolbar-actions">
        <ElTooltip content="刷新">
          <ElButton :icon="Refresh" circle size="small" @click="fetchAll" />
        </ElTooltip>
        <ElButton type="primary" :icon="Plus" size="small" @click="createDialogVisible = true">新建模块</ElButton>
      </div>
    </div>

    <!-- Table -->
    <ElCard shadow="never" :body-style="{ padding: 0 }">
      <ElTable v-if="!isEmpty" :data="store.suites" v-loading="store.loading" style="width: 100%">
        <ElTableColumn label="模块名称" prop="name" min-width="220">
          <template #default="{ row }">
            <div class="cell-name">
              <span class="name-text">{{ row.name }}</span>
              <span v-if="row.description" class="name-desc">{{ row.description }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="类型" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="suiteTypeColor(row.suite_type)" size="small">{{ suiteTypeLabel(row.suite_type) }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="版本" width="120" align="center">
          <template #default="{ row }">
            <span>{{ row.artifact_version || '-' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="用例数" width="80" align="center">
          <template #default="{ row }">
            <ElTag :type="row.case_count > 0 ? 'success' : 'info'" size="small" round>{{ row.case_count }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="更新时间" width="120" align="center">
          <template #default="{ row }">
            <span class="text-muted">{{ formatDate(row.updated_at) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="150" align="center">
          <template #default="{ row }">
            <ElTooltip content="管理用例">
              <ElButton link :icon="Setting" @click="handleManageCases(row)" />
            </ElTooltip>
            <ElTooltip content="编辑">
              <ElButton link :icon="Edit" @click="handleEdit(row)" />
            </ElTooltip>
            <ElTooltip content="删除">
              <ElButton link :icon="Delete" type="danger" @click="handleDelete(row)" />
            </ElTooltip>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty v-else description="暂无功能模块，点击「新建模块」创建" />
    </ElCard>

    <!-- Create Dialog -->
    <ElDialog v-model="createDialogVisible" title="新建功能模块" width="480px" :close-on-click-modal="false">
      <ElForm label-width="80px" label-position="left">
        <ElFormItem label="模块名称" required>
          <ElInput v-model="createForm.name" placeholder="如：v2091 统计数据的磁盘空间占用" maxlength="100" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="createForm.description" type="textarea" :rows="2" placeholder="可选" />
        </ElFormItem>
        <ElFormItem label="测试类型">
          <ElSelect v-model="createForm.suite_type" style="width: 100%">
            <ElOption v-for="o in SUITE_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="版本号">
          <ElInput v-model="createForm.artifact_version" placeholder="如：v2.0.9.1" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="isCreating" @click="handleCreate">创建</ElButton>
      </template>
    </ElDialog>

    <!-- Edit Dialog -->
    <ElDialog v-model="editDialogVisible" title="编辑功能模块" width="480px" :close-on-click-modal="false">
      <ElForm label-width="80px" label-position="left">
        <ElFormItem label="模块名称" required>
          <ElInput v-model="editForm.name" maxlength="100" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editForm.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="测试类型">
          <ElSelect v-model="editForm.suite_type" style="width: 100%">
            <ElOption v-for="o in SUITE_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="版本号">
          <ElInput v-model="editForm.artifact_version" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="isEditing" @click="handleEditSubmit">保存</ElButton>
      </template>
    </ElDialog>

    <!-- Manage Cases Drawer -->
    <ElDrawer v-model="drawerVisible" :title="`管理用例 — ${managingSuite?.name || ''}`" size="500px">
      <div v-loading="isLoadingDetail" class="transfer-container">
        <p class="transfer-hint">左侧为可选测试用例，右侧为已添加到模块的用例</p>
        <ElTransfer
          v-model="transferValue"
          :data="transferData"
          :titles="['可选用例', '已添加']"
          filterable
          filter-placeholder="搜索用例"
          @change="handleTransferChange"
        />
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.test-modules-view {
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
}

.text-muted {
  color: #94a3b8;
  font-size: 12px;
}

.transfer-container {
  padding: 0 4px;
}

.transfer-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 16px;
}

:deep(.el-transfer-panel) {
  width: 200px;
}
</style>
