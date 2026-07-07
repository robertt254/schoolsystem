<script setup>
import { useRoute } from 'vue-router';
import Sidebar from './components/Sidebar.vue';

const route = useRoute();
</script>

<template>
  <div v-if="route.path === '/login'" class="w-full">
      <router-view></router-view>
  </div>
  <div v-else class="min-h-screen bg-gray-bg flex">
    <Sidebar />
    <main class="flex-1 w-full overflow-y-auto">
      <router-view></router-view>
    </main>
  </div>
</template>
