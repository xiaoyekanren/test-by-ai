<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
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
  ElMessageBox,
  ElMessage,
  ElTooltip,
  ElDrawer,
  ElEmpty,
  ElCollapse,
  ElCollapseItem,
  ElSelect,
  ElOption,
  type FormInstance,
  type FormRules
} from 'element-plus'
import { Refresh, Plus, Edit, Delete, Connection, Promotion, Reading } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import { useMonitoringStore } from '@/stores/monitoring'
import type { ProcessInfo, Server, ServerCreate, ServerUpdate } from '@/types'
import { REGION_OPTIONS } from '@/types'
import { getApiErrorMessage } from '@/utils/api'

const serversStore = useServersStore()
const monitoringStore = useMonitoringStore()

interface ServerMetrics {
  cpu?: number
  memoryPercent?: number
  memoryUsed?: number
  memoryTotal?: number
  diskPercent?: number
  diskUsed?: number
  diskTotal?: number
}

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
  region: '私有云'
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

const serverDialogCopy = computed(() => ({
  title: dialogMode.value === 'create' ? '新增服务器' : '编辑服务器',
  subtitle: dialogMode.value === 'create' ? '添加一个新的 SSH 服务器配置' : '修改服务器配置信息',
  actionText: dialogMode.value === 'create' ? '创建' : '保存',
  icon: dialogMode.value === 'create' ? Plus : Edit
}))

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
const serverMetrics = ref<Record<number, ServerMetrics>>({})
const metricLoadingIds = ref<Set<number>>(new Set())

// Process drawer state
const processDrawerVisible = ref(false)
const currentProcessServer = ref<Server | null>(null)
const processList = ref<ProcessInfo[]>([])
const processLoading = ref(false)
const processLimit = ref(20)
const processSortBy = ref<'cpu' | 'memory'>('cpu')

// Sort servers by host:port
const sortedServers = computed(() => {
  const servers = [...serversStore.servers]
  servers.sort((a, b) => `${a.host}:${a.port}`.localeCompare(`${b.host}:${b.port}`))
  return servers
})

// Group servers by region
const groupedServers = computed(() => {
  const groups: Record<string, Server[]> = {}

  sortedServers.value.forEach(server => {
    const region = server.region || '私有云'
    if (!groups[region]) {
      groups[region] = []
    }
    groups[region].push(server)
  })

  // Keep configured regions in their declared order, then append any custom region names.
  return Object.keys(groups).sort((a, b) => {
    const aIndex = REGION_OPTIONS.indexOf(a)
    const bIndex = REGION_OPTIONS.indexOf(b)
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b)
    if (aIndex === -1) return 1
    if (bIndex === -1) return -1
    return aIndex - bIndex
  }).map(region => ({
    region,
    servers: groups[region]
  }))
})

const activeRegionGroups = ref<string[]>([])
const groupedRegionKey = computed(() => groupedServers.value.map(group => group.region).join('|'))

