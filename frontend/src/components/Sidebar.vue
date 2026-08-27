<script setup>
import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useRouter, useRoute } from 'vue-router';
import ChangePasswordModal from './ChangePasswordModal.vue';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const showPasswordModal = ref(false);

const logout = () => {
    authStore.logout();
    router.push('/login');
};

const linkClass = "block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent";
const subLinkClass = "block pl-8 pr-4 py-2 rounded text-sm transition-colors hover:bg-navy-light hover:text-red-accent";
const activeClass = "bg-navy-light text-red-accent border-l-4 border-red-accent";

// Module groups — collapsed by default, the group of the current page opens
const groups = computed(() => [
    {
        key: 'academics', label: 'Academics', show: true,
        links: [
            { to: '/students', label: 'Students' },
            { to: '/classes', label: 'Classes' },
            { to: '/attendance', label: 'Attendance' },
            { to: '/courses', label: 'Courses' },
            { to: '/exams', label: 'Exams' },
            { to: '/report-cards', label: 'Report Cards' },
            { to: '/timetable', label: 'Timetable' },
            { to: '/discipline', label: 'Discipline' },
        ]
    },
    {
        key: 'finance', label: 'Finance', show: authStore.canFees,
        links: [
            { to: '/finance', label: 'Finance Dashboard' },
            { to: '/bulk-payments', label: 'Bulk Payments' },
            { to: '/transport', label: 'Transport' },
            { to: '/activities', label: 'Co-curricular Activities' },
            { to: '/defaulters', label: 'Defaulters' },
            { to: '/fee-statement', label: 'Fee Statement' },
            { to: '/fee-structure', label: 'Fee Structure' },
            ...(authStore.canPayroll ? [{ to: '/payroll', label: 'Payroll' }] : []),
            ...(authStore.canFinance ? [
                { to: '/expenses', label: 'Expenses' },
                { to: '/budgets', label: 'Budgets' },
            ] : []),
        ]
    },
    {
        key: 'people', label: 'People & HR', show: true,
        links: [
            ...(authStore.isAdmin || authStore.isFinance ? [{ to: '/teachers', label: 'Staff & HR' }] : []),
            { to: '/leave', label: 'Leave' },
            { to: '/library', label: 'Library' },
            { to: '/events', label: 'Events' },
            ...(authStore.canComms ? [{ to: '/sms', label: 'SMS' }] : []),
        ]
    },
    {
        key: 'system', label: 'System', show: authStore.isAdmin,
        links: [
            { to: '/reports', label: 'Reports' },
            { to: '/admin', label: 'Admin Tools' },
        ]
    },
]);

// Open the group that contains the page the user is on
const initialOpen = () => {
    for (const g of groups.value) {
        if (g.links.some(l => route.path.startsWith(l.to))) return g.key;
    }
    return null;
};
const openGroup = ref(initialOpen());
const toggle = (key) => {
    openGroup.value = openGroup.value === key ? null : key;
};
</script>

<template>
  <aside class="w-64 bg-navy text-white flex flex-col shadow-lg flex-shrink-0 h-screen">
    <div class="p-6 border-b border-navy-light">
      <h1 class="text-2xl font-bold text-red-accent">THE BONA SCHOOL</h1>
      <p class="text-xs uppercase tracking-widest text-gray-400">In Truth We Excel</p>
      <p v-if="authStore.user" class="text-sm mt-2 text-gray-300">Welcome, {{ authStore.user.name || authStore.user.username }}</p>
    </div>
    <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
      <router-link to="/" :class="linkClass" :active-class="activeClass">Dashboard</router-link>

      <template v-for="g in groups" :key="g.key">
        <div v-if="g.show && g.links.length">
          <button @click="toggle(g.key)"
                  class="w-full flex justify-between items-center px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent"
                  :class="openGroup === g.key ? 'text-red-accent' : 'text-white'">
            <span class="font-semibold">{{ g.label }}</span>
            <span class="text-xs transition-transform" :class="openGroup === g.key ? 'rotate-180' : ''">▼</span>
          </button>
          <div v-show="openGroup === g.key" class="mt-1 space-y-1">
            <router-link v-for="l in g.links" :key="l.to" :to="l.to" :class="subLinkClass" :active-class="activeClass">
              {{ l.label }}
            </router-link>
          </div>
        </div>
      </template>
    </nav>
    <div class="p-4 border-t border-navy-light">
        <button @click="showPasswordModal = true" class="w-full text-left px-4 py-2 rounded transition-colors hover:bg-navy-light text-gray-300 hover:text-white">Change Password</button>
        <button @click="logout" class="w-full text-left px-4 py-2 rounded transition-colors hover:bg-navy-light text-gray-300 hover:text-white">Logout</button>
    </div>
    <ChangePasswordModal v-if="showPasswordModal" @close="showPasswordModal = false" />
  </aside>
</template>
