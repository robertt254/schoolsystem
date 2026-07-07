<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';

const students = ref([]);
const courses = ref([]);
const newStudent = ref({ admission_number: '', name: '', grade: 'Play Group', guardian_contact: '' });

// CBC Grades matching backend
const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];

const cbcLevels = [
    "Exceeding Expectation",
    "Meeting Expectation",
    "Approaching Expectation",
    "Below Expectation"
];

// Assessment Modal State
const isAssessmentModalOpen = ref(false);
const currentStudent = ref(null);
const newAssessment = ref({
    course_id: '',
    term: 1,
    outcome: '',
    level: 'Meeting Expectation'
});
const currentStudentAssessments = ref([]);

const loadStudents = async () => {
  try {
      const response = await api.getStudents();
      students.value = response.data;
  } catch (e) {
      console.error(e);
  }
};

const loadCourses = async () => {
    try {
        const response = await api.getCourses();
        courses.value = response.data;
    } catch (e) {
        console.error(e);
    }
};

const addStudent = async () => {
  if (!newStudent.value.admission_number || !newStudent.value.name || !newStudent.value.guardian_contact) return;
  try {
      await api.createStudent(newStudent.value);
      newStudent.value = { admission_number: '', name: '', grade: 'Play Group', guardian_contact: '' };
      loadStudents();
  } catch (e) {
      console.error(e);
  }
};

const openAssessmentModal = async (student) => {
    currentStudent.value = student;
    isAssessmentModalOpen.value = true;
    newAssessment.value = { course_id: '', term: 1, outcome: '', level: 'Meeting Expectation' };

    // Load their past assessments
    try {
        const res = await api.getStudentAssessments(student.id);
        currentStudentAssessments.value = res.data;
    } catch (e) {
        console.error(e);
    }
};

const closeAssessmentModal = () => {
    isAssessmentModalOpen.value = false;
    currentStudent.value = null;
};

const submitAssessment = async () => {
    if (!newAssessment.value.course_id || !newAssessment.value.outcome) return;
    try {
        await api.createAssessment({
            student_id: currentStudent.value.id,
            course_id: parseInt(newAssessment.value.course_id),
            term: parseInt(newAssessment.value.term),
            outcome: newAssessment.value.outcome,
            level: newAssessment.value.level
        });

        // Reload assessments for the view
        const res = await api.getStudentAssessments(currentStudent.value.id);
        currentStudentAssessments.value = res.data;

        // Reset form slightly but keep term/course for rapid entry
        newAssessment.value.outcome = '';
    } catch (e) {
        console.error(e);
    }
};

onMounted(() => {
  loadStudents();
  loadCourses();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto relative">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Students Management</h1>
    </div>

    <!-- Registration Form -->
    <div class="mb-8 p-6 bg-white rounded-xl shadow-sm border border-gray-200">
      <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Register New Student</h2>
      <form @submit.prevent="addStudent" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Admission No.</label>
            <input v-model="newStudent.admission_number" type="text" placeholder="ADM-001" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input v-model="newStudent.name" type="text" placeholder="Student Name" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Grade Level</label>
            <select v-model="newStudent.grade" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Guardian Contact</label>
            <input v-model="newStudent.guardian_contact" type="text" placeholder="+254..." class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div class="md:col-span-4 mt-2">
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy w-full md:w-auto">Register Student</button>
        </div>
      </form>
    </div>

    <!-- Students Table -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contact</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="student in students" :key="student.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ student.admission_number }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ student.name }}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                    {{ student.grade }}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ student.guardian_contact }}</td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button @click="openAssessmentModal(student)" class="text-navy hover:text-navy-light mx-2 font-bold underline">Evaluate (CBC)</button>
            </td>
          </tr>
          <tr v-if="students.length === 0">
            <td colspan="5" class="px-6 py-8 text-center text-gray-500 text-sm">No students enrolled yet.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- CBC Assessment Modal -->
    <div v-if="isAssessmentModalOpen" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative w-full max-w-2xl bg-white rounded-xl shadow-lg p-8">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-2xl font-bold text-navy">CBC Evaluation: {{ currentStudent?.name }}</h3>
                <button @click="closeAssessmentModal" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
            </div>

            <form @submit.prevent="submitAssessment" class="space-y-4 mb-8">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Course / Learning Area</label>
                        <select v-model="newAssessment.course_id" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm bg-white">
                            <option value="">Select Course</option>
                            <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.title }}</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Term</label>
                        <select v-model="newAssessment.term" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm bg-white">
                            <option :value="1">Term 1</option>
                            <option :value="2">Term 2</option>
                            <option :value="3">Term 3</option>
                        </select>
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700">Specific Learning Outcome</label>
                    <input v-model="newAssessment.outcome" type="text" placeholder="e.g. Identifies basic colors correctly" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Performance Level</label>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                        <label v-for="lvl in cbcLevels" :key="lvl" class="border rounded-md p-2 flex items-center cursor-pointer transition-colors" :class="{'bg-navy text-white border-navy': newAssessment.level === lvl, 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100': newAssessment.level !== lvl}">
                            <input type="radio" :value="lvl" v-model="newAssessment.level" class="sr-only">
                            <span class="text-xs text-center w-full font-semibold">{{ lvl }}</span>
                        </label>
                    </div>
                </div>

                <div class="flex justify-end pt-4">
                    <button type="submit" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-accent">Save Record</button>
                </div>
            </form>

            <!-- Past Records -->
            <div>
                <h4 class="text-lg font-bold text-navy mb-2 border-b pb-1">Recent Evaluations</h4>
                <div class="max-h-48 overflow-y-auto">
                    <ul v-if="currentStudentAssessments.length > 0" class="divide-y divide-gray-200">
                        <li v-for="assessment in currentStudentAssessments" :key="assessment.id" class="py-2 text-sm flex justify-between items-center">
                            <div>
                                <span class="font-semibold text-gray-900">Term {{ assessment.term }}:</span> {{ assessment.outcome }}
                            </div>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full"
                                  :class="{
                                      'bg-green-100 text-green-800': assessment.level === 'Exceeding Expectation',
                                      'bg-blue-100 text-blue-800': assessment.level === 'Meeting Expectation',
                                      'bg-yellow-100 text-yellow-800': assessment.level === 'Approaching Expectation',
                                      'bg-red-100 text-red-800': assessment.level === 'Below Expectation'
                                  }">
                                {{ assessment.level.split(' ')[0] }}
                            </span>
                        </li>
                    </ul>
                    <p v-else class="text-sm text-gray-500 italic">No evaluations recorded yet.</p>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>
