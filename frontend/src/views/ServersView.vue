<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElMessageBox,
  ElMessage,
  ElTooltip,
  type FormInstance,
  type FormRules
} from 'element-plus'
import { Refresh, Plus, Edit, Delete, Connection, Promotion } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import type { Server, ServerCreate, ServerUpdate } from '@/types'

const serversStore = useServersStore()

// Form related
const formRef = ref<FormInstance>()
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const currentServerId = ref<number | null>(null)

const formData = reactive<ServerCreate & { password?: string }>({
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  description: '',
  tags: '',
  role: 'worker'
})

const formRules: FormRules = {
  name: [
    { required: true, message: 'Please input server name', trigger: 'blur' },
    { min: 2, max: 50, message: 'Length should be 2 to 50 characters', trigger: 'blur' }
  ],
  host: [
    { required: true, message: 'Please input host address', trigger: 'blur' }
  ],
  port: [
    { required: true, message: 'Please input port', trigger: 'blur' }
  ],
  username: [
    { required: true, message: 'Please input username', trigger: 'blur' }
  ],
  role: [
    { required: true, message: 'Please select a role', trigger: 'change' }
  ]
}

// Command execution dialog
const commandDialogVisible = ref(false)
const commandInput = ref('')
const commandServerId = ref<number | null>(null)
const commandServerName = ref('')
const commandResult = ref('')
const commandLoading = ref(false)

// Table sorting
const sortProp = ref('name')
const sortOrder = ref('ascending')

const sortedServers = computed(() => {
  const servers = [...serversStore.servers]
  if (sortProp.value && sortOrder.value) {
    servers.sort((a, b) => {
      const aVal = a[sortProp.value as keyof Server]
      const bVal = b[sortProp.value as keyof Server]
      if (aVal === bVal) return 0
      const comparison = aVal! < bVal! ? -1 : 1
      return sortOrder.value === 'ascending' ? comparison : -comparison
    })
  }
  return servers
})

// Load servers on mount
onMounted(async () => {
  await loadServers()
})

async function loadServers() {
  try {
    await serversStore.fetchServers()
  } catch (error) {
    ElMessage.error('Failed to load servers')
  }
}

function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  sortProp.value = prop
  sortOrder.value = order || 'ascending'
}

// Open create dialog
function openCreateDialog() {
  dialogMode.value = 'create'
  currentServerId.value = null
  resetForm()
  dialogVisible.value = true
}

// Open edit dialog
function openEditDialog(server: Server) {
  dialogMode.value = 'edit'
  currentServerId.value = server.id
  Object.assign(formData, {
    name: server.name,
    host: server.host,
    port: server.port,
    username: server.username || '',
    password: '',
    description: server.description || '',
    tags: server.tags || '',
    role: server.role || 'worker'
  })
  dialogVisible.value = true
}

// Reset form
function resetForm() {
  Object.assign(formData, {
    name: '',
    host: '',
    port: 22,
    username: '',
    password: '',
    description: '',
    tags: '',
    role: 'worker'
  })
  formRef.value?.clearValidate()
}

// Submit form
async function submitForm() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (dialogMode.value === 'create') {
        await serversStore.addServer({
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          password: formData.password || null,
          description: formData.description || null,
          tags: formData.tags || null,
          role: formData.role
        })
        ElMessage.success('Server created successfully')
      } else if (currentServerId.value) {
        const updateData: ServerUpdate = {
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          description: formData.description || null,
          tags: formData.tags || null,
          role: formData.role
        }
        if (formData.password) {
          updateData.password = formData.password
        }
        await serversStore.updateServer(currentServerId.value, updateData)
        ElMessage.success('Server updated successfully')
      }
      dialogVisible.value = false
    } catch (error) {
      ElMessage.error(dialogMode.value === 'create' ? 'Failed to create server' : 'Failed to update server')
    }
  })
}

// Delete server
async function deleteServer(server: Server) {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete server "${server.name}"?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
    await serversStore.deleteServer(server.id)
    ElMessage.success('Server deleted successfully')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete server')
    }
  }
}

