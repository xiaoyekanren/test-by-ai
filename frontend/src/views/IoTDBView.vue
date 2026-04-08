<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, computed, watch } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import {
  ElSelect,
  ElOption,
  ElInput,
  ElButton,
  ElTabs,
  ElTabPane,
  ElMessage,
  ElMessageBox,
  ElTag,
  vLoading
} from 'element-plus'
import { Refresh, Document, Setting, Platform } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import { useIoTDBStore } from '@/stores/iotdb'
import { iotdbApi } from '@/api'

const serversStore = useServersStore()
const iotdbStore = useIoTDBStore()

// Control state
const selectedServerId = ref<number | null>(null)
const iotdbHome = ref('')
const activeTab = ref('cli-session')
const LOG_TAIL_LINES = 100
const MAX_LOG_VIEW_CHARS = 256 * 1024
const connected = ref(false)
const connecting = ref(false)

// CLI state
const cliHost = ref('')
const cliPort = ref<number | null>(null)
const cliUsername = ref('')
const cliPassword = ref('')
const persistentCliConnected = ref(false)
const persistentCliConnecting = ref(false)
const persistentTerminalRef = ref<HTMLElement | null>(null)

// Log state
const selectedLogFile = ref('')
const streamingLog = ref(false)
const LOG_PREVIEW_DEFAULT_HEIGHT = 720
const LOG_PREVIEW_MIN_HEIGHT = 360
const LOG_PREVIEW_MAX_HEIGHT = 1200
const LOG_RESIZE_HANDLE_HEIGHT = 18
const logPreviewHeight = ref(LOG_PREVIEW_DEFAULT_HEIGHT)
const resizingLogPreview = ref(false)
const logOutputRef = ref<HTMLElement | null>(null)
let logPreviewResizeStartY = 0
let logPreviewResizeStartHeight = LOG_PREVIEW_DEFAULT_HEIGHT

// Config state
const selectedConfigFile = ref('')
const configEditorContent = ref('')
const configEditMode = ref(false)
const configPreviewHeight = ref(LOG_PREVIEW_DEFAULT_HEIGHT)
const resizingConfigPreview = ref(false)
let configPreviewResizeStartY = 0
let configPreviewResizeStartHeight = LOG_PREVIEW_DEFAULT_HEIGHT

// Computed
const selectedServer = computed(() => {
  return serversStore.servers.find(s => s.id === selectedServerId.value)
})

const connectionReady = computed(() => {
  return Boolean(selectedServerId.value && iotdbHome.value.trim())
})

let logStreamController: AbortController | null = null
let persistentCliSocket: WebSocket | null = null
let persistentTerminal: Terminal | null = null
let persistentFitAddon: FitAddon | null = null
let persistentTerminalResizeObserver: ResizeObserver | null = null
let persistentTerminalResizeFrame: number | null = null

function getErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === 'object') {
    const axiosError = error as { response?: { data?: { detail?: string } }, message?: string }
    return axiosError.response?.data?.detail || axiosError.message || fallback
  }
  return fallback
}

async function readFetchError(response: Response, fallback: string) {
  try {
    const data = await response.json()
    return data.detail || fallback
  } catch {
    return fallback
  }
}

function appendLogContent(chunk: string) {
  iotdbStore.logContent = (iotdbStore.logContent + chunk).slice(-MAX_LOG_VIEW_CHARS)
  nextTick(() => {
    if (!streamingLog.value || !logOutputRef.value) return
    logOutputRef.value.scrollTop = logOutputRef.value.scrollHeight
  })
}

function stopLogStream() {
  logStreamController?.abort()
  logStreamController = null
  streamingLog.value = false
}

function clampLogPreviewHeight(height: number) {
  return Math.min(LOG_PREVIEW_MAX_HEIGHT, Math.max(LOG_PREVIEW_MIN_HEIGHT, height))
}

function handleLogPreviewResizeMove(event: PointerEvent) {
  if (!resizingLogPreview.value) return
  const deltaY = event.clientY - logPreviewResizeStartY
  logPreviewHeight.value = clampLogPreviewHeight(logPreviewResizeStartHeight + deltaY)
}

