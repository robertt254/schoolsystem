<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const courses = ref([]);
const teachers = ref([]);
const newCourse = ref({ title: '', description: '', grade_level: 'Grade 1', teacher_id: '' });

// CBC Grades matching backend
const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];

const loadData = async () => {
  try {
      const [coursesRes, teachersRes] = await Promise.all([
          api.getCourses(),
          api.getTeachers()
      ]);
      courses.value = coursesRes.data;
      teachers.value = teachersRes.data;
  } catch (e) {
      console.error(e);
  }
};

const addCourse = async () => {
  if (!newCourse.value.title || !newCourse.value.teacher_id) return;
  try {
      await api.createCourse(newCourse.value);
      newCourse.value = { title: '', description: '', grade_level: 'Grade 1', teacher_id: '' };
      loadData();
  } catch (e) {
      console.error(e);
  }
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
  <div class="p-8 max-w-7xl mx-auto">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Courses Management</h1>
    </div>

    <!-- Registration Form -->
    <div class="mb-8 p-6 bg-white rounded-xl shadow-sm border border-gray-200">
      <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Add New Course</h2>
      <form @submit.prevent="addCourse" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Course Title</label>
            <input v-model="newCourse.title" type="text" placeholder="e.g. Mathematics" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input v-model="newCourse.description" type="text" placeholder="Short description" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Grade Level</label>
            <select v-model="newCourse.grade_level" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Assigned Teacher</label>
            <select v-model="newCourse.teacher_id" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy" required>
                <option value="">Select Teacher</option>
                <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">{{ teacher.name }}</option>
            </select>
        </div>
        <div class="md:col-span-4 mt-2">
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy w-full md:w-auto">Add Course</button>
        </div>
      </form>
    </div>

    <!-- Courses Table -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Teacher</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="course in courses" :key="course.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ course.title }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ course.description }}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                    {{ course.grade_level }}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ getTeacherName(course.teacher_id) }}</td>
          </tr>
          <tr v-if="courses.length === 0">
            <td colspan="4" class="px-6 py-8 text-center text-gray-500 text-sm">No courses added yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
