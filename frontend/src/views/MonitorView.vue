<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  ElCard,
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElDrawer,
  ElSelect,
  ElOption,
  ElMessage,
  ElMessageBox,
  ElProgress,
  ElTooltip,
  ElEmpty
} from 'element-plus'
import { Refresh, View, CircleClose, Warning, SuccessFilled, Link } from '@element-plus/icons-vue'
import { useMonitoringStore } from '@/stores/monitoring'
import { useServersStore } from '@/stores/servers'
import { useSettingsStore } from '@/stores/settings'
import type { ProcessInfo } from '@/types'

const monitoringStore = useMonitoringStore()
const serversStore = useServersStore()
const settingsStore = useSettingsStore()

// Combined server list with local server included
interface MonitorServer {
  id: number | 'local'
  name: string
  host: string
  port: number
  isLocal: boolean
  status: 'online' | 'offline' | 'loading' | 'unknown'
  cpu?: number
  memoryPercent?: number
  memoryUsed?: number
  memoryTotal?: number
  diskPercent?: number
  diskUsed?: number
  diskTotal?: number
}

const monitorServers = ref<MonitorServer[]>([])
const loading = ref(true)
const refreshInterval = ref<ReturnType<typeof setInterval> | null>(null)

// Process drawer state
const processDrawerVisible = ref(false)
const currentServerForProcess = ref<MonitorServer | null>(null)
const processList = ref<ProcessInfo[]>([])
const processLoading = ref(false)
const processLimit = ref(20)
const processSortBy = ref<'cpu' | 'memory'>('cpu')

function openExternalUrl(url: string | null | undefined) {
  if (!url) {
    ElMessage.warning('Configure the URL first in System Settings')
    return
  }

  window.open(url, '_blank', 'noopener,noreferrer')
}

// Build combined server list
function buildServerList() {
  // Start with local server
  const servers: MonitorServer[] = [
    {
      id: 'local',
      name: 'Local Server',
      host: 'localhost',
      port: 0,
      isLocal: true,
      status: 'loading'
    }
  ]

  // Add remote servers
  serversStore.servers.forEach(server => {
    servers.push({
      id: server.id,
      name: server.name,
      host: server.host,
      port: server.port,
      isLocal: false,
      status: server.status === 'online' ? 'online' : 'unknown'
    })
  })

  monitorServers.value = servers
}

// Format bytes to human readable
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Get progress bar color based on percentage
function getProgressColor(percent: number): string {
  if (percent < 50) return '#67c23a'
  if (percent < 80) return '#e6a23c'
  return '#f56c6c'
}

// Get status icon type
function getStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'online': return 'success'
    case 'loading': return 'warning'
    case 'offline': return 'danger'
    default: return 'info'
  }
}

// Fetch all server statuses (initial load)
async function fetchAllStatuses() {
  // Build parallel promises for all servers
  const promises: Promise<void>[] = []
  const updatedServers: MonitorServer[] = monitorServers.value.map(s => ({ ...s, status: 'loading' as MonitorServer['status'] }))

  // Local server
  const localIdx = updatedServers.findIndex(s => s.id === 'local')
  if (localIdx !== -1) {
    const localServer = updatedServers[localIdx]
    promises.push(
      monitoringStore.fetchLocalStatus()
        .then(status => {
          if (status) {
            updatedServers[localIdx] = {
              ...localServer,
              status: 'online',
              cpu: status.cpu_percent,
              memoryPercent: status.memory.percent,
              memoryUsed: status.memory.used,
              memoryTotal: status.memory.total,
              diskPercent: status.disk.percent,
              diskUsed: status.disk.used,
              diskTotal: status.disk.total
            }
          }
        })
        .catch(() => {
          updatedServers[localIdx] = { ...localServer, status: 'offline' }
        })
    )
  }

  // Remote servers - parallel fetch
  updatedServers.forEach((server, idx) => {
    if (!server.isLocal) {
      promises.push(
        monitoringStore.fetchRemoteStatus(server.id as number)
          .then(status => {
            if (status) {
              updatedServers[idx] = {
                ...server,
                status: 'online',
                cpu: status.cpu_percent,
                memoryPercent: status.memory?.percent,
                memoryUsed: status.memory?.used,
                memoryTotal: status.memory?.total,
                diskPercent: status.disk?.percent,
                diskUsed: status.disk?.used,
                diskTotal: status.disk?.total
              }
            }
          })
          .catch(() => {
            updatedServers[idx] = { ...server, status: 'offline' }
          })
      )
    }
  })

  // Execute all in parallel
  await Promise.all(promises)
  // Replace entire array
  monitorServers.value = updatedServers
}