function stopLogPreviewResize() {
  if (!resizingLogPreview.value) return
  resizingLogPreview.value = false
  document.body.classList.remove('is-resizing-log-preview')
  window.removeEventListener('pointermove', handleLogPreviewResizeMove)
  window.removeEventListener('pointerup', stopLogPreviewResize)
  window.removeEventListener('pointercancel', stopLogPreviewResize)
}

function startLogPreviewResize(event: PointerEvent) {
  event.preventDefault()
  resizingLogPreview.value = true
  logPreviewResizeStartY = event.clientY
  logPreviewResizeStartHeight = logPreviewHeight.value
  document.body.classList.add('is-resizing-log-preview')
  window.addEventListener('pointermove', handleLogPreviewResizeMove)
  window.addEventListener('pointerup', stopLogPreviewResize)
  window.addEventListener('pointercancel', stopLogPreviewResize)
}

function handleConfigPreviewResizeMove(event: PointerEvent) {
  if (!resizingConfigPreview.value) return
  const deltaY = event.clientY - configPreviewResizeStartY
  configPreviewHeight.value = clampLogPreviewHeight(configPreviewResizeStartHeight + deltaY)
}

function stopConfigPreviewResize() {
  if (!resizingConfigPreview.value) return
  resizingConfigPreview.value = false
  document.body.classList.remove('is-resizing-config-preview')
  window.removeEventListener('pointermove', handleConfigPreviewResizeMove)
  window.removeEventListener('pointerup', stopConfigPreviewResize)
  window.removeEventListener('pointercancel', stopConfigPreviewResize)
}

function startConfigPreviewResize(event: PointerEvent) {
  event.preventDefault()
  resizingConfigPreview.value = true
  configPreviewResizeStartY = event.clientY
  configPreviewResizeStartHeight = configPreviewHeight.value
  document.body.classList.add('is-resizing-config-preview')
  window.addEventListener('pointermove', handleConfigPreviewResizeMove)
  window.addEventListener('pointerup', stopConfigPreviewResize)
  window.addEventListener('pointercancel', stopConfigPreviewResize)
}

function writePersistentCliOutput(chunk: string) {
  if (!persistentTerminal) {
    initPersistentTerminal()
  }
  persistentTerminal?.write(chunk)
}

function focusPersistentTerminal() {
  persistentTerminal?.focus()
}

function fitPersistentTerminal(sendResize = true) {
  if (!persistentTerminal || !persistentFitAddon || !persistentTerminalRef.value) return
  try {
    persistentFitAddon.fit()
    if (sendResize && persistentCliSocket?.readyState === WebSocket.OPEN) {
      persistentCliSocket.send(JSON.stringify({
        type: 'resize',
        cols: persistentTerminal.cols,
        rows: persistentTerminal.rows
      }))
    }
  } catch {
    // xterm can throw while its container is hidden during tab transitions.
  }
}

function schedulePersistentTerminalFit(sendResize = true) {
  if (persistentTerminalResizeFrame !== null) {
    window.cancelAnimationFrame(persistentTerminalResizeFrame)
  }
  persistentTerminalResizeFrame = window.requestAnimationFrame(() => {
    persistentTerminalResizeFrame = null
    fitPersistentTerminal(sendResize)
  })
}

function initPersistentTerminal() {
  if (persistentTerminal || !persistentTerminalRef.value) return

  const terminal = new Terminal({
    cursorBlink: true,
    convertEol: true,
    fontFamily: "'Monaco', 'Menlo', 'Consolas', monospace",
    fontSize: 13,
    lineHeight: 1.2,
    scrollback: 5000,
    theme: {
      background: '#101820',
      foreground: '#d7e6f5',
      cursor: '#d7e6f5',
      selectionBackground: '#345b7a'
    }
  })
  const fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(persistentTerminalRef.value)
  terminal.onData(sendPersistentCliInput)

  persistentTerminal = terminal
  persistentFitAddon = fitAddon

  persistentTerminalResizeObserver = new ResizeObserver(() => {
    schedulePersistentTerminalFit()
  })
  persistentTerminalResizeObserver.observe(persistentTerminalRef.value)
  schedulePersistentTerminalFit(false)
}