watch(groupedRegionKey, (key) => {
  activeRegionGroups.value = key ? key.split('|') : []
}, { immediate: true })

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
  serverMetrics.value = {}
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
    const result = await serversStore.testConnection(server.id, { useGlobalLoading: false })
    if (statusCheckRunId.value !== runId) return
    if (result.success) {
      await fetchServerMetrics(server, runId)
    } else {
      clearServerMetrics(server.id)
    }
  } catch (error) {
    clearServerMetrics(server.id)
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

function setMetricLoading(id: number, isLoading: boolean) {
  const next = new Set(metricLoadingIds.value)
  if (isLoading) {
    next.add(id)
  } else {
    next.delete(id)
  }
  metricLoadingIds.value = next
}

function isMetricLoading(id: number) {
  return metricLoadingIds.value.has(id)
}

function getServerMetrics(serverId: number) {
  return serverMetrics.value[serverId] || {}
}

function clearServerMetrics(serverId: number) {
  const next = { ...serverMetrics.value }
  delete next[serverId]
  serverMetrics.value = next
  setMetricLoading(serverId, false)
}

async function fetchServerMetrics(server: Server, runId = statusCheckRunId.value) {
  setMetricLoading(server.id, true)
  try {
    const status = await monitoringStore.fetchRemoteStatus(server.id)
    if (statusCheckRunId.value !== runId || !status) return
    serverMetrics.value = {
      ...serverMetrics.value,
      [server.id]: {
        cpu: status.cpu_percent,
        memoryPercent: status.memory?.percent,
        memoryUsed: status.memory?.used,
        memoryTotal: status.memory?.total,
        diskPercent: status.disk?.percent,
        diskUsed: status.disk?.used,
        diskTotal: status.disk?.total
      }
    }
  } catch {
    clearServerMetrics(server.id)
  } finally {
    setMetricLoading(server.id, false)
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function getProgressColor(percent: number): string {
  if (percent < 50) return '#67c23a'
  if (percent < 80) return '#e6a23c'
  return '#f56c6c'
}

function sortByMetric(key: keyof ServerMetrics) {
  return (a: Server, b: Server) => (getServerMetrics(a.id)[key] ?? -1) - (getServerMetrics(b.id)[key] ?? -1)
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
    region: server.region || '私有云'
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
    region: '私有云'
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
          region: formData.region
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
          region: formData.region
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
      ElMessage.error(getApiErrorMessage(error, 'Failed to delete server'))
    }
  }
}

// Test connection
async function testConnection(server: Server) {
  try {
    const result = await serversStore.testConnection(server.id, { useGlobalLoading: false })
    if (result.success) {
      await fetchServerMetrics(server)
      ElMessage.success(`Connection successful: ${result.message}`)
    } else {
      clearServerMetrics(server.id)
      ElMessage.error(`Connection failed: ${result.message}`)
    }
  } catch (error) {
    clearServerMetrics(server.id)
    ElMessage.error('Failed to test connection')
  }
}

async function openProcessDrawer(server: Server) {
  currentProcessServer.value = server
  processDrawerVisible.value = true
  processList.value = []
  await fetchProcessList()
}

async function fetchProcessList() {
  if (!currentProcessServer.value) return

  processLoading.value = true
  try {
    const result = await monitoringStore.fetchRemoteProcesses(
      currentProcessServer.value.id,
      { limit: processLimit.value, sort_by: processSortBy.value }
    )
    processList.value = result?.processes || []
  } catch {
    ElMessage.error('Failed to fetch process list')
    processList.value = []
  } finally {
    processLoading.value = false
  }
}

async function handleProcessLimitChange() {
  await fetchProcessList()
}

async function handleProcessSortChange() {
  await fetchProcessList()
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
        <ElButton @click="loadServers()" :icon="Refresh" :loading="serversStore.loading" size="small">
          刷新
        </ElButton>
        <ElButton type="primary" @click="openCreateDialog" :icon="Plus" size="small">
          新增服务器
        </ElButton>
      </div>
    </div>

    <!-- Grouped View by Region -->
    <div class="grouped-view">
      <ElCollapse v-if="groupedServers.length > 0" v-model="activeRegionGroups">
        <ElCollapseItem
          v-for="group in groupedServers"
          :key="group.region"
          :name="group.region"
        >
          <template #title>
            <div class="group-header">
              <ElTag size="small" type="info">{{ group.region }}</ElTag>
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

            <ElTableColumn label="Host:Port" width="148" class-name="host-port-column" show-overflow-tooltip>
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

            <ElTableColumn prop="is_busy" label="Busy" width="80" align="center">
              <template #default="{ row }">
                <span class="busy-tag" :class="row.is_busy ? 'busy' : 'idle'">
                  {{ row.is_busy ? '繁忙' : '空闲' }}
                </span>
              </template>
            </ElTableColumn>

            <ElTableColumn
              label="CPU"
              width="100"
              align="center"
              class-name="metric-divider-column"
              sortable
              :sort-method="sortByMetric('cpu')"
            >
              <template #default="{ row }">
                <div class="metric-cell" v-if="getServerMetrics(row.id).cpu !== undefined">
                  <div class="metric-bar">
                    <div
                      class="bar-fill"
                      :style="{ width: `${getServerMetrics(row.id).cpu || 0}%`, background: getProgressColor(getServerMetrics(row.id).cpu || 0) }"
                    ></div>
                  </div>
                  <span class="metric-value" :class="{ high: (getServerMetrics(row.id).cpu || 0) > 80 }">
                    {{ Math.round(getServerMetrics(row.id).cpu || 0) }}%
                  </span>
                </div>
                <span v-else class="metric-error">{{ isMetricLoading(row.id) ? '...' : '-' }}</span>
              </template>
            </ElTableColumn>

            <ElTableColumn
              label="Memory"
              width="240"
              align="center"
              class-name="metric-divider-column"
              sortable
              :sort-method="sortByMetric('memoryPercent')"
            >
              <template #default="{ row }">
                <div class="metric-cell metric-cell-composite" v-if="getServerMetrics(row.id).memoryPercent !== undefined">
                  <div class="metric-bar">
                    <div
                      class="bar-fill"
                      :style="{ width: `${getServerMetrics(row.id).memoryPercent || 0}%`, background: getProgressColor(getServerMetrics(row.id).memoryPercent || 0) }"
                    ></div>
                  </div>
                  <span class="metric-value" :class="{ high: (getServerMetrics(row.id).memoryPercent || 0) > 80 }">
                    {{ Math.round(getServerMetrics(row.id).memoryPercent || 0) }}%
                  </span>
                  <span
                    v-if="getServerMetrics(row.id).memoryUsed !== undefined && getServerMetrics(row.id).memoryTotal !== undefined"
                    class="metric-detail"
                  >
                    {{ formatBytes(getServerMetrics(row.id).memoryUsed || 0) }}/{{ formatBytes(getServerMetrics(row.id).memoryTotal || 0) }}
                  </span>
                </div>
                <span v-else class="metric-error">{{ isMetricLoading(row.id) ? '...' : '-' }}</span>
              </template>
            </ElTableColumn>

            <ElTableColumn
              label="Disk"
              width="240"
              align="center"
              class-name="metric-divider-column metric-divider-end-column"
              sortable
              :sort-method="sortByMetric('diskPercent')"
            >
              <template #default="{ row }">
                <div class="metric-cell metric-cell-composite" v-if="getServerMetrics(row.id).diskPercent !== undefined">
                  <div class="metric-bar">
                    <div
                      class="bar-fill"
                      :style="{ width: `${getServerMetrics(row.id).diskPercent || 0}%`, background: getProgressColor(getServerMetrics(row.id).diskPercent || 0) }"
                    ></div>
                  </div>
                  <span class="metric-value" :class="{ high: (getServerMetrics(row.id).diskPercent || 0) > 80 }">
                    {{ Math.round(getServerMetrics(row.id).diskPercent || 0) }}%
                  </span>
                  <span
                    v-if="getServerMetrics(row.id).diskUsed !== undefined && getServerMetrics(row.id).diskTotal !== undefined"
                    class="metric-detail"
                  >
                    {{ formatBytes(getServerMetrics(row.id).diskUsed || 0) }}/{{ formatBytes(getServerMetrics(row.id).diskTotal || 0) }}
                  </span>
                </div>
                <span v-else class="metric-error">{{ isMetricLoading(row.id) ? '...' : '-' }}</span>
              </template>
            </ElTableColumn>

            <ElTableColumn label="Actions" width="220" align="center">
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
                  <ElTooltip content="Process Monitor" placement="top">
                    <ElButton
                      size="small"
                      :icon="Reading"
                      @click="openProcessDrawer(row)"
                      :disabled="getServerStatus(row) !== 'online'"
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
      width="560px"
      :close-on-click-modal="false"
      class="enhanced-dialog"
    >
      <template #header>
        <div class="dialog-header-enhanced">
          <div class="dialog-header-accent"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon">
              <ElIcon :size="20">
                <component :is="serverDialogCopy.icon" />
              </ElIcon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">{{ serverDialogCopy.title }}</h3>
              <p class="dialog-subtitle">{{ serverDialogCopy.subtitle }}</p>
            </div>
          </div>
        </div>
      </template>
      <ElForm
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-position="top"
        class="dialog-form-enhanced"
      >
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="formData.name" placeholder="请输入服务器名称" />
        </ElFormItem>

        <div class="form-row">
          <ElFormItem label="Host" prop="host" class="form-row-item form-row-item-wide">
            <ElInput v-model="formData.host" placeholder="IP 地址或主机名" />
          </ElFormItem>

          <ElFormItem label="Port" prop="port" class="form-row-item form-row-item-port">
            <ElInputNumber v-model="formData.port" :min="1" :max="65535" style="width: 100%" />
          </ElFormItem>
        </div>

        <div class="form-row">
          <ElFormItem label="用户名" prop="username" class="form-row-item">
            <ElInput v-model="formData.username" placeholder="SSH 用户名" />
          </ElFormItem>

          <ElFormItem label="密码" prop="password" class="form-row-item">
            <ElInput
              v-model="formData.password"
              type="password"
              show-password
              :placeholder="dialogMode === 'edit' ? '留空保持当前密码' : 'SSH 密码'"
            />
          </ElFormItem>
        </div>

        <ElFormItem label="Region" prop="region">
          <ElSelect v-model="formData.region" placeholder="Select region" style="width: 100%">
            <ElOption
              v-for="region in REGION_OPTIONS"
              :key="region"
              :label="region"
              :value="region"
            />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="描述" prop="description">
          <ElInput
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="服务器描述（可选）"
          />
        </ElFormItem>

      </ElForm>

      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton @click="dialogVisible = false" class="btn-cancel">取消</ElButton>
          <ElButton type="primary" @click="submitForm" :loading="serversStore.loading" class="btn-primary">
            <ElIcon><component :is="serverDialogCopy.icon" /></ElIcon>
            {{ serverDialogCopy.actionText }}
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- Execute Command Dialog -->
    <ElDialog
      v-model="commandDialogVisible"
      width="640px"
      :close-on-click-modal="false"
      class="enhanced-dialog command-dialog"
    >
      <template #header>
        <div class="dialog-header-enhanced command-header">
          <div class="dialog-header-accent command-accent"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon command-icon">
              <ElIcon :size="20"><Promotion /></ElIcon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">执行命令</h3>
              <p class="dialog-subtitle">
                <ElTag size="small" effect="plain">{{ commandServerName }}</ElTag>
                远程命令执行
              </p>
            </div>
          </div>
        </div>
      </template>
      <div class="command-content-enhanced">
        <div class="command-section-enhanced">
          <div class="command-input-wrapper">
            <ElInput
              v-model="commandInput"
              type="textarea"
              :rows="3"
              placeholder="输入要执行的命令..."
              @keydown.ctrl.enter="executeCommand"
              class="command-input-enhanced"
            />
          </div>
          <div class="command-actions-enhanced">
            <span class="command-hint">Ctrl + Enter 快速执行</span>
            <ElButton
              type="primary"
              @click="executeCommand"
              :loading="commandLoading"
              :disabled="!commandInput.trim()"
              class="btn-primary"
            >
              <ElIcon><Promotion /></ElIcon>
              执行
            </ElButton>
          </div>
        </div>

        <div v-if="commandResult" class="result-section-enhanced">
          <div class="result-header">
            <span class="result-label">执行结果</span>
          </div>
          <ElScrollbar class="result-scroll">
            <pre class="result-output-enhanced">{{ commandResult }}</pre>
          </ElScrollbar>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton @click="commandDialogVisible = false" class="btn-cancel">关闭</ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- Process Management Drawer -->
    <ElDrawer
      v-model="processDrawerVisible"
      :title="`进程管理 - ${currentProcessServer?.name || ''}`"
      size="50%"
      direction="rtl"
    >
      <div class="process-drawer-content">
        <div class="process-controls">
          <ElSelect v-model="processLimit" placeholder="数量" style="width: 80px" size="small" @change="handleProcessLimitChange">
            <ElOption :value="20" label="20" />
            <ElOption :value="50" label="50" />
            <ElOption :value="100" label="100" />
            <ElOption :value="500" label="所有" />
          </ElSelect>
          <ElSelect v-model="processSortBy" placeholder="取值" style="width: 110px" size="small" @change="handleProcessSortChange">
            <ElOption value="cpu" label="CPU（默认）" />
            <ElOption value="memory" label="MEM" />
          </ElSelect>
          <ElButton @click="fetchProcessList" :loading="processLoading" size="small">
            刷新
          </ElButton>
        </div>

        <ElTable
          :data="processList"
          v-loading="processLoading"
          stripe
          style="width: 100%; margin-top: 12px"
          size="small"
          class="process-table"
        >
          <ElTableColumn prop="pid" label="PID" width="70" />
          <ElTableColumn prop="name" label="名称" min-width="180" show-overflow-tooltip />
          <ElTableColumn prop="cpu_percent" label="CPU %" width="90" sortable>
            <template #default="{ row }">
              <span :class="{ 'high-usage': row.cpu_percent > 50 }" style="font-size:12px">
                {{ row.cpu_percent.toFixed(1) }}%
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="memory_percent" label="Mem %" width="90" sortable>
            <template #default="{ row }">
              <span :class="{ 'high-usage': row.memory_percent > 50 }" style="font-size:12px">
                {{ row.memory_percent.toFixed(1) }}%
              </span>
            </template>
          </ElTableColumn>
        </ElTable>

        <ElEmpty v-if="!processLoading && processList.length === 0" description="无进程数据" />
      </div>
    </ElDrawer>
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

.server-count {
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
  align-items: center;
}

.server-table :deep(.el-table__cell) {
  padding: 4px 0;
}

.server-table :deep(.el-table__header-cell) {
  padding: 4px 0;
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.server-type-tag {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

.server-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.name-text {
  font-weight: 500;
  font-size: 12px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.description {
  font-size: 10px;
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
  padding: 1px 3px;
  border-radius: 4px;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.server-table :deep(.host-port-column .cell) {
  padding-left: 4px;
  padding-right: 4px;
}

.server-table :deep(.metric-divider-column .cell) {
  position: relative;
  padding-left: 10px;
}

.server-table :deep(.metric-divider-column .cell::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 25%;
  width: 1px;
  height: 50%;
  background: #cbd5e1;
}

.server-table :deep(.metric-divider-end-column .cell::after) {
  content: '';
  position: absolute;
  right: 0;
  top: 25%;
  width: 1px;
  height: 50%;
  background: #cbd5e1;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 58px;
  height: 18px;
  font-size: 10px;
  padding: 2px 6px;
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

.busy-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 18px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 6px;
}

.busy-tag.busy {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.busy-tag.idle {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.metric-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-start;
  white-space: nowrap;
}

.metric-cell-composite {
  display: grid;
  grid-template-columns: 70px 38px 112px;
  gap: 8px;
}

.metric-cell-composite .metric-bar {
  width: 70px;
}

.metric-cell-composite .metric-value {
  text-align: right;
}

.metric-cell-composite .metric-detail {
  min-width: 0;
  text-align: left;
}

.metric-bar {
  width: 50px;
  height: 4px;
  background: #f0f0f0;
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.metric-value {
  font-weight: 500;
  font-size: 11px;
  color: #303133;
}

.metric-value.high,
.high-usage {
  color: #f56c6c;
}

.metric-detail {
  display: inline-block;
  min-width: 80px;
  font-size: 10px;
  color: #909399;
  text-align: right;
  white-space: nowrap;
}

.metric-error {
  font-weight: 500;
  font-size: 11px;
  color: #c0c4cc;
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

.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
  align-items: center;
  white-space: nowrap;
}

.action-buttons :deep(.el-button) {
  font-size: 18px;
  width: 22px;
  min-width: 22px;
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
  margin-top: 10px;
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

.process-drawer-content {
  padding: 0 16px;
}

.process-controls {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  gap: 8px;
}

.process-table :deep(.el-table__cell),
.process-table :deep(.el-table__header-cell) {
  padding: 4px 0;
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

.command-accent {
  background: linear-gradient(180deg, #8b5cf6 0%, #a78bfa 100%);
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

.command-icon {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
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

.dialog-form-enhanced {
  padding: 8px 0;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row-item {
  flex: 1;
  min-width: 0;
}

.form-row-item-wide {
  flex: 1 1 auto;
}

.form-row-item-port {
  flex: 0 0 150px;
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

/* Command Dialog Enhanced */
.command-content-enhanced {
  padding: 20px 24px;
}

.command-section-enhanced {
  margin-bottom: 20px;
}

.command-input-wrapper {
  margin-bottom: 12px;
}

.command-input-enhanced {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
}

.command-actions-enhanced {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.command-hint {
  font-size: 11px;
  color: #94a3b8;
  padding: 4px 12px;
  background: #f1f5f9;
  border-radius: 6px;
}

.result-section-enhanced {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #1e293b;
}

.result-header {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px 12px 0 0;
}

.result-label {
  font-weight: 500;
  color: #94a3b8;
  font-size: 12px;
}

.result-scroll {
  max-height: 280px;
}

.result-output-enhanced {
  padding: 16px;
  color: #e2e8f0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  min-height: 80px;
}
</style>
