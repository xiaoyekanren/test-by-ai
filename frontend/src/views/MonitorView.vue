<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import {
  ElCard,
  ElRow,
  ElCol,
  ElProgress,
  ElTable,
  ElTableColumn,
  ElSelect,
  ElOption,
  ElButton,
  ElTabs,
  ElTabPane,
  ElEmpty,
  ElTag,
  ElMessage,
  ElMessageBox,
  type Sort
} from 'element-plus'
import { useMonitoringStore } from '@/stores/monitoring'
import { useServersStore } from '@/stores/servers'
import type { ProcessInfo } from '@/types'

const monitoringStore = useMonitoringStore()
const serversStore = useServersStore()

// Local monitoring state
const localLimit = ref(20)
const localSortBy = ref<'cpu' | 'memory'>('cpu')

// Remote monitoring state
const selectedServerId = ref<number | null>(null)
const remoteLimit = ref(20)
const remoteSortBy = ref<'cpu' | 'memory'>('cpu')

// Auto-refresh interval
let refreshInterval: ReturnType<typeof setInterval> | null = null

// Format bytes to human readable
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Get progress bar color based on percentage
function getProgressColor(percent: number): string {
  if (percent < 50) return '#67c23a'
  if (percent < 80) return '#e6a23c'
  return '#f56c6c'
}

// Fetch local data
async function fetchLocalData() {
  await Promise.all([
    monitoringStore.fetchLocalStatus(),
    monitoringStore.fetchLocalProcesses({ limit: localLimit.value, sort_by: localSortBy.value })
  ])
}

// Fetch remote data
async function fetchRemoteData() {
  if (selectedServerId.value) {
    await Promise.all([
      monitoringStore.fetchRemoteStatus(selectedServerId.value),
      monitoringStore.fetchRemoteProcesses(selectedServerId.value, {
        limit: remoteLimit.value,
        sort_by: remoteSortBy.value
      })
    ])
  }
}

// Refresh all data
async function refreshData() {
  await fetchLocalData()
  if (selectedServerId.value) {
    await fetchRemoteData()
  }
}

// Handle local limit change
async function handleLocalLimitChange() {
  await monitoringStore.fetchLocalProcesses({ limit: localLimit.value, sort_by: localSortBy.value })
}

// Handle local sort change
async function handleLocalSortChange() {
  await monitoringStore.fetchLocalProcesses({ limit: localLimit.value, sort_by: localSortBy.value })
}

// Handle remote limit change
async function handleRemoteLimitChange() {
  if (selectedServerId.value) {
    await monitoringStore.fetchRemoteProcesses(selectedServerId.value, {
      limit: remoteLimit.value,
      sort_by: remoteSortBy.value
    })
  }
}

// Handle remote sort change
async function handleRemoteSortChange() {
  if (selectedServerId.value) {
    await monitoringStore.fetchRemoteProcesses(selectedServerId.value, {
      limit: remoteLimit.value,
      sort_by: remoteSortBy.value
    })
  }
}

// Handle server selection change
async function handleServerChange() {
  if (selectedServerId.value) {
    await fetchRemoteData()
  } else {
    monitoringStore.clearRemoteData()
  }
}

// Handle table sort
function handleTableSort(sort: Sort) {
  if (sort.prop === 'cpu_percent') {
    localSortBy.value = sort.order === 'descending' ? 'cpu' : 'cpu'
  } else if (sort.prop === 'memory_percent') {
    localSortBy.value = sort.order === 'descending' ? 'memory' : 'memory'
  }
  handleLocalSortChange()
}

