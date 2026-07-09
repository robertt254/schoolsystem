<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import api from '../api';
import SchoolBadge from '../components/SchoolBadge.vue';

const route = useRoute();
const students = ref([]);
const selectedStudent = ref('');
const selectedTerm = ref('Term 1');
const academicYear = ref(String(new Date().getFullYear()));
const report = ref(null);
const examResults = ref([]);
const terms = ["Term 1", "Term 2", "Term 3"];

const SCORE_LABELS = { EE: 'Exceeding', ME: 'Meeting', AE: 'Approaching', BE: 'Below' };

const loadStudents = async () => {
    try {
        const res = await api.getStudents();
        students.value = res.data;
        if (route.query.student) selectedStudent.value = route.query.student;
    } catch (e) { console.error(e); }
};

const generate = async () => {
    if (!selectedStudent.value) return;
    report.value = null;
    try {
        const res = await api.getReportCard(selectedStudent.value, selectedTerm.value, academicYear.value);
        report.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStudentExamResults(selectedStudent.value);
        examResults.value = res.data.filter(r => r.term === selectedTerm.value && String(r.academic_year) === String(academicYear.value));
    } catch (e) { console.error(e); }
};

const printCard = () => window.print();

onMounted(async () => {
    await loadStudents();
    if (selectedStudent.value) generate();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Report Cards</h1>
        <button v-if="report" @click="printCard" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Print</button>
    </div>

    <!-- Selector -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Student</label>
                <select v-model="selectedStudent" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="">Select student</option>
                    <option v-for="s in students" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }})</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term</label>
                <select v-model="selectedTerm" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Academic Year</label>
                <input v-model="academicYear" type="number" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <button @click="generate" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Generate</button>
        </div>
    </div>

    <!-- Report card -->
    <div v-if="report" class="bg-white rounded-xl shadow-sm border border-gray-200 p-8 print-area">
        <div class="text-center border-b pb-4 mb-6">
            <div class="flex justify-center mb-2">
                <SchoolBadge :size="88" />
            </div>
            <h2 class="text-2xl font-bold text-navy">THE BONA SCHOOL</h2>
            <p class="text-xs font-semibold uppercase tracking-widest text-red-accent">In Truth We Excel</p>
            <p class="text-lg font-semibold text-gray-700 mt-1">CBC Progress Report</p>
            <p class="text-gray-600 mt-1">
                <span class="font-semibold">{{ report.student_name }}</span> · {{ report.admission_number }} ·
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ report.grade_level }}</span>
            </p>
            <p class="text-sm text-gray-500">{{ report.term }} {{ report.academic_year }}</p>
        </div>

        <h3 class="text-lg font-bold text-navy mb-2">Learning Areas</h3>
        <table class="min-w-full divide-y divide-gray-200 mb-8">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Learning Area</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Strands & Levels</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Remarks</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in report.results" :key="r.learning_area">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy align-top">{{ r.learning_area }}</td>
                    <td class="px-6 py-3 text-sm">
                        <div v-for="(score, strand) in r.strands" :key="strand" class="mb-1">
                            <span class="text-gray-700">{{ strand || 'General' }}:</span>
                            <span class="ml-1 px-2 py-0.5 text-xs font-semibold rounded-full"
                                  :class="{
                                      'bg-green-100 text-green-800': score === 'EE',
                                      'bg-blue-100 text-blue-800': score === 'ME',
                                      'bg-yellow-100 text-yellow-800': score === 'AE',
                                      'bg-red-100 text-red-800': score === 'BE'
                                  }">{{ score }} — {{ SCORE_LABELS[score] || score }} Expectation</span>
                        </div>
                    </td>
                    <td class="px-6 py-3 text-sm text-gray-500 align-top">{{ r.remarks || '—' }}</td>
                </tr>
                <tr v-if="report.results.length === 0">
                    <td colspan="3" class="px-6 py-6 text-center text-gray-500 text-sm">No CBC assessments recorded for this term.</td>
                </tr>
            </tbody>
        </table>

        <h3 class="text-lg font-bold text-navy mb-2">Exam Results — {{ selectedTerm }}</h3>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exam</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Marks</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">%</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in examResults" :key="r.id">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ r.subject }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ r.exam_type }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ r.marks }}/{{ r.max_marks }}</td>
                    <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ Math.round(r.marks / r.max_marks * 100) }}%</td>
                </tr>
                <tr v-if="examResults.length === 0">
                    <td colspan="4" class="px-6 py-6 text-center text-gray-500 text-sm">No exam results for this term.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