function disposePersistentTerminal() {
  if (persistentTerminalResizeFrame !== null) {
    window.cancelAnimationFrame(persistentTerminalResizeFrame)
    persistentTerminalResizeFrame = null
  }
  persistentTerminalResizeObserver?.disconnect()
  persistentTerminalResizeObserver = null
  persistentTerminal?.dispose()
  persistentTerminal = null
  persistentFitAddon = null
}

function buildWebSocketUrl(path: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

function closePersistentCliSession(sendDisconnect = true) {
  if (persistentCliSocket) {
    if (sendDisconnect && persistentCliSocket.readyState === WebSocket.OPEN) {
      persistentCliSocket.send(JSON.stringify({ type: 'disconnect' }))
    }
    persistentCliSocket.close()
  }
  persistentCliSocket = null
  persistentCliConnected.value = false
  persistentCliConnecting.value = false
}

// Load servers on mount
onMounted(async () => {
  await serversStore.fetchServers()
})

onUnmounted(() => {
  stopLogStream()
  closePersistentCliSession()
  stopLogPreviewResize()
  stopConfigPreviewResize()
  disposePersistentTerminal()
})

// Watch connection target changes to clear stale state
watch([selectedServerId, () => iotdbHome.value.trim()], () => {
  connected.value = false
  stopLogStream()
  closePersistentCliSession()
  disposePersistentTerminal()
  iotdbStore.clearState()
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditMode.value = false
  cliHost.value = ''
  cliPort.value = null
  persistentTerminal?.clear()
})

watch(activeTab, async (tab) => {
  if (tab !== 'cli-session' || !connected.value) return
  await nextTick()
  initPersistentTerminal()
  schedulePersistentTerminalFit(persistentCliConnected.value)
  focusPersistentTerminal()
})

function parseProperties(content: string) {
  const properties = new Map<string, string>()
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const separatorIndex = line.search(/[:=]/)
    if (separatorIndex === -1) continue
    const key = line.slice(0, separatorIndex).trim()
    const value = line.slice(separatorIndex + 1).trim()
    if (key) properties.set(key, value)
  }
  return properties
}

async function loadCliDefaultsFromConfig() {
  const configPath = `${iotdbHome.value.trim().replace(/\/+$/, '')}/conf/iotdb-system.properties`
  const result = await iotdbApi.readConfig(selectedServerId.value!, iotdbHome.value.trim(), configPath)
  const properties = parseProperties(result.content)
  cliHost.value = properties.get('dn_rpc_address') || properties.get('rpc_address') || ''
  const port = Number(properties.get('dn_rpc_port') || properties.get('rpc_port'))
  cliPort.value = Number.isFinite(port) ? port : null
}

async function reloadConnectedIoTDB() {
  if (!connectionReady.value) return

  connecting.value = true
  try {
    await loadCliDefaultsFromConfig()
    await Promise.all([
      refreshLogFiles(),
      refreshConfigFiles()
    ])
  } finally {
    connecting.value = false
  }
}

async function reloadCurrentConnection() {
  try {
    const reconnectPersistentCli = persistentCliConnected.value
    closePersistentCliSession()
    await reloadConnectedIoTDB()
    if (reconnectPersistentCli) {
      await connectPersistentCliSession()
    }
    ElMessage.success('IoTDB 已重载')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '重载 IoTDB 失败'))
  }
}

async function connectIoTDB() {
  if (!connectionReady.value) return

  try {
    await reloadConnectedIoTDB()
    connected.value = true
    activeTab.value = 'cli-session'
    ElMessage.success('IoTDB 已连接')
  } catch (error) {
    connected.value = false
    ElMessage.error(getErrorMessage(error, '连接 IoTDB 失败'))
  }
}

function disconnectIoTDB() {
  connected.value = false
  stopLogStream()
  closePersistentCliSession()
  disposePersistentTerminal()
  iotdbStore.clearState()
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditMode.value = false
  ElMessage.info('IoTDB 已断开')
}

