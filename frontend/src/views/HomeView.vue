<script setup lang="ts">
import { ElRow, ElCol, ElCard } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()

const quickActions = [
  { title: '服务器管理', description: '管理服务器连接和配置', route: '/servers', icon: '🖥️' },
  { title: '工作流管理', description: '创建和管理自动化工作流', route: '/workflows', icon: '📋' },
  { title: '系统监控', description: '监控系统运行状态', route: '/monitor', icon: '📊' }
]

const handleNavigate = (route: string) => {
  router.push(route)
}
</script>

<template>
  <div class="home-view">
    <div class="welcome-section">
      <h1>欢迎使用管理系统</h1>
      <p>一个现代化的服务器与工作流管理平台</p>
    </div>

    <ElRow :gutter="20" class="quick-actions">
      <ElCol :xs="24" :sm="12" :md="8" v-for="action in quickActions" :key="action.route">
        <ElCard shadow="hover" class="action-card" @click="handleNavigate(action.route)">
          <div class="action-content">
            <span class="action-icon">{{ action.icon }}</span>
            <h3>{{ action.title }}</h3>
            <p>{{ action.description }}</p>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElCard class="stats-section">
      <template #header>
        <span>系统概览</span>
      </template>
      <ElRow :gutter="20">
        <ElCol :span="6">
          <div class="stat-item">
            <div class="stat-value">12</div>
            <div class="stat-label">服务器数量</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="stat-item">
            <div class="stat-value">28</div>
            <div class="stat-label">工作流数量</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="stat-item">
            <div class="stat-value">156</div>
            <div class="stat-label">今日执行</div>
          </div>
        </ElCol>
        <ElCol :span="6">
          <div class="stat-item">
            <div class="stat-value">98.5%</div>
            <div class="stat-label">成功率</div>
          </div>
        </ElCol>
      </ElRow>
    </ElCard>
  </div>
</template>

<style scoped>
.home-view {
  padding: 0;
}

.welcome-section {
  text-align: center;
  padding: 40px 0;
}

.welcome-section h1 {
  font-size: 28px;
  color: #303133;
  margin-bottom: 10px;
}

.welcome-section p {
  color: #909399;
  font-size: 16px;
}

.quick-actions {
  margin-bottom: 30px;
}

.action-card {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.action-card:hover {
  transform: translateY(-4px);
}

.action-content {
  text-align: center;
  padding: 20px 0;
}

.action-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 15px;
}

.action-content h3 {
  font-size: 18px;
  color: #303133;
  margin-bottom: 8px;
}

.action-content p {
  color: #909399;
  font-size: 14px;
}

.stats-section {
  margin-top: 20px;
}

.stat-item {
  text-align: center;
  padding: 20px 0;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #409eff;
}

.stat-label {
  margin-top: 8px;
  color: #909399;
  font-size: 14px;
}
</style>