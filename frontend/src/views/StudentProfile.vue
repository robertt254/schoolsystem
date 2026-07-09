<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import api from '../api';
import { gradeLabel } from '../utils/grading';

const route = useRoute();
const profile = ref(null);
const examResults = ref([]);
const discipline = ref([]);

const SCORE_TO_LEVEL = {
    EE: "Exceeding Expectation",
    ME: "Meeting Expectation",
    AE: "Approaching Expectation",
    BE: "Below Expectation"
};

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString() : '—';

const load = async () => {
    const id = route.params.id;
    try {
        const res = await api.getStudentProfile(id);
        profile.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStudentExamResults(id);
        examResults.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getDisciplineRecords({ student_id: id });
        discipline.value = res.data;
    } catch (e) { console.error(e); }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8" v-if="profile">
    <div class="flex justify-between items-center">
        <div>
            <h1 class="text-3xl font-bold text-navy">{{ profile.student.first_name }} {{ profile.student.last_name }}</h1>
            <p class="text-gray-600 mt-1">
                {{ profile.student.admission_number }} ·
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ profile.student.grade_level }}</span>
                · {{ profile.student.status }}
            </p>
        </div>
        <router-link :to="`/report-cards?student=${profile.student.id}`" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Report Card</router-link>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Attendance</h3>
            <p class="text-3xl font-bold text-navy">{{ profile.attendance_percentage }}%</p>
            <p class="text-sm text-gray-500">{{ profile.days_present }} of {{ profile.total_days }} days present</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Paid</h3>
            <p class="text-3xl font-bold text-green-600">{{ money(profile.total_paid) }}</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Annual Fee Balance</h3>
            <p class="text-3xl font-bold" :class="profile.fee_balance > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(profile.fee_balance) }}</p>
            <div v-if="profile.fee_balance > 0" class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
        </div>
    </div>

    <!-- Bio details -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Student Details</h2>
        <dl class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><dt class="text-gray-500">Date of Birth</dt><dd class="font-semibold text-gray-900">{{ profile.student.date_of_birth || '—' }}</dd></div>
            <div><dt class="text-gray-500">Gender</dt><dd class="font-semibold text-gray-900">{{ profile.student.gender || '—' }}</dd></div>
            <div><dt class="text-gray-500">Guardian</dt><dd class="font-semibold text-gray-900">{{ profile.student.guardian_name || '—' }}</dd></div>
            <div><dt class="text-gray-500">Guardian Phone</dt><dd class="font-semibold text-gray-900">{{ profile.student.guardian_phone || '—' }}</dd></div>
            <div><dt class="text-gray-500">Guardian 2</dt><dd class="font-semibold text-gray-900">{{ profile.student.guardian2_name || '—' }}</dd></div>
            <div><dt class="text-gray-500">Guardian 2 Phone</dt><dd class="font-semibold text-gray-900">{{ profile.student.guardian2_phone || '—' }}</dd></div>
            <div><dt class="text-gray-500">Address</dt><dd class="font-semibold text-gray-900">{{ profile.student.address || '—' }}</dd></div>
            <div><dt class="text-gray-500">Previous School</dt><dd class="font-semibold text-gray-900">{{ profile.student.previous_school || '—' }}</dd></div>
        </dl>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- CBC Assessments -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">CBC Assessments</h2>
            <div class="max-h-72 overflow-y-auto">
                <ul v-if="profile.assessments.length" class="divide-y divide-gray-200">
                    <li v-for="a in profile.assessments" :key="a.id" class="py-2 text-sm flex justify-between items-center">
                        <div>
                            <span class="font-semibold text-gray-900">{{ a.term }} · {{ a.learning_area }}:</span>
                            {{ a.remarks || '' }}
                        </div>
                        <span class="px-2 py-1 text-xs font-semibold rounded-full"
                              :class="{
                                  'bg-green-100 text-green-800': a.score === 'EE',
                                  'bg-blue-100 text-blue-800': a.score === 'ME',
                                  'bg-yellow-100 text-yellow-800': a.score === 'AE',
                                  'bg-red-100 text-red-800': a.score === 'BE'
                              }">
                            {{ (SCORE_TO_LEVEL[a.score] || a.score).split(' ')[0] }}
                        </span>
                    </li>
                </ul>
                <p v-else class="text-sm text-gray-500 italic">No assessments recorded yet.</p>
            </div>
        </div>

        <!-- Recent Payments -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Recent Fee Payments</h2>
            <div class="max-h-72 overflow-y-auto">
                <ul v-if="profile.recent_payments.length" class="divide-y divide-gray-200">
                    <li v-for="p in profile.recent_payments" :key="p.id" class="py-2 text-sm flex justify-between items-center">
                        <div>
                            <span class="font-semibold text-gray-900">{{ money(p.amount) }}</span>
                            <span class="text-gray-600"> · {{ p.payment_type }} · {{ p.term }}</span>
                            <p class="text-xs text-gray-400">{{ p.receipt_number }} · {{ dateFmt(p.payment_date) }}</p>
                        </div>
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Paid</span>
                    </li>
                </ul>
                <p v-else class="text-sm text-gray-500 italic">No payments recorded yet.</p>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Exam Results -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Exam Results</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subject</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exam</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Term</th>
                        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Marks</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Evaluation</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="r in examResults" :key="r.id" class="hover:bg-gray-50">
                        <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-navy">{{ r.subject }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ r.exam_type }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ r.term }} {{ r.academic_year }}</td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ r.marks }}/{{ r.max_marks }}</td>
                        <td class="px-6 py-3 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                                  :class="gradeLabel(r.marks, r.max_marks).cls">
                                {{ gradeLabel(r.marks, r.max_marks).abbr }}
                            </span>
                        </td>
                    </tr>
                    <tr v-if="examResults.length === 0">
                        <td colspan="5" class="px-6 py-6 text-center text-gray-500 text-sm">No exam results yet.</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Discipline -->
        <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
            <h2 class="text-xl font-bold text-navy p-6 pb-3">Disciplinary Records</h2>
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Incident</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="d in discipline" :key="d.id" class="hover:bg-gray-50">
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ d.incident_date }}</td>
                        <td class="px-6 py-3 text-sm text-gray-900">{{ d.incident_type }}</td>
                        <td class="px-6 py-3 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                                  :class="{ 'bg-yellow-100 text-yellow-800': d.severity === 'Minor', 'bg-orange-100 text-orange-800': d.severity === 'Moderate', 'bg-red-100 text-red-800': d.severity === 'Serious' }">
                                {{ d.severity }}
                            </span>
                        </td>
                        <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ d.status }}</td>
                    </tr>
                    <tr v-if="discipline.length === 0">
                        <td colspan="4" class="px-6 py-6 text-center text-gray-500 text-sm">No disciplinary records. 🎉</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
  </div>
  <div v-else class="p-8 text-gray-500">Loading student profile…</div>
</template>
