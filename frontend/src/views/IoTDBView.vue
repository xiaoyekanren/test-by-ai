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
  ElDialog,
  ElTag,
  vLoading
} from 'element-plus'
import { Refresh, Document, Setting, Platform } from '@element-plus/icons-vue'
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
const configFilesByNode = ref<Record<string, IoTDBFileInfo[]>>({})
const configContentByNode = ref<Record<string, string>>({})
const configsLoadingByNode = ref<Record<string, boolean>>({})
const configSavingByNode = ref<Record<string, boolean>>({})
const configPreviewHeight = ref(LOG_PREVIEW_DEFAULT_HEIGHT)
const resizingConfigPreview = ref(false)
let configPreviewResizeStartY = 0
let configPreviewResizeStartHeight = LOG_PREVIEW_DEFAULT_HEIGHT

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
  try {
    const result = await iotdbApi.readLog(activeNode.value.serverId, activeNode.value.iotdbHome, path, LOG_TAIL_LINES)
    logContentByNode.value[activeNode.value.id] = result.content
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
    <!-- Top Control Card -->
    <div class="connection-card">
      <div class="connection-card-header">
        <div>
          <div class="connection-card-title">连接控制</div>
          <div class="connection-card-desc">选择连接组后加载节点、刷新配置，CLI 会按节点常驻。</div>
        </div>
        <ElTag v-if="currentTargetLabel" type="info" size="small" class="current-target-tag">
          当前：{{ currentTargetLabel }}
        </ElTag>
      </div>

      <div class="control-bar">
        <div class="open-target-group">
          <ElSelect
            v-model="selectedSavedTargetId"
            placeholder="已保存连接"
            class="saved-target-select"
            clearable
          >
            <ElOption
              v-for="target in savedTargets"
              :key="target.id"
              :label="target.name"
              :value="target.id"
            />
          </ElSelect>
        </div>

        <ElButton
          type="primary"
          :loading="connecting"
          :disabled="connected || (!connectionReady && !selectedSavedTarget)"
          @click="connectSelectedOrCurrentTarget"
        >
          连接
        </ElButton>

        <ElButton @click="manageTargetsDialogVisible = true">
          管理连接
        </ElButton>

        <div class="control-spacer" />

        <ElButton
          type="danger"
          :disabled="!connected"
          @click="disconnectIoTDB"
        >
          断开
        </ElButton>

        <ElButton
          :icon="Refresh"
          :disabled="!connected"
          :loading="connecting"
          @click="reloadCurrentConnection"
        >
          刷新
        </ElButton>
      </div>
    </div>

    <ElDialog
      v-model="createTargetDialogVisible"
      :title="targetDialogTitle"
      width="720px"
    >
      <div class="create-target-form">
        <label class="create-target-field">
          <span>连接名称</span>
          <ElInput
            v-model="newTargetName"
            placeholder="如 test-cluster，留空自动生成"
            clearable
          />
        </label>

        <label class="create-target-field">
          <span>模式</span>
          <ElSelect v-model="newTargetMode" @change="ensureNewTargetNodes">
            <ElOption label="单机" value="standalone" />
            <ElOption label="分布式" value="cluster" />
          </ElSelect>
        </label>

        <div class="create-node-list">
          <div
            v-for="(node, index) in newTargetNodes"
            :key="index"
            class="create-node-row"
          >
            <ElInput
              v-model="node.name"
              placeholder="节点名"
              class="node-name-input"
              clearable
            />
            <ElSelect
              v-model="node.restartScope"
              class="node-scope-select"
            >
              <ElOption label="ALL" value="all" />
              <ElOption label="CN" value="cn" />
              <ElOption label="DN" value="dn" />
            </ElSelect>
            <ElSelect
              v-model="node.serverId"
              placeholder="选择 IP"
              class="node-server-select"
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
              v-model="node.iotdbHome"
              placeholder="如 /opt/iotdb"
              class="node-home-input"
              clearable
            />
            <ElButton
              type="danger"
              plain
              :disabled="newTargetNodes.length <= 1"
              @click="removeNewTargetNode(index)"
            >
              删除
            </ElButton>
          </div>
        </div>

        <ElButton
          v-if="newTargetMode === 'cluster'"
          type="primary"
          plain
          @click="addNewTargetNode"
        >
          添加节点
        </ElButton>
      </div>

      <template #footer>
        <ElButton @click="createTargetDialogVisible = false">
          取消
        </ElButton>
        <ElButton type="primary" @click="createTargetFromDialog">
          保存并加载
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="manageTargetsDialogVisible"
      title="管理连接"
      width="760px"
    >
      <div class="manage-toolbar">
        <ElButton type="primary" @click="openCreateTargetDialog">
          新建连接
        </ElButton>
      </div>

      <div v-if="savedTargets.length === 0" class="manage-empty">
        暂无保存连接
      </div>

      <div v-else class="saved-target-list">
        <div
          v-for="target in savedTargets"
          :key="target.id"
          class="saved-target-item"
        >
          <div class="saved-target-main">
            <div class="saved-target-title">
              <span>{{ target.name }}</span>
              <ElTag size="small" effect="plain">
                {{ target.mode === 'cluster' ? '分布式' : '单机' }}
              </ElTag>
              <ElTag size="small" type="info" effect="plain">
                {{ target.nodes.length }} 节点
              </ElTag>
            </div>
            <div class="saved-target-nodes">
              <div
                v-for="node in target.nodes.slice(0, 5)"
                :key="node.id"
              >
                {{ getNodeDisplayName(node) }}
              </div>
              <div v-if="target.nodes.length > 5">...</div>
            </div>
          </div>
          <div class="saved-target-actions">
            <ElButton
              type="primary"
              plain
              @click="loadSavedTarget(target)"
            >
              加载
            </ElButton>
            <ElButton
              @click="openEditTargetDialog(target)"
            >
              编辑
            </ElButton>
            <ElButton
              type="danger"
              plain
              :disabled="connected"
              @click="deleteSavedTarget(target)"
            >
              删除
            </ElButton>
          </div>
        </div>
      </div>
    </ElDialog>

    <!-- Tab Area -->
    <ElTabs v-model="activeNodeId" class="node-tabs iotdb-node-tabs" v-if="connected">
      <ElTabPane
        v-for="node in connectedNodes"
        :key="node.id"
        :name="node.id"
      >
        <template #label>
          <span class="node-tab-label">
            <span>{{ getNodeTitle(node) }}</span>
            <ElTag size="small" type="info" effect="plain">
              {{ getRestartScopeLabel(node.restartScope) }}
            </ElTag>
          </span>
        </template>

        <div class="node-action-bar">
          <div class="node-action-info">
            <div class="node-title-stack">
              <div class="node-title-row">
                <span class="node-action-title">{{ getNodeTitle(node) }}</span>
                <ElTag size="small" type="info" effect="plain">
                  {{ getRestartScopeLabel(node.restartScope) }}
                </ElTag>
              </div>
              <span class="node-action-path">{{ node.iotdbHome }}</span>
            </div>
          </div>
          <div class="node-action-right">
            <div class="node-function-actions">
              <ElButton
                :type="activeTab === 'cli-session' ? 'primary' : 'default'"
                plain
                @click="activeTab = 'cli-session'"
              >
                CLI
              </ElButton>
              <ElButton
                :type="activeTab === 'logs' ? 'primary' : 'default'"
                plain
                @click="activeTab = 'logs'"
              >
                日志管理
              </ElButton>
              <ElButton
                :type="activeTab === 'configs' ? 'primary' : 'default'"
                plain
                @click="activeTab = 'configs'"
              >
                配置管理
              </ElButton>
              <ElButton
                type="warning"
                :disabled="!connected || activeNodeId !== node.id"
                :loading="restarting && activeNodeId === node.id"
                @click="restartActiveNode"
              >
                重启当前节点
              </ElButton>
            </div>
          </div>
        </div>

        <ElTabs v-model="activeTab" class="iotdb-tabs node-function-tabs">
          <ElTabPane label="CLI" name="cli-session">
            <div class="cli-section">
              <div class="cli-connection-panel">
                <div class="cli-param">
                  <span class="cli-param-label">Host (-h)</span>
                  <ElInput
                    v-model="activeCliHost"
                    placeholder="默认 127.0.0.1"
                    clearable
                    :disabled="activePersistentCliConnected || activePersistentCliConnecting || activeCliDefaultsLoading"
                  />
                </div>
                <div class="cli-param">
                  <span class="cli-param-label">Port (-p)</span>
                  <ElInput
                    v-model.number="activeCliPort"
                    placeholder="默认 6667"
                    clearable
                    :disabled="activePersistentCliConnected || activePersistentCliConnecting || activeCliDefaultsLoading"
                  />
                </div>
                <div class="cli-param">
                  <span class="cli-param-label">User (-u)</span>
                  <ElInput
                    v-model="cliUsername"
                    placeholder="留空则不指定"
                    clearable
                    :disabled="activePersistentCliConnected || activePersistentCliConnecting"
                  />
                </div>
                <div class="cli-param">
                  <span class="cli-param-label">Password (-pw)</span>
                  <ElInput
                    v-model="cliPassword"
                    placeholder="留空则不指定"
                    show-password
                    clearable
                    :disabled="activePersistentCliConnected || activePersistentCliConnecting"
                  />
                </div>
              </div>
              <div class="persistent-cli-toolbar">
                <ElTag
                  :type="activePersistentCliConnected ? 'success' : (activeCliDefaultsLoading ? 'warning' : 'info')"
                  effect="plain"
                >
                  {{ activePersistentCliConnected ? 'CLI 已连接' : (activeCliDefaultsLoading ? '读取 CLI 参数中' : 'CLI 未连接') }}
                </ElTag>
                <ElButton
                  v-if="!activePersistentCliConnected"
                  type="primary"
                  :loading="activePersistentCliConnecting || activeCliDefaultsLoading"
                  :disabled="!activeCliDefaultsLoaded"
                  @click="handleConnectPersistentCli"
                >
                  连接 CLI
                </ElButton>
                <ElButton
                  v-else
                  type="danger"
                  @click="closePersistentCliSession(true, node.id)"
                >
                  断开 CLI
                </ElButton>
                <ElButton @click="clearPersistentCliOutput">
                  清空输出
                </ElButton>
              </div>

              <div
                :ref="element => setPersistentTerminalRef(element, node.id)"
                class="persistent-cli-terminal"
                @click="focusPersistentTerminal(node.id)"
              ></div>
            </div>
          </ElTabPane>

          <ElTabPane label="日志管理" name="logs">
            <div class="logs-section">
              <div class="file-layout">
                <aside
                  class="file-panel"
                  v-loading="activeLogsLoading"
                >
                  <div class="file-panel-header">
                    <span>日志目录</span>
                    <ElButton
                      size="small"
                      :icon="Refresh"
                      @click="refreshLogFiles()"
                      :loading="activeLogsLoading"
                    >
                      刷新
                    </ElButton>
                  </div>

                  <div v-if="activeLogFiles.length === 0" class="file-empty">
                    暂无日志文件
                  </div>

                  <div
                    v-else
                    class="file-list log-file-list"
                    :style="{ height: `${logPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT}px` }"
                  >
                    <button
                      v-for="file in activeLogFiles"
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
                          :loading="activeLogsLoading"
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
                    >{{ activeLogContent || '等待日志输出...' }}</pre>
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

          <ElTabPane label="配置管理" name="configs">
            <div class="configs-section">
              <div class="file-layout">
                <aside
                  class="file-panel"
                  v-loading="activeConfigsLoading"
                >
                  <div class="file-panel-header">
                    <span>配置目录</span>
                    <ElButton
                      size="small"
                      :icon="Refresh"
                      @click="refreshConfigFiles()"
                      :loading="activeConfigsLoading"
                    >
                      刷新
                    </ElButton>
                  </div>

                  <div v-if="activeConfigFiles.length === 0" class="file-empty">
                    暂无配置文件
                  </div>

                  <div
                    v-else
                    class="file-list config-file-list"
                    :style="{ height: `${configPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT}px` }"
                  >
                    <button
                      v-for="file in activeConfigFiles"
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
                            :loading="activeConfigSaving"
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
                    >{{ activeConfigContent }}</pre>
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
      </ElTabPane>
    </ElTabs>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <el-icon :size="64"><Platform /></el-icon>
      <p>请选择已保存连接，或新建单机/分布式连接后点击连接</p>
    </div>
  </div>
</template>

<style scoped>
.iotdb-view {
  padding: 0;
}

.connection-card {
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.connection-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid #ebeef5;
}

.connection-card-title {
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.connection-card-desc {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}

.control-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.open-target-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.control-spacer {
  flex: 1 1 auto;
}

.saved-target-select {
  width: 320px;
}

.current-target-tag {
  max-width: 420px;
}

.current-target-tag :deep(.el-tag__content) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.create-target-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.create-target-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #606266;
  font-size: 13px;
}

.create-node-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.create-node-row {
  display: grid;
  grid-template-columns: minmax(100px, 1fr) 120px minmax(160px, 1.2fr) minmax(180px, 1.4fr) auto;
  gap: 8px;
  align-items: center;
}

.node-tabs {
  width: 100%;
}

.node-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.node-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 260px;
}

