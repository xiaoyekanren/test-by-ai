import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { settingsApi, type SettingsPayload } from '@/api'

export interface MonitorSettings {
  refreshInterval: number
}

export interface ObservabilitySettings {
  prometheusUrl: string | null
  grafanaUrl: string | null
  grafanaDashboardUid: string | null
  grafanaDatasource: string | null
  grafanaOrgId: string | null
  grafanaTimeRange: string
  grafanaEmbedEnabled: boolean
}

export interface Settings {
  monitor: MonitorSettings
  observability: ObservabilitySettings
}

const DEFAULT_SETTINGS: Settings = {
  monitor: {
    refreshInterval: 10
  },
  observability: {
    prometheusUrl: null,
    grafanaUrl: null,
    grafanaDashboardUid: null,
    grafanaDatasource: null,
    grafanaOrgId: null,
    grafanaTimeRange: 'now-6h',
    grafanaEmbedEnabled: false
  }
}

const STORAGE_KEY = 'system-settings'

function mergeSettings(value?: Partial<SettingsPayload> | null): Settings {
  return {
    monitor: {
      ...DEFAULT_SETTINGS.monitor,
      ...(value?.monitor ?? {})
    },
    observability: {
      ...DEFAULT_SETTINGS.observability,
      ...(value?.observability ?? {})
    }
  }
}

function loadLocalSettings(): Settings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return mergeSettings(JSON.parse(stored))
    }
  } catch (error) {
    console.error('Failed to load settings from local cache:', error)
  }

  return mergeSettings()
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings>(loadLocalSettings())
  const loading = ref(false)
  const loaded = ref(false)

  watch(
    settings,
    (newValue) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newValue))
      } catch (error) {
        console.error('Failed to save settings to local cache:', error)
      }
    },
    { deep: true }
  )

  const hasObservabilityConfigured = computed(() => {
    const { prometheusUrl, grafanaUrl } = settings.value.observability
    return Boolean(prometheusUrl || grafanaUrl)
  })

  async function fetchSettings(force = false) {
    if (loading.value || (loaded.value && !force)) {
      return settings.value
    }

    loading.value = true
    try {
      const remoteSettings = await settingsApi.get()
      settings.value = mergeSettings(remoteSettings)
      loaded.value = true
      return settings.value
    } catch (error) {
      console.error('Failed to fetch settings from backend:', error)
      loaded.value = true
      return settings.value
    } finally {
      loading.value = false
    }
  }

  async function updateMonitorSettings(newSettings: Partial<MonitorSettings>) {
    const nextSettings = {
      ...settings.value.monitor,
      ...newSettings
    }
    const response = await settingsApi.update({ monitor: nextSettings })
    settings.value = mergeSettings(response)
  }

  async function updateObservabilitySettings(newSettings: Partial<ObservabilitySettings>) {
    const nextSettings = {
      ...settings.value.observability,
      ...newSettings
    }
    const response = await settingsApi.update({ observability: nextSettings })
    settings.value = mergeSettings(response)
  }

  async function resetSettings() {
    const response = await settingsApi.update(DEFAULT_SETTINGS)
    settings.value = mergeSettings(response)
  }

  function buildGrafanaDashboardUrl() {
    const {
      grafanaUrl,
      grafanaDashboardUid,
      grafanaOrgId,
      grafanaTimeRange,
      grafanaEmbedEnabled
    } = settings.value.observability

    if (!grafanaUrl) {
      return null
    }

    const baseUrl = grafanaUrl.replace(/\/$/, '')
    if (!grafanaDashboardUid) {
      return baseUrl
    }

    const params = new URLSearchParams()
    if (grafanaOrgId) {
      params.set('orgId', grafanaOrgId)
    }
    if (grafanaTimeRange) {
      params.set('from', grafanaTimeRange)
      params.set('to', 'now')
    }
    if (grafanaEmbedEnabled) {
      params.set('kiosk', 'tv')
    }

    const query = params.toString()
    return `${baseUrl}/d/${grafanaDashboardUid}${query ? `?${query}` : ''}`
  }

  return {
    settings,
    loading,
    loaded,
    hasObservabilityConfigured,
    fetchSettings,
    updateMonitorSettings,
    updateObservabilitySettings,
    resetSettings,
    buildGrafanaDashboardUrl
  }
})
