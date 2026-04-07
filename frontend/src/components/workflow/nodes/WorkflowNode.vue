<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import {
  Monitor,
  Upload,
  Download,
  Setting,
  Document,
  VideoPlay,
  VideoPause,
  Tools,
  Share,
  Refresh,
  Timer,
  Grid,
  CircleCheck,
  DataAnalysis,
  Bell
} from '@element-plus/icons-vue'
import type { NodeType, NodeTypeConfig } from '@/types'
import { NODE_CONFIGS } from '@/types'

const props = defineProps<{
  id: string
  data: {
    label: string
    nodeType: NodeType
    config: Record<string, unknown>
  }
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'click', id: string): void
  (e: 'dblclick', id: string): void
}>()

// Get node configuration
const nodeConfig = computed<NodeTypeConfig>(() => {
  return NODE_CONFIGS[props.data.nodeType] || NODE_CONFIGS.shell
})

// Icon mapping
const iconMap: Record<string, typeof Monitor> = {
  Monitor,
  Upload,
  Download,
  Setting,
  Document,
  VideoPlay,
  VideoPause,
  Tools,
  Share,
  Refresh,
  Timer,
  Grid,
  CircleCheck,
  DataAnalysis,
  Bell
}

// Get icon component
const iconComponent = computed(() => {
  return iconMap[nodeConfig.value.icon] || Monitor
})

// Handle positions for condition node (2 outputs)
const getOutputHandles = computed(() => {
  const outputs = nodeConfig.value.outputs
  if (outputs === 0) return []
  if (outputs === 1) return [{ id: 'output', position: Position.Right, top: '50%' }]
  if (outputs === 2) return [
    { id: 'output-true', position: Position.Right, top: '30%', label: 'True' },
    { id: 'output-false', position: Position.Right, top: '70%', label: 'False' }
  ]
  return [{ id: 'output', position: Position.Right, top: '50%' }]
})

// Input handle
const hasInput = computed(() => nodeConfig.value.inputs > 0)

// Handle click
const handleClick = () => {
  emit('click', props.id)
}

const handleDoubleClick = () => {
  emit('dblclick', props.id)
}
</script>

<template>
  <div
    class="workflow-node"
    :class="{ selected: selected }"
    :style="{ borderColor: nodeConfig.color }"
    @click="handleClick"
    @dblclick.stop="handleDoubleClick"
  >
    <!-- Input Handle -->
    <Handle
      v-if="hasInput"
      type="target"
      :position="Position.Left"
      id="input"
      class="handle-input"
    />

    <!-- Node Content -->
    <div class="node-header" :style="{ backgroundColor: nodeConfig.color }">
      <component :is="iconComponent" class="node-icon" />
      <span class="node-type-label">{{ nodeConfig.label }}</span>
    </div>
    <div class="node-body">
      <div class="node-title">{{ data.label }}</div>
      <div class="node-id">{{ id }}</div>
    </div>

    <!-- Output Handles -->
    <Handle
      v-for="handle in getOutputHandles"
      :key="handle.id"
      type="source"
      :position="handle.position"
      :id="handle.id"
      class="handle-output"
      :style="{ top: handle.top }"
    />

    <!-- Handle labels for condition node -->
    <div
      v-if="nodeConfig.outputs === 2"
      class="handle-labels"
    >
      <span class="handle-label true-label">True</span>
      <span class="handle-label false-label">False</span>
    </div>
  </div>
</template>

<style scoped>
.workflow-node {
  background: #fff;
  border: 2px solid #dcdfe6;
  border-radius: 8px;
  min-width: 150px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s ease;
}

.workflow-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.workflow-node.selected {
  border-width: 2px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.node-header {
  padding: 8px 12px;
  border-radius: 6px 6px 0 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  width: 16px;
  height: 16px;
  color: #fff;
}

.node-type-label {
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.node-body {
  padding: 10px 12px;
}

.node-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.node-id {
  font-size: 11px;
  color: #909399;
}

/* Handles */
.handle-input {
  width: 12px;
  height: 12px;
  background: #409eff;
  border: 2px solid #fff;
  border-radius: 6px;
}

.handle-output {
  width: 12px;
  height: 12px;
  background: #67c23a;
  border: 2px solid #fff;
  border-radius: 6px;
}

.handle-labels {
  position: absolute;
  right: -35px;
  top: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  padding: 8px 0;
}

.handle-label {
  font-size: 10px;
  color: #909399;
  background: #f5f7fa;
  padding: 2px 4px;
  border-radius: 2px;
}

.true-label {
  color: #67c23a;
}

.false-label {
  color: #f56c6c;
}
</style>
