<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { gradeLabel, EXAM_TYPES, examTypeLabel } from '../utils/grading';
import { wasEnrolledForTerm } from '../utils/enrollment';
import { useAuthStore } from '../stores/auth';
import { printElement } from '../utils/printFrame';
import SchoolBadge from '../components/SchoolBadge.vue';

const authStore = useAuthStore();

const grades = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6"
];
const terms = ["Term 1", "Term 2", "Term 3"];
const examTypes = EXAM_TYPES;

const filters = ref({
    grade: 'Grade 1',
    term: 'Term 1',
    exam_type: 'Opener',
    subject: '',
    academic_year: new Date().getFullYear(),
    max_marks: 100
});

const subjects = ref([]);
const entryRows = ref([]);       // [{student_id, student_name, admission_number, marks}]
const resultsView = ref(null);   // {subjects: [], students: []}
const message = ref('');
const saving = ref(false);

const loadSubjects = async () => {
    try {
        const res = await api.getSubjects({ grade: filters.value.grade });
        subjects.value = res.data;
        if (!filters.value.subject && subjects.value.length) {
            filters.value.subject = subjects.value[0].name;
        }
    } catch (e) { console.error(e); }
};

const loadEntrySheet = async () => {
    message.value = '';
    try {
        // Load the class list AND any marks already recorded for this
        // grade/term/exam/subject, so re-opening a sheet shows saved marks
        // instead of a blank grid (prevents double entry).
        const [studentsRes, existingRes] = await Promise.all([
            api.getStudents({ grade: filters.value.grade }),
            api.getGradeExamResults(
                filters.value.grade, filters.value.term,
                filters.value.academic_year, filters.value.exam_type
            ).catch(() => null)
        ]);
        const existing = {};
        if (existingRes) {
            for (const row of existingRes.data.students) {
                const score = row.scores[filters.value.subject];
                if (score) existing[row.student_id] = score.marks;
            }
        }
        // A mid-year joiner has nothing to enter for a term before they were
        // admitted — leave them off the entry sheet entirely rather than
        // showing a row with nowhere to record a real mark.
        const year = parseInt(filters.value.academic_year);
        entryRows.value = studentsRes.data
            .filter(s => wasEnrolledForTerm(s, filters.value.term, year))
            .map(s => ({
                student_id: s.id,
                student_name: `${s.first_name} ${s.last_name}`,
                admission_number: s.admission_number,
                marks: existing[s.id] ?? null
            }));
    } catch (e) { console.error(e); }
};

const loadResults = async () => {
    try {
        // Results are stored separately per exam type and must be viewed
        // that way too — the merit list is always scoped to exactly one
        // exam (Opener / Mid Term / End Term), never a blend of all three.
        const res = await api.getGradeExamResults(
            filters.value.grade, filters.value.term,
            filters.value.academic_year, filters.value.exam_type
        );
        resultsView.value = res.data;
    } catch (e) { console.error(e); }
};

const saveMarks = async () => {
    const rows = entryRows.value.filter(r => r.marks !== null && r.marks !== '');
    if (!rows.length || !filters.value.subject) return;
    saving.value = true;
    message.value = '';
    try {
        const res = await api.recordExamResults({
            grade_level: filters.value.grade,
            term: filters.value.term,
            exam_type: filters.value.exam_type,
            subject: filters.value.subject,
            academic_year: parseInt(filters.value.academic_year),
            results: rows.map(r => ({
                student_id: r.student_id,
                marks: parseFloat(r.marks),
                max_marks: parseInt(filters.value.max_marks)
            }))
        });
        message.value = `Saved ${res.data.saved} result(s) for ${filters.value.subject} (${examTypeLabel(filters.value.exam_type)}).`;
        if (res.data.skipped_ineligible) {
            message.value += ` ${res.data.skipped_ineligible} skipped — not yet enrolled for ${filters.value.term}.`;
        }
        loadResults();
    } catch (e) {
        console.error(e);
        message.value = e.response?.data?.detail || 'Failed to save results.';
    }
    saving.value = false;
};

const meritListRoot = ref(null);
const printMeritList = () => printElement(
    meritListRoot.value,
    `${filters.value.grade} — ${examTypeLabel(filters.value.exam_type)} Merit List`
);

const onGradeChange = async () => {
    filters.value.subject = '';
    await loadSubjects();   // sets the default subject before prefilling marks
    loadEntrySheet();
    loadResults();
};

