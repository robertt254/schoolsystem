import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Teachers from '../views/Teachers.vue'
import Courses from '../views/Courses.vue'
import Students from '../views/Students.vue'
import StudentProfile from '../views/StudentProfile.vue'
import Classes from '../views/Classes.vue'
import Attendance from '../views/Attendance.vue'
import Exams from '../views/Exams.vue'
import ReportCard from '../views/ReportCard.vue'
import Timetable from '../views/Timetable.vue'
import Discipline from '../views/Discipline.vue'
import Leave from '../views/Leave.vue'
import Login from '../views/Login.vue'
import FinanceDashboard from '../views/FinanceDashboard.vue'
import Defaulters from '../views/Defaulters.vue'
import FeeStructure from '../views/FeeStructure.vue'
import Payroll from '../views/Payroll.vue'
import Expenses from '../views/Expenses.vue'
import Budgets from '../views/Budgets.vue'
import Library from '../views/Library.vue'
import Events from '../views/Events.vue'
import Sms from '../views/Sms.vue'
import Admin from '../views/Admin.vue'
import FeeStatement from '../views/FeeStatement.vue'
import BulkPayments from '../views/BulkPayments.vue'
import Reports from '../views/Reports.vue'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', component: Dashboard },

  // Academics
  { path: '/students', component: Students },
  { path: '/students/:id', component: StudentProfile },
  { path: '/classes', component: Classes },
  { path: '/attendance', component: Attendance },
  { path: '/courses', component: Courses },
  { path: '/exams', component: Exams },
  { path: '/report-cards', component: ReportCard },
  { path: '/timetable', component: Timetable },
  { path: '/discipline', component: Discipline },

  // Fee operations — includes the secretary (mirrors backend FINANCE_ROLES)
  { path: '/finance', component: FinanceDashboard, meta: { requiresFees: true } },
  { path: '/defaulters', component: Defaulters, meta: { requiresFees: true } },
  { path: '/fee-structure', component: FeeStructure, meta: { requiresFees: true } },
  { path: '/fee-statement', component: FeeStatement, meta: { requiresFees: true } },
  { path: '/bulk-payments', component: BulkPayments, meta: { requiresFees: true } },
  // School finances — admin/principal/accountant only
  { path: '/expenses', component: Expenses, meta: { requiresFinance: true } },
  { path: '/budgets', component: Budgets, meta: { requiresFinance: true } },
  // Payroll — admin/accountant only (matches the backend)
  { path: '/payroll', component: Payroll, meta: { requiresPayroll: true } },
  { path: '/reports', component: Reports, meta: { requiresAdmin: true } },

  // People & office
  { path: '/teachers', component: Teachers, meta: { requiresAdmin: true } },
  { path: '/leave', component: Leave },
  { path: '/library', component: Library },
  { path: '/events', component: Events },
  { path: '/sms', component: Sms, meta: { requiresComms: true } },

  // System
  { path: '/admin', component: Admin, meta: { requiresAdmin: true } },
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
  } else if (to.meta.requiresAdmin && !authStore.isAdmin && !authStore.isFinance) {
    next('/'); // Or a 403 page
  } else if (to.meta.requiresFees && !authStore.canFees) {
    next('/');
  } else if (to.meta.requiresFinance && !authStore.canFinance) {
    next('/'); // Or a 403 page
  } else if (to.meta.requiresPayroll && !authStore.canPayroll) {
    next('/');
  } else if (to.meta.requiresComms && !authStore.canComms) {
    next('/');
  } else if (to.path === '/login' && isAuthenticated) {
    next('/');
  } else {
    next();
  }
})

export default router
