<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';
import { exportCsv } from '../utils/csvExport';

const authStore = useAuthStore();

const exportStudents = () => {
    exportCsv('students.csv',
        [['admission_number', 'Admission No'], ['name', 'Name'], ['grade', 'Grade'], ['guardian_contact', 'Guardian Contact']],
        students.value);
};
const students = ref([]);
const courses = ref([]);
const blankStudent = () => ({
    first_name: '', last_name: '', grade: 'Play Group',
    date_of_birth: '', gender: '', guardian_name: '', guardian_contact: '',
    guardian2_name: '', guardian2_phone: '', address: '', previous_school: ''
});
const newStudent = ref(blankStudent());
const searchTerm = ref('');
const filterGrade = ref('');
const registerMessage = ref('');

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

// CBC score codes used by the backend <-> display labels used in the UI
const LEVEL_TO_SCORE = {
    "Exceeding Expectation": "EE",
    "Meeting Expectation": "ME",
    "Approaching Expectation": "AE",
    "Below Expectation": "BE"
};
const SCORE_TO_LEVEL = {
    EE: "Exceeding Expectation",
    ME: "Meeting Expectation",
    AE: "Approaching Expectation",
    BE: "Below Expectation"
};

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

// Backend student record -> shape the table renders
const mapStudent = (s) => ({
    id: s.id,
    admission_number: s.admission_number,
    name: `${s.first_name} ${s.last_name}`.trim(),
    grade: s.grade_level,
    guardian_contact: s.guardian_phone || '—'
});

const loadStudents = async () => {
  try {
      const params = {};
      if (searchTerm.value) params.search = searchTerm.value;
      if (filterGrade.value) params.grade = filterGrade.value;
      const response = await api.getStudents(params);
      students.value = response.data.map(mapStudent);
  } catch (e) {
      console.error(e);
  }
};

const archiveStudent = async (student) => {
    if (!window.confirm(`Archive ${student.name}? The record is kept and can be restored from Admin.`)) return;
    try {
        await api.archiveStudent(student.id);
        loadStudents();
    } catch (e) {
        console.error(e);
    }
};

// Edit modal — full CBC record with guardians and bio fields
const isEditOpen = ref(false);
const editForm = ref({});
const openEdit = async (student) => {
    try {
        const res = await api.getStudentProfile(student.id);
        const s = res.data.student;
        editForm.value = {
            id: s.id,
            first_name: s.first_name, last_name: s.last_name,
            grade_level: s.grade_level, status: s.status,
            date_of_birth: s.date_of_birth || '', gender: s.gender || '',
            guardian_name: s.guardian_name || '', guardian_phone: s.guardian_phone || '',
            guardian2_name: s.guardian2_name || '', guardian2_phone: s.guardian2_phone || '',
            address: s.address || '', previous_school: s.previous_school || ''
        };
        isEditOpen.value = true;
    } catch (e) { console.error(e); }
};

const saveEdit = async () => {
    const f = editForm.value;
    try {
        await api.updateStudent(f.id, {
            first_name: f.first_name, last_name: f.last_name,
            grade_level: f.grade_level, status: f.status,
            date_of_birth: f.date_of_birth || null, gender: f.gender || null,
            guardian_name: f.guardian_name || null, guardian_phone: f.guardian_phone || null,
            guardian2_name: f.guardian2_name || null, guardian2_phone: f.guardian2_phone || null,
            address: f.address || null, previous_school: f.previous_school || null
        });
        isEditOpen.value = false;
        loadStudents();
    } catch (e) { console.error(e); }
};

const loadCourses = async () => {
    try {
        const response = await api.getSubjects();
        courses.value = response.data.map(s => ({ id: s.id, title: `${s.name} (${s.grade_level})`, name: s.name }));
    } catch (e) {
        console.error(e);
    }
};

const addStudent = async () => {
  const f = newStudent.value;
  if (!f.first_name || !f.last_name) return;
  registerMessage.value = '';
  try {
      const res = await api.createStudent({
          first_name: f.first_name,
          last_name: f.last_name,
          // Admission number is system-generated (BNS-XXXX) and immutable
          grade_level: f.grade,
          date_of_birth: f.date_of_birth || null,
          gender: f.gender || null,
          guardian_name: f.guardian_name || null,
          guardian_phone: f.guardian_contact || null,
          guardian2_name: f.guardian2_name || null,
          guardian2_phone: f.guardian2_phone || null,
          address: f.address || null,
          previous_school: f.previous_school || null
      });
      registerMessage.value = `Admitted ${res.data.first_name} ${res.data.last_name} — admission number ${res.data.admission_number}.`;
      newStudent.value = blankStudent();
      loadStudents();
  } catch (e) {
      console.error(e);
      registerMessage.value = e.response?.data?.detail || 'Failed to register student.';
  }
};

const loadStudentAssessments = async (studentId) => {
    const res = await api.getStudentProfile(studentId);
    currentStudentAssessments.value = (res.data.assessments || []).map(a => ({
        id: a.id,
        term: parseInt((a.term || '').replace(/\D/g, '')) || a.term,
        outcome: a.remarks || a.learning_area,
        level: SCORE_TO_LEVEL[a.score] || a.score
    }));
};