onMounted(async () => {
    await loadSubjects();
    loadEntrySheet();
    loadResults();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Exams</h1>
    </div>

    <!-- Marks entry — roles that may record marks (backend: admin/principal/teachers) -->
    <div v-if="authStore.canAcademics" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Enter Exam Marks</h2>
        <div class="grid grid-cols-2 md:grid-cols-6 gap-4 items-end mb-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Grade</label>
                <select v-model="filters.grade" @change="onGradeChange" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Term</label>
                <select v-model="filters.term" @change="loadResults(); loadEntrySheet()" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Exam</label>
                <select v-model="filters.exam_type" @change="loadEntrySheet(); loadResults()" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="e in examTypes" :key="e" :value="e">{{ examTypeLabel(e) }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <select v-model="filters.subject" @change="loadEntrySheet" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="">Select subject</option>
                    <option v-for="s in subjects" :key="s.id" :value="s.name">{{ s.name }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <input v-model="filters.academic_year" type="number" @change="loadResults(); loadEntrySheet()" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Out of</label>
                <input v-model="filters.max_marks" type="number" min="1" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
        </div>

        <table class="min-w-full divide-y divide-gray-200 mb-4">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Marks</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Evaluation</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in entryRows" :key="r.student_id" class="hover:bg-gray-50">
                    <td class="px-6 py-2 whitespace-nowrap text-sm font-medium text-navy">{{ r.admission_number }}</td>
                    <td class="px-6 py-2 whitespace-nowrap text-sm text-gray-900">{{ r.student_name }}</td>
                    <td class="px-6 py-2">
                        <input v-model="r.marks" type="number" min="0" :max="filters.max_marks" step="0.5"
                               class="border border-gray-300 p-1.5 rounded-md w-28 text-sm focus:ring-navy focus:border-navy" />
                    </td>
                    <td class="px-6 py-2 whitespace-nowrap">
                        <span v-if="r.marks !== null && r.marks !== ''"
                              class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="gradeLabel(r.marks, filters.max_marks).cls">
                            {{ gradeLabel(r.marks, filters.max_marks).label }}
                        </span>
                        <span v-else class="text-gray-300 text-sm">—</span>
                    </td>
                </tr>
                <tr v-if="entryRows.length === 0">
                    <td colspan="4" class="px-6 py-8 text-center text-gray-500 text-sm">No students in this grade.</td>
                </tr>
            </tbody>
        </table>

        <div class="flex items-center gap-4">
            <button @click="saveMarks" :disabled="saving" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">
                {{ saving ? 'Saving…' : 'Save Marks' }}
            </button>
            <p v-if="message" class="text-sm font-medium" :class="message.startsWith('Saved') ? 'text-green-600' : 'text-red-accent'">{{ message }}</p>
        </div>
    </div>

    <!-- Results / merit list -->
    <div v-if="resultsView" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">{{ filters.grade }} · {{ filters.term }} · {{ examTypeLabel(filters.exam_type) }} Merit List</h2>
            <button @click="printMeritList" class="no-print bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Print Merit List</button>
        </div>
        <div ref="meritListRoot" class="print-area">
        <!-- Print-only letterhead -->
        <div class="hidden print:block text-center border-b-2 border-navy pb-4 mb-4 px-6">
            <div class="flex justify-center mb-2">
                <SchoolBadge :size="80" />
            </div>
            <h2 class="text-2xl font-extrabold text-navy">THE BONA SCHOOL</h2>
            <p class="text-xs font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
            <p class="text-xs uppercase tracking-widest text-gray-500 mt-1">Official Merit List</p>
            <p class="text-sm text-gray-600 mt-2">
                {{ filters.grade }} · {{ filters.term }} · {{ examTypeLabel(filters.exam_type) }} · {{ filters.academic_year }}
            </p>
        </div>
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pos</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                        <th v-for="sub in resultsView.subjects" :key="sub" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{{ sub }}</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">%</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="row in resultsView.students" :key="row.student_id" class="hover:bg-gray-50">
                        <td class="px-6 py-3 whitespace-nowrap text-sm font-bold text-navy">{{ row.position }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-900">{{ row.student_name }}</td>
                        <td v-for="sub in resultsView.subjects" :key="sub" class="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                            <template v-if="row.scores[sub]">
                                {{ row.scores[sub].marks }}
                                <span class="ml-1 px-1.5 inline-flex text-xs leading-5 font-semibold rounded-full"
                                      :class="gradeLabel(row.scores[sub].marks, row.scores[sub].max_marks).cls">
                                    {{ gradeLabel(row.scores[sub].marks, row.scores[sub].max_marks).abbr }}
                                </span>
                            </template>
                            <span v-else>—</span>
                        </td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ row.total_marks }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right">
                            <span v-if="row.percentage !== null" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                                  :class="row.percentage >= 70 ? 'bg-green-100 text-green-800' : row.percentage >= 50 ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'">
                                {{ row.percentage }}%
                            </span>
                            <span v-else class="text-gray-400">—</span>
                        </td>
                    </tr>
                    <tr v-if="resultsView.students.length === 0">
                        <td :colspan="3 + resultsView.subjects.length" class="px-6 py-8 text-center text-gray-500 text-sm">No results recorded for this selection.</td>
                    </tr>
                </tbody>
            </table>
        </div>
        </div>
    </div>
  </div>
</template>
