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

    ElMessage.success('设置已保存')
  } catch (error) {
    console.error(error)
    ElMessage.error('保存设置失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  saving.value = true
  try {
    await settingsStore.resetSettings()
    ElMessage.success('设置已恢复默认值')
  } catch (error) {
    console.error(error)
    ElMessage.error('重置设置失败')
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
        <h2>系统设置</h2>
      </div>
      <div class="toolbar-actions">
        <ElButton @click="handleReset" :icon="Refresh" :loading="saving">
          重置
        </ElButton>
        <ElButton type="primary" @click="handleSave" :disabled="!hasChanges" :loading="saving">
          保存
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="info" size="small">监控</ElTag>
          <span>系统监控刷新设置</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="刷新间隔">
          <ElInputNumber
            v-model="monitorForm.refreshInterval"
            :min="5"
            :max="300"
            :step="5"
            style="width: 180px"
          />
          <span class="unit">秒</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="当前刷新间隔">
          {{ settingsStore.settings.monitor.refreshInterval }} 秒
        </ElDescriptionsItem>
        <ElDescriptionsItem label="说明">
          控制监控面板刷新本地和远程服务器指标的频率。
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="success" size="small">可观测性</ElTag>
          <span>外部 Prometheus 和 Grafana 入口配置</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="Prometheus 地址">
          <ElInput
            v-model="observabilityForm.prometheusUrl"
            placeholder="http://prometheus.example.com:9090"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 地址">
          <ElInput
            v-model="observabilityForm.grafanaUrl"
            placeholder="http://grafana.example.com:3000"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 仪表盘 UID">
          <ElInput
            v-model="observabilityForm.grafanaDashboardUid"
            placeholder="iotdb-overview"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 数据源">
          <ElInput
            v-model="observabilityForm.grafanaDatasource"
            placeholder="Prometheus"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 组织 ID">
          <ElInput
            v-model="observabilityForm.grafanaOrgId"
            placeholder="1"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="默认时间范围">
          <ElInput
            v-model="observabilityForm.grafanaTimeRange"
            placeholder="now-6h"
          />
        </ElFormItem>

        <ElFormItem label="Grafana 嵌入模式">
          <ElSwitch v-model="observabilityForm.grafanaEmbedEnabled" />
          <span class="hint">为仪表盘链接添加 Kiosk 模式，获得更简洁的展示视图。</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="推荐配置">
          建议将 Prometheus 和 Grafana 独立部署，通过此处配置的地址作为统一入口。
        </ElDescriptionsItem>
        <ElDescriptionsItem label="生效位置">
          监控页面将显示已配置的 Prometheus 和 Grafana 快捷链接。
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
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.toolbar-actions {
  display: flex;
  gap: 6px;
}

.settings-card {
  margin-bottom: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.unit {
  margin-left: 6px;
  color: #94a3b8;
  font-size: 10px;
}

.hint {
  margin-left: 10px;
  color: #94a3b8;
  font-size: 10px;
}
</style>
