<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Monitor, Setting, Document, DataAnalysis, Platform } from '@element-plus/icons-vue'

const router = useRouter()

const rootFeature = {
  title: '服务器管理',
  description: '统一维护 SSH 连接、认证信息和远程执行入口，是整个平台能力的起点。',
  icon: Setting,
  path: '/servers',
  color: '#3b82f6'
}

const branches = [
  {
    title: '系统监控',
    description: '从服务器连接延伸到 CPU、内存、磁盘和进程监控。',
    icon: Monitor,
    path: '/monitor',
    color: '#10b981',
    eyebrow: '观测'
  },
  {
    title: 'IoTDB可视化',
    description: '基于已管理服务器连接 IoTDB，查看日志、配置和 CLI。',
    icon: Platform,
    path: '/iotdb',
    color: '#ef4444',
    eyebrow: '数据服务'
  },
  {
    title: '工作流管理',
    description: '把服务器操作编排成拖拽式工作流，沉淀自动化执行能力。',
    icon: Document,
    path: '/workflows',
    color: '#f59e0b',
    eyebrow: '自动化'
  }
]

const branchExtension = {
  title: '运行分析',
  description: '工作流执行后的历史、状态和性能分析，属于自动化链路的结果视图。',
  icon: DataAnalysis,
  path: '/executions',
  color: '#8b5cf6'
}

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <div class="home-view">
    <section class="mindmap">
      <div class="mindmap-head">
        <div class="mindmap-label">模块关系</div>
        <p class="mindmap-desc">服务器管理是起点，向外分出监控、IoTDB 和工作流，工作流再延伸到运行分析。</p>
      </div>

      <div class="mindmap-canvas">
        <!-- 中心卡片 -->
        <div class="center-card" @click="navigateTo(rootFeature.path)">
          <div class="center-icon" :style="{ background: rootFeature.color }">
            <el-icon :size="26"><component :is="rootFeature.icon" /></el-icon>
          </div>
          <div class="center-content">
            <div class="center-title">{{ rootFeature.title }}</div>
            <div class="center-desc">{{ rootFeature.description }}</div>
          </div>
        </div>

        <!-- 主连接线 -->
        <svg class="line-main" width="520" height="28" viewBox="0 0 520 28">
          <line x1="260" y1="0" x2="260" y2="10" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="100" y1="10" x2="420" y2="10" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="100" cy="10" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="260" cy="10" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="420" cy="10" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="100" y1="10" x2="100" y2="28" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="260" y1="10" x2="260" y2="28" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="420" y1="10" x2="420" y2="28" stroke="#cbd5e1" stroke-width="1.5"/>
        </svg>

        <!-- 三个分支卡片 -->
        <div class="branch-row">
          <div
            v-for="feature in branches"
            :key="feature.path"
            class="branch-card"
            :style="{ borderColor: feature.color }"
            @click="navigateTo(feature.path)"
          >
            <div class="branch-icon" :style="{ background: feature.color }">
              <el-icon :size="18"><component :is="feature.icon" /></el-icon>
            </div>
            <div class="branch-content">
              <div class="branch-eyebrow" :style="{ color: feature.color }">{{ feature.eyebrow }}</div>
              <div class="branch-title">{{ feature.title }}</div>
              <div class="branch-desc">{{ feature.description }}</div>
            </div>
          </div>
        </div>

        <!-- 工作流到运行分析的连接线 -->
        <svg class="line-sub" width="520" height="24" viewBox="0 0 520 24">
          <line x1="420" y1="0" x2="420" y2="24" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="420" cy="24" r="3" fill="white" stroke="#8b5cf6" stroke-width="1.5"/>
        </svg>

        <!-- 运行分析卡片 -->
        <div class="sub-card-wrap">
          <div class="sub-card" @click="navigateTo(branchExtension.path)">
            <div class="sub-icon" :style="{ background: branchExtension.color }">
              <el-icon :size="16"><component :is="branchExtension.icon" /></el-icon>
            </div>
            <div class="sub-content">
              <div class="sub-eyebrow" :style="{ color: branchExtension.color }">分析</div>
              <div class="sub-title">{{ branchExtension.title }}</div>
              <div class="sub-desc">{{ branchExtension.description }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-view {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 20px;
}

.mindmap {
  width: 100%;
  max-width: 1000px;
}

.mindmap-head {
  text-align: center;
  margin-bottom: 20px;
}

.mindmap-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.mindmap-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.mindmap-canvas {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.center-card {
  width: 280px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;
}

.center-card:hover {
  border-color: #3b82f6;
  transform: translateY(-2px);
}

.center-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: white;
  flex-shrink: 0;
}

.center-content {
  display: flex;
  flex-direction: column;
}

.center-title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.center-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.4;
}

.line-main,
.line-sub {
  display: block;
}

.branch-row {
  display: flex;
  gap: 16px;
}

.branch-card {
  width: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 12px;
  background: white;
  border: 1px solid;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.2s;
}

.branch-card:hover {
  transform: translateY(-2px);
}

.branch-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: white;
  flex-shrink: 0;
}

.branch-content {
  display: flex;
  flex-direction: column;
  text-align: center;
}

.branch-eyebrow {
  font-size: 11px;
  font-weight: 500;
}

.branch-title {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.branch-desc {
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.sub-card-wrap {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  max-width: 520px;
  padding-right: 10px;
}

.sub-card {
  width: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 14px;
  background: white;
  border: 1px solid #8b5cf6;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.2s;
}

.sub-card:hover {
  transform: translateY(-2px);
}

.sub-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: white;
  flex-shrink: 0;
}

.sub-content {
  display: flex;
  flex-direction: column;
  text-align: center;
}

.sub-eyebrow {
  font-size: 11px;
  font-weight: 500;
}

.sub-title {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.sub-desc {
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

@media (max-width: 640px) {
  .branch-row {
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .branch-card {
    width: 180px;
  }

  .line-main {
    display: none;
  }

  .line-sub {
    display: none;
  }

  .sub-card-wrap {
    justify-content: center;
    padding-right: 0;
  }

  .sub-card {
    width: 180px;
  }
}
</style>