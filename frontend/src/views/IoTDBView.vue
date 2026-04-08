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
  ElMessage,
  ElMessageBox,
  ElDialog,
  ElTag,
  vLoading
} from 'element-plus'
import { Refresh, Platform } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import { useIoTDBStore } from '@/stores/iotdb'
import { iotdbApi } from '@/api'
import type { IoTDBFileInfo } from '@/types'

const serversStore = useServersStore()
const iotdbStore = useIoTDBStore()

type IoTDBConnectionMode = 'standalone' | 'cluster'
type IoTDBRestartScope = 'all' | 'cn' | 'dn'

interface SavedIoTDBNode {
  id: string
  name: string
  restartScope: IoTDBRestartScope
  serverId: number
  iotdbHome: string
}

interface SavedIoTDBTarget {
  id: string
  name: string
  mode: IoTDBConnectionMode
  nodes: SavedIoTDBNode[]
  updatedAt: number
}

// Control state
const selectedServerId = ref<number | null>(null)
const iotdbHome = ref('')
const selectedSavedTargetId = ref('')
const savedTargets = ref<SavedIoTDBTarget[]>([])
const createTargetDialogVisible = ref(false)
const manageTargetsDialogVisible = ref(false)
const editingTargetId = ref('')
const newTargetName = ref('')
const newTargetMode = ref<IoTDBConnectionMode>('standalone')
const newTargetNodes = ref<SavedIoTDBNode[]>([])
const connectedNodes = ref<SavedIoTDBNode[]>([])
const activeNodeId = ref('')
const activeTab = ref('cli-session')
const LOG_TAIL_LINES = 100
const MAX_LOG_VIEW_CHARS = 256 * 1024
const connected = ref(false)
const connecting = ref(false)
const restarting = ref(false)
const SAVED_TARGETS_STORAGE_KEY = 'iotdb-visualization-targets'
const DEFAULT_CLI_HOST = '127.0.0.1'
const DEFAULT_CLI_PORT = 6667

// CLI state
const cliHostsByNode = ref<Record<string, string>>({})
const cliPortsByNode = ref<Record<string, number | null>>({})
const cliUsername = ref('')
const cliPassword = ref('')
const persistentCliConnectedByNode = ref<Record<string, boolean>>({})
const persistentCliConnectingByNode = ref<Record<string, boolean>>({})
const cliDefaultsLoadingByNode = ref<Record<string, boolean>>({})
const cliDefaultsLoadedByNode = ref<Record<string, boolean>>({})

// Log state
const selectedLogFile = ref('')
const streamingLog = ref(false)
const logFilesByNode = ref<Record<string, IoTDBFileInfo[]>>({})
const logContentByNode = ref<Record<string, string>>({})
const logsLoadingByNode = ref<Record<string, boolean>>({})
const logContentLoadingByNode = ref<Record<string, boolean>>({})
const logOutputRef = ref<HTMLElement | null>(null)

// Config state
const selectedConfigFile = ref('')
const configEditorContent = ref('')
const configEditMode = ref(false)
const configFilesByNode = ref<Record<string, IoTDBFileInfo[]>>({})
const configContentByNode = ref<Record<string, string>>({})
const configsLoadingByNode = ref<Record<string, boolean>>({})
const configSavingByNode = ref<Record<string, boolean>>({})

// Computed
const selectedSavedTarget = computed(() => {
  return savedTargets.value.find(target => target.id === selectedSavedTargetId.value)
})

const activeNode = computed(() => {
  return connectedNodes.value.find(node => node.id === activeNodeId.value) || connectedNodes.value[0]
})

const activeLogFiles = computed(() => {
  return activeNode.value ? (logFilesByNode.value[activeNode.value.id] || []) : []
})

const activeLogContent = computed(() => {
  return activeNode.value ? (logContentByNode.value[activeNode.value.id] || '') : ''
})

const activeConfigFiles = computed(() => {
  return activeNode.value ? (configFilesByNode.value[activeNode.value.id] || []) : []
})

const activeConfigContent = computed(() => {
  return activeNode.value ? (configContentByNode.value[activeNode.value.id] || '') : ''
})

const activeLogsLoading = computed(() => {
  return activeNode.value ? Boolean(logsLoadingByNode.value[activeNode.value.id]) : false
})

const activeLogContentLoading = computed(() => {
  return activeNode.value ? Boolean(logContentLoadingByNode.value[activeNode.value.id]) : false
})

const activeConfigsLoading = computed(() => {
  return activeNode.value ? Boolean(configsLoadingByNode.value[activeNode.value.id]) : false
})

const activeConfigSaving = computed(() => {
  return activeNode.value ? Boolean(configSavingByNode.value[activeNode.value.id]) : false
})

const activeCliHost = computed({
  get() {
    return activeNode.value ? (cliHostsByNode.value[activeNode.value.id] || DEFAULT_CLI_HOST) : DEFAULT_CLI_HOST
  },
  set(value: string) {
    if (!activeNode.value) return
    cliHostsByNode.value[activeNode.value.id] = value
  }
})

const activeCliPort = computed({
  get() {
    return activeNode.value ? (cliPortsByNode.value[activeNode.value.id] ?? DEFAULT_CLI_PORT) : DEFAULT_CLI_PORT
  },
  set(value: number | null) {
    if (!activeNode.value) return
    cliPortsByNode.value[activeNode.value.id] = value
  }
})

const activePersistentCliConnected = computed(() => {
  return activeNode.value ? Boolean(persistentCliConnectedByNode.value[activeNode.value.id]) : false
})

const activePersistentCliConnecting = computed(() => {
  return activeNode.value ? Boolean(persistentCliConnectingByNode.value[activeNode.value.id]) : false
})

const activeCliDefaultsLoading = computed(() => {
  return activeNode.value ? Boolean(cliDefaultsLoadingByNode.value[activeNode.value.id]) : false
})

