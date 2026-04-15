<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ElCollapse,
  ElCollapseItem,
  ElInput,
  ElTooltip
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
const searchText = ref('')

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
const filteredNodeCategories = computed(() => {
  const categories: Record<NodeCategory, NodeTypeConfig[]> = {
    basic: [],
    iotdb: [],
    control: [],
    result: []
  }

  const query = searchText.value.trim().toLowerCase()
  Object.values(NODE_CONFIGS).forEach(config => {
    const matchesSearch = !query || [
      config.label,
      config.type,
      config.category,
      config.description
    ].some(value => String(value).toLowerCase().includes(query))

    if (matchesSearch) {
      categories[config.category].push(config)
    }
  })

  return categories
})

const visibleCategoryEntries = computed(() => {
  return Object.entries(filteredNodeCategories.value).filter(([, nodes]) => nodes.length > 0)
})

const totalVisibleNodes = computed(() => {
  return visibleCategoryEntries.value.reduce((total, [, nodes]) => total + nodes.length, 0)
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

const getPaletteLabel = (node: NodeTypeConfig) => {
  if (node.category !== 'iotdb') {
    return node.label
  }

  return node.label
    .replace(/^IoTDB\s+/, '')
    .replace(/\s+IoT\s+Benchmark$/, ' Benchmark')
}

const isWideNode = (node: NodeTypeConfig) => {
  return getPaletteLabel(node).length > 15
}
</script>

<template>
  <div class="node-palette">
    <div class="palette-header">
      <span class="title">Node Types</span>
      <span class="total-count">{{ totalVisibleNodes }}</span>
      <ElInput
        v-model="searchText"
        placeholder="Search nodes"
        size="small"
        clearable
        class="node-search"
      />
    </div>
    <div class="palette-content">
      <ElCollapse v-model="activeCategories" class="category-collapse">
        <ElCollapseItem
          v-for="[category, nodes] in visibleCategoryEntries"
          :key="category"
          :name="category"
        >
          <template #title>
            <span class="category-title">{{ categoryLabels[category as NodeCategory] }}</span>
            <span class="category-count">{{ nodes.length }}</span>
          </template>
          <div class="node-list">
            <ElTooltip
              v-for="node in nodes"
              :key="node.type"
              :content="`${node.label}: ${node.description}`"
              placement="right"
              :show-after="250"
            >
              <div
                class="node-item"
                :class="{ 'is-wide': isWideNode(node) }"
                draggable="true"
                @dragstart="handleDragStart($event, node.type)"
              >
                <span class="node-color" :style="{ backgroundColor: node.color }"></span>
                <div class="node-icon" :style="{ color: node.color }">
                  <component :is="getIcon(node.icon)" class="icon" />
                </div>
                <span class="node-label">{{ getPaletteLabel(node) }}</span>
                <span class="node-chip">{{ node.category }}</span>
              </div>
            </ElTooltip>
          </div>
        </ElCollapseItem>
      </ElCollapse>
      <div v-if="totalVisibleNodes === 0" class="empty-search">No nodes found</div>
    </div>
  </div>
</template>

<style scoped>
.node-palette {
  width: 240px;
  min-width: 240px;
  flex: 0 0 240px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
}

.palette-header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #dcdfe6;
  background: #f5f7fa;
}

.palette-header .title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.total-count {
  align-self: center;
  font-size: 10px;
  color: #64748b;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 8px;
}

.node-search {
  grid-column: 1 / -1;
}

.node-search :deep(.el-input__wrapper) {
  min-height: 26px;
  border-radius: 6px;
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
  padding: 0 10px;
  height: 28px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.category-title {
  font-size: 12px;
  font-weight: 500;
  color: #606266;
}

.category-count {
  margin-left: 6px;
  font-size: 11px;
  color: #909399;
  background: #f0f2f5;
  padding: 0 5px;
  border-radius: 10px;
}

.category-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.category-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.node-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 3px;
  padding: 4px 6px;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  min-width: 0;
  padding: 0 6px;
  background: #fff;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: grab;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.node-item:hover {
  border-color: #409eff;
  background: #f8fafc;
  transform: translateY(-1px);
}

.node-item:active {
  cursor: grabbing;
}

.node-item.is-wide {
  grid-column: 1 / -1;
  gap: 6px;
}

.node-color {
  width: 3px;
  height: 18px;
  border-radius: 2px;
  flex-shrink: 0;
}

.node-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.node-icon .icon {
  width: 13px;
  height: 13px;
}

.node-label {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  min-width: 0;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-chip {
  display: none;
  flex-shrink: 0;
  max-width: 50px;
  font-size: 9px;
  line-height: 16px;
  color: #64748b;
  background: #f1f5f9;
  padding: 0 5px;
  border-radius: 5px;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-item.is-wide .node-chip {
  display: inline-block;
}

.empty-search {
  padding: 18px 10px;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
}
</style>
