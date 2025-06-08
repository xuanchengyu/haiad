import { createRouter, createWebHistory } from 'vue-router'
import VideoList from '@/views/VideoList.vue'
import ModeSelection from '@/views/ModeSelection.vue'
import HumanOnlyEdit from '@/views/HumanOnlyEdit.vue'
import CollaborativeEdit from '@/views/CollaborativeEdit.vue'
import Login from '@/views/Login.vue'
import Register from '@/views/Register.vue'
import AiAssistant from '@/components/AiAssistant.vue'

const routes = [
  {
    path: '/',
    name: 'VideoList',
    component: VideoList
  },
  {
    path: '/mode-select/:id',
    name: 'ModeSelection',
    component: ModeSelection
  },
  {
    path: '/human-only/:id',
    name: 'HumanOnlyEdit',
    component: HumanOnlyEdit
  },
  {
    path: '/collaborative/:id',
    name: 'CollaborativeEdit',
    component: CollaborativeEdit
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/register',
    name: 'Register',
    component: Register
  },
  {
    path: '/ai-assistant',
    name: 'AiAssistant',
    component: AiAssistant
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 添加路由守卫
router.beforeEach((to, from, next) => {
  const publicPages = ['/login', '/register'];
  const authRequired = !publicPages.includes(to.path);
  const loggedIn = localStorage.getItem('token');

  if (authRequired && !loggedIn) {
    return next('/login');
  }

  next();
})

export default router 