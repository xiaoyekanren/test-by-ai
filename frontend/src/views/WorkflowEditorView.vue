<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

const route = useRoute()

const nodes = ref([
  { id: '1', type: 'input', position: { x: 250, y: 0 }, data: { label: 'Start' } },
  { id: '2', position: { x: 100, y: 100 }, data: { label: 'Task 1' } },
  { id: '3', position: { x: 400, y: 100 }, data: { label: 'Task 2' } },
  { id: '4', type: 'output', position: { x: 250, y: 200 }, data: { label: 'End' } }
])

const edges = ref([
  { id: 'e1-2', source: '1', target: '2' },
  { id: 'e1-3', source: '1', target: '3' },
  { id: 'e2-4', source: '2', target: '4' },
  { id: 'e3-4', source: '3', target: '4' }
])

const workflowId = route.params.id
</script>

<template>
  <div class="workflow-editor">
    <div class="editor-header">
      <h2>Workflow Editor: {{ workflowId }}</h2>
    </div>
    <div class="editor-canvas">
      <VueFlow v-model:nodes="nodes" v-model:edges="edges" fit-view-on-init>
        <Background />
        <Controls />
      </VueFlow>
    </div>
  </div>
</template>

<style scoped>
.workflow-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.editor-header {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.editor-canvas {
  flex: 1;
  background: #f5f7fa;
}
</style>