async function connectPersistentCliSession() {
  if (!connected.value || persistentCliConnecting.value || persistentCliConnected.value) return

  persistentCliConnecting.value = true
  await nextTick()
  initPersistentTerminal()
  persistentTerminal?.clear()

  const rpcPort = Number(cliPort.value)
  const socket = new WebSocket(buildWebSocketUrl('/api/iotdb/cli/session'))
  persistentCliSocket = socket

  await new Promise<void>((resolve, reject) => {
    let settled = false

    socket.onopen = () => {
      socket.send(JSON.stringify({
        server_id: selectedServerId.value,
        iotdb_home: iotdbHome.value.trim(),
        host: cliHost.value.trim() || undefined,
        rpc_port: Number.isFinite(rpcPort) && rpcPort > 0 ? rpcPort : undefined,
        username: cliUsername.value.trim() || undefined,
        cli_password: cliPassword.value || undefined
      }))
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'ready') {
          persistentCliConnected.value = true
          persistentCliConnecting.value = false
          schedulePersistentTerminalFit()
          if (!settled) {
            settled = true
            resolve()
          }
          return
        }
        if (message.type === 'output') {
          writePersistentCliOutput(message.data || '')
          return
        }
        if (message.type === 'error') {
          writePersistentCliOutput(`\r\n${message.message || 'CLI session error'}\r\n`)
          persistentCliConnected.value = false
          persistentCliConnecting.value = false
          if (!settled) {
            settled = true
            reject(new Error(message.message || 'CLI session error'))
          } else {
            ElMessage.error(message.message || 'CLI session error')
          }
          return
        }
        if (message.type === 'exit') {
          persistentCliConnected.value = false
          writePersistentCliOutput('\r\nCLI session exited.\r\n')
        }
      } catch {
        writePersistentCliOutput(String(event.data))
      }
    }

    socket.onerror = () => {
      persistentCliConnected.value = false
      persistentCliConnecting.value = false
      if (!settled) {
        settled = true
        reject(new Error('CLI WebSocket connection failed'))
      }
    }

    socket.onclose = () => {
      if (persistentCliSocket === socket) {
        persistentCliSocket = null
      }
      persistentCliConnected.value = false
      persistentCliConnecting.value = false
      if (!settled) {
        settled = true
        reject(new Error('CLI WebSocket closed'))
      }
    }
  })
}

async function handleConnectPersistentCli() {
  try {
    await connectPersistentCliSession()
    await nextTick()
    focusPersistentTerminal()
    ElMessage.success('长连接 CLI 已连接')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '长连接 CLI 连接失败'))
  }
}

function sendPersistentCliInput(data: string) {
  if (!persistentCliSocket || persistentCliSocket.readyState !== WebSocket.OPEN || !data) return
  persistentCliSocket.send(JSON.stringify({
    type: 'input',
    data
  }))
}

function clearPersistentCliOutput() {
  persistentTerminal?.clear()
}

// Logs: Refresh file list
async function refreshLogFiles() {
  if (!connectionReady.value) return

  try {
    await iotdbStore.listLogFiles(selectedServerId.value!, iotdbHome.value.trim())
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to list log files'))
  }
}

// Logs: Load log content
async function loadLogFile(path: string) {
  selectedLogFile.value = path
  stopLogStream()
  try {
    await iotdbStore.readLogFile(selectedServerId.value!, iotdbHome.value.trim(), path, LOG_TAIL_LINES)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to read log file'))
  }
}

// Logs: Refresh current log
async function refreshCurrentLog() {
  if (!selectedLogFile.value) return
  await loadLogFile(selectedLogFile.value)
}

async function startLogStream() {
  if (!connected.value || !selectedLogFile.value) return

  stopLogStream()
  iotdbStore.logContent = ''
  const controller = new AbortController()
  logStreamController = controller
  streamingLog.value = true

  try {
    const response = await fetch('/api/iotdb/logs/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        server_id: selectedServerId.value,
        iotdb_home: iotdbHome.value.trim(),
        path: selectedLogFile.value,
        tail: LOG_TAIL_LINES
      }),
      signal: controller.signal
    })

    if (!response.ok) {
      throw new Error(await readFetchError(response, 'Failed to stream log file'))
    }
    if (!response.body) {
      throw new Error('Log stream is not available')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      appendLogContent(decoder.decode(value, { stream: true }))
    }
  } catch (error) {
    if (!controller.signal.aborted) {
      ElMessage.error(getErrorMessage(error, 'Failed to stream log file'))
    }
  } finally {
    if (logStreamController === controller) {
      logStreamController = null
      streamingLog.value = false
    }
  }
}