const activeCliDefaultsLoaded = computed(() => {
  return activeNode.value ? Boolean(cliDefaultsLoadedByNode.value[activeNode.value.id]) : false
})

const connectionReady = computed(() => {
  return Boolean(connectedNodes.value.length || selectedSavedTarget.value)
})

const currentTargetLabel = computed(() => {
  if (connectedNodes.value.length > 1) return `${connectedNodes.value.length} 节点分布式`
  if (connectedNodes.value.length === 1) return getNodeDisplayName(connectedNodes.value[0])
  if (selectedSavedTarget.value) return selectedSavedTarget.value.name
  if (!selectedServerId.value || !iotdbHome.value.trim()) return ''
  return getSavedTargetName(selectedServerId.value, normalizeIoTDBHome(iotdbHome.value))
})

const targetDialogTitle = computed(() => {
  return editingTargetId.value ? '编辑连接' : '新建连接'
})

let logStreamController: AbortController | null = null
const persistentCliSockets = new Map<string, WebSocket>()
const persistentTerminals = new Map<string, Terminal>()
const persistentFitAddons = new Map<string, FitAddon>()
const persistentTerminalResizeObservers = new Map<string, ResizeObserver>()
const persistentTerminalResizeFrames = new Map<string, number>()
const persistentTerminalRefs = new Map<string, HTMLElement>()

function isTerminalHost(value: unknown): value is HTMLElement {
  return value instanceof HTMLElement && Boolean(value.ownerDocument?.defaultView)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === 'object') {
    const axiosError = error as { response?: { data?: { detail?: string } }, message?: string }
    return axiosError.response?.data?.detail || axiosError.message || fallback
  }
  return fallback
}

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

function normalizeIoTDBHome(value: string) {
  return value.trim().replace(/\/+$/, '')
}

function makeSavedNodeId(serverId: number, home: string, index = 0) {
  return `${serverId}:${home}:${index}`
}

function getSavedTargetName(serverId: number, home: string) {
  const server = serversStore.servers.find(item => item.id === serverId)
  const serverLabel = server ? `${server.host} (${server.name})` : `Server ${serverId}`
  return `${serverLabel} - ${home}`
}

function getNodeDisplayName(node: SavedIoTDBNode) {
  const server = serversStore.servers.find(item => item.id === node.serverId)
  const serverLabel = server ? server.host : `Server ${node.serverId}`
  return `${node.name || serverLabel} - ${node.iotdbHome}`
}

function getNodeTitle(node: SavedIoTDBNode) {
  const server = serversStore.servers.find(item => item.id === node.serverId)
  return node.name || server?.host || `Server ${node.serverId}`
}

function normalizeRestartScope(value: unknown): IoTDBRestartScope {
  if (value === 'cn' || value === 'configNode') return 'cn'
  if (value === 'dn' || value === 'dataNode') return 'dn'
  return 'all'
}

function getRestartScopeLabel(scope: IoTDBRestartScope) {
  if (scope === 'cn') return 'CN'
  if (scope === 'dn') return 'DN'
  return 'ALL'
}

function makeTargetFromNodes(nodes: SavedIoTDBNode[], name?: string): SavedIoTDBTarget {
  const normalizedNodes = nodes.map((node, index) => ({
    ...node,
    iotdbHome: normalizeIoTDBHome(node.iotdbHome),
    id: node.id || makeSavedNodeId(node.serverId, normalizeIoTDBHome(node.iotdbHome), index),
    name: node.name || `节点 ${index + 1}`,
    restartScope: normalizeRestartScope(node.restartScope)
  }))
  const mode: IoTDBConnectionMode = normalizedNodes.length > 1 ? 'cluster' : 'standalone'
  const targetName = name?.trim() || (
    mode === 'cluster'
      ? `分布式 ${normalizedNodes.length} 节点`
      : getNodeDisplayName(normalizedNodes[0])
  )
  return {
    id: `${mode}:${normalizedNodes.map(node => `${node.serverId}:${node.iotdbHome}`).join('|')}`,
    name: targetName,
    mode,
    nodes: normalizedNodes,
    updatedAt: Date.now()
  }
}

function persistSavedTargets() {
  localStorage.setItem(SAVED_TARGETS_STORAGE_KEY, JSON.stringify(savedTargets.value))
}

