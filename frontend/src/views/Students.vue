<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const students = ref([]);
const newStudent = ref({ name: '', email: '' });

const loadStudents = async () => {
  const response = await api.getStudents();
  students.value = response.data;
};

const addStudent = async () => {
  if (!newStudent.value.name || !newStudent.value.email) return;
  await api.createStudent(newStudent.value);
  newStudent.value = { name: '', email: '' };
  loadStudents();
};

onMounted(() => {
  loadStudents();
});
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-4">Students</h1>

    <div class="mb-8 p-4 bg-gray-50 rounded border">
      <h2 class="text-xl font-semibold mb-3">Add New Student</h2>
      <div class="flex gap-4">
        <input v-model="newStudent.name" type="text" placeholder="Name" class="border p-2 rounded" />
        <input v-model="newStudent.email" type="email" placeholder="Email" class="border p-2 rounded" />
        <button @click="addStudent" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Add</button>
      </div>
    </div>

    <div class="bg-white shadow rounded-lg border overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="student in students" :key="student.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ student.id }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ student.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ student.email }}</td>
          </tr>
          <tr v-if="students.length === 0">
            <td colspan="3" class="px-6 py-4 text-center text-gray-500">No students found.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
