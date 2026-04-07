<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import {
  ElSelect,
  ElOption,
  ElInput,
  ElButton,
  ElTabs,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElMessage,
  ElMessageBox,
  ElTag,
  ElTooltip,
  ElRadioGroup,
  ElRadioButton,
  vLoading
} from 'element-plus'
import { Refresh, VideoPlay, Document, Setting, Platform } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import { useIoTDBStore } from '@/stores/iotdb'
import type { Server } from '@/types'

const serversStore = useServersStore()
const iotdbStore = useIoTDBStore()

// Control state
const selectedServerId = ref<number | null>(null)
const iotdbHome = ref('')
const activeTab = ref('cli')

// CLI state
const sqlInput = ref('')

// Log state
const selectedLogFile = ref('')
const logTailLines = ref(500)

// Config state
const selectedConfigFile = ref('')
const configEditorContent = ref('')
const configEditMode = ref(false)

// Computed
const selectedServer = computed(() => {
  return serversStore.servers.find(s => s.id === selectedServerId.value)
})

const connectionReady = computed(() => {
  return selectedServerId.value && iotdbHome.value.trim()
})

// Load servers on mount
onMounted(async () => {
  await serversStore.fetchServers()
})

// Watch server change to clear state
watch(selectedServerId, () => {
  iotdbStore.clearState()
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditMode.value = false
})

// CLI: Execute SQL
async function executeSQL() {
  if (!connectionReady.value || !sqlInput.value.trim()) return

  try {
    await iotdbStore.executeCLI(
      selectedServerId.value!,
      iotdbHome.value.trim(),
      sqlInput.value.trim(),
      120
    )
  } catch (error) {
    ElMessage.error('Failed to execute SQL')
  }
}

// CLI: Clear result
function clearCLIResult() {
  iotdbStore.cliResult = null
  sqlInput.value = ''
}

// Logs: Refresh file list
async function refreshLogFiles() {
  if (!connectionReady.value) return

  try {
    await iotdbStore.listLogFiles(selectedServerId.value!, iotdbHome.value.trim())
  } catch (error) {
    ElMessage.error('Failed to list log files')
  }
}

// Logs: Load log content
async function loadLogFile(path: string) {
  selectedLogFile.value = path
  try {
    await iotdbStore.readLogFile(selectedServerId.value!, path, logTailLines.value)
  } catch (error) {
    ElMessage.error('Failed to read log file')
  }
}

// Logs: Refresh current log
async function refreshCurrentLog() {
  if (!selectedLogFile.value) return
  await loadLogFile(selectedLogFile.value)
}

// Configs: Refresh file list
async function refreshConfigFiles() {
  if (!connectionReady.value) return

  try {
    await iotdbStore.listConfigFiles(selectedServerId.value!, iotdbHome.value.trim())
  } catch (error) {
    ElMessage.error('Failed to list config files')
  }
}

// Configs: Load config content
async function loadConfigFile(path: string) {
  selectedConfigFile.value = path
  configEditMode.value = false
  try {
    await iotdbStore.readConfigFile(selectedServerId.value!, path)
    configEditorContent.value = iotdbStore.configContent
  } catch (error) {
    ElMessage.error('Failed to read config file')
  }
}

// Configs: Enter edit mode
function enterEditMode() {
  configEditMode.value = true
  configEditorContent.value = iotdbStore.configContent
}

// Configs: Cancel edit
function cancelEdit() {
  configEditMode.value = false
  configEditorContent.value = iotdbStore.configContent
}

// Configs: Save config
async function saveConfig() {
  if (!selectedConfigFile.value) return

  try {
    const result = await iotdbStore.writeConfigFile(
      selectedServerId.value!,
      selectedConfigFile.value,
      configEditorContent.value
    )
    if (result.success) {
      ElMessage.success('Config saved successfully')
      configEditMode.value = false
    }
  } catch (error) {
    ElMessage.error('Failed to save config')
  }
}