// Configs: Refresh file list
async function refreshConfigFiles() {
  if (!connectionReady.value) return

  try {
    await iotdbStore.listConfigFiles(selectedServerId.value!, iotdbHome.value.trim())
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to list config files'))
  }
}

// Configs: Load config content
async function loadConfigFile(path: string) {
  selectedConfigFile.value = path
  configEditMode.value = false
  try {
    await iotdbStore.readConfigFile(selectedServerId.value!, iotdbHome.value.trim(), path)
    configEditorContent.value = iotdbStore.configContent
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to read config file'))
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
      iotdbHome.value.trim(),
      selectedConfigFile.value,
      configEditorContent.value
    )
    if (result.success) {
      ElMessage.success('Config saved successfully')
      configEditMode.value = false
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to save config'))
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
      ElMessage.error(getErrorMessage(error, 'Failed to restart IoTDB'))
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
          placeholder="选择 IP"
          style="width: 200px"
          clearable
        >
          <ElOption
            v-for="server in serversStore.servers"
            :key="server.id"
            :label="`${server.host} (${server.name})`"
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
          :type="connected ? 'danger' : 'primary'"
          :loading="connecting"
          :disabled="!connectionReady"
          @click="connected ? disconnectIoTDB() : connectIoTDB()"
        >
          {{ connected ? '断开' : '连接' }}
        </ElButton>
        <ElButton
          :icon="Refresh"
          :disabled="!connected"
          :loading="connecting"
          @click="reloadCurrentConnection"
        >
          重载
        </ElButton>
        <ElButton
          type="warning"
          :icon="Refresh"
          @click="restartIoTDB"
          :disabled="!connected"
          :loading="iotdbStore.loading"
        >
          重启 IoTDB
        </ElButton>
      </div>
    </div>

    <!-- Tab Area -->
    <ElTabs v-model="activeTab" class="iotdb-tabs" v-if="connected">
      <!-- Persistent CLI Tab -->
      <ElTabPane label="CLI" name="cli-session">
        <div class="cli-section">
          <div class="cli-connection-panel">
            <div class="cli-param">
              <span class="cli-param-label">Host (-h)</span>
              <ElInput
                v-model="cliHost"
                placeholder="从 iotdb-system.properties 读取"
                clearable
                :disabled="persistentCliConnected || persistentCliConnecting"
              />
            </div>
            <div class="cli-param">
              <span class="cli-param-label">Port (-p)</span>
              <ElInput
                v-model.number="cliPort"
                placeholder="从 iotdb-system.properties 读取"
                clearable
                :disabled="persistentCliConnected || persistentCliConnecting"
              />
            </div>
            <div class="cli-param">
              <span class="cli-param-label">User (-u)</span>
              <ElInput
                v-model="cliUsername"
                placeholder="留空则不指定"
                clearable
                :disabled="persistentCliConnected || persistentCliConnecting"
              />
            </div>
            <div class="cli-param">
              <span class="cli-param-label">Password (-pw)</span>
              <ElInput
                v-model="cliPassword"
                placeholder="留空则不指定"
                show-password
                clearable
                :disabled="persistentCliConnected || persistentCliConnecting"
              />
            </div>
          </div>

          <div class="persistent-cli-toolbar">
            <ElTag :type="persistentCliConnected ? 'success' : 'info'" effect="plain">
              {{ persistentCliConnected ? 'CLI 已连接' : 'CLI 未连接' }}
            </ElTag>
            <ElButton
              v-if="!persistentCliConnected"
              type="primary"
              :loading="persistentCliConnecting"
              @click="handleConnectPersistentCli"
            >
              连接 CLI
            </ElButton>
            <ElButton
              v-else
              type="danger"
              @click="closePersistentCliSession()"
            >
              断开 CLI
            </ElButton>
            <ElButton @click="clearPersistentCliOutput">
              清空输出
            </ElButton>
          </div>

          <div
            ref="persistentTerminalRef"
            class="persistent-cli-terminal"
            @click="focusPersistentTerminal"
          ></div>
        </div>
      </ElTabPane>

      <!-- Log Management Tab -->
      <ElTabPane label="日志管理" name="logs">
        <div class="logs-section">
          <div class="file-layout">
            <aside
              class="file-panel"
              v-loading="iotdbStore.logsLoading"
            >
              <div class="file-panel-header">
                <span>日志目录</span>
                <ElButton
                  size="small"
                  :icon="Refresh"
                  @click="refreshLogFiles"
                  :loading="iotdbStore.logsLoading"
                >
                  刷新
                </ElButton>
              </div>

              <div v-if="iotdbStore.logFiles.length === 0" class="file-empty">
                暂无日志文件
              </div>

              <div
                v-else
                class="file-list log-file-list"
                :style="{ height: `${logPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT}px` }"
              >
                <button
                  v-for="file in iotdbStore.logFiles"
                  :key="file.path"
                  type="button"
                  class="file-item"
                  :class="{ active: selectedLogFile === file.path }"
                  @click="loadLogFile(file.path)"
                >
                  <Document class="file-icon" />
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ formatSize(file.size) }}</span>
                </button>
              </div>
            </aside>

            <section class="file-detail">
              <div class="log-preview" v-if="selectedLogFile">
                <div class="preview-header">
                  <div class="preview-title">
                    <span class="preview-file-name">{{ selectedLogFile }}</span>
                    <ElTag type="info" effect="plain">
                      默认读取最后 {{ LOG_TAIL_LINES }} 行，页面最多保留 {{ Math.round(MAX_LOG_VIEW_CHARS / 1024) }} KB
                    </ElTag>
                  </div>
                  <div class="preview-actions">
                    <ElTag v-if="streamingLog" type="success" effect="plain">实时日志</ElTag>
                    <ElButton
                      size="small"
                      :icon="Refresh"
                      @click="refreshCurrentLog"
                      :loading="iotdbStore.logsLoading"
                      :disabled="streamingLog"
                    >
                      刷新最后 {{ LOG_TAIL_LINES }} 行
                    </ElButton>
                    <ElButton
                      v-if="!streamingLog"
                      size="small"
                      type="success"
                      @click="startLogStream"
                    >
                      实时查看
                    </ElButton>
                    <ElButton
                      v-else
                      size="small"
                      type="danger"
                      @click="stopLogStream"
                    >
                      停止实时
                    </ElButton>
                  </div>
                </div>
                <pre
                  ref="logOutputRef"
                  class="log-output"
                  :style="{ height: `${logPreviewHeight}px` }"
                >{{ iotdbStore.logContent || '等待日志输出...' }}</pre>
                <button
                  type="button"
                  class="log-resize-handle"
                  :class="{ active: resizingLogPreview }"
                  aria-label="拖拽调整日志预览高度"
                  title="拖拽调整日志预览高度"
                  @pointerdown="startLogPreviewResize"
                >
                  <span />
                </button>
              </div>

              <div v-else class="detail-empty">
                从左侧选择一个日志文件
              </div>
            </section>
          </div>
        </div>
      </ElTabPane>

      <!-- Config Management Tab -->
      <ElTabPane label="配置管理" name="configs">
        <div class="configs-section">
          <div class="file-layout">
            <aside
              class="file-panel"
              v-loading="iotdbStore.configsLoading"
            >
              <div class="file-panel-header">
                <span>配置目录</span>
                <ElButton
                  size="small"
                  :icon="Refresh"
                  @click="refreshConfigFiles"
                  :loading="iotdbStore.configsLoading"
                >
                  刷新
                </ElButton>
              </div>

              <div v-if="iotdbStore.configFiles.length === 0" class="file-empty">
                暂无配置文件
              </div>

              <div
                v-else
                class="file-list config-file-list"
                :style="{ height: `${configPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT}px` }"
              >
                <button
                  v-for="file in iotdbStore.configFiles"
                  :key="file.path"
                  type="button"
                  class="file-item"
                  :class="{ active: selectedConfigFile === file.path }"
                  @click="loadConfigFile(file.path)"
                >
                  <Setting class="file-icon" />
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ formatSize(file.size) }}</span>
                </button>
              </div>
            </aside>

            <section class="file-detail">
              <div class="config-editor" v-if="selectedConfigFile">
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
                  class="config-textarea"
                  :input-style="{ height: `${configPreviewHeight}px` }"
                />
                <pre
                  v-else
                  class="config-output"
                  :style="{ height: `${configPreviewHeight}px` }"
                >{{ iotdbStore.configContent }}</pre>
                <button
                  type="button"
                  class="config-resize-handle"
                  :class="{ active: resizingConfigPreview }"
                  aria-label="拖拽调整配置预览高度"
                  title="拖拽调整配置预览高度"
                  @pointerdown="startConfigPreviewResize"
                >
                  <span />
                </button>
              </div>

              <div v-else class="detail-empty">
                从左侧选择一个配置文件
              </div>
            </section>
          </div>
        </div>
      </ElTabPane>
    </ElTabs>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <el-icon :size="64"><Platform /></el-icon>
      <p>请选择 IP、输入 IoTDB 安装目录，然后点击连接</p>
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
  flex-wrap: wrap;
}

