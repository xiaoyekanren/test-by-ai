<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ElCollapse,
  ElCollapseItem
} from 'element-plus'
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
import type { NodeType, NodeCategory, NodeTypeConfig } from '@/types'
import { NODE_CONFIGS } from '@/types'

const emit = defineEmits<{
  (e: 'dragstart', nodeType: NodeType): void
}>()

// Active categories for collapse
const activeCategories = ref<string[]>(['basic', 'iotdb', 'control', 'result'])

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

// Category labels
const categoryLabels: Record<NodeCategory, string> = {
  basic: 'Basic Nodes',
  iotdb: 'IoTDB Nodes',
  control: 'Control Nodes',
  result: 'Result Nodes'
}

// Group nodes by category
const nodeCategories = computed(() => {
  const categories: Record<NodeCategory, NodeTypeConfig[]> = {
    basic: [],
    iotdb: [],
    control: [],
    result: []
  }

  Object.values(NODE_CONFIGS).forEach(config => {
    categories[config.category].push(config)
  })

  return categories
})

// Handle drag start
const handleDragStart = (event: DragEvent, nodeType: NodeType) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }
  emit('dragstart', nodeType)
}

// Get icon component
const getIcon = (iconName: string) => {
  return iconMap[iconName] || Monitor
}
</script>

<template>
  <div class="node-palette">
    <div class="palette-header">
      <span class="title">Node Types</span>
    </div>
    <div class="palette-content">
      <ElCollapse v-model="activeCategories" class="category-collapse">
        <ElCollapseItem
          v-for="(nodes, category) in nodeCategories"
          :key="category"
          :name="category"
        >
          <template #title>
            <span class="category-title">{{ categoryLabels[category as NodeCategory] }}</span>
            <span class="category-count">{{ nodes.length }}</span>
          </template>
          <div class="node-list">
            <div
              v-for="node in nodes"
              :key="node.type"
              class="node-item"
              draggable="true"
              @dragstart="handleDragStart($event, node.type)"
            >
              <div class="node-icon" :style="{ backgroundColor: node.color }">
                <component :is="getIcon(node.icon)" class="icon" />
              </div>
              <div class="node-info">
                <span class="node-label">{{ node.label }}</span>
                <span class="node-desc">{{ node.description }}</span>
              </div>
            </div>
          </div>
        </ElCollapseItem>
      </ElCollapse>
    </div>
  </div>
</template>

<style scoped>
.node-palette {
  width: 280px;
  min-width: 280px;
  flex: 0 0 280px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
}

.palette-header {
  padding: 12px 16px;
  border-bottom: 1px solid #dcdfe6;
  background: #f5f7fa;
}

.palette-header .title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.palette-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.category-collapse {
  border: none;
}

.category-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  height: 40px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.category-title {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.category-count {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
  background: #f0f2f5;
  padding: 1px 6px;
  border-radius: 10px;
}

.category-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.category-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.node-list {
  padding: 8px;
}

.node-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 6px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s ease;
}

.node-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
  transform: translateY(-1px);
}

.node-item:active {
  cursor: grabbing;
}

.node-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.node-icon .icon {
  width: 18px;
  height: 18px;
  color: #fff;
}

.node-info {
  margin-left: 10px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.node-label {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-desc {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
</style>