function hydrateSavedTargets() {
  try {
    const raw = localStorage.getItem(SAVED_TARGETS_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Array<Partial<SavedIoTDBTarget> & Partial<SavedIoTDBNode>>
    savedTargets.value = parsed
      .map(target => {
        if (Array.isArray(target.nodes) && target.nodes.length > 0) {
          const hydrated = makeTargetFromNodes(target.nodes.map(node => ({
            ...node,
            restartScope: normalizeRestartScope(node.restartScope || (node as { role?: unknown }).role)
          })), target.name)
          return {
            ...hydrated,
            id: target.id || hydrated.id,
            updatedAt: target.updatedAt || hydrated.updatedAt
          }
        }

        if (Number.isFinite(target.serverId) && typeof target.iotdbHome === 'string' && target.iotdbHome.trim()) {
          const home = normalizeIoTDBHome(target.iotdbHome)
          const hydrated = makeTargetFromNodes([{
            id: makeSavedNodeId(target.serverId!, home),
            name: '单机',
            restartScope: 'all',
            serverId: target.serverId!,
            iotdbHome: home
          }], target.name || getSavedTargetName(target.serverId!, home))
          return {
            ...hydrated,
            id: target.id || hydrated.id,
            updatedAt: target.updatedAt || hydrated.updatedAt
          }
        }

        return null
      })
      .filter((target): target is SavedIoTDBTarget => Boolean(target))
      .sort((a, b) => b.updatedAt - a.updatedAt)
  } catch {
    savedTargets.value = []
  }
}

function refreshSavedTargetNames() {
  let changed = false
  savedTargets.value = savedTargets.value.map(target => {
    const fallback = target.nodes.length > 1 ? target.name : getNodeDisplayName(target.nodes[0])
    if (target.name === fallback) return target
    changed = true
    return { ...target, name: fallback }
  })
  if (changed) persistSavedTargets()
}

function openCreateTargetDialog() {
  editingTargetId.value = ''
  newTargetMode.value = connectedNodes.value.length > 1 ? 'cluster' : 'standalone'
  newTargetName.value = ''
  newTargetNodes.value = connectedNodes.value.length > 0
    ? connectedNodes.value.map(node => ({ ...node }))
    : [{
        id: '',
        name: '节点 1',
        restartScope: 'all',
        serverId: selectedServerId.value || 0,
        iotdbHome: iotdbHome.value
      }]
  createTargetDialogVisible.value = true
}

function openEditTargetDialog(target: SavedIoTDBTarget) {
  editingTargetId.value = target.id
  newTargetMode.value = target.mode
  newTargetName.value = target.name
  newTargetNodes.value = target.nodes.map(node => ({ ...node }))
  createTargetDialogVisible.value = true
}

function ensureNewTargetNodes() {
  if (newTargetNodes.value.length > 0) return
  newTargetNodes.value = [{
    id: '',
    name: '节点 1',
    restartScope: 'all',
    serverId: 0,
    iotdbHome: ''
  }]
}

function addNewTargetNode() {
  newTargetMode.value = 'cluster'
  newTargetNodes.value.push({
    id: '',
    name: `节点 ${newTargetNodes.value.length + 1}`,
    restartScope: 'all',
    serverId: 0,
    iotdbHome: ''
  })
}

function removeNewTargetNode(index: number) {
  if (newTargetNodes.value.length <= 1) return
  newTargetNodes.value.splice(index, 1)
  if (newTargetNodes.value.length === 1) {
    newTargetMode.value = 'standalone'
    newTargetNodes.value[0].restartScope = 'all'
  }
}

function applyTarget(target: SavedIoTDBTarget) {
  connectedNodes.value = target.nodes.map(node => ({ ...node }))
  activeNodeId.value = connectedNodes.value[0]?.id || ''
  selectedServerId.value = connectedNodes.value[0]?.serverId || null
  iotdbHome.value = connectedNodes.value[0]?.iotdbHome || ''
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditorContent.value = ''
  configEditMode.value = false
}

function createTargetFromDialog() {
  ensureNewTargetNodes()
  const validNodes = newTargetNodes.value
    .filter(node => node.serverId && node.iotdbHome.trim())
    .map((node, index) => {
      const home = normalizeIoTDBHome(node.iotdbHome)
      return {
        ...node,
        id: makeSavedNodeId(node.serverId, home, index),
        name: node.name.trim() || `节点 ${index + 1}`,
        restartScope: normalizeRestartScope(node.restartScope),
        serverId: node.serverId,
        iotdbHome: home
      }
    })

  if (validNodes.length !== newTargetNodes.value.length || validNodes.length === 0) {
    ElMessage.warning('请为每个节点选择 IP 并填写 IoTDB 安装目录')
    return
  }

  const target = makeTargetFromNodes(
    newTargetMode.value === 'standalone' ? validNodes.slice(0, 1) : validNodes,
    newTargetName.value
  )

  savedTargets.value = [
    target,
    ...savedTargets.value.filter(item => item.id !== target.id && item.id !== editingTargetId.value)
  ]
  selectedSavedTargetId.value = target.id
  applyTarget(target)
  persistSavedTargets()
  createTargetDialogVisible.value = false
  manageTargetsDialogVisible.value = false
  ElMessage.success(editingTargetId.value ? '已更新并加载连接' : '已新建并加载连接')
  editingTargetId.value = ''
}

function loadSelectedTarget(showMessage = true) {
  if (!selectedSavedTarget.value) return
  applyTarget(selectedSavedTarget.value)
  if (showMessage) {
    ElMessage.success('已加载保存项，请按需连接或重载')
  }
}

function loadSavedTarget(target: SavedIoTDBTarget) {
  selectedSavedTargetId.value = target.id
  applyTarget(target)
  manageTargetsDialogVisible.value = false
  ElMessage.success('已加载连接，请按需连接或刷新')
}

function deleteSavedTarget(target: SavedIoTDBTarget) {
  if (connected.value) {
    ElMessage.warning('请先断开连接再删除')
    return
  }

  savedTargets.value = savedTargets.value.filter(item => item.id !== target.id)
  if (selectedSavedTargetId.value === target.id) {
    selectedSavedTargetId.value = ''
  }
  persistSavedTargets()
  ElMessage.success('已删除连接')
}

async function connectSelectedOrCurrentTarget() {
  if (selectedSavedTarget.value) {
    loadSelectedTarget(false)
  }
  await connectIoTDB()
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
  if (!activeNode.value) return
  const nodeId = activeNode.value.id
  logContentByNode.value[nodeId] = ((logContentByNode.value[nodeId] || '') + chunk).slice(-MAX_LOG_VIEW_CHARS)
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

function getActiveNodeId() {
  return activeNode.value?.id || ''
}

function writePersistentCliOutput(chunk: string, nodeId = getActiveNodeId()) {
  if (!nodeId) return
  if (!persistentTerminals.get(nodeId)) {
    initPersistentTerminal(nodeId)
  }
  persistentTerminals.get(nodeId)?.write(chunk)
}

function setPersistentTerminalRef(element: unknown, nodeId: string) {
  if (isTerminalHost(element)) {
    persistentTerminalRefs.set(nodeId, element)
    if (activeTab.value === 'cli-session') {
      initPersistentTerminal(nodeId)
      schedulePersistentTerminalFit(nodeId, persistentCliConnectedByNode.value[nodeId])
    }
  } else {
    persistentTerminalRefs.delete(nodeId)
  }
}

function focusPersistentTerminal(nodeId = getActiveNodeId()) {
  if (!nodeId) return
  persistentTerminals.get(nodeId)?.focus()
}

function fitPersistentTerminal(nodeId = getActiveNodeId(), sendResize = true) {
  const terminal = persistentTerminals.get(nodeId)
  const fitAddon = persistentFitAddons.get(nodeId)
  const terminalHost = persistentTerminalRefs.get(nodeId)
  if (!terminal || !fitAddon || !terminalHost) return
  try {
    fitAddon.fit()
    const socket = persistentCliSockets.get(nodeId)
    if (sendResize && socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: 'resize',
        cols: terminal.cols,
        rows: terminal.rows
      }))
    }
  } catch {
    // xterm can throw while its container is hidden during tab transitions.
  }
}

