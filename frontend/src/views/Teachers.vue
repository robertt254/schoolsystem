<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const teachers = ref([]);
const newTeacher = ref({ name: '', department: '' });

const loadTeachers = async () => {
  const response = await api.getTeachers();
  teachers.value = response.data;
};

const addTeacher = async () => {
  if (!newTeacher.value.name || !newTeacher.value.department) return;
  await api.createTeacher(newTeacher.value);
  newTeacher.value = { name: '', department: '' };
  loadTeachers();
};

onMounted(() => {
  loadTeachers();
});
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-4">Teachers</h1>

    <div class="mb-8 p-4 bg-gray-50 rounded border">
      <h2 class="text-xl font-semibold mb-3">Add New Teacher</h2>
      <div class="flex gap-4">
        <input v-model="newTeacher.name" type="text" placeholder="Name" class="border p-2 rounded" />
        <input v-model="newTeacher.department" type="text" placeholder="Department" class="border p-2 rounded" />
        <button @click="addTeacher" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Add</button>
      </div>
    </div>

    <div class="bg-white shadow rounded-lg border overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Department</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="teacher in teachers" :key="teacher.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ teacher.id }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ teacher.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ teacher.department }}</td>
          </tr>
          <tr v-if="teachers.length === 0">
            <td colspan="3" class="px-6 py-4 text-center text-gray-500">No teachers found.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
