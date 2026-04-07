import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { IoTDBFileInfo, IoTDBCLIResult, IoTDBLogContent, IoTDBConfigContent, IoTDBRestartResult } from '@/types'
import { iotdbApi } from '@/api'

export const useIoTDBStore = defineStore('iotdb', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)

  // CLI state
  const cliResult = ref<IoTDBCLIResult | null>(null)
  const cliLoading = ref(false)

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

  // Execute CLI command
  async function executeCLI(serverId: number, iotdbHome: string, sql: string, timeout?: number) {
    cliLoading.value = true
    error.value = null
    try {
      cliResult.value = await iotdbApi.cli(serverId, iotdbHome, sql, timeout)
      return cliResult.value
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to execute CLI'
      throw e
    } finally {
      cliLoading.value = false
    }
  }

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
  async function readLogFile(serverId: number, path: string, tail?: number) {
    logsLoading.value = true
    error.value = null
    try {
      const result = await iotdbApi.readLog(serverId, path, tail)
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
  async function readConfigFile(serverId: number, path: string) {
    configsLoading.value = true
    error.value = null
    try {
      const result = await iotdbApi.readConfig(serverId, path)
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
  async function writeConfigFile(serverId: number, path: string, content: string) {
    configSaving.value = true
    error.value = null
    try {
      const result = await iotdbApi.writeConfig(serverId, path, content)
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
  async function restartIoTDB(serverId: number, iotdbHome: string) {
    loading.value = true
    error.value = null
    try {
      const result = await iotdbApi.restart(serverId, iotdbHome)
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
    cliResult.value = null
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
    cliResult,
    cliLoading,
    logFiles,
    logContent,
    currentLogFile,
    logsLoading,
    configFiles,
    configContent,
    currentConfigFile,
    configsLoading,
    configSaving,
    executeCLI,
    listLogFiles,
    readLogFile,
    listConfigFiles,
    readConfigFile,
    writeConfigFile,
    restartIoTDB,
    clearState
  }
})