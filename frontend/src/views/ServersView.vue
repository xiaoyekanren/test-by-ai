<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import {
  ElCard,
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessageBox,
  ElMessage,
  ElTooltip,
  ElCollapse,
  ElCollapseItem,
  ElRadioGroup,
  ElRadioButton,
  type FormInstance,
  type FormRules
} from 'element-plus'
import { Refresh, Plus, Edit, Delete, Connection, Promotion, CollectionTag, List } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import type { Server, ServerCreate, ServerUpdate } from '@/types'

const serversStore = useServersStore()

// View mode: 'group' for tags grouping, 'list' for flat list
const viewMode = ref<'group' | 'list'>('list')

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
  tags: ''
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
  ]
}

// Command execution dialog
const commandDialogVisible = ref(false)
const commandInput = ref('')
const commandServerId = ref<number | null>(null)
const commandServerName = ref('')
const commandResult = ref('')
const commandLoading = ref(false)
const pendingStatusChecks = ref(0)
const statusCheckRunId = ref(0)
const isStatusChecking = computed(() => pendingStatusChecks.value > 0)

// Table sorting - default to host:port ascending
const sortProp = ref('host')
const sortOrder = ref('ascending')

// Sort servers by host:port
const sortedServers = computed(() => {
  const servers = [...serversStore.servers]
  if (sortProp.value && sortOrder.value) {
    servers.sort((a, b) => {
      let aVal: string | number
      let bVal: string | number
      if (sortProp.value === 'host') {
        // Sort by host:port combination
        aVal = `${a.host}:${a.port}`
        bVal = `${b.host}:${b.port}`
      } else {
        aVal = a[sortProp.value as keyof Server] as string | number
        bVal = b[sortProp.value as keyof Server] as string | number
      }
      if (aVal === bVal) return 0
      const comparison = aVal < bVal ? -1 : 1
      return sortOrder.value === 'ascending' ? comparison : -comparison
    })
  }
  return servers
})

// Group servers by tags
const groupedServers = computed(() => {
  const groups: Record<string, Server[]> = {}
  const untagged: Server[] = []

  sortedServers.value.forEach(server => {
    const tags = parseTags(server.tags)
    if (tags.length === 0) {
      untagged.push(server)
    } else {
      tags.forEach(tag => {
        if (!groups[tag]) {
          groups[tag] = []
        }
        groups[tag].push(server)
      })
    }
  })

  // Sort groups by tag name
  const sortedGroups = Object.keys(groups).sort().map(tag => ({
    tag,
    servers: groups[tag]
  }))

  // Add untagged group at the end if there are any
  if (untagged.length > 0) {
    sortedGroups.push({
      tag: 'Untagged',
      servers: untagged
    })
  }

  return sortedGroups
})

// Load servers on mount
onMounted(async () => {
  await loadServers()
})

async function loadServers(checkStatuses = true) {
  try {
    await serversStore.fetchServers()
    if (checkStatuses) {
      refreshServerStatuses()
    }
  } catch (error) {
    ElMessage.error('Failed to load servers')
  }
}

function refreshServerStatuses() {
  const servers = [...serversStore.servers]
  const runId = statusCheckRunId.value + 1
  statusCheckRunId.value = runId
  pendingStatusChecks.value = servers.length

  if (servers.length === 0) {
    return
  }

  servers.forEach(server => {
    void checkServerStatus(server, runId)
  })
}

async function checkServerStatus(server: Server, runId: number) {
  try {
    await serversStore.testConnection(server.id, { useGlobalLoading: false })
  } catch (error) {
    // Keep the page responsive; each failed host is marked offline in the store.
  } finally {
    if (statusCheckRunId.value === runId) {
      pendingStatusChecks.value = Math.max(0, pendingStatusChecks.value - 1)
    }
  }
}

function getServerStatus(server: Server) {
  return serversStore.isTestingServer(server.id) ? 'loading' : server.status
}