// Test connection
async function testConnection(server: Server) {
  try {
    const result = await serversStore.testConnection(server.id)
    if (result.success) {
      ElMessage.success(`Connection successful: ${result.message}`)
    } else {
      ElMessage.error(`Connection failed: ${result.message}`)
    }
  } catch (error) {
    ElMessage.error('Failed to test connection')
  }
}

// Open command dialog
function openCommandDialog(server: Server) {
  commandServerId.value = server.id
  commandServerName.value = server.name
  commandInput.value = ''
  commandResult.value = ''
  commandDialogVisible.value = true
}

// Execute command
async function executeCommand() {
  if (!commandInput.value.trim() || !commandServerId.value) return

  commandLoading.value = true
  commandResult.value = ''

  try {
    const result = await serversStore.executeCommand(commandServerId.value, commandInput.value)
    if (result.error) {
      commandResult.value = `Error: ${result.error}\n\nStderr:\n${result.stderr}`
    } else {
      let output = `Exit Status: ${result.exit_status}\n\n`
      if (result.stdout) {
        output += `Stdout:\n${result.stdout}\n\n`
      }
      if (result.stderr) {
        output += `Stderr:\n${result.stderr}`
      }
      commandResult.value = output
    }
  } catch (error) {
    commandResult.value = `Error: ${error instanceof Error ? error.message : 'Failed to execute command'}`
  } finally {
    commandLoading.value = false
  }
}

// Get status tag type
function getStatusType(status: string): 'success' | 'danger' | 'info' {
  switch (status) {
    case 'online':
      return 'success'
    case 'offline':
      return 'danger'
    default:
      return 'info'
  }
}

// Parse tags string to array
function parseTags(tags: string | null): string[] {
  if (!tags) return []
  return tags.split(',').map(t => t.trim()).filter(t => t)
}
</script>

