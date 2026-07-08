<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();

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
  // Subjects are visible to everyone; the staff list needs elevated rights,
  // so a 403 there must not break the page (teacher names come with subjects).
  const [coursesRes, teachersRes] = await Promise.allSettled([
      api.getSubjects(),
      api.getStaff()
  ]);
  if (coursesRes.status === 'fulfilled') {
      courses.value = coursesRes.value.data.map(s => ({
          id: s.id,
          title: s.name,
          description: 'CBC Learning Area',
          grade_level: s.grade_level,
          teacher_id: s.teacher_id,
          teacher_name: s.teacher_name
      }));
  } else {
      console.error(coursesRes.reason);
  }
  if (teachersRes.status === 'fulfilled') {
      teachers.value = teachersRes.value.data
          .filter(s => ['teacher', 'senior_teacher'].includes(s.role))
          .map(s => ({ id: s.id, name: s.name }));
  }
};

const addCourse = async () => {
  if (!newCourse.value.title || !newCourse.value.teacher_id) return;
  try {
      await api.createSubject({
          name: newCourse.value.title,
          grade_level: newCourse.value.grade_level,
          teacher_id: parseInt(newCourse.value.teacher_id)
      });
      newCourse.value = { title: '', description: '', grade_level: 'Grade 1', teacher_id: '' };
      loadData();
  } catch (e) {
      console.error(e);
  }
};

const getTeacherName = (id) => {
  if (!id) return 'Unassigned';
  const teacher = teachers.value.find(t => t.id === id);
  if (teacher) return teacher.name;
  const course = courses.value.find(c => c.teacher_id === id);
  return course?.teacher_name || 'Unknown';
};

// Preload the standard CBC learning areas for every grade in one click
const seedSubjects = async () => {
  if (!window.confirm('Seed the standard CBC learning areas for all grades?')) return;
  try {
      await api.seedSubjects();
      loadData();
  } catch (e) {
      window.alert(e.response?.data?.detail || 'Failed to seed subjects.');
  }
};

const removeCourse = async (course) => {
  if (!window.confirm(`Delete "${course.title}" (${course.grade_level})?`)) return;
  try {
      await api.deleteSubject(course.id);
      loadData();
  } catch (e) {
      window.alert(e.response?.data?.detail || 'Failed to delete course.');
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Courses Management</h1>
        <button v-if="authStore.isAdmin" @click="seedSubjects" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light">Seed CBC Subjects</button>
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
            <th v-if="authStore.isAdmin" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
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
            <td v-if="authStore.isAdmin" class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button @click="removeCourse(course)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
            </td>
          </tr>
          <tr v-if="courses.length === 0">
            <td :colspan="authStore.isAdmin ? 5 : 4" class="px-6 py-8 text-center text-gray-500 text-sm">No courses added yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
