<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, User, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const pageTitle = computed(() => {
  const routeMap: Record<string, string> = {
    '/': '首页',
    '/servers': '服务器管理 / 系统监控',
    '/workflows': '工作流管理',
    '/settings': '系统设置',
    '/executions': '运行分析',
  }
  if (route.path.includes('/workflows/') && route.path.includes('/edit')) {
    return '工作流编辑'
  }
  return routeMap[route.path] || '管理系统'
})

const breadcrumbs = computed(() => {
  const crumbs: { title: string; path?: string }[] = [{ title: '首页', path: '/' }]
  if (route.path !== '/') {
    const routeMap: Record<string, string> = {
      '/servers': '服务器管理',
      '/workflows': '工作流管理',
      '/settings': '系统设置',
      '/executions': '运行分析',
    }
    if (route.path.includes('/workflows/') && route.path.includes('/edit')) {
      crumbs.push({ title: '工作流管理', path: '/workflows' })
      crumbs.push({ title: '编辑' })
    } else if (routeMap[route.path]) {
      crumbs.push({ title: routeMap[route.path] })
    }
  }
  return crumbs
})

const emit = defineEmits<{
  refresh: []
}>()

const handleRefresh = () => {
  emit('refresh')
}

const goToSettings = () => {
  router.push('/settings')
}
</script>

<template>
  <div class="topbar">
    <div class="topbar-left">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="(crumb, index) in breadcrumbs"
          :key="index"
          :to="crumb.path ? { path: crumb.path } : undefined"
        >
          {{ crumb.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
      <h2 class="page-title">{{ pageTitle }}</h2>
    </div>

    <div class="topbar-right">
      <el-tooltip content="刷新页面" placement="bottom">
        <el-button :icon="Refresh" circle size="small" @click="handleRefresh" />
      </el-tooltip>

      <el-dropdown trigger="click">
        <div class="user-info">
          <div class="user-avatar">
            <el-icon :size="14"><User /></el-icon>
          </div>
          <span class="username">管理员</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item>个人中心</el-dropdown-item>
            <el-dropdown-item @click="goToSettings">
              <el-icon><Setting /></el-icon>
              系统设置
            </el-dropdown-item>
            <el-dropdown-item divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped>
.topbar {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #ffffff;
}

.topbar-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

:deep(.el-breadcrumb__item) {
  font-size: 12px;
}

:deep(.el-breadcrumb__inner) {
  color: #94a3b8;
  font-weight: 400;
}

:deep(.el-breadcrumb__inner.is-link:hover) {
  color: #3b82f6;
}

.page-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.user-info:hover {
  background: #f8fafc;
}

.user-avatar {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 8px;
  color: #64748b;
}

.username {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
}
</style>
