<script setup lang="ts">
import { ElMenu, ElMenuItem, ElContainer, ElHeader, ElAside, ElMain, ElMenuItemGroup } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()

const handleMenuSelect = (index: string) => {
  router.push(index)
}
</script>

<template>
  <ElContainer class="layout-container">
    <ElAside :width="appStore.sidebarCollapsed ? '64px' : '200px'" class="layout-aside">
      <div class="logo">
        <span v-if="!appStore.sidebarCollapsed">Workflow Manager</span>
        <span v-else>WM</span>
      </div>
      <ElMenu
        :default-active="route.path"
        :collapse="appStore.sidebarCollapsed"
        @select="handleMenuSelect"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <ElMenuItem index="/">
          <template #title>Home</template>
        </ElMenuItem>
        <ElMenuItem index="/servers">
          <template #title>Servers</template>
        </ElMenuItem>
        <ElMenuItem index="/workflows">
          <template #title>Workflows</template>
        </ElMenuItem>
        <ElMenuItem index="/monitor">
          <template #title>Monitor</template>
        </ElMenuItem>
      </ElMenu>
    </ElAside>
    <ElContainer>
      <ElHeader class="layout-header">
        <div class="header-left">
          <span class="toggle-btn" @click="appStore.toggleSidebar">
            {{ appStore.sidebarCollapsed ? '>' : '<' }}
          </span>
        </div>
        <div class="header-right">
          <span>Workflow Manager</span>
        </div>
      </ElHeader>
      <ElMain class="layout-main">
        <RouterView />
      </ElMain>
    </ElContainer>
  </ElContainer>
</template>

<style scoped>
.layout-container {
  height: 100%;
}

.layout-aside {
  background-color: #304156;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
}

.layout-header {
  background-color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.toggle-btn {
  cursor: pointer;
  font-size: 20px;
  padding: 0 10px;
}

.layout-main {
  background-color: #f5f7fa;
}
</style>