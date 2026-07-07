<script setup>
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-4">School Dashboard</h1>
    <p class="text-gray-700">Welcome to the school management system.</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
      <div class="bg-white shadow rounded-lg p-6 border">
        <h2 class="text-xl font-semibold mb-2">Teachers</h2>
        <p class="text-gray-600 mb-4">Manage teaching staff.</p>
        <router-link to="/teachers" class="text-blue-500 hover:underline">View Teachers</router-link>
      </div>
      <div class="bg-white shadow rounded-lg p-6 border">
        <h2 class="text-xl font-semibold mb-2">Courses</h2>
        <p class="text-gray-600 mb-4">Manage academic courses.</p>
        <router-link to="/courses" class="text-blue-500 hover:underline">View Courses</router-link>
      </div>
      <div class="bg-white shadow rounded-lg p-6 border">
        <h2 class="text-xl font-semibold mb-2">Students</h2>
        <p class="text-gray-600 mb-4">Manage enrolled students.</p>
        <router-link to="/students" class="text-blue-500 hover:underline">View Students</router-link>
      </div>
    </div>
  </div>
</template>
