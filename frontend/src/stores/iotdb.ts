import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { IoTDBFileInfo } from '@/types'
import { iotdbApi } from '@/api'

export const useIoTDBStore = defineStore('iotdb', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Logs state
  const logFiles = ref<IoTDBFileInfo[]>([])
  const logContent = ref<string>('')
  const currentLogFile = ref<string>('')
  const logsLoading = ref(false)

  // Configs state
  const configFiles = ref<IoTDBFileInfo[]>([])
  const configContent = ref<string>('')
  const currentConfigFile = ref<string>('')
  const configsLoading = ref(false)
  const configSaving = ref(false)

  // List log files
  async function listLogFiles(serverId: number, iotdbHome: string) {
    logsLoading.value = true
    error.value = null
    try {
      logFiles.value = await iotdbApi.listLogs(serverId, iotdbHome)
      return logFiles.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to list log files'
      throw e
    } finally {
      logsLoading.value = false
    }
  }

  // Read log file
  async function readLogFile(serverId: number, iotdbHome: string, path: string, tail?: number) {
    logsLoading.value = true
    error.value = null
    try {
      const result = await iotdbApi.readLog(serverId, iotdbHome, path, tail)
      logContent.value = result.content
      currentLogFile.value = path
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to read log file'
      throw e
    } finally {
      logsLoading.value = false
    }
  }

  // List config files
  async function listConfigFiles(serverId: number, iotdbHome: string) {
    configsLoading.value = true
    error.value = null
    try {
      configFiles.value = await iotdbApi.listConfigs(serverId, iotdbHome)
      return configFiles.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to list config files'
      throw e
    } finally {
      configsLoading.value = false
    }
  }

  // Read config file
  async function readConfigFile(serverId: number, iotdbHome: string, path: string) {
    configsLoading.value = true
    error.value = null
    try {
      const result = await iotdbApi.readConfig(serverId, iotdbHome, path)
      configContent.value = result.content
      currentConfigFile.value = path
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to read config file'
      throw e
    } finally {
      configsLoading.value = false
    }
  }

  // Write config file
  async function writeConfigFile(serverId: number, iotdbHome: string, path: string, content: string) {
    configSaving.value = true
    error.value = null
    try {
      const result = await iotdbApi.writeConfig(serverId, iotdbHome, path, content)
      if (result.success) {
        configContent.value = content
      }
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to write config file'
      throw e
    } finally {
      configSaving.value = false
    }
  }

  // Restart IoTDB
  async function restartIoTDB(serverId: number, iotdbHome: string, restartScope = 'all') {
    loading.value = true
    error.value = null
    try {
      const result = await iotdbApi.restart(serverId, iotdbHome, restartScope)
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to restart IoTDB'
      throw e
    } finally {
      loading.value = false
    }
  }

  // Clear state
  function clearState() {
    logFiles.value = []
    logContent.value = ''
    currentLogFile.value = ''
    configFiles.value = []
    configContent.value = ''
    currentConfigFile.value = ''
    error.value = null
  }

  return {
    loading,
    error,
    logFiles,
    logContent,
    currentLogFile,
    logsLoading,
    configFiles,
    configContent,
    currentConfigFile,
    configsLoading,
    configSaving,
    listLogFiles,
    readLogFile,
    listConfigFiles,
    readConfigFile,
    writeConfigFile,
    restartIoTDB,
    clearState
  }
})