// Refresh all data - stream update, each server updates independently
function refreshData() {
  // Set all servers to loading state (keep existing data)
  monitorServers.value = monitorServers.value.map(s => ({
    ...s,
    status: 'loading' as MonitorServer['status']
  }))

  // Local server
  const localIdx = monitorServers.value.findIndex(s => s.id === 'local')
  if (localIdx !== -1) {
    monitoringStore.fetchLocalStatus()
      .then(status => {
        if (status) {
          const updated = [...monitorServers.value]
          updated[localIdx] = {
            ...updated[localIdx],
            status: 'online',
            cpu: status.cpu_percent,
            memoryPercent: status.memory.percent,
            memoryUsed: status.memory.used,
            memoryTotal: status.memory.total,
            diskPercent: status.disk.percent,
            diskUsed: status.disk.used,
            diskTotal: status.disk.total
          }
          monitorServers.value = updated
        }
      })
      .catch(() => {
        const updated = [...monitorServers.value]
        updated[localIdx] = { ...updated[localIdx], status: 'offline' }
        monitorServers.value = updated
      })
  }

  // Remote servers - each updates independently
  monitorServers.value.forEach((server, idx) => {
    if (!server.isLocal) {
      monitoringStore.fetchRemoteStatus(server.id as number)
        .then(status => {
          if (status) {
            const updated = [...monitorServers.value]
            updated[idx] = {
              ...updated[idx],
              status: 'online',
              cpu: status.cpu_percent,
              memoryPercent: status.memory?.percent,
              memoryUsed: status.memory?.used,
              memoryTotal: status.memory?.total,
              diskPercent: status.disk?.percent,
              diskUsed: status.disk?.used,
              diskTotal: status.disk?.total
            }
            monitorServers.value = updated
          }
        })
        .catch(() => {
          const updated = [...monitorServers.value]
          updated[idx] = { ...updated[idx], status: 'offline' }
          monitorServers.value = updated
        })
    }
  })
}

// Open process drawer for a server
async function openProcessDrawer(server: MonitorServer) {
  currentServerForProcess.value = server
  processDrawerVisible.value = true
  processList.value = []
  await fetchProcessList()
}

// Fetch process list
async function fetchProcessList() {
  if (!currentServerForProcess.value) return

  processLoading.value = true
  try {
    if (currentServerForProcess.value.isLocal) {
      processList.value = await monitoringStore.fetchLocalProcesses({
        limit: processLimit.value,
        sort_by: processSortBy.value
      })
    } else {
      const result = await monitoringStore.fetchRemoteProcesses(
        currentServerForProcess.value.id as number,
        { limit: processLimit.value, sort_by: processSortBy.value }
      )
      processList.value = result?.processes || []
    }
  } catch (e) {
    ElMessage.error('Failed to fetch process list')
    processList.value = []
  } finally {
    processLoading.value = false
  }
}

// Handle limit/sort change
async function handleProcessLimitChange() {
  await fetchProcessList()
}

async function handleProcessSortChange() {
  await fetchProcessList()
}

// Kill process
async function handleKillProcess(row: ProcessInfo) {
  try {
    await ElMessageBox.confirm(
      `Kill process "${row.name}" (PID: ${row.pid})?`,
      'Confirm Kill',
      { confirmButtonText: 'Kill', cancelButtonText: 'Cancel', type: 'warning' }
    )

    // Only local kill supported for now
    if (currentServerForProcess.value?.isLocal) {
      const result = await monitoringStore.killProcess(row.pid)
      if (result.success) {
        ElMessage.success(`Process ${row.name} killed`)
        await fetchProcessList()
      } else {
        ElMessage.error(result.error || 'Failed to kill process')
      }
    } else {
      ElMessage.warning('Remote process kill not supported yet')
    }
  } catch {
    // User cancelled
  }
}

