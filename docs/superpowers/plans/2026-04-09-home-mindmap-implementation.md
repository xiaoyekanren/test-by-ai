# 首页思维导图重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将首页从 Hero+Flow Map 结构重构为纯思维导图式垂直树形布局，扁平简约风格。

**Architecture:** 单文件 Vue 组件重写，移除 Hero 和底部信息区，用 SVG 绘制连接线，垂直树形结构展示模块关系。

**Tech Stack:** Vue 3 + Element Plus + SVG

---

## Files

- Modify: `frontend/src/views/HomeView.vue` — 完整重写模板和样式
- Spec: `docs/superpowers/specs/2026-04-09-home-redesign-mindmap-design.md`

---

### Task 1: 重写 HomeView.vue 模板结构

**Files:**
- Modify: `frontend/src/views/HomeView.vue`

- [ ] **Step 1: 移除 Hero Section 和 quick-info，保留脚本部分**

保留现有 script setup 中的数据定义（rootFeature, branches, branchExtension, quickLinks 可移除，navigateTo 保留）。

模板只保留一个 `.home-view` 容器，内部为 `.mindmap` 区域。

- [ ] **Step 2: 编写新的模板结构**

```vue
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
            <el-icon :size="20"><component :is="rootFeature.icon" /></el-icon>
          </div>
          <div class="center-title">{{ rootFeature.title }}</div>
          <div class="center-desc">起点模块</div>
        </div>

        <!-- 主连接线 -->
        <svg class="line-main" width="140" height="32" viewBox="0 0 140 32">
          <line x1="70" y1="0" x2="70" y2="12" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="25" y1="12" x2="115" y2="12" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="25" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="70" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="115" cy="12" r="3" fill="white" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="25" y1="12" x2="25" y2="32" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="70" y1="12" x2="70" y2="32" stroke="#cbd5e1" stroke-width="1.5"/>
          <line x1="115" y1="12" x2="115" y2="32" stroke="#cbd5e1" stroke-width="1.5"/>
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
            <div class="branch-eyebrow" :style="{ color: feature.color }">{{ feature.eyebrow }}</div>
            <div class="branch-title">{{ feature.title }}</div>
          </div>
        </div>

        <!-- 工作流到运行分析的连接线 -->
        <svg class="line-sub" width="140" height="24" viewBox="0 0 140 24">
          <line x1="115" y1="0" x2="115" y2="24" stroke="#cbd5e1" stroke-width="1.5"/>
          <circle cx="115" cy="24" r="3" fill="white" stroke="#8b5cf6" stroke-width="1.5"/>
        </svg>

        <!-- 运行分析卡片 -->
        <div class="sub-card-wrap">
          <div class="sub-card" @click="navigateTo(branchExtension.path)">
            <div class="sub-eyebrow" :style="{ color: branchExtension.color }">分析</div>
            <div class="sub-title">{{ branchExtension.title }}</div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
```

- [ ] **Step 3: 清理 script setup，移除 quickLinks**

```vue
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
```

---

### Task 2: 编写扁平简约样式

**Files:**
- Modify: `frontend/src/views/HomeView.vue`

- [ ] **Step 1: 编写完整样式**

```vue
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
  max-width: 480px;
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
  gap: 16px;
}

.center-card {
  width: 180px;
  padding: 16px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;
}

.center-card:hover {
  border-color: #3b82f6;
  transform: translateY(-2px);
}

.center-icon {
  width: 40px;
  height: 40px;
  margin: 0 auto 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: white;
}

.center-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.center-desc {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
}

.line-main,
.line-sub {
  display: block;
}

.branch-row {
  display: flex;
  gap: 12px;
}

.branch-card {
  width: 80px;
  padding: 12px 10px;
  background: white;
  border: 1px solid;
  border-radius: 6px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.branch-card:hover {
  transform: translateY(-2px);
}

.branch-eyebrow {
  font-size: 10px;
  font-weight: 500;
}

.branch-title {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.sub-card-wrap {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  max-width: 280px;
  padding-right: 30px;
}

.sub-card {
  width: 90px;
  padding: 10px 12px;
  background: white;
  border: 1px solid #8b5cf6;
  border-radius: 6px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.sub-card:hover {
  transform: translateY(-2px);
}

.sub-eyebrow {
  font-size: 10px;
  font-weight: 500;
}

.sub-title {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

@media (max-width: 400px) {
  .branch-row {
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .branch-card {
    width: 100px;
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
}
</style>
```

---

### Task 3: 验证并提交

**Files:**
- Modify: `frontend/src/views/HomeView.vue`

- [ ] **Step 1: 启动前端开发服务器验证**

Run: `cd /Users/zzm/Desktop/test-by-ai/frontend && npm run dev`
Expected: 页面正常显示，无报错

- [ ] **Step 2: 浏览器检查**

打开首页，验证：
- Hero Section 已移除
- 底部信息区已移除
- 垂直树形布局正确显示
- 连接线 SVG 正常渲染
- 卡片点击导航正常
- hover 效果正常

- [ ] **Step 3: 提交更改**

```bash
git add frontend/src/views/HomeView.vue docs/superpowers/specs/2026-04-09-home-redesign-mindmap-design.md
git commit -m "refactor: redesign home page with mindmap layout

- Remove Hero section and bottom info area
- Use vertical tree structure with flat/minimal style
- SVG connecting lines with thin gray lines and small nodes
- All card levels use unified flat style

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```