.node-tab-label > span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-action-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 12px 16px;
  margin: 14px 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.node-action-info {
  display: flex;
  align-items: center;
  flex: 0 1 360px;
  min-width: 180px;
  gap: 8px;
}

.node-title-stack {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}

.node-title-row {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.node-action-title {
  min-width: 0;
  overflow: hidden;
  color: #303133;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-action-path {
  min-width: 0;
  overflow: hidden;
  color: #909399;
  font-size: 12px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-action-right {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 360px;
}

.node-function-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  margin-right: auto;
  flex-wrap: wrap;
}

.node-function-actions :deep(.el-button) {
  height: 30px;
  padding: 6px 12px;
}

.manage-empty {
  padding: 32px 0;
  color: #909399;
  text-align: center;
}

.manage-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.saved-target-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.saved-target-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
}

.saved-target-main {
  min-width: 0;
}

.saved-target-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.saved-target-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #303133;
  font-weight: 600;
}

.saved-target-nodes {
  display: block;
  max-width: 520px;
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.iotdb-tabs {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 20px;
}

.node-function-tabs :deep(.el-tabs__header) {
  display: none;
}

/* CLI Section */
.cli-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cli-connection-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #f8fbff;
  flex-wrap: wrap;
}

.cli-param {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.cli-param:nth-child(1),
.cli-param:nth-child(3),
.cli-param:nth-child(4) {
  flex: 1 1 180px;
}

.cli-param:nth-child(2) {
  flex: 0 1 140px;
}

.cli-param-label {
  color: #606266;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.cli-param :deep(.el-input) {
  min-width: 0;
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
  .file-layout {
    grid-template-columns: 1fr;
  }

  .node-action-bar,
  .node-action-right,
  .cli-connection-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .node-action-info,
  .node-action-right {
    min-width: 0;
    width: 100%;
  }

  .node-function-actions {
    margin-right: 0;
  }
}
</style>
