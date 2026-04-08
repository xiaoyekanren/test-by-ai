<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, Monitor, Setting, HomeFilled, DataAnalysis, Platform } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const isCollapse = ref(false)
const isReady = ref(false)

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

onMounted(() => {
  setTimeout(() => {
    isReady.value = true
  }, 50)
})
</script>

<template>
  <div class="sidebar" :class="{ 'is-collapse': isCollapse, 'is-ready': isReady }">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="logo" @click="goToHome">
        <div class="logo-icon">
          <el-icon :size="14"><Monitor /></el-icon>
        </div>
        <transition name="fade">
          <div v-show="!isCollapse" class="logo-text">
            <span class="logo-title">OpsCenter</span>
            <span class="logo-subtitle">运维管理平台</span>
          </div>
        </transition>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="sidebar-nav">
      <!-- Home -->
      <div
        class="nav-item"
        :class="{ 'is-active': activeMenu === '/' }"
        @click="handleSelect('/')"
      >
        <div class="nav-icon">
          <el-icon :size="14"><HomeFilled /></el-icon>
        </div>
        <transition name="fade">
          <span v-show="!isCollapse" class="nav-label">首页</span>
        </transition>
        <div class="nav-indicator"></div>
      </div>

      <!-- Groups -->
      <template v-for="(group, groupIndex) in menuGroups" :key="group.title">
        <transition name="fade">
          <div v-show="!isCollapse" class="nav-group" :style="{ '--i': groupIndex }">
            <span class="nav-group-title">{{ group.title }}</span>
          </div>
        </transition>

        <div
          v-for="(item, itemIndex) in group.items"
          :key="item.index"
          class="nav-item"
          :class="{ 'is-active': activeMenu === item.index }"
          :style="{ '--i': groupIndex * 10 + itemIndex + 1 }"
          @click="handleSelect(item.index)"
        >
          <div class="nav-icon">
            <el-icon :size="14"><component :is="item.icon" /></el-icon>
          </div>
          <transition name="fade">
            <span v-show="!isCollapse" class="nav-label">{{ item.title }}</span>
          </transition>
          <div class="nav-indicator"></div>
        </div>
      </template>
    </nav>

    <!-- Footer -->
    <div class="sidebar-footer">
      <button class="collapse-btn" @click="toggleCollapse">
        <svg class="collapse-icon" :class="{ 'is-collapsed': isCollapse }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <polyline points="11 17 6 12 11 7"></polyline>
          <polyline points="18 17 13 12 18 7"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Light Modern Theme */
.sidebar {
  --bg: #ffffff;
  --bg-hover: #f8fafc;
  --bg-active: #eff6ff;
  --accent: #3b82f6;
  --accent-light: rgba(59, 130, 246, 0.1);
  --text: #1e293b;
  --text-dim: #64748b;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --border-light: #f1f5f9;

  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  width: 180px;
  border-right: 1px solid var(--border);
  transition: width 0.25s ease;
  overflow: hidden;
}

.sidebar.is-collapse {
  width: 52px;
}

/* Header */
.sidebar-header {
  padding: 10px 8px;
  border-bottom: 1px solid var(--border-light);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.logo:hover {
  opacity: 0.8;
}

.logo-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent) 0%, #2563eb 100%);
  border-radius: 6px;
  color: white;
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: hidden;
}

.logo-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.3px;
}

.logo-subtitle {
  font-size: 9px;
  color: var(--text-muted);
}

/* Navigation */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 4px;
}

/* Nav Group */
.nav-group {
  padding: 10px 6px 4px;
  opacity: 0;
  transform: translateY(-4px);
}

.sidebar.is-ready .nav-group {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.3s ease, transform 0.3s ease;
  transition-delay: calc(var(--i) * 0.05s);
}

.nav-group-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

/* Nav Item */
.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 6px;
  height: 34px;
  margin-bottom: 2px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
  opacity: 0;
  transform: translateX(-8px);
}

.sidebar.is-ready .nav-item {
  opacity: 1;
  transform: translateX(0);
  transition: opacity 0.3s ease, transform 0.3s ease, background-color 0.15s ease, color 0.15s ease;
  transition-delay: calc(var(--i) * 0.03s);
}

.nav-item:hover {
  background: var(--bg-hover);
}

.nav-item.is-active {
  background: var(--bg-active);
}

.nav-item.is-active .nav-icon {
  color: var(--accent);
}

.nav-item.is-active .nav-label {
  color: var(--accent);
  font-weight: 600;
}

.nav-item.is-active .nav-indicator {
  opacity: 1;
  transform: scaleY(1);
}

/* Nav Icon */
.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  color: var(--text-dim);
  flex-shrink: 0;
  transition: color 0.15s ease;
}

/* Nav Label */
.nav-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
  white-space: nowrap;
  transition: color 0.15s ease;
}

/* Active Indicator */
.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 14px;
  background: var(--accent);
  border-radius: 0 3px 3px 0;
  opacity: 0;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

/* Footer */
.sidebar-footer {
  padding: 6px;
  border-top: 1px solid var(--border-light);
}

.collapse-btn {
  width: 100%;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-dim);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.collapse-btn:hover {
  background: var(--bg);
  border-color: var(--text-muted);
  color: var(--text);
}

.collapse-icon {
  width: 14px;
  height: 14px;
  transition: transform 0.25s ease;
}

.collapse-icon.is-collapsed {
  transform: rotate(180deg);
}

/* Transitions */
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
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.1);
  }
}
</style>