.control-right {
  display: flex;
  flex-wrap: wrap;
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

.cli-connection-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #f8fbff;
}

.cli-param {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cli-param-label {
  color: #606266;
  font-size: 12px;
  font-weight: 500;
}

.persistent-cli-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.persistent-cli-terminal {
  position: relative;
  border: 1px solid #303743;
  border-radius: 4px;
  overflow: hidden;
  background: #101820;
  height: 720px;
  min-height: 360px;
  padding: 8px;
  outline: none;
}

.persistent-cli-terminal:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.persistent-cli-terminal :deep(.xterm) {
  height: 100%;
}

.persistent-cli-terminal :deep(.xterm-viewport) {
  overflow-y: auto;
}

/* Logs Section */
.logs-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.log-preview {
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 13px;
}

.preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.preview-title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.preview-file-name {
  min-width: 0;
  overflow: hidden;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  overflow: auto;
  margin: 0;
}

.log-resize-handle,
.config-resize-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 18px;
  padding: 0;
  border: 0;
  border-top: 1px solid #303743;
  background: #252d36;
  cursor: ns-resize;
}

.log-resize-handle:hover,
.log-resize-handle.active,
.config-resize-handle:hover,
.config-resize-handle.active {
  background: #303b47;
}

.log-resize-handle span,
.config-resize-handle span {
  display: block;
  width: 44px;
  height: 3px;
  border-radius: 3px;
  background: #7b8794;
}