function handleSortChange({ prop, order }: { prop: string; order: string | null }) {
  sortProp.value = prop || 'host'
  sortOrder.value = order || 'ascending'
}

// Switch view mode
function handleViewModeChange() {
  // View mode changed, no additional action needed
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
    tags: server.tags || ''
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
    tags: ''
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
        const newServer = await serversStore.addServer({
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          password: formData.password || null,
          description: formData.description || null,
          tags: formData.tags || null
        })
        dialogVisible.value = false
        // Auto test connection after creating server
        testConnection(newServer)
      } else if (currentServerId.value) {
        const updateData: ServerUpdate = {
          name: formData.name,
          host: formData.host,
          port: formData.port,
          username: formData.username || null,
          description: formData.description || null,
          tags: formData.tags || null
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
    const result = await serversStore.testConnection(server.id, { useGlobalLoading: false })
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
        <h2>🖥️ 服务器管理</h2>
        <span class="server-count">{{ serversStore.servers.length }} 台</span>
        <span class="refresh-info">{{ serversStore.loading ? '加载中' : isStatusChecking ? `检查中 ${pendingStatusChecks} 台` : '按 Host:Port 排序' }}</span>
      </div>
      <div class="toolbar-actions">
        <ElRadioGroup v-model="viewMode" size="small" @change="handleViewModeChange">
          <ElRadioButton value="list" :icon="List">List</ElRadioButton>
          <ElRadioButton value="group" :icon="CollectionTag">By Tags</ElRadioButton>
        </ElRadioGroup>
        <ElButton @click="loadServers()" :icon="Refresh" :loading="serversStore.loading" size="small">
          刷新
        </ElButton>
        <ElButton type="primary" @click="openCreateDialog" :icon="Plus" size="small">
          新增服务器
        </ElButton>
      </div>
    </div>

    <!-- List View -->
    <ElCard v-if="viewMode === 'list'" shadow="hover" class="servers-card">
      <ElTable
        :data="sortedServers"
        v-loading="serversStore.loading"
        stripe
        style="width: 100%"
        class="server-table"
        @sort-change="handleSortChange"
        :default-sort="{ prop: 'host', order: 'ascending' }"
        :fit="false"
      >
        <ElTableColumn prop="name" label="Name" sortable="custom" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="server-info">
              <ElTag type="info" size="small" class="server-type-tag">SSH</ElTag>
              <div class="server-name">
                <span class="name-text">{{ row.name }}</span>
                <span v-if="row.description" class="description">{{ row.description }}</span>
              </div>
            </div>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Host:Port" prop="host" sortable="custom" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <code class="host-port">{{ row.host }}:{{ row.port }}</code>
          </template>
        </ElTableColumn>

        <ElTableColumn prop="status" label="Status" sortable="custom" width="90" align="center">
          <template #default="{ row }">
            <span class="status-tag" :class="getServerStatus(row)">
              <span v-if="getServerStatus(row) === 'loading'" class="status-icon spinning">◐</span>
              <span v-else>●</span>
              {{ getServerStatus(row) }}
            </span>
          </template>
        </ElTableColumn>

        <ElTableColumn label="Tags" width="180">
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

        <ElTableColumn label="Actions" width="150" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <ElTooltip content="Test Connection" placement="top">
                <ElButton
                  size="small"
                  :icon="Connection"
                  @click="testConnection(row)"
                  :loading="serversStore.isTestingServer(row.id)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Execute Command" placement="top">
                <ElButton
                  size="small"
                  :icon="Promotion"
                  @click="openCommandDialog(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Edit" placement="top">
                <ElButton
                  size="small"
                  type="primary"
                  :icon="Edit"
                  @click="openEditDialog(row)"
                  link
                />
              </ElTooltip>
              <ElTooltip content="Delete" placement="top">
                <ElButton
                  size="small"
                  type="danger"
                  :icon="Delete"
                  @click="deleteServer(row)"
                  link
                />
              </ElTooltip>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- Grouped View by Tags -->
    <div v-else class="grouped-view">
      <ElCollapse v-if="groupedServers.length > 0" accordion>
        <ElCollapseItem
          v-for="group in groupedServers"
          :key="group.tag"
          :name="group.tag"
        >
          <template #title>
            <div class="group-header">
              <ElTag size="small" type="info">{{ group.tag }}</ElTag>
              <span class="group-count">{{ group.servers.length }} servers</span>
            </div>
          </template>
          <ElTable
            :data="group.servers"
            stripe
            style="width: 100%"
            size="small"
            class="server-table"
            :fit="false"
          >
            <ElTableColumn prop="name" label="Name" width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="server-info">
                  <ElTag type="info" size="small" class="server-type-tag">SSH</ElTag>
                  <div class="server-name">
                    <span class="name-text">{{ row.name }}</span>
                    <span v-if="row.description" class="description">{{ row.description }}</span>
                  </div>
                </div>
              </template>
            </ElTableColumn>

            <ElTableColumn label="Host:Port" width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <code class="host-port">{{ row.host }}:{{ row.port }}</code>
              </template>
            </ElTableColumn>

            <ElTableColumn prop="status" label="Status" width="90" align="center">
              <template #default="{ row }">
                <span class="status-tag" :class="getServerStatus(row)">
                  <span v-if="getServerStatus(row) === 'loading'" class="status-icon spinning">◐</span>
                  <span v-else>●</span>
                  {{ getServerStatus(row) }}
                </span>
              </template>
            </ElTableColumn>

            <ElTableColumn label="Actions" width="120" align="center">
              <template #default="{ row }">
                <div class="action-buttons">
                  <ElTooltip content="Test Connection" placement="top">
                    <ElButton
                      size="small"
                      :icon="Connection"
                      @click="testConnection(row)"
                      :loading="serversStore.isTestingServer(row.id)"
                      link
                    />
                  </ElTooltip>
                  <ElTooltip content="Edit" placement="top">
                    <ElButton
                      size="small"
                      type="primary"
                      :icon="Edit"
                      @click="openEditDialog(row)"
                      link
                    />
                  </ElTooltip>
                  <ElTooltip content="Delete" placement="top">
                    <ElButton
                      size="small"
                      type="danger"
                      :icon="Delete"
                      @click="deleteServer(row)"
                      link
                    />
                  </ElTooltip>
                </div>
              </template>
            </ElTableColumn>
          </ElTable>
        </ElCollapseItem>
      </ElCollapse>
      <div v-else class="empty-groups">
        <span>No servers found</span>
      </div>
    </div>

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
  margin-bottom: 12px;
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.server-count {
  font-size: 11px;
  color: #3b82f6;
}

.refresh-info {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 4px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.servers-card {
  width: 100%;
  margin: 0;
}

.server-table :deep(.el-table__cell) {
  padding: 6px 0;
}

.server-table :deep(.el-table__header-cell) {
  padding: 6px 0;
  font-size: 11px;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.server-type-tag {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

.server-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}

.name-text {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.description {
  font-size: 11px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.host-port {
  display: inline-block;
  max-width: 100%;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 58px;
  height: 20px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
}

.status-tag.online {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.status-tag.offline {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.status-tag.loading {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 10px;
  height: 10px;
  font-size: 8px;
  line-height: 1;
}

.status-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
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
  color: #94a3b8;
  font-size: 12px;
}

.action-buttons {
  display: flex;
  gap: 4px;
  justify-content: center;
  align-items: center;
}

.action-buttons :deep(.el-button) {
  font-size: 18px;
  padding: 4px;
}

.action-buttons :deep(.el-button .el-icon) {
  font-size: 18px;
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
  color: #64748b;
}

.result-output {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}

.grouped-view {
  margin-top: 0;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-count {
  font-size: 12px;
  color: #94a3b8;
}

.empty-groups {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}
</style>
