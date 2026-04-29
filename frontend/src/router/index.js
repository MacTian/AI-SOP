import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
  },
  {
    path: '/sop-editor',
    name: 'SopEditor',
    component: () => import('../views/SopEditor.vue'),
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
  },
  {
    path: '/training',
    name: 'Training',
    component: () => import('../views/Training.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