:global(.is-resizing-log-preview) {
  cursor: ns-resize;
  user-select: none;
}

:global(.is-resizing-config-preview) {
  cursor: ns-resize;
  user-select: none;
}

/* Configs Section */
.configs-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.file-layout {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) minmax(0, 8fr);
  gap: 16px;
  min-height: 560px;
}

.file-panel,
.file-detail {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
}

.file-panel {
  overflow: hidden;
}

.file-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
  font-weight: 500;
}

.file-list {
  max-height: 520px;
  overflow-y: auto;
}

.log-file-list {
  max-height: none;
}

.config-file-list {
  max-height: none;
}

.file-item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid #edf0f5;
  background: transparent;
  color: #303133;
  cursor: pointer;
  text-align: left;
}

.file-item:hover,
.file-item.active {
  background: #eef5ff;
  color: #337ecc;
}

.file-icon {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  color: #7a8da6;
}

.file-name {
  min-width: 0;
  overflow: hidden;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  grid-column: 2;
  color: #909399;
  font-size: 12px;
}

.file-empty,
.detail-empty {
  padding: 40px 16px;
  color: #909399;
  text-align: center;
}

.file-detail {
  min-width: 0;
  overflow: hidden;
}

.detail-note {
  padding: 10px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.config-editor {
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
  resize: none;
}

.config-output {
  background: #f5f7fa;
  padding: 16px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  margin: 0;
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

@media (max-width: 900px) {
  .cli-connection-panel,
  .file-layout {
    grid-template-columns: 1fr;
  }
}
</style>
