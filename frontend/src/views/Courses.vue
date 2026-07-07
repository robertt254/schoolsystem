<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const courses = ref([]);
const teachers = ref([]);
const newCourse = ref({ title: '', description: '', teacher_id: '' });

const loadData = async () => {
  const [coursesRes, teachersRes] = await Promise.all([
    api.getCourses(),
    api.getTeachers()
  ]);
  courses.value = coursesRes.data;
  teachers.value = teachersRes.data;
};

const addCourse = async () => {
  if (!newCourse.value.title || !newCourse.value.teacher_id) return;
  await api.createCourse(newCourse.value);
  newCourse.value = { title: '', description: '', teacher_id: '' };
  loadData();
};

const getTeacherName = (id) => {
  const teacher = teachers.value.find(t => t.id === id);
  return teacher ? teacher.name : 'Unknown';
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-4">Courses</h1>

    <div class="mb-8 p-4 bg-gray-50 rounded border">
      <h2 class="text-xl font-semibold mb-3">Add New Course</h2>
      <div class="flex gap-4 flex-wrap">
        <input v-model="newCourse.title" type="text" placeholder="Title" class="border p-2 rounded" />
        <input v-model="newCourse.description" type="text" placeholder="Description" class="border p-2 rounded" />
        <select v-model="newCourse.teacher_id" class="border p-2 rounded bg-white">
          <option value="">Select Teacher</option>
          <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
            {{ teacher.name }}
          </option>
        </select>
        <button @click="addCourse" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Add</button>
      </div>
    </div>

    <div class="bg-white shadow rounded-lg border overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Teacher</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="course in courses" :key="course.id">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ course.id }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ course.title }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ course.description }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ getTeacherName(course.teacher_id) }}</td>
          </tr>
          <tr v-if="courses.length === 0">
            <td colspan="4" class="px-6 py-4 text-center text-gray-500">No courses found.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
