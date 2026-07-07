import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Teachers from '../views/Teachers.vue'
import Courses from '../views/Courses.vue'
import Students from '../views/Students.vue'
import Login from '../views/Login.vue'
import FinanceDashboard from '../views/FinanceDashboard.vue'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', component: Dashboard },
  { path: '/teachers', component: Teachers, meta: { requiresAdmin: true } },
  { path: '/courses', component: Courses },
  { path: '/students', component: Students },
  { path: '/finance', component: FinanceDashboard, meta: { requiresFinance: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // Try to fetch user if we have a token but no user
  if (authStore.token && !authStore.user) {
      await authStore.fetchUser();
  }

  const isAuthenticated = authStore.isAuthenticated;

  if (!to.meta.public && !isAuthenticated) {
    next('/login');
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/'); // Or a 403 page
  } else if (to.meta.requiresFinance && !authStore.isAdmin && !authStore.isFinance) {
    next('/'); // Or a 403 page
  } else if (to.path === '/login' && isAuthenticated) {
    next('/');
  } else {
    next();
  }
})

export default router
