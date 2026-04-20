<script setup lang="ts">
import { computed } from 'vue'
import {
  ElButton,
  ElTooltip,
  ElSwitch
} from 'element-plus'
import {
  DocumentChecked,
  Refresh,
  Back,
  Right,
  ZoomIn,
  ZoomOut,
  FullScreen,
  Loading
} from '@element-plus/icons-vue'

const props = defineProps<{
  workflowId: number | null
  workflowName: string
  isSaving: boolean
  isDirty: boolean
  autoSave: boolean
  canUndo: boolean
  canRedo: boolean
  canRun: boolean
  runBlockedReason: string
}>()

const emit = defineEmits<{
  (e: 'save'): void
  (e: 'autoSaveChange', value: boolean): void
  (e: 'undo'): void
  (e: 'redo'): void
  (e: 'zoomIn'): void
  (e: 'zoomOut'): void
  (e: 'fitView'): void
  (e: 'run'): void
}>()

const handleSave = () => {
  emit('save')
}

const handleAutoSaveChange = (value: boolean | number | string) => {
  emit('autoSaveChange', Boolean(value))
}

const handleUndo = () => {
  emit('undo')
}

const handleRedo = () => {
  emit('redo')
}

const handleZoomIn = () => {
  emit('zoomIn')
}

const handleZoomOut = () => {
  emit('zoomOut')
}

const handleFitView = () => {
  emit('fitView')
}

const handleRun = () => {
  emit('run')
}

const pageTitle = computed(() => {
  if (props.workflowId) {
    return `Edit: ${props.workflowName}`
  }
  return 'New Workflow'
})
</script>

<template>
  <div class="editor-toolbar">
    <div class="toolbar-left">
      <h2 class="page-title">{{ pageTitle }}</h2>
      <span v-if="isDirty" class="dirty-badge">Unsaved</span>
    </div>

    <div class="toolbar-center">
      <ElTooltip content="Undo" placement="bottom">
        <ElButton
          :icon="Back"
          circle
          size="small"
          :disabled="!canUndo"
          @click="handleUndo"
        />
      </ElTooltip>
      <ElTooltip content="Redo" placement="bottom">
        <ElButton
          :icon="Right"
          circle
          size="small"
          :disabled="!canRedo"
          @click="handleRedo"
        />
      </ElTooltip>
      <div class="separator"></div>
      <ElTooltip content="Zoom In" placement="bottom">
        <ElButton
          :icon="ZoomIn"
          circle
          size="small"
          @click="handleZoomIn"
        />
      </ElTooltip>
      <ElTooltip content="Zoom Out" placement="bottom">
        <ElButton
          :icon="ZoomOut"
          circle
          size="small"
          @click="handleZoomOut"
        />
      </ElTooltip>
      <ElTooltip content="Fit View" placement="bottom">
        <ElButton
          :icon="FullScreen"
          circle
          size="small"
          @click="handleFitView"
        />
      </ElTooltip>
    </div>

    <div class="toolbar-right">
      <div class="auto-save-toggle">
        <span class="label">Auto Save</span>
        <ElSwitch
          :model-value="autoSave"
          size="small"
          @update:model-value="handleAutoSaveChange"
        />
      </div>
      <ElButton
        type="primary"
        :icon="isSaving ? Loading : DocumentChecked"
        :loading="isSaving"
        :disabled="!isDirty"
        @click="handleSave"
      >
        Save
      </ElButton>
      <ElTooltip
        v-if="workflowId"
        :content="runBlockedReason || 'Run workflow'"
        placement="bottom"
      >
        <span>
          <ElButton
            type="success"
            :icon="Refresh"
            :disabled="!canRun"
            @click="handleRun"
          >
            Run
          </ElButton>
        </span>
      </ElTooltip>
    </div>
  </div>
</template>

<style scoped>
.editor-toolbar {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.dirty-badge {
  font-size: 12px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #e6a23c;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
}

.separator {
  width: 1px;
  height: 20px;
  background: #dcdfe6;
  margin: 0 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.auto-save-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.auto-save-toggle .label {
  font-size: 13px;
  color: #606266;
}
</style>
