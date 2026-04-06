<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElSwitch,
  ElTag
} from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const saving = ref(false)

const monitorForm = ref({
  refreshInterval: 10
})

const observabilityForm = ref({
  prometheusUrl: '',
  grafanaUrl: '',
  grafanaDashboardUid: '',
  grafanaDatasource: '',
  grafanaOrgId: '',
  grafanaTimeRange: 'now-6h',
  grafanaEmbedEnabled: false
})

function syncFormsFromStore() {
  monitorForm.value.refreshInterval = settingsStore.settings.monitor.refreshInterval
  observabilityForm.value = {
    prometheusUrl: settingsStore.settings.observability.prometheusUrl ?? '',
    grafanaUrl: settingsStore.settings.observability.grafanaUrl ?? '',
    grafanaDashboardUid: settingsStore.settings.observability.grafanaDashboardUid ?? '',
    grafanaDatasource: settingsStore.settings.observability.grafanaDatasource ?? '',
    grafanaOrgId: settingsStore.settings.observability.grafanaOrgId ?? '',
    grafanaTimeRange: settingsStore.settings.observability.grafanaTimeRange,
    grafanaEmbedEnabled: settingsStore.settings.observability.grafanaEmbedEnabled
  }
}

watch(() => settingsStore.settings, syncFormsFromStore, { deep: true })

const hasChanges = computed(() => {
  const { monitor, observability } = settingsStore.settings
  return (
    monitorForm.value.refreshInterval !== monitor.refreshInterval ||
    observabilityForm.value.prometheusUrl !== (observability.prometheusUrl ?? '') ||
    observabilityForm.value.grafanaUrl !== (observability.grafanaUrl ?? '') ||
    observabilityForm.value.grafanaDashboardUid !== (observability.grafanaDashboardUid ?? '') ||
    observabilityForm.value.grafanaDatasource !== (observability.grafanaDatasource ?? '') ||
    observabilityForm.value.grafanaOrgId !== (observability.grafanaOrgId ?? '') ||
    observabilityForm.value.grafanaTimeRange !== observability.grafanaTimeRange ||
    observabilityForm.value.grafanaEmbedEnabled !== observability.grafanaEmbedEnabled
  )
})

async function handleSave() {
  saving.value = true
  try {
    await settingsStore.updateMonitorSettings({
      refreshInterval: monitorForm.value.refreshInterval
    })

    await settingsStore.updateObservabilitySettings({
      prometheusUrl: observabilityForm.value.prometheusUrl || null,
      grafanaUrl: observabilityForm.value.grafanaUrl || null,
      grafanaDashboardUid: observabilityForm.value.grafanaDashboardUid || null,
      grafanaDatasource: observabilityForm.value.grafanaDatasource || null,
      grafanaOrgId: observabilityForm.value.grafanaOrgId || null,
      grafanaTimeRange: observabilityForm.value.grafanaTimeRange || 'now-6h',
      grafanaEmbedEnabled: observabilityForm.value.grafanaEmbedEnabled
    })

    ElMessage.success('Settings saved')
  } catch (error) {
    console.error(error)
    ElMessage.error('Failed to save settings')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  saving.value = true
  try {
    await settingsStore.resetSettings()
    ElMessage.success('Settings reset to defaults')
  } catch (error) {
    console.error(error)
    ElMessage.error('Failed to reset settings')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  syncFormsFromStore()
})
</script>

<template>
  <div class="settings-view">
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>System Settings</h2>
      </div>
      <div class="toolbar-actions">
        <ElButton @click="handleReset" :icon="Refresh" :loading="saving">
          Reset
        </ElButton>
        <ElButton type="primary" @click="handleSave" :disabled="!hasChanges" :loading="saving">
          Save
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="info" size="small">Monitor</ElTag>
          <span>System monitor refresh settings</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="Refresh interval">
          <ElInputNumber
            v-model="monitorForm.refreshInterval"
            :min="5"
            :max="300"
            :step="5"
            style="width: 180px"
          />
          <span class="unit">seconds</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="Current refresh interval">
          {{ settingsStore.settings.monitor.refreshInterval }} seconds
        </ElDescriptionsItem>
        <ElDescriptionsItem label="Usage">
          Controls how often the monitor dashboard refreshes local and remote server metrics.
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="success" size="small">Observability</ElTag>
          <span>External Prometheus and Grafana entry points</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="Prometheus URL">
          <ElInput
            v-model="observabilityForm.prometheusUrl"
            placeholder="http://prometheus.example.com:9090"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana URL">
          <ElInput
            v-model="observabilityForm.grafanaUrl"
            placeholder="http://grafana.example.com:3000"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana dashboard UID">
          <ElInput
            v-model="observabilityForm.grafanaDashboardUid"
            placeholder="iotdb-overview"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana datasource">
          <ElInput
            v-model="observabilityForm.grafanaDatasource"
            placeholder="Prometheus"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana org ID">
          <ElInput
            v-model="observabilityForm.grafanaOrgId"
            placeholder="1"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Default time range">
          <ElInput
            v-model="observabilityForm.grafanaTimeRange"
            placeholder="now-6h"
          />
        </ElFormItem>

        <ElFormItem label="Grafana embed mode">
          <ElSwitch v-model="observabilityForm.grafanaEmbedEnabled" />
          <span class="hint">Adds kiosk mode to dashboard links for cleaner wallboard views.</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="Recommended setup">
          Keep Prometheus and Grafana external to this app, and use these URLs as shared entry points.
        </ElDescriptionsItem>
        <ElDescriptionsItem label="Where it appears">
          The monitor page will show quick links to the configured Prometheus and Grafana targets.
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>
  </div>
</template>

<style scoped>
.settings-view {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.toolbar-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
}

.settings-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit {
  margin-left: 8px;
  color: #909399;
}

.hint {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}
</style>