// Restart IoTDB
async function restartIoTDB() {
  if (!connectionReady.value) return

  try {
    await ElMessageBox.confirm(
      'Are you sure you want to restart IoTDB?',
      'Confirm Restart',
      {
        confirmButtonText: 'Restart',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )

    const result = await iotdbStore.restartIoTDB(selectedServerId.value!, iotdbHome.value.trim())
    if (result.success) {
      ElMessage.success('IoTDB restarted successfully')
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to restart IoTDB')
    }
  }
}

// Format file size
function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="iotdb-view">
    <!-- Top Control Bar -->
    <div class="control-bar">
      <div class="control-left">
        <ElSelect
          v-model="selectedServerId"
          placeholder="选择服务器"
          style="width: 200px"
          clearable
        >
          <ElOption
            v-for="server in serversStore.servers"
            :key="server.id"
            :label="server.name"
            :value="server.id"
          />
        </ElSelect>

        <ElInput
          v-model="iotdbHome"
          placeholder="IoTDB 安装目录 (如 /opt/iotdb)"
          style="width: 300px"
          clearable
        />

        <ElTag v-if="selectedServer" type="info" size="small">
          {{ selectedServer.host }}:{{ selectedServer.port }}
        </ElTag>
      </div>

      <div class="control-right">
        <ElButton
          type="warning"
          :icon="Refresh"
          @click="restartIoTDB"
          :disabled="!connectionReady"
          :loading="iotdbStore.loading"
        >
          重启 IoTDB
        </ElButton>
      </div>
    </div>

    <!-- Tab Area -->
    <ElTabs v-model="activeTab" class="iotdb-tabs" v-if="connectionReady">
      <!-- CLI Execution Tab -->
      <ElTabPane label="CLI 执行" name="cli">
        <div class="cli-section">
          <div class="cli-input">
            <ElInput
              v-model="sqlInput"
              type="textarea"
              :rows="4"
              placeholder="输入 SQL 命令，如: SHOW DEVICES, SHOW TIMESERIES..."
              @keydown.ctrl.enter="executeSQL"
            />
            <div class="cli-actions">
              <ElButton
                type="primary"
                :icon="VideoPlay"
                @click="executeSQL"
                :loading="iotdbStore.cliLoading"
                :disabled="!sqlInput.trim()"
              >
                执行 (Ctrl+Enter)
              </ElButton>
              <ElButton @click="clearCLIResult">
                清除
              </ElButton>
            </div>
          </div>

          <div class="cli-result" v-if="iotdbStore.cliResult">
            <div class="result-header">
              <span>执行结果</span>
              <ElTag :type="iotdbStore.cliResult.exit_status === 0 ? 'success' : 'danger'" size="small">
                Exit: {{ iotdbStore.cliResult.exit_status }}
              </ElTag>
            </div>
            <pre class="result-output">{{ iotdbStore.cliResult.stdout || iotdbStore.cliResult.stderr || iotdbStore.cliResult.error }}</pre>
          </div>
        </div>
      </ElTabPane>

      <!-- Log Management Tab -->
      <ElTabPane label="日志管理" name="logs">
        <div class="logs-section">
          <div class="logs-toolbar">
            <ElRadioGroup v-model="logTailLines" size="small">
              <ElRadioButton :value="100">最近 100 行</ElRadioButton>
              <ElRadioButton :value="500">最近 500 行</ElRadioButton>
              <ElRadioButton :value="0">全部</ElRadioButton>
            </ElRadioGroup>
            <ElButton
              :icon="Refresh"
              @click="refreshLogFiles"
              :loading="iotdbStore.logsLoading"
            >
              刷新列表
            </ElButton>
          </div>

          <div class="logs-content">
            <ElTable
              :data="iotdbStore.logFiles"
              v-loading="iotdbStore.logsLoading"
              stripe
              size="small"
              style="width: 100%"
            >
              <ElTableColumn prop="name" label="文件名" min-width="200">
                <template #default="{ row }">
                  <span class="file-name">{{ row.name }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn label="大小" width="100">
                <template #default="{ row }">
                  {{ formatSize(row.size) }}
                </template>
              </ElTableColumn>
              <ElTableColumn label="操作" width="120">
                <template #default="{ row }">
                  <ElButton
                    size="small"
                    type="primary"
                    :icon="Document"
                    @click="loadLogFile(row.path)"
                  >
                    查看
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>

          <div class="log-preview" v-if="iotdbStore.logContent">
            <div class="preview-header">
              <span>{{ selectedLogFile }}</span>
              <ElButton
                size="small"
                :icon="Refresh"
                @click="refreshCurrentLog"
                :loading="iotdbStore.logsLoading"
              >
                刷新
              </ElButton>
            </div>
            <pre class="log-output">{{ iotdbStore.logContent }}</pre>
          </div>
        </div>
      </ElTabPane>

      <!-- Config Management Tab -->
      <ElTabPane label="配置管理" name="configs">
        <div class="configs-section">
          <div class="configs-toolbar">
            <ElButton
              :icon="Refresh"
              @click="refreshConfigFiles"
              :loading="iotdbStore.configsLoading"
            >
              刷新列表
            </ElButton>
          </div>

          <div class="configs-content">
            <ElTable
              :data="iotdbStore.configFiles"
              v-loading="iotdbStore.configsLoading"
              stripe
              size="small"
              style="width: 100%"
            >
              <ElTableColumn prop="name" label="文件名" min-width="250">
                <template #default="{ row }">
                  <span class="file-name">{{ row.name }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn label="大小" width="100">
                <template #default="{ row }">
                  {{ formatSize(row.size) }}
                </template>
              </ElTableColumn>
              <ElTableColumn label="操作" width="120">
                <template #default="{ row }">
                  <ElButton
                    size="small"
                    type="primary"
                    :icon="Setting"
                    @click="loadConfigFile(row.path)"
                  >
                    编辑
                  </ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
          </div>

          <div class="config-editor" v-if="iotdbStore.configContent">
            <div class="editor-header">
              <span>{{ selectedConfigFile }}</span>
              <div class="editor-actions">
                <ElButton
                  v-if="!configEditMode"
                  size="small"
                  type="primary"
                  @click="enterEditMode"
                >
                  进入编辑
                </ElButton>
                <template v-else>
                  <ElButton
                    size="small"
                    type="success"
                    @click="saveConfig"
                    :loading="iotdbStore.configSaving"
                  >
                    保存
                  </ElButton>
                  <ElButton
                    size="small"
                    @click="cancelEdit"
                  >
                    取消
                  </ElButton>
                </template>
              </div>
            </div>
            <ElInput
              v-if="configEditMode"
              v-model="configEditorContent"
              type="textarea"
              :rows="20"
              class="config-textarea"
            />
            <pre v-else class="config-output">{{ iotdbStore.configContent }}</pre>
          </div>
        </div>
      </ElTabPane>
    </ElTabs>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <el-icon :size="64"><Platform /></el-icon>
      <p>请选择服务器并输入 IoTDB 安装目录</p>
    </div>
  </div>
</template>

<style scoped>
.iotdb-view {
  padding: 0;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.control-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-right {
  display: flex;
  gap: 10px;
}

.iotdb-tabs {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 20px;
}

/* CLI Section */
.cli-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cli-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cli-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cli-result {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
}

.result-output {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}

/* Logs Section */
.logs-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.logs-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logs-content {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.log-preview {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 13px;
}

.log-output {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 500px;
  overflow-y: auto;
  margin: 0;
}

/* Configs Section */
.configs-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.configs-toolbar {
  display: flex;
  justify-content: flex-end;
}

.configs-content {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.config-editor {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 13px;
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.config-textarea {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
}

.config-textarea :deep(textarea) {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.config-output {
  background: #f5f7fa;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 500px;
  overflow-y: auto;
  margin: 0;
}

.file-name {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  color: #909399;
  gap: 16px;
}

.empty-state p {
  font-size: 16px;
  margin: 0;
}
</style>