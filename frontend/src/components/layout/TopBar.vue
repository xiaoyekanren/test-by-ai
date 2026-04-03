<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, User, Setting } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const pageTitle = computed(() => {
  const routeMap: Record<string, string> = {
    '/': '首页',
    '/servers': '服务器管理',
    '/workflows': '工作流管理',
    '/monitor': '系统监控',
    '/settings': '系统设置'
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
      '/monitor': '系统监控',
      '/settings': '系统设置'
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
        <el-button :icon="Refresh" circle @click="handleRefresh" />
      </el-tooltip>

      <el-dropdown trigger="click" class="user-dropdown">
        <div class="user-info">
          <el-avatar :size="32" :icon="User" />
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
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.topbar-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-dropdown {
  cursor: pointer;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.username {
  font-size: 14px;
  color: #606266;
}
</style>