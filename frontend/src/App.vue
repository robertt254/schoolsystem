<script setup>
import { useRoute } from 'vue-router';
import Sidebar from './components/Sidebar.vue';
import { useAutoLogout } from './composables/useAutoLogout';

const route = useRoute();
useAutoLogout();
</script>

<template>
  <div v-if="route.path === '/login'" class="w-full">
      <router-view></router-view>
  </div>
  <div v-else class="h-screen bg-gray-bg flex overflow-hidden">
    <Sidebar />
    <main class="flex-1 w-full overflow-y-auto">
      <router-view></router-view>
    </main>
  </div>
</template>