// Initialize
onMounted(async () => {
  loading.value = true
  try {
    await settingsStore.fetchSettings()
    await serversStore.fetchServers()
    buildServerList()
    await fetchAllStatuses()
  } finally {
    loading.value = false
  }

  // Auto refresh based on settings
  startAutoRefresh()
})

// Start auto refresh with current settings
function startAutoRefresh() {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
  const intervalMs = settingsStore.settings.monitor.refreshInterval * 1000
  refreshInterval.value = setInterval(refreshData, intervalMs)
}

// Cleanup
onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})

// Watch servers list changes
watch(() => serversStore.servers, () => {
  buildServerList()
}, { deep: true })

// Watch settings changes
watch(() => settingsStore.settings.monitor.refreshInterval, () => {
  startAutoRefresh()
})
</script>

<template>
  <div class="monitor-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>System Monitor</h2>
        <span class="server-count">{{ monitorServers.length }} servers</span>
        <span class="refresh-info">每 {{ settingsStore.settings.monitor.refreshInterval }}s 刷新</span>
      </div>
      <div class="toolbar-actions">
        <ElButton
          v-if="settingsStore.settings.observability.prometheusUrl"
          @click="openExternalUrl(settingsStore.settings.observability.prometheusUrl)"
          :icon="Link"
        >
          Prometheus
        </ElButton>
        <ElButton
          v-if="settingsStore.settings.observability.grafanaUrl"
          @click="openExternalUrl(settingsStore.buildGrafanaDashboardUrl())"
          :icon="Link"
        >
          Grafana
        </ElButton>
        <ElButton @click="refreshData" :icon="Refresh">
          Refresh
        </ElButton>
      </div>
    </div>

    <!-- Server Monitor Table -->
    <ElCard shadow="hover">
      <ElTable
        :data="monitorServers"
        stripe
        style="width: 100%"
      >
        <!-- Server Info -->
        <ElTableColumn label="Server" min-width="180">
          <template #default="{ row }">
            <div class="server-info">
              <ElTag :type="row.isLocal ? 'warning' : 'info'" size="small">
                {{ row.isLocal ? 'LOCAL' : 'SSH' }}
              </ElTag>
              <span class="server-name">{{ row.name }}</span>
              <span class="server-host">{{ row.host }}{{ row.port ? `:${row.port}` : '' }}</span>
            </div>
          </template>
        </ElTableColumn>

        <!-- CPU -->
        <ElTableColumn label="CPU" width="140" align="center">
          <template #default="{ row }">
            <div class="metric-cell" v-if="row.cpu !== undefined">
              <ElProgress
                :percentage="row.cpu || 0"
                :color="getProgressColor(row.cpu || 0)"
                :stroke-width="6"
                :show-text="false"
                style="width: 60px"
              />
              <span class="metric-value" :class="{ 'high-usage': row.cpu > 80 }">
                {{ (row.cpu || 0).toFixed(1) }}%
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Memory -->
        <ElTableColumn label="Memory" width="160" align="center">
          <template #default="{ row }">
            <div class="metric-cell" v-if="row.memoryPercent !== undefined">
              <ElProgress
                :percentage="row.memoryPercent || 0"
                :color="getProgressColor(row.memoryPercent || 0)"
                :stroke-width="6"
                :show-text="false"
                style="width: 60px"
              />
              <span class="metric-value" :class="{ 'high-usage': row.memoryPercent > 80 }">
                {{ (row.memoryPercent || 0).toFixed(1) }}%
              </span>
              <span class="metric-detail">
                {{ formatBytes(row.memoryUsed || 0) }}/{{ formatBytes(row.memoryTotal || 0) }}
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Disk / -->
        <ElTableColumn label="Disk /" width="160" align="center">
          <template #default="{ row }">
            <div class="metric-cell" v-if="row.diskPercent !== undefined">
              <ElProgress
                :percentage="row.diskPercent || 0"
                :color="getProgressColor(row.diskPercent || 0)"
                :stroke-width="6"
                :show-text="false"
                style="width: 60px"
              />
              <span class="metric-value" :class="{ 'high-usage': row.diskPercent > 80 }">
                {{ (row.diskPercent || 0).toFixed(1) }}%
              </span>
              <span class="metric-detail">
                {{ formatBytes(row.diskUsed || 0) }}/{{ formatBytes(row.diskTotal || 0) }}
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Status -->
        <ElTableColumn label="Status" width="100" align="center">
          <template #default="{ row }">
            <ElTag :type="getStatusType(row.status)" size="small" class="status-tag">
              <span v-if="row.status === 'loading'" class="status-icon spinning">◐</span>
              <component v-else :is="row.status === 'online' ? SuccessFilled : (row.status === 'offline' ? CircleClose : Warning)" class="status-icon" />
              {{ row.status }}
            </ElTag>
          </template>
        </ElTableColumn>

        <!-- Actions -->
        <ElTableColumn label="Actions" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <ElTooltip content="View Processes" placement="top">
              <ElButton
                size="small"
                :icon="View"
                @click="openProcessDrawer(row)"
                :disabled="row.status !== 'online'"
              >
                Processes
              </ElButton>
            </ElTooltip>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- Process Management Drawer -->
    <ElDrawer
      v-model="processDrawerVisible"
      :title="`Processes - ${currentServerForProcess?.name || ''}`"
      size="50%"
      direction="rtl"
    >
      <div class="process-drawer-content">
        <!-- Controls -->
        <div class="process-controls">
          <ElSelect v-model="processLimit" placeholder="Limit" style="width: 100px" @change="handleProcessLimitChange">
            <ElOption :value="20" label="20" />
            <ElOption :value="50" label="50" />
            <ElOption :value="100" label="100" />
          </ElSelect>
          <ElSelect v-model="processSortBy" placeholder="Sort by" style="width: 120px; margin-left: 10px" @change="handleProcessSortChange">
            <ElOption value="cpu" label="CPU Usage" />
            <ElOption value="memory" label="Memory Usage" />
          </ElSelect>
          <ElButton @click="fetchProcessList" :loading="processLoading" style="margin-left: 10px">
            Refresh
          </ElButton>
        </div>

        <!-- Process Table -->
        <ElTable
          :data="processList"
          v-loading="processLoading"
          stripe
          max-height="500"
          style="width: 100%; margin-top: 16px"
        >
          <ElTableColumn prop="pid" label="PID" width="80" />
          <ElTableColumn prop="name" label="Name" min-width="200" show-overflow-tooltip />
          <ElTableColumn prop="cpu_percent" label="CPU %" width="100">
            <template #default="{ row }">
              <span :class="{ 'high-usage': row.cpu_percent > 50 }">
                {{ row.cpu_percent.toFixed(1) }}%
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="memory_percent" label="Mem %" width="100">
            <template #default="{ row }">
              <span :class="{ 'high-usage': row.memory_percent > 50 }">
                {{ row.memory_percent.toFixed(1) }}%
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Action" width="80" fixed="right">
            <template #default="{ row }">
              <ElButton
                type="danger"
                size="small"
                @click="handleKillProcess(row)"
                :disabled="row.pid < 2 || !currentServerForProcess?.isLocal"
              >
                Kill
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>

        <ElEmpty v-if="!processLoading && processList.length === 0" description="No processes found" />
      </div>
    </ElDrawer>
  </div>
</template>

<style scoped>
.monitor-view {
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

.refresh-info {
  font-size: 12px;
  color: #c0c4cc;
  padding: 2px 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.server-name {
  font-weight: 500;
  color: #303133;
}

.server-host {
  font-size: 12px;
  color: #909399;
  font-family: 'Monaco', 'Menlo', monospace;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-icon {
  width: 12px;
  height: 12px;
  font-size: 12px;
}

.status-icon.spinning {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.metric-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}

.metric-value {
  font-weight: 600;
  font-size: 13px;
}

.metric-detail {
  font-size: 11px;
  color: #909399;
  width: 100%;
  text-align: center;
}

.metric-error {
  color: #c0c4cc;
}

.high-usage {
  color: #f56c6c;
}

.process-drawer-content {
  padding: 0 20px;
}

.process-controls {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
</style>