const openAssessmentModal = async (student) => {
    currentStudent.value = student;
    isAssessmentModalOpen.value = true;
    newAssessment.value = { course_id: '', term: 1, outcome: '', level: 'Meeting Expectation' };

    // Load their past assessments
    try {
        await loadStudentAssessments(student.id);
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
        const subject = courses.value.find(c => c.id === parseInt(newAssessment.value.course_id));
        await api.recordScores([{
            student_id: currentStudent.value.id,
            academic_year: String(new Date().getFullYear()),
            term: `Term ${parseInt(newAssessment.value.term)}`,
            learning_area: subject ? subject.name : 'General',
            strand: newAssessment.value.outcome.slice(0, 100),
            score: LEVEL_TO_SCORE[newAssessment.value.level] || 'ME',
            remarks: newAssessment.value.outcome
        }]);

        // Reload assessments for the view
        await loadStudentAssessments(currentStudent.value.id);

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
        <button @click="exportStudents" :disabled="students.length === 0" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">Export CSV</button>
    </div>

    <!-- Registration Form -->
    <div class="mb-8 p-6 bg-white rounded-xl shadow-sm border border-gray-200">
      <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Register New Student — Bona School Kenya</h2>
      <form @submit.prevent="addStudent" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">First Name</label>
            <input v-model="newStudent.first_name" type="text" placeholder="First name" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
            <input v-model="newStudent.last_name" type="text" placeholder="Last name" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" required />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Grade Level</label>
            <select v-model="newStudent.grade" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
            <input v-model="newStudent.date_of_birth" type="date" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Gender</label>
            <select v-model="newStudent.gender" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                <option value="">—</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Guardian Name</label>
            <input v-model="newStudent.guardian_name" type="text" placeholder="Parent / guardian" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Guardian Phone</label>
            <input v-model="newStudent.guardian_contact" type="text" placeholder="+254..." class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Guardian 2 Name (optional)</label>
            <input v-model="newStudent.guardian2_name" type="text" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Guardian 2 Phone (optional)</label>
            <input v-model="newStudent.guardian2_phone" type="text" placeholder="+254..." class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Home Address</label>
            <input v-model="newStudent.address" type="text" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Previous School (optional)</label>
            <input v-model="newStudent.previous_school" type="text" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div class="md:col-span-4 mt-2 flex items-center gap-4">
            <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy w-full md:w-auto">Register Student</button>
            <span v-if="registerMessage" class="text-sm font-medium" :class="registerMessage.startsWith('Admitted') ? 'text-green-600' : 'text-red-accent'">{{ registerMessage }}</span>
        </div>
      </form>
    </div>

    <!-- Search & Filter -->
    <div class="mb-4 flex flex-col md:flex-row gap-4">
        <input v-model="searchTerm" @keyup.enter="loadStudents" type="text" placeholder="Search by name or admission number..." class="border border-gray-300 p-2 rounded-md w-full md:flex-1 focus:ring-navy focus:border-navy" />
        <select v-model="filterGrade" @change="loadStudents" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy md:w-48">
            <option value="">All Grades</option>
            <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
        </select>
        <button @click="loadStudents" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy">Search</button>
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
                <router-link :to="`/students/${student.id}`" class="text-navy hover:text-navy-light mx-2 font-bold underline">Profile</router-link>
                <button @click="openAssessmentModal(student)" class="text-navy hover:text-navy-light mx-2 font-bold underline">Evaluate (CBC)</button>
                <button v-if="authStore.canManageStudents" @click="openEdit(student)" class="text-navy hover:text-navy-light mx-2 font-bold underline">Edit</button>
                <button v-if="authStore.isAdmin" @click="archiveStudent(student)" class="text-red-accent hover:text-red-hover mx-2 font-bold underline">Archive</button>
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

    <!-- Edit Student Modal -->
    <div v-if="isEditOpen" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative w-full max-w-2xl bg-white rounded-xl shadow-lg p-8 my-8 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-2xl font-bold text-navy">Edit Student: {{ editForm.first_name }} {{ editForm.last_name }}</h3>
                <button @click="isEditOpen = false" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
            </div>
            <form @submit.prevent="saveEdit" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">First Name</label>
                        <input v-model="editForm.first_name" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Last Name</label>
                        <input v-model="editForm.last_name" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Grade Level</label>
                        <select v-model="editForm.grade_level" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Status</label>
                        <select v-model="editForm.status" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option>Active</option>
                            <option>Graduated</option>
                            <option>Transferred</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Date of Birth</label>
                        <input v-model="editForm.date_of_birth" type="date" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Gender</label>
                        <select v-model="editForm.gender" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option value="">—</option>
                            <option value="Male">Male</option>
                            <option value="Female">Female</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Guardian Name</label>
                        <input v-model="editForm.guardian_name" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Guardian Phone</label>
                        <input v-model="editForm.guardian_phone" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Guardian 2 Name</label>
                        <input v-model="editForm.guardian2_name" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Guardian 2 Phone</label>
                        <input v-model="editForm.guardian2_phone" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Address</label>
                        <input v-model="editForm.address" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Previous School</label>
                        <input v-model="editForm.previous_school" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <div class="flex justify-end pt-4">
                    <button type="submit" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover">Save Changes</button>
                </div>
            </form>
        </div>
    </div>
  </div>
</template>