function schedulePersistentTerminalFit(nodeId = getActiveNodeId(), sendResize = true) {
  if (!nodeId) return
  const resizeFrame = persistentTerminalResizeFrames.get(nodeId)
  if (resizeFrame !== undefined) {
    window.cancelAnimationFrame(resizeFrame)
  }
  persistentTerminalResizeFrames.set(nodeId, window.requestAnimationFrame(() => {
    persistentTerminalResizeFrames.delete(nodeId)
    fitPersistentTerminal(nodeId, sendResize)
  }))
}

function initPersistentTerminal(nodeId = getActiveNodeId()) {
  if (!nodeId) return false
  if (persistentTerminals.get(nodeId)) return true
  const terminalHost = persistentTerminalRefs.get(nodeId)
  if (!isTerminalHost(terminalHost)) return false

  let terminal: Terminal | null = null
  try {
    terminal = new Terminal({
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
    terminal.open(terminalHost)
    terminal.onData(data => sendPersistentCliInput(data, nodeId))

    persistentTerminals.set(nodeId, terminal)
    persistentFitAddons.set(nodeId, fitAddon)

    const resizeObserver = new ResizeObserver(() => {
      schedulePersistentTerminalFit(nodeId)
    })
    resizeObserver.observe(terminalHost)
    persistentTerminalResizeObservers.set(nodeId, resizeObserver)
    schedulePersistentTerminalFit(nodeId, false)
  } catch (error) {
    terminal?.dispose()
    persistentTerminals.delete(nodeId)
    persistentFitAddons.delete(nodeId)
    throw error
  }
  return true
}

function disposePersistentTerminal(nodeId?: string) {
  const nodeIds = nodeId ? [nodeId] : Array.from(persistentTerminals.keys())
  for (const id of nodeIds) {
    const resizeFrame = persistentTerminalResizeFrames.get(id)
    if (resizeFrame !== undefined) {
      window.cancelAnimationFrame(resizeFrame)
      persistentTerminalResizeFrames.delete(id)
    }
    persistentTerminalResizeObservers.get(id)?.disconnect()
    persistentTerminalResizeObservers.delete(id)
    persistentTerminals.get(id)?.dispose()
    persistentTerminals.delete(id)
    persistentFitAddons.delete(id)
  }
}

function buildWebSocketUrl(path: string) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

function closePersistentCliSession(sendDisconnect = true, nodeId?: string) {
  const nodeIds = nodeId ? [nodeId] : Array.from(persistentCliSockets.keys())
  for (const id of nodeIds) {
    const socket = persistentCliSockets.get(id)
    if (socket) {
      if (sendDisconnect && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'disconnect' }))
      }
      socket.close()
    }
    persistentCliSockets.delete(id)
    persistentCliConnectedByNode.value[id] = false
    persistentCliConnectingByNode.value[id] = false
  }
}

// Load servers on mount
onMounted(async () => {
  await serversStore.fetchServers()
  hydrateSavedTargets()
  refreshSavedTargetNames()
})

onUnmounted(() => {
  stopLogStream()
  closePersistentCliSession()
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
  cliHostsByNode.value = {}
  cliPortsByNode.value = {}
  cliDefaultsLoadingByNode.value = {}
  cliDefaultsLoadedByNode.value = {}
})

watch(activeNodeId, () => {
  stopLogStream()
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditorContent.value = ''
  configEditMode.value = false
  void loadCliDefaultsFromConfig(activeNode.value, false)
  if (activeTab.value === 'cli-session') {
    nextTick(() => {
      initPersistentTerminal()
      schedulePersistentTerminalFit(getActiveNodeId(), activePersistentCliConnected.value)
      focusPersistentTerminal()
    })
  }
})

watch(activeTab, async (tab) => {
  if (tab !== 'cli-session' || !connected.value) return
  await nextTick()
  initPersistentTerminal()
  schedulePersistentTerminalFit(getActiveNodeId(), activePersistentCliConnected.value)
  focusPersistentTerminal()
})

async function loadCliDefaultsFromConfig(node = activeNode.value, showWarning = true) {
  if (!node) return

  const configPath = `${normalizeIoTDBHome(node.iotdbHome)}/conf/iotdb-system.properties`
  cliDefaultsLoadingByNode.value[node.id] = true
  cliDefaultsLoadedByNode.value[node.id] = false
  try {
    const result = await iotdbApi.readConfig(node.serverId, node.iotdbHome, configPath)
    const properties = parseProperties(result.content)
    cliHostsByNode.value[node.id] = properties.get('dn_rpc_address') || properties.get('rpc_address') || DEFAULT_CLI_HOST
    const port = Number(properties.get('dn_rpc_port') || properties.get('rpc_port'))
    cliPortsByNode.value[node.id] = Number.isFinite(port) && port > 0 ? port : DEFAULT_CLI_PORT
  } catch (error) {
    cliHostsByNode.value[node.id] = cliHostsByNode.value[node.id] || DEFAULT_CLI_HOST
    cliPortsByNode.value[node.id] = cliPortsByNode.value[node.id] || DEFAULT_CLI_PORT
    if (showWarning) {
      ElMessage.warning(getErrorMessage(error, '读取 CLI 默认参数失败，已使用默认值'))
    }
  } finally {
    cliDefaultsLoadingByNode.value[node.id] = false
    cliDefaultsLoadedByNode.value[node.id] = true
  }
}

