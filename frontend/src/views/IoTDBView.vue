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
import { Refresh, Platform, Delete, Plus, Edit, Link } from '@element-plus/icons-vue'
import { useServersStore } from '@/stores/servers'
import { useIoTDBStore } from '@/stores/iotdb'
import { iotdbApi } from '@/api'
import type { IoTDBFileInfo } from '@/types'

const serversStore = useServersStore()
const iotdbStore = useIoTDBStore()

type IoTDBConnectionMode = 'standalone' | 'cluster'
type IoTDBRestartScope = 'all' | 'cn' | 'dn'
type IoTDBSqlDialect = 'tree' | 'table'

interface SavedIoTDBNode {
  id: string
  name: string
  restartScope: IoTDBRestartScope
  serverId: number
  iotdbHome: string
}

interface EditableSavedIoTDBNode extends Omit<SavedIoTDBNode, 'serverId'> {
  serverId: number | null
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
const newTargetNodes = ref<EditableSavedIoTDBNode[]>([])
const connectedNodes = ref<SavedIoTDBNode[]>([])
const activeNodeId = ref('')
const activeTab = ref('cli-session')
const LOG_TAIL_LINES = 100
const MAX_LOG_VIEW_CHARS = 256 * 1024
const connected = ref(false)
const connecting = ref(false)
const connectionError = ref('')
const restarting = ref(false)
const SAVED_TARGETS_STORAGE_KEY = 'iotdb-visualization-targets'
const DEFAULT_CLI_HOST = '127.0.0.1'
const DEFAULT_CLI_PORT = 6667

// CLI state
const cliHostsByNode = ref<Record<string, string>>({})
const cliPortsByNode = ref<Record<string, number | null>>({})
const cliUsername = ref('')
const cliPassword = ref('')
const cliSqlDialect = ref<IoTDBSqlDialect>('tree')
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
const logContentLoadingByNode = ref<Record<string, boolean>>({})
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

const activeCliConnectButtonLabel = computed(() => {
  if (activeCliDefaultsLoading.value) return '读取 CLI 参数中'
  return '连接 CLI'
})

const connectionReady = computed(() => {
  return Boolean(connectedNodes.value.length || selectedSavedTarget.value)
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

function getSavedTargetMeta(target: SavedIoTDBTarget) {
  return target.mode === 'cluster' ? `${target.nodes.length} 节点分布式` : '单机'
}

function getSavedTargetById(targetId: string) {
  return savedTargets.value.find(target => target.id === targetId)
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
  newTargetMode.value = 'standalone'
  newTargetName.value = ''
  newTargetNodes.value = [{
    id: '',
    name: '节点 1',
    restartScope: 'all',
    serverId: null,
    iotdbHome: ''
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
    serverId: null,
    iotdbHome: ''
  }]
}

function addNewTargetNode() {
  newTargetMode.value = 'cluster'
  newTargetNodes.value.push({
    id: '',
    name: `节点 ${newTargetNodes.value.length + 1}`,
    restartScope: 'all',
    serverId: null,
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
    .filter((node): node is EditableSavedIoTDBNode & { serverId: number } => {
      return Number.isFinite(node.serverId) && Boolean(node.iotdbHome.trim())
    })
    .map<SavedIoTDBNode>((node, index) => {
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

async function deleteSavedTarget(target: SavedIoTDBTarget) {
  if (connected.value) {
    ElMessage.warning('请先断开连接再删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除连接「${target.name}」吗？`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    savedTargets.value = savedTargets.value.filter(item => item.id !== target.id)
    if (selectedSavedTargetId.value === target.id) {
      selectedSavedTargetId.value = ''
    }
    persistSavedTargets()
    ElMessage.success('已删除连接')
  } catch {
    // 用户取消
  }
}

async function connectSelectedOrCurrentTarget() {
  connectionError.value = ''
  if (selectedSavedTarget.value) {
    loadSelectedTarget(false)
  }
  await connectIoTDB()
}

async function autoConnectSelectedTarget(targetId: string) {
  if (!targetId || !selectedSavedTarget.value || connecting.value) return
  loadSelectedTarget(false)
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
  connectionError.value = ''
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

watch(selectedSavedTargetId, (targetId) => {
  if (!targetId) return
  void autoConnectSelectedTarget(targetId)
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
    connectionError.value = ''
    if (selectedSavedTarget.value && connectedNodes.value.length === 0) {
      applyTarget(selectedSavedTarget.value)
    }
    await reloadConnectedIoTDB()
    connected.value = true
    activeTab.value = 'cli-session'
    ElMessage.success('IoTDB 已连接')
  } catch (error) {
    connected.value = false
    connectionError.value = getErrorMessage(error, '连接 IoTDB 失败')
    ElMessage.error(getErrorMessage(error, '连接 IoTDB 失败'))
  }
}

function disconnectIoTDB() {
  connected.value = false
  selectedSavedTargetId.value = ''
  connectionError.value = ''
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
        cli_password: cliPassword.value || undefined,
        sql_dialect: cliSqlDialect.value
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
        <template #label="{ value }">
          <div v-if="value && getSavedTargetById(String(value))" class="saved-target-option">
            <span class="saved-target-option-name">{{ getSavedTargetById(String(value))?.name }}</span>
            <span class="saved-target-option-meta">{{ getSavedTargetMeta(getSavedTargetById(String(value))!) }}</span>
          </div>
        </template>
        <ElOption
          v-for="target in savedTargets"
          :key="target.id"
          :label="target.name"
          :value="target.id"
        >
          <div class="saved-target-option">
            <span class="saved-target-option-name">{{ target.name }}</span>
            <span class="saved-target-option-meta">{{ getSavedTargetMeta(target) }}</span>
          </div>
        </ElOption>
      </ElSelect>

      <ElButton @click="manageTargetsDialogVisible = true">
        管理
      </ElButton>

      <div class="toolbar-spacer" />

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
    <div v-if="connectedNodes.length > 0" class="content-area" :class="{ 'is-disabled': !connected }">
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
            <div class="cli-actions">
              <ElButton
                v-if="!activePersistentCliConnected"
                type="primary"
                :loading="activePersistentCliConnecting || activeCliDefaultsLoading"
                :disabled="!activeCliDefaultsLoaded"
                @click="handleConnectPersistentCli"
              >
                {{ activeCliConnectButtonLabel }}
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
              <label>Model</label>
              <ElSelect
                v-model="cliSqlDialect"
                :disabled="activePersistentCliConnected || activePersistentCliConnecting || activeCliDefaultsLoading"
              >
                <ElOption label="树模型" value="tree" />
                <ElOption label="表模型" value="table" />
              </ElSelect>
            </div>
            <div class="cli-param">
              <label>Host</label>
              <ElInput
                v-model="activeCliHost"
                placeholder="127.0.0.1"
                :disabled="activePersistentCliConnected || activePersistentCliConnecting || activeCliDefaultsLoading"
              />
            </div>
            <div class="cli-param">
              <label>Port</label>
              <ElInput
                v-model.number="activeCliPort"
                placeholder="6667"
                :disabled="activePersistentCliConnected || activePersistentCliConnecting || activeCliDefaultsLoading"
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
            v-for="node in connectedNodes"
            v-show="activeNodeId === node.id"
            :key="node.id"
            :ref="element => setPersistentTerminalRef(element, node.id)"
            class="cli-terminal"
            @click="focusPersistentTerminal(node.id)"
          ></div>
        </div>

        <!-- Logs -->
        <div
          v-show="activeTab === 'logs'"
          class="file-panel"
          :style="{ height: `${logPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT + 42}px` }"
        >
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
              <pre
                ref="logOutputRef"
                class="content-output log-output"
                :style="{ height: `${logPreviewHeight}px` }"
              >{{ activeLogContent || '等待日志...' }}</pre>
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
            <div v-else class="content-placeholder">选择日志文件</div>
          </div>
        </div>

        <!-- Configs -->
        <div
          v-show="activeTab === 'configs'"
          class="file-panel"
          :style="{ height: `${configPreviewHeight + LOG_RESIZE_HANDLE_HEIGHT + 42}px` }"
        >
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
              <div
                v-if="configEditMode"
                class="config-editor-shell"
                :style="{ height: `${configPreviewHeight}px` }"
              >
                <ElInput
                  v-model="configEditorContent"
                  type="textarea"
                  class="config-editor"
                  :input-style="{ height: '100%' }"
                />
              </div>
              <pre
                v-else
                class="content-output"
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
            <div v-else class="content-placeholder">选择配置文件</div>
          </div>
        </div>
      </div>
      <div v-if="!connected" class="content-mask">
        <div class="content-mask-card">
          <div class="content-mask-title">{{ connecting ? '连接中...' : (connectionError ? '连接失败' : '尚未连接') }}</div>
          <div class="content-mask-desc">
            {{ connecting ? '正在加载节点配置、日志和配置文件，请稍候。' : (connectionError || '请选择已保存连接，系统会自动发起连接。') }}
          </div>
          <ElButton
            v-if="!connecting && selectedSavedTarget"
            type="primary"
            size="small"
            class="content-mask-action"
            @click="connectSelectedOrCurrentTarget"
          >
            重试连接
          </ElButton>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <el-icon :size="48"><Platform /></el-icon>
      <p>选择已保存连接后会自动发起连接</p>
    </div>

    <!-- Create Target Dialog -->
    <ElDialog
      v-model="createTargetDialogVisible"
      width="640px"
      class="enhanced-dialog iotdb-dialog"
    >
      <template #header>
        <div class="dialog-header-enhanced">
          <div class="dialog-header-accent iotdb-accent"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon iotdb-icon">
              <el-icon :size="20"><Link /></el-icon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">{{ targetDialogTitle }}</h3>
              <p class="dialog-subtitle">配置 IoTDB 数据库连接</p>
            </div>
          </div>
        </div>
      </template>
      <div class="dialog-form-enhanced">
        <div class="form-row-enhanced">
          <label class="form-label">连接名称</label>
          <ElInput v-model="newTargetName" placeholder="留空自动生成" clearable />
        </div>
        <div class="nodes-section-enhanced">
          <div class="nodes-header">
            <span class="nodes-title">节点配置</span>
            <ElButton type="primary" plain size="small" @click="addNewTargetNode">
              <el-icon><Plus /></el-icon>
              添加节点
            </ElButton>
          </div>
          <div v-for="(node, index) in newTargetNodes" :key="index" class="node-row-enhanced">
            <ElSelect v-model="node.serverId" placeholder="选择服务器" class="node-server-select-enhanced" clearable>
              <ElOption
                v-for="server in serversStore.servers"
                :key="server.id"
                :label="`${server.host} (${server.name})`"
                :value="server.id"
              />
            </ElSelect>
            <ElInput v-model="node.iotdbHome" placeholder="IoTDB 安装路径" clearable class="node-path-input" />
            <ElButton
              v-if="newTargetNodes.length > 1"
              type="danger"
              :icon="Delete"
              @click="removeNewTargetNode(index)"
              circle
              size="small"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton @click="createTargetDialogVisible = false" class="btn-cancel">取消</ElButton>
          <ElButton type="primary" @click="createTargetFromDialog" class="btn-primary">
            <el-icon><Link /></el-icon>
            保存连接
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- Manage Targets Dialog -->
    <ElDialog v-model="manageTargetsDialogVisible" width="720px" class="enhanced-dialog manage-dialog">
      <template #header>
        <div class="dialog-header-enhanced manage-header">
          <div class="dialog-header-accent manage-accent"></div>
          <div class="dialog-header-content">
            <div class="dialog-header-icon manage-icon">
              <el-icon :size="20"><Platform /></el-icon>
            </div>
            <div class="dialog-header-text">
              <h3 class="dialog-title">管理连接</h3>
              <p class="dialog-subtitle">{{ savedTargets.length }} 个已保存的连接配置</p>
            </div>
          </div>
        </div>
      </template>
      <div v-if="savedTargets.length === 0" class="manage-empty-enhanced">
        <el-icon :size="48"><Platform /></el-icon>
        <p>暂无保存连接</p>
        <span class="manage-empty-tip">点击下方按钮新建连接</span>
      </div>
      <div v-else class="target-list-enhanced">
        <div
          v-for="target in savedTargets"
          :key="target.id"
          class="target-card-enhanced"
          @click="loadSavedTarget(target)"
        >
          <div class="target-card-row-enhanced">
            <div class="target-card-icon-enhanced">
              <el-icon :size="18"><Platform /></el-icon>
            </div>
            <div class="target-card-info-enhanced">
              <div class="target-card-name-enhanced">
                <span class="target-name-text">{{ target.name }}</span>
                <ElTag size="small" effect="plain" class="mode-tag">{{ target.mode === 'cluster' ? '分布式' : '单机' }}</ElTag>
              </div>
              <div class="target-card-nodes-enhanced">
                <div v-for="node in target.nodes" :key="node.id" class="node-line-enhanced">
                  <span class="node-main-enhanced">{{ node.name || getNodeTitle(node) }}</span>
                  <div class="node-sub-enhanced">
                    <span class="node-host">{{ serversStore.servers.find(s => s.id === node.serverId)?.host || `Server ${node.serverId}` }}</span>
                    <span class="node-separator"></span>
                    <span class="node-path">{{ node.iotdbHome }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="target-card-actions-enhanced">
              <ElButton size="small" @click.stop="openEditTargetDialog(target)">
                <el-icon><Edit /></el-icon>
                编辑
              </ElButton>
              <ElButton size="small" type="danger" :disabled="connected" @click.stop="deleteSavedTarget(target)">
                <el-icon><Delete /></el-icon>
                删除
              </ElButton>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer-enhanced">
          <ElButton type="primary" @click="openCreateTargetDialog" class="btn-primary">
            <el-icon><Plus /></el-icon>
            新建连接
          </ElButton>
        </div>
      </template>
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
  padding: 8px 10px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  margin-bottom: 10px;
}

.toolbar-spacer {
  flex: 1;
}

.target-select {
  width: 280px;
}

.saved-target-option {
  display: flex;
  align-items: baseline;
  justify-content: flex-start;
  gap: 6px;
  min-width: 0;
  width: 100%;
}

.saved-target-option-name {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1e293b;
}

.saved-target-option-meta {
  color: #94a3b8;
  font-size: 11px;
  flex-shrink: 0;
}

.target-select :deep(.el-select__selected-item) {
  min-width: 0;
}

/* Content Area */
.content-area {
  position: relative;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.content-area.is-disabled {
  user-select: none;
}

.content-area.is-disabled .tabs-header,
.content-area.is-disabled .tab-content {
  pointer-events: none;
  filter: grayscale(0.15);
}

.content-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(1px);
}

.content-mask-card {
  max-width: 320px;
  padding: 16px 18px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  text-align: center;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.content-mask-title {
  color: #1e293b;
  font-size: 14px;
  font-weight: 600;
}

.content-mask-desc {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.content-mask-action {
  margin-top: 12px;
}

/* Tabs Header */
.tabs-header {
  border-bottom: 1px solid #e2e8f0;
}

.tabs-row {
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid #f1f5f9;
}

.node-tabs {
  display: flex;
  gap: 0;
}

.node-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: #64748b;
  font-size: 12px;
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
  font-weight: 500;
}

.node-info {
  display: flex;
  align-items: center;
  margin-left: 8px;
}

.node-path {
  color: #64748b;
  font-size: 10px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  background: #f8fafc;
  padding: 2px 6px;
  border-radius: 4px;
}

.func-spacer {
  flex: 1;
}

.function-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
}

.func-tab {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: #64748b;
  font-size: 12px;
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
  min-height: 400px;
}

/* CLI Panel */
.cli-panel {
  display: flex;
  flex-direction: column;
}

.cli-params {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
}

.cli-param {
  display: flex;
  align-items: center;
  gap: 4px;
}

.cli-param label {
  font-size: 10px;
  color: #64748b;
  white-space: nowrap;
}

.cli-param :deep(.el-input) {
  width: 140px;
}

.cli-param :deep(.el-select) {
  width: 140px;
}

.cli-actions {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
}

.cli-terminal {
  position: relative;
  border: 1px solid #303743;
  border-radius: 4px;
  height: 720px;
  min-height: 360px;
  background: #1e293b;
  padding: 8px;
  overflow: hidden;
  outline: none;
}

.cli-terminal:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
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
  align-items: start;
}

.file-sidebar {
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
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
  min-height: 0;
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
  gap: 8px;
}

.content-actions :deep(.el-tag) {
  height: 28px;
  line-height: 26px;
}

.content-actions :deep(.el-button) {
  margin: 0;
}

.content-output {
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

.log-output {
  background: #1e1e1e;
  color: #d4d4d4;
}

.config-editor-shell {
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.config-editor {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.config-editor :deep(.el-textarea) {
  display: flex;
  flex: 1;
  min-height: 0;
  height: 100%;
}

.config-editor :deep(.el-textarea__inner) {
  flex: 1;
  min-height: 0;
  height: 100% !important;
  box-sizing: border-box;
}

.config-editor :deep(textarea) {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  background: #f8fafc;
  height: 100% !important;
  resize: none;
}

.log-resize-handle,
.config-resize-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 18px;
  border: none;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  cursor: ns-resize;
  padding: 0;
}

.log-resize-handle span,
.config-resize-handle span {
  width: 52px;
  height: 4px;
  border-radius: 999px;
  background: #cbd5e1;
}

.log-resize-handle.active span,
.config-resize-handle.active span,
.log-resize-handle:hover span,
.config-resize-handle:hover span {
  background: #94a3b8;
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
  gap: 20px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.form-row label {
  width: 90px;
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
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

.node-row-simple {
  display: flex;
  gap: 8px;
  align-items: center;
}

.node-server-select {
  width: 180px;
}

.node-row-simple :deep(.el-input) {
  flex: 1;
}

.manage-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 20px;
  color: #94a3b8;
}

.manage-empty p {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  color: #64748b;
}

.manage-empty-tip {
  font-size: 12px;
}

.target-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.target-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.target-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}

.target-card-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}

.target-card-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 8px;
  color: white;
  flex-shrink: 0;
}

.target-card-info {
  flex: 1;
  min-width: 0;
}

.target-card-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.target-card-nodes {
  margin-top: 6px;
}

.node-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 0;
}

.node-main {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
}

.node-sub {
  font-size: 11px;
  color: #64748b;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
}

.target-card-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
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

  .node-card-row {
    flex-direction: column;
    gap: 12px;
  }

  .node-field-large {
    flex: none;
  }
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

.iotdb-accent {
  background: linear-gradient(180deg, #10b981 0%, #34d399 100%);
}

.manage-accent {
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

.iotdb-icon {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.manage-icon {
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
}

.dialog-form-enhanced {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-row-enhanced {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
}

.nodes-section-enhanced {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nodes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
}

.nodes-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.node-row-enhanced {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.node-server-select-enhanced {
  width: 200px;
}

.node-path-input {
  flex: 1;
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

/* Manage Dialog Enhanced */
.manage-empty-enhanced {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 20px;
  color: #94a3b8;
}

.manage-empty-enhanced p {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  color: #64748b;
}

.manage-empty-tip {
  font-size: 12px;
}

.target-list-enhanced {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 24px;
}

.target-card-enhanced {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.target-card-enhanced:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-2px);
}

.target-card-row-enhanced {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}

.target-card-icon-enhanced {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-radius: 10px;
  color: white;
  flex-shrink: 0;
}

.target-card-info-enhanced {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.target-card-name-enhanced {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  padding-bottom: 8px;
  border-bottom: 1px dashed #e2e8f0;
}

.target-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.mode-tag {
  font-size: 10px;
  padding: 1px 6px;
}

.target-card-nodes-enhanced {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-line-enhanced {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.node-main-enhanced {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
}

.node-sub-enhanced {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
}

.node-host {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  color: #3b82f6;
}

.node-separator {
  width: 1px;
  height: 12px;
  background: linear-gradient(to bottom, transparent, #94a3b8, transparent);
}

.node-path {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  color: #64748b;
}

.target-card-actions-enhanced {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
</style>
