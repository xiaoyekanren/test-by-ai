import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export interface MonitorSettings {
  refreshInterval: number // seconds, default 10
}

export interface Settings {
  monitor: MonitorSettings
}

const DEFAULT_SETTINGS: Settings = {
  monitor: {
    refreshInterval: 10
  }
}

const STORAGE_KEY = 'system-settings'

export const useSettingsStore = defineStore('settings', () => {
  // Load from localStorage
  function loadSettings(): Settings {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return {
          ...DEFAULT_SETTINGS,
          ...parsed,
          monitor: { ...DEFAULT_SETTINGS.monitor, ...parsed.monitor }
        }
      }
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
    return { ...DEFAULT_SETTINGS }
  }

  const settings = ref<Settings>(loadSettings())

  // Save to localStorage on change
  watch(settings, (newVal) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newVal))
    } catch (e) {
      console.error('Failed to save settings:', e)
    }
  }, { deep: true })

  function updateMonitorSettings(newSettings: Partial<MonitorSettings>) {
    settings.value.monitor = { ...settings.value.monitor, ...newSettings }
  }

  function resetSettings() {
    settings.value = { ...DEFAULT_SETTINGS }
  }

  return {
    settings,
    updateMonitorSettings,
    resetSettings
  }
})