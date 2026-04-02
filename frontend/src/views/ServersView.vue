<script setup lang="ts">
import { ElCard, ElButton } from 'element-plus'

const servers = [
  { id: '1', name: 'Server 1', host: '192.168.1.1', port: 22, status: 'online' },
  { id: '2', name: 'Server 2', host: '192.168.1.2', port: 22, status: 'offline' }
]
</script>

<template>
  <div class="servers-view">
    <ElCard>
      <template #header>
        <div class="card-header">
          <span>Servers</span>
          <ElButton type="primary">Add Server</ElButton>
        </div>
      </template>
      <div class="server-list">
        <div v-for="server in servers" :key="server.id" class="server-item">
          <div class="server-info">
            <span class="server-name">{{ server.name }}</span>
            <span class="server-host">{{ server.host }}:{{ server.port }}</span>
          </div>
          <div class="server-status" :class="server.status">
            {{ server.status }}
          </div>
        </div>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
.servers-view {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.server-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.server-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.server-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.server-name {
  font-weight: 500;
}

.server-host {
  color: #909399;
  font-size: 14px;
}

.server-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  text-transform: uppercase;
}

.server-status.online {
  background-color: #f0f9eb;
  color: #67c23a;
}

.server-status.offline {
  background-color: #fef0f0;
  color: #f56c6c;
}
</style>