<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
import ChangePasswordModal from './ChangePasswordModal.vue';

const authStore = useAuthStore();
const router = useRouter();
const showPasswordModal = ref(false);

const logout = () => {
    authStore.logout();
    router.push('/login');
};

const linkClass = "block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent";
const activeClass = "bg-navy-light text-red-accent border-l-4 border-red-accent";
const sectionClass = "px-4 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400";
</script>

<template>
  <aside class="w-64 bg-navy text-white flex flex-col shadow-lg flex-shrink-0 min-h-screen">
    <div class="p-6 border-b border-navy-light">
      <h1 class="text-2xl font-bold text-red-accent">School System</h1>
      <p v-if="authStore.user" class="text-sm mt-2 text-gray-300">Welcome, {{ authStore.user.name || authStore.user.username }}</p>
    </div>
    <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
      <router-link to="/" :class="linkClass" :active-class="activeClass">Dashboard</router-link>

      <p :class="sectionClass">Academics</p>
      <router-link to="/students" :class="linkClass" :active-class="activeClass">Students</router-link>
      <router-link to="/classes" :class="linkClass" :active-class="activeClass">Classes</router-link>
      <router-link to="/attendance" :class="linkClass" :active-class="activeClass">Attendance</router-link>
      <router-link to="/courses" :class="linkClass" :active-class="activeClass">Courses</router-link>
      <router-link to="/exams" :class="linkClass" :active-class="activeClass">Exams</router-link>
      <router-link to="/report-cards" :class="linkClass" :active-class="activeClass">Report Cards</router-link>
      <router-link to="/timetable" :class="linkClass" :active-class="activeClass">Timetable</router-link>
      <router-link to="/discipline" :class="linkClass" :active-class="activeClass">Discipline</router-link>

      <template v-if="authStore.canFinance">
        <p :class="sectionClass">Finance</p>
        <router-link to="/finance" :class="linkClass" :active-class="activeClass">Finance</router-link>
        <router-link to="/defaulters" :class="linkClass" :active-class="activeClass">Defaulters</router-link>
        <router-link to="/fee-statement" :class="linkClass" :active-class="activeClass">Fee Statement</router-link>
        <router-link to="/fee-structure" :class="linkClass" :active-class="activeClass">Fee Structure</router-link>
        <router-link to="/payroll" :class="linkClass" :active-class="activeClass">Payroll</router-link>
        <router-link to="/expenses" :class="linkClass" :active-class="activeClass">Expenses</router-link>
        <router-link to="/budgets" :class="linkClass" :active-class="activeClass">Budgets</router-link>
      </template>

      <p :class="sectionClass">People & Office</p>
      <router-link v-if="authStore.isAdmin || authStore.isFinance" to="/teachers" :class="linkClass" :active-class="activeClass">Staff & HR</router-link>
      <router-link to="/leave" :class="linkClass" :active-class="activeClass">Leave</router-link>
      <router-link to="/library" :class="linkClass" :active-class="activeClass">Library</router-link>
      <router-link to="/events" :class="linkClass" :active-class="activeClass">Events</router-link>
      <router-link v-if="authStore.canComms" to="/sms" :class="linkClass" :active-class="activeClass">SMS</router-link>

      <template v-if="authStore.isAdmin">
        <p :class="sectionClass">System</p>
        <router-link to="/reports" :class="linkClass" :active-class="activeClass">Reports</router-link>
        <router-link to="/admin" :class="linkClass" :active-class="activeClass">Admin Tools</router-link>
      </template>
    </nav>
    <div class="p-4 border-t border-navy-light">
        <button @click="showPasswordModal = true" class="w-full text-left px-4 py-2 rounded transition-colors hover:bg-navy-light text-gray-300 hover:text-white">Change Password</button>
        <button @click="logout" class="w-full text-left px-4 py-2 rounded transition-colors hover:bg-navy-light text-gray-300 hover:text-white">Logout</button>
    </div>
    <ChangePasswordModal v-if="showPasswordModal" @close="showPasswordModal = false" />
  </aside>
</template>
