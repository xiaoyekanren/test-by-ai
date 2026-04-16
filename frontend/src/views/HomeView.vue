<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Setting, Document, DataAnalysis, Platform } from '@element-plus/icons-vue'

const router = useRouter()

const rootFeature = {
  title: '服务器管理 / 系统监控',
  description: '统一维护 SSH 连接、远程执行入口、资源指标和进程查看。',
  icon: Setting,
  path: '/servers',
  color: '#3b82f6'
}

const branches = [
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
        <svg class="line-main" width="600" height="36" viewBox="0 0 600 36">
          <line x1="300" y1="0" x2="300" y2="12" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="143" y1="12" x2="457" y2="12" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="143" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="300" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="457" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="143" y1="12" x2="143" y2="36" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="457" y1="12" x2="457" y2="36" stroke="#cbd5e1" stroke-width="1.5"/>
        </svg>

        <!-- 两个分支卡片 -->
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
        <svg class="line-sub" width="600" height="30" viewBox="0 0 600 30">
          <line x1="457" y1="0" x2="457" y2="30" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="457" cy="30" r="3" fill="white" stroke="#8b5cf6" stroke-width="1.5"/>
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
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 20px 24px;
}

.mindmap {
  width: 100%;
  max-width: 1120px;
  display: flex;
  justify-content: center;
}

.mindmap-canvas {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

.center-card {
  width: 348px;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 24px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid #93c5fd;
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(59, 130, 246, 0.12);
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}

.center-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 22px 46px rgba(59, 130, 246, 0.18);
  transform: translateY(-3px);
}

.center-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 12px 28px rgba(59, 130, 246, 0.2);
}

.center-content {
  display: flex;
  flex-direction: column;
}

.center-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
}

.center-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.55;
}

.line-main,
.line-sub {
  display: block;
}

.branch-row {
  display: flex;
  gap: 28px;
}

.branch-card {
  width: 286px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 16px;
  background: white;
  border: 1px solid;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.branch-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
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
  margin-top: 8px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
}

.sub-card-wrap {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  max-width: 600px;
}

.sub-card {
  width: 286px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 16px;
  background: white;
  border: 1px solid #8b5cf6;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 10px 24px rgba(139, 92, 246, 0.08);
}

.sub-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 16px 32px rgba(139, 92, 246, 0.14);
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
  margin-top: 8px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .home-view {
    min-height: auto;
    justify-content: flex-start;
  }

  .branch-row {
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .branch-card {
    width: 286px;
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
    width: 286px;
  }
}
</style>
