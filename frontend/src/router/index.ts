import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue')
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
      path: '/workflows/:id/edit',
      name: 'workflow-edit',
      component: () => import('@/views/WorkflowEditorView.vue')
    },
    {
      path: '/monitor',
      name: 'monitor',
      component: () => import('@/views/MonitorView.vue')
    }
  ]
})

export default router