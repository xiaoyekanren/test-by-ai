import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/servers'
    },
    {
      path: '/servers',
      name: 'servers',
      component: () => import('@/views/ServersView.vue')
    },
    {
      path: '/workflows',
      name: 'workflows',
      component: () => import('@/views/WorkflowsView.vue')
    },
    {
      path: '/executions',
      name: 'executions',
      component: () => import('@/views/ExecutionInsightsView.vue')
    },
    {
      path: '/workflows/new',
      name: 'workflow-new',
      redirect: '/workflows'
    },
    {
      path: '/workflows/:id/edit',
      name: 'workflow-edit',
      component: () => import('@/views/WorkflowEditorView.vue')
    },
    {
      path: '/monitor',
      name: 'monitor',
      component: () => import('@/views/MonitorView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue')
    },
    {
      path: '/iotdb',
      name: 'iotdb',
      component: () => import('@/views/IoTDBView.vue')
    }
  ]
})

export default router
