<script setup lang="ts">
import { ElCard, ElRow, ElCol } from 'element-plus'

const stats = {
  totalWorkflows: 10,
  activeWorkflows: 7,
  totalExecutions: 150,
  successRate: 95
}
</script>

<template>
  <div class="monitor-view">
    <ElRow :gutter="20">
      <ElCol :span="6">
        <ElCard shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ stats.totalWorkflows }}</div>
            <div class="stat-label">Total Workflows</div>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :span="6">
        <ElCard shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ stats.activeWorkflows }}</div>
            <div class="stat-label">Active Workflows</div>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :span="6">
        <ElCard shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ stats.totalExecutions }}</div>
            <div class="stat-label">Total Executions</div>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :span="6">
        <ElCard shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ stats.successRate }}%</div>
            <div class="stat-label">Success Rate</div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElCard class="recent-section">
      <template #header>
        <span>Recent Executions</span>
      </template>
      <div class="execution-list">
        <p>No recent executions</p>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
.monitor-view {
  padding: 0;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  margin-top: 8px;
  color: #909399;
  font-size: 14px;
}

.recent-section {
  margin-top: 20px;
}

.execution-list {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
</style>