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
  ElTooltip,
  ElEmpty
} from 'element-plus'
import { Refresh, Reading, Link } from '@element-plus/icons-vue'
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
const refreshing = ref(false)
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

function sortByMetric(key: 'cpu' | 'memoryPercent' | 'diskPercent') {
  return (a: MonitorServer, b: MonitorServer) => (a[key] ?? -1) - (b[key] ?? -1)
}

// Fetch all server statuses (initial load)
async function fetchAllStatuses() {
  // Build parallel promises for all servers
  const promises: Promise<void>[] = []
  monitorServers.value = monitorServers.value.map(s => ({ ...s, status: 'loading' as MonitorServer['status'] }))

  // Local server
  const localIdx = monitorServers.value.findIndex(s => s.id === 'local')
  if (localIdx !== -1) {
    promises.push(
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
    )
  }

  // Remote servers - parallel fetch
  monitorServers.value.forEach((server, idx) => {
    if (!server.isLocal) {
      promises.push(
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
      )
    }
  })

  // Execute all in parallel
  await Promise.allSettled(promises)
}

// Refresh all data - stream update, each server updates independently
async function refreshData() {
  if (refreshing.value) return

  refreshing.value = true
  monitorServers.value = monitorServers.value.map(s => ({
    ...s,
    status: 'loading' as MonitorServer['status']
  }))

  const requests: Promise<void>[] = []

  try {
    // Local server
    const localIdx = monitorServers.value.findIndex(s => s.id === 'local')
    if (localIdx !== -1) {
      requests.push(
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
      )
    }

    // Remote servers - each updates independently
    monitorServers.value.forEach((server, idx) => {
      if (!server.isLocal) {
        requests.push(
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
        )
      }
    })

    await Promise.allSettled(requests)
  } finally {
    refreshing.value = false
  }
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

// Handle process query changes
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
        <h2>📊 系统监控</h2>
        <span class="server-count">{{ monitorServers.length }} 台</span>
        <span class="refresh-info">{{ settingsStore.settings.monitor.refreshInterval }}s 刷新</span>
      </div>
      <div class="toolbar-actions">
        <ElButton
          v-if="settingsStore.settings.observability.prometheusUrl"
          @click="openExternalUrl(settingsStore.settings.observability.prometheusUrl)"
          :icon="Link"
          size="small"
        >
          Prometheus
        </ElButton>
        <ElButton
          v-if="settingsStore.settings.observability.grafanaUrl"
          @click="openExternalUrl(settingsStore.buildGrafanaDashboardUrl())"
          :icon="Link"
          size="small"
        >
          Grafana
        </ElButton>
        <ElButton
          @click="refreshData"
          :icon="Refresh"
          :loading="refreshing"
          size="small"
          type="primary"
        >
          刷新
        </ElButton>
      </div>
    </div>

    <!-- Server Monitor Table -->
    <ElCard shadow="hover" class="monitor-card">
      <ElTable
        :data="monitorServers"
        class="monitor-table"
        stripe
        style="width: 100%"
        :fit="false"
      >
        <!-- Server Info -->
        <ElTableColumn label="Server" width="340" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="server-info">
              <ElTag :type="row.isLocal ? 'warning' : 'info'" size="small" class="server-type-tag">
                {{ row.isLocal ? 'LOCAL' : 'SSH' }}
              </ElTag>
              <span class="server-name">{{ row.name }}</span>
              <span v-if="!row.isLocal" class="server-host">{{ row.host }}:{{ row.port }}</span>
            </div>
          </template>
        </ElTableColumn>

        <!-- CPU -->
        <ElTableColumn
          label="CPU"
          prop="cpu"
          width="100"
          align="center"
          sortable
          :sort-method="sortByMetric('cpu')"
        >
          <template #default="{ row }">
            <div class="metric-cell" v-if="row.cpu !== undefined">
              <div class="metric-bar">
                <div class="bar-fill" :style="{ width: `${row.cpu || 0}%`, background: getProgressColor(row.cpu || 0) }"></div>
              </div>
              <span class="metric-value" :class="{ high: row.cpu > 80 }">
                {{ Math.round(row.cpu || 0) }}%
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Memory -->
        <ElTableColumn
          label="Memory"
          prop="memoryPercent"
          width="240"
          align="center"
          sortable
          :sort-method="sortByMetric('memoryPercent')"
        >
          <template #default="{ row }">
            <div class="metric-cell metric-cell-composite" v-if="row.memoryPercent !== undefined">
              <div class="metric-bar">
                <div class="bar-fill" :style="{ width: `${row.memoryPercent || 0}%`, background: getProgressColor(row.memoryPercent || 0) }"></div>
              </div>
              <span class="metric-value" :class="{ high: row.memoryPercent > 80 }">
                {{ Math.round(row.memoryPercent || 0) }}%
              </span>
              <span v-if="row.memoryUsed !== undefined && row.memoryTotal !== undefined" class="metric-detail">
                {{ formatBytes(row.memoryUsed) }}/{{ formatBytes(row.memoryTotal) }}
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Disk -->
        <ElTableColumn
          label="Disk"
          prop="diskPercent"
          width="240"
          align="center"
          sortable
          :sort-method="sortByMetric('diskPercent')"
        >
          <template #default="{ row }">
            <div class="metric-cell metric-cell-composite" v-if="row.diskPercent !== undefined">
              <div class="metric-bar">
                <div class="bar-fill" :style="{ width: `${row.diskPercent || 0}%`, background: getProgressColor(row.diskPercent || 0) }"></div>
              </div>
              <span class="metric-value" :class="{ high: row.diskPercent > 80 }">
                {{ Math.round(row.diskPercent || 0) }}%
              </span>
              <span v-if="row.diskUsed !== undefined && row.diskTotal !== undefined" class="metric-detail">
                {{ formatBytes(row.diskUsed) }}/{{ formatBytes(row.diskTotal) }}
              </span>
            </div>
            <span v-else class="metric-error">-</span>
          </template>
        </ElTableColumn>

        <!-- Status -->
        <ElTableColumn label="Status" width="90" align="center">
          <template #default="{ row }">
            <span class="status-tag" :class="row.status">
              <span v-if="row.status === 'loading'" class="status-icon spinning">◐</span>
              <span v-else>●</span>
              {{ row.status }}
            </span>
          </template>
        </ElTableColumn>

        <!-- Actions -->
        <ElTableColumn label="查看进程" width="90" align="center">
          <template #default="{ row }">
            <ElTooltip content="进程管理" placement="top">
              <ElButton
                size="small"
                :icon="Reading"
                @click="openProcessDrawer(row)"
                :disabled="row.status !== 'online'"
                link
              />
            </ElTooltip>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <!-- Process Management Drawer -->
    <ElDrawer
      v-model="processDrawerVisible"
      :title="`进程管理 - ${currentServerForProcess?.name || ''}`"
      size="50%"
      direction="rtl"
    >
      <div class="process-drawer-content">
        <!-- Controls -->
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

        <!-- Process Table -->
        <ElTable
          :data="processList"
          v-loading="processLoading"
          stripe
          style="width: 100%; margin-top: 12px"
          size="small"
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
          <ElTableColumn label="操作" width="70" fixed="right">
            <template #default="{ row }">
              <ElButton
                type="danger"
                size="small"
                @click="handleKillProcess(row)"
                :disabled="row.pid < 2 || !currentServerForProcess?.isLocal"
                link
              >
                Kill
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>

        <ElEmpty v-if="!processLoading && processList.length === 0" description="无进程数据" />
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
  margin-bottom: 12px;
  padding: 10px 16px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.server-count {
  font-size: 11px;
  color: #1890ff;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  padding: 2px 6px;
  border-radius: 10px;
}

.refresh-info {
  font-size: 11px;
  color: #909399;
  margin-left: 4px;
}

.toolbar-actions {
  display: flex;
  gap: 6px;
}

.monitor-card {
  width: 100%;
  margin: 0;
}

.server-info {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  overflow: hidden;
}

.server-name {
  font-weight: 500;
  color: #303133;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.server-host {
  font-size: 10px;
  color: #909399;
  font-family: 'Monaco', 'Menlo', monospace;
  margin-left: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 58px;
  height: 20px;
  line-height: 1;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
}

.status-tag.online {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #c2e7b0;
}

.status-tag.offline {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

.status-tag.loading {
  background: #fdf6ec;
  color: #e6a23c;
  border: 1px solid #faecd8;
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

.metric-value.high {
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

.monitor-table :deep(.el-table__cell) {
  padding: 6px 0;
}

.monitor-table :deep(.el-table__header-cell) {
  padding: 6px 0;
  font-size: 11px;
}

.monitor-table :deep(.el-progress-bar__outer) {
  height: 4px !important;
}

.monitor-table :deep(.el-progress-bar__inner) {
  border-radius: 2px;
}

.high-usage {
  color: #f56c6c;
}

.server-type-tag {
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 600;
}

.server-type-tag.local {
  background: #fdf6ec;
  color: #e6a23c;
}

.server-type-tag.ssh {
  background: #f4f4f5;
  color: #909399;
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
</style>
