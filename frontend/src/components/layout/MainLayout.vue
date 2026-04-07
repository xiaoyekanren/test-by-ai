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
    <el-aside :width="isSidebarCollapse ? '64px' : '220px'" class="layout-aside">
      <Sidebar @collapse="handleSidebarCollapse" />
    </el-aside>

    <el-container class="layout-container">
      <el-header class="layout-header" height="60px">
        <TopBar @refresh="handleRefresh" />
      </el-header>

      <el-main class="layout-main">
        <div class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100%;
  width: 100%;
}

.layout-aside {
  background-color: #304156;
  transition: width 0.3s ease;
  overflow: hidden;
}

.layout-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.layout-header {
  padding: 0;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.layout-main {
  background-color: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}

.main-content {
  background-color: #fff;
  border-radius: 4px;
  padding: 20px;
  min-height: calc(100vh - 120px);
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

/* Transition animations */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .layout-aside {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
  }

  .layout-main {
    padding: 10px;
  }

  .main-content {
    padding: 15px;
  }
}
</style>