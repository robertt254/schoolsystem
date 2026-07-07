<script setup>
</script>

<template>
  <div class="min-h-screen bg-gray-100 flex flex-col">
    <nav class="bg-blue-600 text-white p-4 shadow-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <router-link to="/" class="text-2xl font-bold">School System</router-link>
        <div class="space-x-4">
          <router-link to="/teachers" class="hover:text-blue-200">Teachers</router-link>
          <router-link to="/courses" class="hover:text-blue-200">Courses</router-link>
          <router-link to="/students" class="hover:text-blue-200">Students</router-link>
        </div>
      </div>
    </nav>
    <main class="flex-grow max-w-7xl mx-auto w-full">
      <router-view></router-view>
    </main>
  </div>
</template>
