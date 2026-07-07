<script setup>
</script>

<template>
  <div class="min-h-screen bg-gray-bg flex">
    <!-- Sidebar -->
    <aside class="w-64 bg-navy text-white flex flex-col shadow-lg flex-shrink-0">
      <div class="p-6 border-b border-navy-light">
        <h1 class="text-2xl font-bold text-red-accent">School System</h1>
      </div>
      <nav class="flex-1 p-4 space-y-2">
        <router-link to="/" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Dashboard</router-link>
        <router-link to="/teachers" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Teachers</router-link>
        <router-link to="/courses" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Courses</router-link>
        <router-link to="/students" class="block px-4 py-2 rounded transition-colors hover:bg-navy-light hover:text-red-accent" active-class="bg-navy-light text-red-accent border-l-4 border-red-accent">Students</router-link>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 w-full overflow-y-auto">
      <router-view></router-view>
    </main>
  </div>
</template>