async function reloadConnectedIoTDB() {
  if (!connectionReady.value) return

  connecting.value = true
  try {
    await loadCliDefaultsFromConfig(activeNode.value, false)
    await Promise.all(connectedNodes.value.flatMap(node => [
      refreshLogFiles(node),
      refreshConfigFiles(node)
    ]))
  } finally {
    connecting.value = false
  }
}

async function reloadCurrentConnection() {
  try {
    await reloadConnectedIoTDB()
    ElMessage.success('IoTDB 已重载')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '重载 IoTDB 失败'))
  }
}

async function restartActiveNode() {
  if (!activeNode.value) return

  const node = activeNode.value
  try {
    await ElMessageBox.confirm(
      `确定重启 ${getNodeDisplayName(node)} 的 ${getRestartScopeLabel(node.restartScope)} 吗？`,
      '确认重启',
      {
        confirmButtonText: '重启',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    restarting.value = true
    const result = await iotdbApi.restart(node.serverId, node.iotdbHome, node.restartScope)
    if (result.success) {
      ElMessage.success('IoTDB 已重启')
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(getErrorMessage(error, '重启 IoTDB 失败'))
    }
  } finally {
    restarting.value = false
  }
}

async function connectIoTDB() {
  if (!connectionReady.value) return

  try {
    if (selectedSavedTarget.value && connectedNodes.value.length === 0) {
      applyTarget(selectedSavedTarget.value)
    }
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
  logFilesByNode.value = {}
  logContentByNode.value = {}
  logContentLoadingByNode.value = {}
  configFilesByNode.value = {}
  configContentByNode.value = {}
  selectedLogFile.value = ''
  selectedConfigFile.value = ''
  configEditMode.value = false
  cliHostsByNode.value = {}
  cliPortsByNode.value = {}
  persistentCliConnectedByNode.value = {}
  persistentCliConnectingByNode.value = {}
  cliDefaultsLoadingByNode.value = {}
  cliDefaultsLoadedByNode.value = {}
  ElMessage.info('IoTDB 已断开')
}

async function connectPersistentCliSession() {
  if (
    !connected.value ||
    !activeNode.value ||
    activePersistentCliConnecting.value ||
    activePersistentCliConnected.value ||
    activeCliDefaultsLoading.value ||
    !activeCliDefaultsLoaded.value
  ) return

  const node = activeNode.value
  persistentCliConnectingByNode.value[node.id] = true
  await nextTick()
  try {
    if (!initPersistentTerminal(node.id)) {
      throw new Error('CLI 终端容器未准备好，请切到 CLI 页签后重试')
    }
  } catch (error) {
    persistentCliConnectingByNode.value[node.id] = false
    throw error
  }
  persistentTerminals.get(node.id)?.clear()

  const rpcPort = Number(cliPortsByNode.value[node.id] ?? DEFAULT_CLI_PORT)
  const socket = new WebSocket(buildWebSocketUrl('/api/iotdb/cli/session'))
  persistentCliSockets.set(node.id, socket)

  await new Promise<void>((resolve, reject) => {
    let settled = false

    socket.onopen = () => {
      socket.send(JSON.stringify({
        server_id: node.serverId,
        iotdb_home: node.iotdbHome,
        host: (cliHostsByNode.value[node.id] || DEFAULT_CLI_HOST).trim() || undefined,
        rpc_port: Number.isFinite(rpcPort) && rpcPort > 0 ? rpcPort : undefined,
        username: cliUsername.value.trim() || undefined,
        cli_password: cliPassword.value || undefined
      }))
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'ready') {
          persistentCliConnectedByNode.value[node.id] = true
          persistentCliConnectingByNode.value[node.id] = false
          schedulePersistentTerminalFit(node.id)
          if (!settled) {
            settled = true
            resolve()
          }
          return
        }
        if (message.type === 'output') {
          writePersistentCliOutput(message.data || '', node.id)
          return
        }
        if (message.type === 'error') {
          writePersistentCliOutput(`\r\n${message.message || 'CLI session error'}\r\n`, node.id)
          persistentCliConnectedByNode.value[node.id] = false
          persistentCliConnectingByNode.value[node.id] = false
          if (!settled) {
            settled = true
            reject(new Error(message.message || 'CLI session error'))
          } else {
            ElMessage.error(message.message || 'CLI session error')
          }
          return
        }
        if (message.type === 'exit') {
          persistentCliConnectedByNode.value[node.id] = false
          writePersistentCliOutput('\r\nCLI session exited.\r\n', node.id)
        }
      } catch {
        writePersistentCliOutput(String(event.data), node.id)
      }
    }

    socket.onerror = () => {
      persistentCliConnectedByNode.value[node.id] = false
      persistentCliConnectingByNode.value[node.id] = false
      if (!settled) {
        settled = true
        reject(new Error('CLI WebSocket connection failed'))
      }
    }

    socket.onclose = () => {
      if (persistentCliSockets.get(node.id) === socket) {
        persistentCliSockets.delete(node.id)
      }
      persistentCliConnectedByNode.value[node.id] = false
      persistentCliConnectingByNode.value[node.id] = false
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

function sendPersistentCliInput(data: string, nodeId = getActiveNodeId()) {
  const socket = persistentCliSockets.get(nodeId)
  if (!socket || socket.readyState !== WebSocket.OPEN || !data) return
  socket.send(JSON.stringify({
    type: 'input',
    data
  }))
}

function clearPersistentCliOutput() {
  const nodeId = getActiveNodeId()
  if (!nodeId) return
  persistentTerminals.get(nodeId)?.clear()
}

// Logs: Refresh file list
async function refreshLogFiles(node = activeNode.value) {
  if (!node) return

  logsLoadingByNode.value[node.id] = true
  try {
    logFilesByNode.value[node.id] = await iotdbApi.listLogs(node.serverId, node.iotdbHome)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to list log files'))
  } finally {
    logsLoadingByNode.value[node.id] = false
  }
}

// Logs: Load log content
async function loadLogFile(path: string) {
  if (!activeNode.value) return
  selectedLogFile.value = path
  stopLogStream()
  logContentLoadingByNode.value[activeNode.value.id] = true
  try {
    const result = await iotdbApi.readLog(activeNode.value.serverId, activeNode.value.iotdbHome, path, LOG_TAIL_LINES)
    logContentByNode.value[activeNode.value.id] = result.content
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to read log file'))
  } finally {
    logContentLoadingByNode.value[activeNode.value.id] = false
  }
}

// Logs: Refresh current log
async function refreshCurrentLog() {
  if (!selectedLogFile.value) return
  await loadLogFile(selectedLogFile.value)
}

async function startLogStream() {
  if (!connected.value || !selectedLogFile.value || !activeNode.value) return

  stopLogStream()
  const node = activeNode.value
  logContentByNode.value[node.id] = ''
  const controller = new AbortController()
  logStreamController = controller
  streamingLog.value = true

  try {
    const response = await fetch('/api/iotdb/logs/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        server_id: node.serverId,
        iotdb_home: node.iotdbHome,
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
async function refreshConfigFiles(node = activeNode.value) {
  if (!node) return

  configsLoadingByNode.value[node.id] = true
  try {
    configFilesByNode.value[node.id] = await iotdbApi.listConfigs(node.serverId, node.iotdbHome)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to list config files'))
  } finally {
    configsLoadingByNode.value[node.id] = false
  }
}

// Configs: Load config content
async function loadConfigFile(path: string) {
  if (!activeNode.value) return
  selectedConfigFile.value = path
  configEditMode.value = false
  try {
    const result = await iotdbApi.readConfig(activeNode.value.serverId, activeNode.value.iotdbHome, path)
    configContentByNode.value[activeNode.value.id] = result.content
    configEditorContent.value = result.content
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to read config file'))
  }
}

// Configs: Enter edit mode
function enterEditMode() {
  configEditMode.value = true
  configEditorContent.value = activeConfigContent.value
}

// Configs: Cancel edit
function cancelEdit() {
  configEditMode.value = false
  configEditorContent.value = activeConfigContent.value
}

// Configs: Save config
async function saveConfig() {
  if (!selectedConfigFile.value || !activeNode.value) return

  configSavingByNode.value[activeNode.value.id] = true
  try {
    const result = await iotdbApi.writeConfig(
      activeNode.value.serverId,
      activeNode.value.iotdbHome,
      selectedConfigFile.value,
      configEditorContent.value
    )
    if (result.success) {
      ElMessage.success('Config saved successfully')
      configEditMode.value = false
      configContentByNode.value[activeNode.value.id] = configEditorContent.value
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Failed to save config'))
  } finally {
    configSavingByNode.value[activeNode.value.id] = false
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
    <!-- Toolbar -->
    <div class="toolbar">
      <ElSelect
        v-model="selectedSavedTargetId"
        placeholder="选择已保存连接"
        class="target-select"
        clearable
      >
        <ElOption
          v-for="target in savedTargets"
          :key="target.id"
          :label="target.name"
          :value="target.id"
        />
      </ElSelect>

      <ElButton
        type="primary"
        :loading="connecting"
        :disabled="connected || (!connectionReady && !selectedSavedTarget)"
        @click="connectSelectedOrCurrentTarget"
      >
        连接
      </ElButton>

      <ElButton @click="manageTargetsDialogVisible = true">
        管理
      </ElButton>

      <div class="toolbar-spacer" />

      <ElTag v-if="currentTargetLabel" type="info" size="small">
        {{ currentTargetLabel }}
      </ElTag>

      <ElButton
        v-if="connected"
        type="danger"
        @click="disconnectIoTDB"
      >
        断开
      </ElButton>

      <ElButton
        v-if="connected"
        :icon="Refresh"
        :loading="connecting"
        @click="reloadCurrentConnection"
      >
        刷新
      </ElButton>
    </div>

    <!-- Connected Content -->
    <div v-if="connected" class="content-area">
      <!-- Node Tabs + Function Tabs -->
      <div class="tabs-header">
        <div class="tabs-row">
          <div class="node-tabs">
            <button
              v-for="node in connectedNodes"
              :key="node.id"
              class="node-tab"
              :class="{ active: activeNodeId === node.id }"
              @click="activeNodeId = node.id"
            >
              <span class="node-tab-name">{{ getNodeTitle(node) }}</span>
              <ElTag size="small" effect="plain">{{ getRestartScopeLabel(node.restartScope) }}</ElTag>
            </button>
          </div>
          <div class="node-info">
            <span class="node-path">{{ activeNode?.iotdbHome }}</span>
          </div>
          <div class="func-spacer" />
          <ElButton
            type="warning"
            size="small"
            :loading="restarting"
            @click="restartActiveNode"
          >
            重启
          </ElButton>
        </div>
        <div class="function-tabs">
          <button
            class="func-tab"
            :class="{ active: activeTab === 'cli-session' }"
            @click="activeTab = 'cli-session'"
          >
            CLI
          </button>
          <button
            class="func-tab"
            :class="{ active: activeTab === 'logs' }"
            @click="activeTab = 'logs'"
          >
            日志
          </button>
          <button
            class="func-tab"
            :class="{ active: activeTab === 'configs' }"
            @click="activeTab = 'configs'"
          >
            配置
          </button>
        </div>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- CLI Session -->
        <div v-show="activeTab === 'cli-session'" class="cli-panel">
          <div class="cli-params">
            <ElButton size="small">切换模型（待实现）</ElButton>
            <div class="cli-actions">
              <ElButton
                v-if="!activePersistentCliConnected"
                type="primary"
                :loading="activePersistentCliConnecting"
                @click="handleConnectPersistentCli"
              >
                连接 CLI
              </ElButton>
              <template v-else>
                <ElButton type="danger" @click="closePersistentCliSession(true, activeNode?.id)">
                  断开
                </ElButton>
                <ElButton @click="clearPersistentCliOutput">
                  清空
                </ElButton>
              </template>
            </div>
            <div class="cli-param">
              <label>Host</label>
              <ElInput
                v-model="activeCliHost"
                placeholder="127.0.0.1"
                :disabled="activePersistentCliConnected || activePersistentCliConnecting"
              />
            </div>
            <div class="cli-param">
              <label>Port</label>
              <ElInput
                v-model.number="activeCliPort"
                placeholder="6667"
                :disabled="activePersistentCliConnected || activePersistentCliConnecting"
              />
            </div>
            <div class="cli-param">
              <label>User</label>
              <ElInput
                v-model="cliUsername"
                placeholder="用户名"
                :disabled="activePersistentCliConnected"
              />
            </div>
            <div class="cli-param">
              <label>Password</label>
              <ElInput
                v-model="cliPassword"
                type="password"
                show-password
                placeholder="密码"
                :disabled="activePersistentCliConnected"
              />
            </div>
          </div>
          <div
            :ref="element => setPersistentTerminalRef(element, activeNode?.id)"
            class="cli-terminal"
            @click="focusPersistentTerminal(activeNode?.id)"
          ></div>
        </div>

        <!-- Logs -->
        <div v-show="activeTab === 'logs'" class="file-panel">
          <aside class="file-sidebar" v-loading="activeLogsLoading">
            <div class="sidebar-header">
              <span>日志文件</span>
              <ElButton size="small" :icon="Refresh" @click="refreshLogFiles()" :loading="activeLogsLoading" />
            </div>
            <div class="file-list">
              <button
                v-for="file in activeLogFiles"
                :key="file.path"
                class="file-item"
                :class="{ active: selectedLogFile === file.path }"
                @click="loadLogFile(file.path)"
              >
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatSize(file.size) }}</span>
              </button>
              <div v-if="activeLogFiles.length === 0" class="file-empty">暂无日志</div>
            </div>
          </aside>
          <div class="file-content">
            <div v-if="selectedLogFile" class="content-wrapper">
              <div class="content-header">
                <span class="content-title">{{ selectedLogFile }}</span>
                <div class="content-actions">
                  <ElTag v-if="streamingLog" type="success" size="small">实时</ElTag>
                  <ElButton v-if="!streamingLog" size="small" :loading="activeLogContentLoading" @click="refreshCurrentLog">刷新</ElButton>
                  <ElButton
                    size="small"
                    :type="streamingLog ? 'danger' : 'success'"
                    @click="streamingLog ? stopLogStream() : startLogStream()"
                  >
                    {{ streamingLog ? '停止' : '实时' }}
                  </ElButton>
                </div>
              </div>
              <pre ref="logOutputRef" class="content-output">{{ activeLogContent || '等待日志...' }}</pre>
            </div>
            <div v-else class="content-placeholder">选择日志文件</div>
          </div>
        </div>

        <!-- Configs -->
        <div v-show="activeTab === 'configs'" class="file-panel">
          <aside class="file-sidebar" v-loading="activeConfigsLoading">
            <div class="sidebar-header">
              <span>配置文件</span>
              <ElButton size="small" :icon="Refresh" @click="refreshConfigFiles()" :loading="activeConfigsLoading" />
            </div>
            <div class="file-list">
              <button
                v-for="file in activeConfigFiles"
                :key="file.path"
                class="file-item"
                :class="{ active: selectedConfigFile === file.path }"
                @click="loadConfigFile(file.path)"
              >
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatSize(file.size) }}</span>
              </button>
              <div v-if="activeConfigFiles.length === 0" class="file-empty">暂无配置</div>
            </div>
          </aside>
          <div class="file-content">
            <div v-if="selectedConfigFile" class="content-wrapper">
              <div class="content-header">
                <span class="content-title">{{ selectedConfigFile }}</span>
                <div class="content-actions">
                  <template v-if="configEditMode">
                    <ElButton size="small" type="success" @click="saveConfig" :loading="activeConfigSaving">保存</ElButton>
                    <ElButton size="small" @click="cancelEdit">取消</ElButton>
                  </template>
                  <ElButton v-else size="small" type="primary" @click="enterEditMode">编辑</ElButton>
                </div>
              </div>
              <ElInput
                v-if="configEditMode"
                v-model="configEditorContent"
                type="textarea"
                class="config-editor"
              />
              <pre v-else class="content-output">{{ activeConfigContent }}</pre>
            </div>
            <div v-else class="content-placeholder">选择配置文件</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <el-icon :size="48"><Platform /></el-icon>
      <p>选择已保存连接后点击连接</p>
    </div>

    <!-- Create Target Dialog -->
    <ElDialog
      v-model="createTargetDialogVisible"
      :title="targetDialogTitle"
      width="640px"
    >
      <div class="dialog-form">
        <div class="form-row">
          <label>连接名称</label>
          <ElInput v-model="newTargetName" placeholder="留空自动生成" clearable />
        </div>
        <div class="form-row">
          <label>模式</label>
          <ElSelect v-model="newTargetMode" @change="ensureNewTargetNodes">
            <ElOption label="单机" value="standalone" />
            <ElOption label="分布式" value="cluster" />
          </ElSelect>
        </div>
        <div class="nodes-section">
          <div v-for="(node, index) in newTargetNodes" :key="index" class="node-row">
            <ElInput v-model="node.name" placeholder="节点名" class="node-name" clearable />
            <ElSelect v-model="node.restartScope" class="node-scope">
              <ElOption label="ALL" value="all" />
              <ElOption label="CN" value="cn" />
              <ElOption label="DN" value="dn" />
            </ElSelect>
            <ElSelect v-model="node.serverId" placeholder="选择服务器" class="node-server" clearable>
              <ElOption
                v-for="server in serversStore.servers"
                :key="server.id"
                :label="`${server.host} (${server.name})`"
                :value="server.id"
              />
            </ElSelect>
            <ElInput v-model="node.iotdbHome" placeholder="IoTDB 路径" class="node-path" clearable />
            <ElButton
              type="danger"
              size="small"
              :disabled="newTargetNodes.length <= 1"
              @click="removeNewTargetNode(index)"
            >
              删除
            </ElButton>
          </div>
        </div>
        <ElButton v-if="newTargetMode === 'cluster'" type="primary" plain @click="addNewTargetNode">
          添加节点
        </ElButton>
      </div>
      <template #footer>
        <ElButton @click="createTargetDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="createTargetFromDialog">保存</ElButton>
      </template>
    </ElDialog>

    <!-- Manage Targets Dialog -->
    <ElDialog v-model="manageTargetsDialogVisible" title="管理连接" width="600px">
      <div class="manage-header">
        <ElButton type="primary" @click="openCreateTargetDialog">新建连接</ElButton>
      </div>
      <div v-if="savedTargets.length === 0" class="manage-empty">暂无保存连接</div>
      <div v-else class="target-list">
        <div v-for="target in savedTargets" :key="target.id" class="target-item">
          <div class="target-info">
            <div class="target-name">
              {{ target.name }}
              <ElTag size="small" effect="plain">{{ target.mode === 'cluster' ? '分布式' : '单机' }}</ElTag>
            </div>
            <div class="target-nodes">
              {{ target.nodes.map(n => getNodeDisplayName(n)).join(', ') }}
            </div>
          </div>
          <div class="target-actions">
            <ElButton size="small" type="primary" @click="loadSavedTarget(target)">加载</ElButton>
            <ElButton size="small" @click="openEditTargetDialog(target)">编辑</ElButton>
            <ElButton size="small" type="danger" :disabled="connected" @click="deleteSavedTarget(target)">删除</ElButton>
          </div>
        </div>
      </div>
    </ElDialog>
  </div>
</template>

<style scoped>
.iotdb-view {
  min-height: 100%;
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #ffffff;
  border-radius: 12px;
  margin-bottom: 16px;
}

.toolbar-spacer {
  flex: 1;
}

.target-select {
  width: 240px;
}

/* Content Area */
.content-area {
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
}

/* Tabs Header */
.tabs-header {
  border-bottom: 1px solid #e2e8f0;
}

.tabs-row {
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-bottom: 1px solid #f1f5f9;
}

.node-tabs {
  display: flex;
  gap: 0;
}

.node-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  transition: all 0.15s;
}

.node-tab:hover {
  color: #1e293b;
  background: #f8fafc;
}

.node-tab.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.node-tab-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-info {
  display: flex;
  align-items: center;
  margin-left: 12px;
}

.node-path {
  color: #64748b;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 4px;
}

.func-spacer {
  flex: 1;
}

.function-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
}

.func-tab {
  padding: 6px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  transition: all 0.15s;
}

.func-tab:hover {
  background: #f1f5f9;
}

.func-tab.active {
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 500;
}

.func-spacer {
  flex: 1;
}

/* Tab Content */
.tab-content {
  min-height: 500px;
}

/* CLI Panel */
.cli-panel {
  display: flex;
  flex-direction: column;
}

.cli-params {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
}

.cli-param {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cli-param label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.cli-param :deep(.el-input) {
  width: 140px;
}

.cli-actions {
  display: flex;
  gap: 6px;
}

.cli-terminal {
  height: 500px;
  background: #1e293b;
  padding: 12px;
  overflow: hidden;
}

.cli-terminal :deep(.xterm) {
  height: 100%;
}

.cli-terminal :deep(.xterm-viewport) {
  overflow-y: auto;
}

/* File Panel */
.file-panel {
  display: grid;
  grid-template-columns: 300px 1fr;
  height: 600px;
}

.file-sidebar {
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  font-weight: 500;
}

.file-list {
  flex: 1;
  overflow-y: auto;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  text-align: left;
}

.file-item:hover {
  background: #f8fafc;
}

.file-item.active {
  background: #eff6ff;
}

.file-item .file-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item .file-size {
  flex-shrink: 0;
  margin-left: 8px;
  font-size: 11px;
  color: #94a3b8;
}

.file-empty {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.file-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.content-title {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  color: #64748b;
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.content-actions :deep(.el-tag) {
  height: 28px;
  line-height: 26px;
}

.content-output {
  flex: 1;
  min-height: 0;
  padding: 12px;
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #f8fafc;
  color: #475569;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 100%;
}

.config-editor {
  flex: 1;
}

.config-editor :deep(.el-textarea) {
  height: 100%;
}

.config-editor :deep(textarea) {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #f8fafc;
  height: 100% !important;
  resize: none;
}

.content-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 14px;
}

/* Dialogs */
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-row label {
  width: 80px;
  font-size: 13px;
  color: #64748b;
}

.form-row :deep(.el-input),
.form-row :deep(.el-select) {
  flex: 1;
}

.nodes-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.node-row {
  display: grid;
  grid-template-columns: 100px 80px 1fr 1fr auto;
  gap: 8px;
  align-items: center;
}

.manage-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.manage-empty {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
}

.target-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.target-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.target-info {
  min-width: 0;
}

.target-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 4px;
}

.target-nodes {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.target-actions {
  display: flex;
  gap: 6px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  background: #ffffff;
  border-radius: 12px;
  color: #94a3b8;
  gap: 12px;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
}

/* Responsive */
@media (max-width: 900px) {
  .file-panel {
    grid-template-columns: 1fr;
  }

  .file-sidebar {
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
    max-height: 200px;
  }

  .cli-params {
    flex-wrap: wrap;
  }

  .cli-param :deep(.el-input) {
    width: 120px;
  }

  .node-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