// Kill process
async function handleKillProcess(row: ProcessInfo, isRemote: boolean = false) {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to kill process "${row.name}" (PID: ${row.pid})?`,
      'Confirm Kill Process',
      {
        confirmButtonText: 'Kill',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )

    const result = await monitoringStore.killProcess(row.pid)
    if (result.success) {
      ElMessage.success(`Process ${row.name} (PID: ${row.pid}) killed successfully`)
      // Refresh the process list
      if (isRemote && selectedServerId.value) {
        await monitoringStore.fetchRemoteProcesses(selectedServerId.value, {
          limit: remoteLimit.value,
          sort_by: remoteSortBy.value
        })
      }
    } else {
      ElMessage.error(result.error || 'Failed to kill process')
    }
  } catch {
    // User cancelled
  }
}

// Computed for remote processes
const remoteProcesses = computed(() => {
  return monitoringStore.remoteProcesses?.processes || []
})

// Initialize
onMounted(async () => {
  await serversStore.fetchServers()
  await fetchLocalData()

  // Set up auto-refresh every 5 seconds
  refreshInterval = setInterval(refreshData, 5000)
})

// Cleanup
onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

// Watch for server selection changes
watch(selectedServerId, () => {
  handleServerChange()
})
</script>

<template>
  <div class="monitor-view">
    <ElTabs type="border-card" class="monitor-tabs">
      <!-- Local Server Tab -->
      <ElTabPane label="Local Server">
        <div class="monitor-content">
          <!-- Status Panel -->
          <ElRow :gutter="20" class="status-panel">
            <ElCol :span="8">
              <ElCard shadow="hover" class="status-card">
                <template #header>
                  <div class="card-header">
                    <span>CPU Usage</span>
                    <ElTag :type="monitoringStore.localStatus?.cpu_percent && monitoringStore.localStatus.cpu_percent < 80 ? 'success' : 'danger'">
                      {{ monitoringStore.localStatus?.cpu_percent?.toFixed(1) || 0 }}%
                    </ElTag>
                  </div>
                </template>
                <ElProgress
                  :percentage="monitoringStore.localStatus?.cpu_percent || 0"
                  :color="getProgressColor(monitoringStore.localStatus?.cpu_percent || 0)"
                  :stroke-width="20"
                />
              </ElCard>
            </ElCol>
            <ElCol :span="8">
              <ElCard shadow="hover" class="status-card">
                <template #header>
                  <div class="card-header">
                    <span>Memory Usage</span>
                    <ElTag :type="monitoringStore.localStatus?.memory?.percent && monitoringStore.localStatus.memory.percent < 80 ? 'success' : 'danger'">
                      {{ monitoringStore.localStatus?.memory?.percent?.toFixed(1) || 0 }}%
                    </ElTag>
                  </div>
                </template>
                <ElProgress
                  :percentage="monitoringStore.localStatus?.memory?.percent || 0"
                  :color="getProgressColor(monitoringStore.localStatus?.memory?.percent || 0)"
                  :stroke-width="20"
                />
                <div class="usage-detail">
                  {{ formatBytes(monitoringStore.localStatus?.memory?.used || 0) }} /
                  {{ formatBytes(monitoringStore.localStatus?.memory?.total || 0) }}
                </div>
              </ElCard>
            </ElCol>
            <ElCol :span="8">
              <ElCard shadow="hover" class="status-card">
                <template #header>
                  <div class="card-header">
                    <span>Disk Usage</span>
                    <ElTag :type="monitoringStore.localStatus?.disk?.percent && monitoringStore.localStatus.disk.percent < 80 ? 'success' : 'danger'">
                      {{ monitoringStore.localStatus?.disk?.percent?.toFixed(1) || 0 }}%
                    </ElTag>
                  </div>
                </template>
                <ElProgress
                  :percentage="monitoringStore.localStatus?.disk?.percent || 0"
                  :color="getProgressColor(monitoringStore.localStatus?.disk?.percent || 0)"
                  :stroke-width="20"
                />
                <div class="usage-detail">
                  {{ formatBytes(monitoringStore.localStatus?.disk?.used || 0) }} /
                  {{ formatBytes(monitoringStore.localStatus?.disk?.total || 0) }}
                </div>
              </ElCard>
            </ElCol>
          </ElRow>

          <!-- Process Table -->
          <ElCard shadow="hover" class="process-card">
            <template #header>
              <div class="card-header">
                <span>Processes</span>
                <div class="controls">
                  <ElSelect v-model="localLimit" placeholder="Limit" style="width: 100px" @change="handleLocalLimitChange">
                    <ElOption :value="20" label="20" />
                    <ElOption :value="50" label="50" />
                    <ElOption :value="100" label="100" />
                  </ElSelect>
                  <ElSelect v-model="localSortBy" placeholder="Sort by" style="width: 120px; margin-left: 10px" @change="handleLocalSortChange">
                    <ElOption value="cpu" label="CPU Usage" />
                    <ElOption value="memory" label="Memory Usage" />
                  </ElSelect>
                </div>
              </div>
            </template>
            <ElTable
              :data="monitoringStore.localProcesses"
              stripe
              style="width: 100%"
              v-loading="monitoringStore.loading"
              @sort-change="handleTableSort"
            >
              <ElTableColumn prop="pid" label="PID" width="100" sortable />
              <ElTableColumn prop="name" label="Name" min-width="200" show-overflow-tooltip />
              <ElTableColumn prop="cpu_percent" label="CPU %" width="120" sortable>
                <template #default="{ row }">
                  <span :class="{ 'high-usage': row.cpu_percent > 50 }">
                    {{ row.cpu_percent.toFixed(1) }}%
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn prop="memory_percent" label="Memory %" width="120" sortable>
                <template #default="{ row }">
                  <span :class="{ 'high-usage': row.memory_percent > 50 }">
                    {{ row.memory_percent.toFixed(1) }}%
                  </span>
                </template>
              </ElTableColumn>
              <ElTableColumn label="Actions" width="100" fixed="right">
                <template #default="{ row }">
                  <ElButton
                    type="danger"
                    size="small"
                    @click="handleKillProcess(row)"
                    :disabled="row.pid < 2"
                  >
                    Kill
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </ElCard>
        </div>
      </ElTabPane>

      <!-- Remote Server Tab -->
      <ElTabPane label="Remote Server">
        <div class="monitor-content">
          <!-- Server Selector -->
          <ElCard shadow="hover" class="server-selector-card">
            <template #header>
              <span>Select Remote Server</span>
            </template>
            <div class="server-selector">
              <ElSelect
                v-model="selectedServerId"
                placeholder="Select a server to monitor"
                clearable
                style="width: 300px"
                :loading="serversStore.loading"
              >
                <ElOption
                  v-for="server in serversStore.servers"
                  :key="server.id"
                  :value="server.id"
                  :label="`${server.name} (${server.host})`"
                />
              </ElSelect>
            </div>
          </ElCard>

          <!-- Remote Status Panel -->
          <template v-if="selectedServerId && monitoringStore.remoteStatus">
            <ElRow :gutter="20" class="status-panel">
              <ElCol :span="8">
                <ElCard shadow="hover" class="status-card">
                  <template #header>
                    <div class="card-header">
                      <span>CPU Usage</span>
                      <ElTag :type="monitoringStore.remoteStatus.cpu_percent < 80 ? 'success' : 'danger'">
                        {{ monitoringStore.remoteStatus.cpu_percent?.toFixed(1) || 0 }}%
                      </ElTag>
                    </div>
                  </template>
                  <ElProgress
                    :percentage="monitoringStore.remoteStatus.cpu_percent || 0"
                    :color="getProgressColor(monitoringStore.remoteStatus.cpu_percent || 0)"
                    :stroke-width="20"
                  />
                </ElCard>
              </ElCol>
              <ElCol :span="8">
                <ElCard shadow="hover" class="status-card">
                  <template #header>
                    <div class="card-header">
                      <span>Memory Usage</span>
                      <ElTag :type="monitoringStore.remoteStatus.memory?.percent < 80 ? 'success' : 'danger'">
                        {{ monitoringStore.remoteStatus.memory?.percent?.toFixed(1) || 0 }}%
                      </ElTag>
                    </div>
                  </template>
                  <ElProgress
                    :percentage="monitoringStore.remoteStatus.memory?.percent || 0"
                    :color="getProgressColor(monitoringStore.remoteStatus.memory?.percent || 0)"
                    :stroke-width="20"
                  />
                  <div class="usage-detail">
                    {{ formatBytes(monitoringStore.remoteStatus.memory?.used || 0) }} /
                    {{ formatBytes(monitoringStore.remoteStatus.memory?.total || 0) }}
                  </div>
                </ElCard>
              </ElCol>
              <ElCol :span="8">
                <ElCard shadow="hover" class="status-card">
                  <template #header>
                    <div class="card-header">
                      <span>Disk Usage</span>
                      <ElTag :type="monitoringStore.remoteStatus.disk?.percent < 80 ? 'success' : 'danger'">
                        {{ monitoringStore.remoteStatus.disk?.percent?.toFixed(1) || 0 }}%
                      </ElTag>
                    </div>
                  </template>
                  <ElProgress
                    :percentage="monitoringStore.remoteStatus.disk?.percent || 0"
                    :color="getProgressColor(monitoringStore.remoteStatus.disk?.percent || 0)"
                    :stroke-width="20"
                  />
                  <div class="usage-detail">
                    {{ formatBytes(monitoringStore.remoteStatus.disk?.used || 0) }} /
                    {{ formatBytes(monitoringStore.remoteStatus.disk?.total || 0) }}
                  </div>
                </ElCard>
              </ElCol>
            </ElRow>

            <!-- Remote Process Table -->
            <ElCard shadow="hover" class="process-card">
              <template #header>
                <div class="card-header">
                  <span>Remote Processes - {{ monitoringStore.remoteProcesses?.server_name || '' }} ({{ monitoringStore.remoteProcesses?.host || '' }})</span>
                  <div class="controls">
                    <ElSelect v-model="remoteLimit" placeholder="Limit" style="width: 100px" @change="handleRemoteLimitChange">
                      <ElOption :value="20" label="20" />
                      <ElOption :value="50" label="50" />
                      <ElOption :value="100" label="100" />
                    </ElSelect>
                    <ElSelect v-model="remoteSortBy" placeholder="Sort by" style="width: 120px; margin-left: 10px" @change="handleRemoteSortChange">
                      <ElOption value="cpu" label="CPU Usage" />
                      <ElOption value="memory" label="Memory Usage" />
                    </ElSelect>
                  </div>
                </div>
              </template>
              <ElTable
                :data="remoteProcesses"
                stripe
                style="width: 100%"
                v-loading="monitoringStore.loading"
              >
                <ElTableColumn prop="pid" label="PID" width="100" />
                <ElTableColumn prop="name" label="Name" min-width="200" show-overflow-tooltip />
                <ElTableColumn prop="cpu_percent" label="CPU %" width="120">
                  <template #default="{ row }">
                    <span :class="{ 'high-usage': row.cpu_percent > 50 }">
                      {{ row.cpu_percent.toFixed(1) }}%
                    </span>
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="memory_percent" label="Memory %" width="120">
                  <template #default="{ row }">
                    <span :class="{ 'high-usage': row.memory_percent > 50 }">
                      {{ row.memory_percent.toFixed(1) }}%
                    </span>
                  </template>
                </ElTableColumn>
                <ElTableColumn label="Actions" width="100" fixed="right">
                  <template #default="{ row }">
                    <ElButton
                      type="danger"
                      size="small"
                      @click="handleKillProcess(row, true)"
                      :disabled="row.pid < 2"
                    >
                      Kill
                    </ElButton>
                  </template>
                </ElTableColumn>
              </ElTable>
            </ElCard>
          </template>

          <!-- Empty State -->
          <template v-else-if="!selectedServerId">
            <ElEmpty description="Please select a remote server to monitor" />
          </template>
        </div>
      </ElTabPane>
    </ElTabs>
  </div>
</template>

<style scoped>
.monitor-view {
  padding: 0;
}

.monitor-tabs {
  min-height: calc(100vh - 200px);
}

.monitor-content {
  padding: 0;
}

.status-panel {
  margin-bottom: 20px;
}

.status-card {
  text-align: center;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.usage-detail {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}

.process-card {
  margin-top: 0;
}

.controls {
  display: flex;
  align-items: center;
}

.server-selector-card {
  margin-bottom: 20px;
}

.server-selector {
  display: flex;
  align-items: center;
}

.high-usage {
  color: #f56c6c;
  font-weight: bold;
}
</style>