<script setup>
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const logout = () => {
    authStore.logout();
    router.push('/login');
};
</script>

<template>
  <aside class="w-64 bg-navy text-white flex flex-col shadow-lg flex-shrink-0 min-h-screen">
    <div class="p-6 border-b border-navy-light">
      <h1 class="text-2xl font-bold text-red-accent">School System</h1>
      <p v-if="authStore.user" class="text-sm mt-2 text-gray-300">Welcome, {{ authStore.user.username }}</p>
    </div>
    <nav class="flex-1 p-4 space-y-2">
      <router-link to="/" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Dashboard</router-link>
      <router-link v-if="authStore.isAdmin" to="/teachers" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Teachers</router-link>
      <router-link to="/courses" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Courses</router-link>
      <router-link to="/students" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Students</router-link>
      <router-link v-if="authStore.isAdmin || authStore.isFinance" to="/finance" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Finance</router-link>
    </nav>
    <div class="p-4 border-t border-navy-light">
        <button @click="logout" class="w-full text-left px-4 py-2 rounded transition-colors hover:bg-navy-light text-gray-300 hover:text-white">Logout</button>
    </div>
  </aside>
</template>
