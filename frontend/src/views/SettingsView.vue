<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ElCard,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElButton,
  ElMessage,
  ElDivider,
  ElDescriptions,
  ElDescriptionsItem,
  ElTag
} from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

// Local form state
const monitorForm = ref({
  refreshInterval: settingsStore.settings.monitor.refreshInterval
})

// Check if settings changed
const hasChanges = computed(() => {
  return monitorForm.value.refreshInterval !== settingsStore.settings.monitor.refreshInterval
})

// Save settings
function handleSave() {
  settingsStore.updateMonitorSettings({
    refreshInterval: monitorForm.value.refreshInterval
  })
  ElMessage.success('设置已保存')
}

// Reset to default
function handleReset() {
  monitorForm.value.refreshInterval = 10
  settingsStore.resetSettings()
  ElMessage.success('已恢复默认设置')
}

// Refresh interval options
const refreshOptions = [
  { label: '5 秒', value: 5 },
  { label: '10 秒（默认）', value: 10 },
  { label: '30 秒', value: 30 },
  { label: '1 分钟', value: 60 },
  { label: '5 分钟', value: 300 }
]
</script>

<template>
  <div class="settings-view">
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>系统设置</h2>
      </div>
      <div class="toolbar-actions">
        <ElButton @click="handleReset" :icon="Refresh">
          恢复默认
        </ElButton>
        <ElButton type="primary" @click="handleSave" :disabled="!hasChanges">
          保存设置
        </ElButton>
      </div>
    </div>

    <!-- Monitor Settings -->
    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="info" size="small">监控</ElTag>
          <span>系统监控设置</span>
        </div>
      </template>

      <ElForm label-width="140px" label-position="left">
        <ElFormItem label="数据刷新频率">
          <ElInputNumber
            v-model="monitorForm.refreshInterval"
            :min="5"
            :max="300"
            :step="5"
            style="width: 150px"
          />
          <span class="unit">秒</span>
        </ElFormItem>

        <ElFormItem label="可选预设">
          <div class="preset-options">
            <ElTag
              v-for="opt in refreshOptions"
              :key="opt.value"
              :type="monitorForm.refreshInterval === opt.value ? 'primary' : 'info'"
              class="preset-tag"
              @click="monitorForm.refreshInterval = opt.value"
            >
              {{ opt.label }}
            </ElTag>
          </div>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="当前刷新频率">
          {{ settingsStore.settings.monitor.refreshInterval }} 秒
        </ElDescriptionsItem>
        <ElDescriptionsItem label="说明">
          设置系统监控页面自动刷新数据的时间间隔，范围 5-300 秒
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <!-- Placeholder for future settings -->
    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="warning" size="small">工作流</ElTag>
          <span>工作流设置</span>
        </div>
      </template>

      <div class="placeholder-content">
        <ElTag type="info">开发中...</ElTag>
        <span>更多工作流配置选项即将推出</span>
      </div>
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

.preset-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
}

.placeholder-content {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #909399;
  padding: 20px 0;
}
</style>