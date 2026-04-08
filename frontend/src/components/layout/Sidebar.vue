<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, Monitor, Setting, HomeFilled, DataAnalysis, Platform } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)

const emit = defineEmits<{
  collapse: [collapsed: boolean]
}>()

const menuGroups = [
  {
    title: '运维管理',
    items: [
      { index: '/servers', title: '服务器管理', icon: Setting },
      { index: '/monitor', title: '系统监控', icon: Monitor }
    ]
  },
  {
    title: '工作流',
    items: [
      { index: '/workflows', title: '工作流管理', icon: Document },
      { index: '/executions', title: '运行分析', icon: DataAnalysis }
    ]
  },
  {
    title: '数据服务',
    items: [
      { index: '/iotdb', title: 'IoTDB可视化', icon: Platform }
    ]
  }
]

const activeMenu = computed(() => {
  const path = route.path
  // Match workflow-edit to workflows
  if (path.startsWith('/workflows')) {
    return '/workflows'
  }
  if (path.startsWith('/executions')) {
    return '/executions'
  }
  return path
})

const handleSelect = (index: string) => {
  router.push(index)
}

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
  emit('collapse', isCollapse.value)
}

watch(isCollapse, (val) => {
  emit('collapse', val)
})

const goToHome = () => {
  router.push('/')
}
</script>

<template>
  <div class="sidebar" :class="{ 'is-collapse': isCollapse }">
    <div class="sidebar-header">
      <div class="logo" @click="goToHome">
        <el-icon :size="24"><Monitor /></el-icon>
        <span v-show="!isCollapse" class="logo-text">管理系统</span>
      </div>
    </div>

    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      :collapse-transition="false"
      @select="handleSelect"
      class="sidebar-menu"
    >
      <!-- 首页 -->
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <template #title>首页</template>
      </el-menu-item>

      <!-- 分组菜单 -->
      <template v-for="group in menuGroups" :key="group.title">
        <div v-show="!isCollapse" class="menu-group-title">{{ group.title }}</div>
        <el-menu-item
          v-for="item in group.items"
          :key="item.index"
          :index="item.index"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </template>
    </el-menu>

    <div class="sidebar-footer">
      <el-button
        :icon="isCollapse ? 'Expand' : 'Fold'"
        text
        @click="toggleCollapse"
        class="collapse-btn"
      />
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #304156;
  transition: width 0.3s ease;
  width: 220px;
}

.sidebar.is-collapse {
  width: 64px;
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  overflow: hidden;
  cursor: pointer;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background-color: transparent;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}

:deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.7);
  height: 50px;
  line-height: 50px;
}

:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.1);
  color: #fff;
}

:deep(.el-menu-item.is-active) {
  background-color: #409eff;
  color: #fff;
}

:deep(.el-menu-item .el-icon) {
  color: inherit;
}

.sidebar-footer {
  padding: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.collapse-btn {
  width: 100%;
  color: rgba(255, 255, 255, 0.7);
}

.collapse-btn:hover {
  color: #fff;
}

.menu-group-title {
  padding: 12px 20px 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 1px;
}

.sidebar-menu:not(.el-menu--collapse) .menu-group-title:first-child {
  margin-top: 8px;
}
</style>
