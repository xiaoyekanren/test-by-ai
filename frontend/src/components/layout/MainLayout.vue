<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './Sidebar.vue'
import TopBar from './TopBar.vue'

const isSidebarCollapse = ref(false)

const handleRefresh = () => {
  window.location.reload()
}

const handleSidebarCollapse = (collapsed: boolean) => {
  isSidebarCollapse.value = collapsed
}
</script>

<template>
  <el-container class="main-layout">
    <el-aside :width="isSidebarCollapse ? '52px' : '180px'" class="layout-aside">
      <Sidebar @collapse="handleSidebarCollapse" />
    </el-aside>

    <el-container class="layout-container">
      <el-header class="layout-header" height="56px">
        <TopBar @refresh="handleRefresh" />
      </el-header>

      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100%;
  width: 100%;
  background: #f8fafc;
}

.layout-aside {
  transition: width 0.25s ease;
  overflow: hidden;
}

.layout-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.layout-header {
  padding: 0;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
}

.layout-main {
  background: #f8fafc;
  padding: 20px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .layout-main {
    padding: 12px;
  }
}
</style>