<template>
  <div class="servers-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>Servers Management</h2>
        <span class="server-count">{{ serversStore.servers.length }} servers</span>
      </div>
      <div class="toolbar-actions">
        <ElButton @click="loadServers" :icon="Refresh" :loading="serversStore.loading">
          Refresh
        </ElButton>
        <ElButton type="primary" @click="openCreateDialog" :icon="Plus">
          Add Server
        </ElButton>
      </div>
    </div>

    <!-- Server Table -->
    <ElTable
      :data="sortedServers"
      v-loading="serversStore.loading"
      stripe
      style="width: 100%"
      @sort-change="handleSortChange"
      :default-sort="{ prop: 'name', order: 'ascending' }"
    >
      <ElTableColumn prop="name" label="Name" sortable="custom" min-width="150">
        <template #default="{ row }">
          <div class="server-name">
            <span class="name-text">{{ row.name }}</span>
            <span v-if="row.description" class="description">{{ row.description }}</span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="Host:Port" min-width="180">
        <template #default="{ row }">
          <code class="host-port">{{ row.host }}:{{ row.port }}</code>
        </template>
      </ElTableColumn>

      <ElTableColumn prop="status" label="Status" sortable="custom" width="120">
        <template #default="{ row }">
          <ElTag :type="getStatusType(row.status)" size="small">
            {{ row.status }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="Tags" min-width="150">
        <template #default="{ row }">
          <div class="tags-container">
            <ElTag
              v-for="tag in parseTags(row.tags)"
              :key="tag"
              size="small"
              type="info"
              class="tag-item"
            >
              {{ tag }}
            </ElTag>
            <span v-if="!parseTags(row.tags).length" class="no-tags">-</span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn prop="role" label="Role" width="100">
        <template #default="{ row }">
          <ElTag size="small" :type="row.role === 'master' ? 'warning' : 'info'">
            {{ row.role }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="Actions" width="280" fixed="right">
        <template #default="{ row }">
          <div class="action-buttons">
            <ElTooltip content="Test Connection" placement="top">
              <ElButton
                size="small"
                :icon="Connection"
                @click="testConnection(row)"
                :loading="serversStore.loading"
              />
            </ElTooltip>
            <ElTooltip content="Execute Command" placement="top">
              <ElButton
                size="small"
                :icon="Promotion"
                @click="openCommandDialog(row)"
              />
            </ElTooltip>
            <ElTooltip content="Edit" placement="top">
              <ElButton
                size="small"
                type="primary"
                :icon="Edit"
                @click="openEditDialog(row)"
              />
            </ElTooltip>
            <ElTooltip content="Delete" placement="top">
              <ElButton
                size="small"
                type="danger"
                :icon="Delete"
                @click="deleteServer(row)"
              />
            </ElTooltip>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- Add/Edit Server Dialog -->
    <ElDialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? 'Add Server' : 'Edit Server'"
      width="500px"
      :close-on-click-modal="false"
    >
      <ElForm
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        label-position="right"
      >
        <ElFormItem label="Name" prop="name">
          <ElInput v-model="formData.name" placeholder="Server name" />
        </ElFormItem>

        <ElFormItem label="Host" prop="host">
          <ElInput v-model="formData.host" placeholder="IP address or hostname" />
        </ElFormItem>

        <ElFormItem label="Port" prop="port">
          <ElInputNumber v-model="formData.port" :min="1" :max="65535" style="width: 100%" />
        </ElFormItem>

        <ElFormItem label="Username" prop="username">
          <ElInput v-model="formData.username" placeholder="SSH username" />
        </ElFormItem>

        <ElFormItem label="Password" prop="password">
          <ElInput
            v-model="formData.password"
            type="password"
            show-password
            :placeholder="dialogMode === 'edit' ? 'Leave empty to keep current' : 'SSH password'"
          />
        </ElFormItem>

        <ElFormItem label="Description" prop="description">
          <ElInput
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="Server description (optional)"
          />
        </ElFormItem>

        <ElFormItem label="Tags" prop="tags">
          <ElInput
            v-model="formData.tags"
            placeholder="Comma separated tags (e.g. production, web)"
          />
        </ElFormItem>

        <ElFormItem label="Role" prop="role">
          <ElSelect v-model="formData.role" style="width: 100%">
            <ElOption label="Master" value="master" />
            <ElOption label="Worker" value="worker" />
          </ElSelect>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">Cancel</ElButton>
        <ElButton type="primary" @click="submitForm" :loading="serversStore.loading">
          {{ dialogMode === 'create' ? 'Create' : 'Save' }}
        </ElButton>
      </template>
    </ElDialog>

    <!-- Execute Command Dialog -->
    <ElDialog
      v-model="commandDialogVisible"
      :title="`Execute Command on ${commandServerName}`"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="command-section">
        <ElInput
          v-model="commandInput"
          type="textarea"
          :rows="3"
          placeholder="Enter command to execute..."
          @keydown.ctrl.enter="executeCommand"
        />
        <div class="command-actions">
          <ElButton
            type="primary"
            @click="executeCommand"
            :loading="commandLoading"
            :disabled="!commandInput.trim()"
          >
            Execute
          </ElButton>
        </div>
      </div>

      <div v-if="commandResult" class="result-section">
        <div class="result-label">Output:</div>
        <pre class="result-output">{{ commandResult }}</pre>
      </div>

      <template #footer>
        <ElButton @click="commandDialogVisible = false">Close</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.servers-view {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.toolbar-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.server-count {
  font-size: 14px;
  color: #909399;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
}

.server-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-text {
  font-weight: 500;
  color: #303133;
}

.description {
  font-size: 12px;
  color: #909399;
}

.host-port {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  background: #f5f7fa;
  padding: 4px 8px;
  border-radius: 4px;
  color: #606266;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag-item {
  margin: 0;
}

.no-tags {
  color: #c0c4cc;
}

.action-buttons {
  display: flex;
  gap: 4px;
}

.command-section {
  margin-bottom: 20px;
}

.command-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.result-section {
  margin-top: 20px;
}

.result-label {
  font-weight: 500;
  margin-bottom: 8px;
  color: #606266;
}

.result-output {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}
</style>