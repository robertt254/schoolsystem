import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Teachers from '../views/Teachers.vue'
import Courses from '../views/Courses.vue'
import Students from '../views/Students.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/teachers', component: Teachers },
  { path: '/courses', component: Courses },
  { path: '/students', component: Students }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
