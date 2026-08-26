<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import api from '../api';
import ReceiptModal from '../components/ReceiptModal.vue';

const currentTerm = ref('Term 1');
const academicYear = ref(new Date().getFullYear());
const term = ref('Term 1');          // roster is computed "up to and including" this term
const activities = ref([]);          // [{activity_name, category, amount}]
const selectedActivity = ref('');
const roster = ref(null);            // ActivityRosterResponse
const message = ref('');
const loadingRoster = ref(false);

// Subscribe-a-student panel
const students = ref([]);
const studentSearch = ref('');
const subscribeStudentId = ref('');
const subscribeTerm = ref('Term 1');
const subscribing = ref(false);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const terms = ["Term 1", "Term 2", "Term 3"];

const selectedActivityInfo = computed(() =>
    activities.value.find(a => a.activity_name === selectedActivity.value) || null);

const filteredStudents = computed(() => {
    const q = studentSearch.value.trim().toLowerCase();
    // Exclude students already subscribed (active) to the selected activity
    const subscribedIds = new Set((roster.value?.entries || []).filter(e => e.is_active).map(e => e.student_id));
    let pool = students.value.filter(s => !subscribedIds.has(s.id));
    if (!q) return pool;
    return pool.filter(s =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.admission_number || '').toLowerCase().includes(q) ||
        (s.grade_level || '').toLowerCase().includes(q));
});

const load = async () => {
    try {
        const termRes = await api.getCurrentTerm();
        currentTerm.value = termRes.data.term;
        term.value = termRes.data.term;
        subscribeTerm.value = termRes.data.term;
        academicYear.value = termRes.data.academic_year;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getActivities(academicYear.value);
        activities.value = res.data;
        if (!selectedActivity.value && activities.value.length) {
            selectedActivity.value = activities.value[0].activity_name;
        }
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
    loadRoster();
};

const loadRoster = async () => {
    if (!selectedActivity.value) { roster.value = null; return; }
    loadingRoster.value = true;
    message.value = '';
    try {
        const res = await api.getActivityRoster(selectedActivity.value, term.value, academicYear.value);
        roster.value = res.data;
    } catch (e) {
        console.error(e);
        roster.value = null;
        message.value = e.response?.data?.detail || 'Failed to load roster.';
    }
    loadingRoster.value = false;
};

watch([selectedActivity, term], loadRoster);

const subscribe = async () => {
    if (!subscribeStudentId.value || !selectedActivity.value) return;
    subscribing.value = true;
    message.value = '';
    try {
        await api.subscribeToActivity({
            student_id: parseInt(subscribeStudentId.value),
            activity_name: selectedActivity.value,
            academic_year: parseInt(academicYear.value),
            enrolled_term: subscribeTerm.value,
        });
        subscribeStudentId.value = '';
        studentSearch.value = '';
        message.value = 'Student subscribed.';
        loadRoster();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to subscribe student.';
    }
    subscribing.value = false;
};

const unsubscribe = async (entry) => {
    if (!window.confirm(`Unsubscribe ${entry.student_name} from ${selectedActivity.value}? Any arrears already owed stay on record.`)) return;
    try {
        await api.unsubscribeFromActivity(entry.enrollment_id);
        loadRoster();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to unsubscribe student.');
    }
};

// Per-row payment entry
const payAmount = ref({});   // enrollment_id -> amount string
const paying = ref({});      // enrollment_id -> bool
const receipt = ref(null);

const pay = async (entry) => {
    const amount = parseFloat(payAmount.value[entry.enrollment_id]);
    if (!(amount > 0)) return;
    paying.value = { ...paying.value, [entry.enrollment_id]: true };
    message.value = '';
    try {
        const res = await api.recordActivityPayment({
            student_id: entry.student_id,
            activity_name: selectedActivity.value,
            amount,
            term: term.value,
            academic_year: parseInt(academicYear.value),
        });
        payAmount.value = { ...payAmount.value, [entry.enrollment_id]: '' };
        receipt.value = {
            ...res.data,
            student_name: entry.student_name,
            admission_number: entry.admission_number,
            grade_level: entry.grade_level,
        };
        loadRoster();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to record payment.';
    }
    paying.value = { ...paying.value, [entry.enrollment_id]: false };
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <div>
            <h1 class="text-3xl font-bold text-navy">Transport & Activities</h1>
            <p class="text-sm text-gray-500">Subscriptions and arrears for Transport and co-curricular activities</p>
        </div>
        <span class="px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800">{{ academicYear }}</span>
    </div>

    <p v-if="message" class="text-sm font-medium" :class="message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Activity + term selector -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Activity</label>
                <select v-model="selectedActivity" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option value="" disabled>Select an activity</option>
                    <option v-for="a in activities" :key="a.activity_name" :value="a.activity_name">
                        {{ a.activity_name }} ({{ a.category }} · {{ money(a.amount) }}/term)
                    </option>
                </select>
                <p v-if="activities.length === 0" class="text-xs text-gray-400 mt-1">
                    No priced Transport or co-curricular items yet — add them on the Fee Structure page.
                </p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Arrears up to term</label>
                <select v-model="term" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                </select>
            </div>
            <div v-if="selectedActivityInfo" class="text-sm text-gray-600">
                <span class="font-semibold text-navy">{{ money(selectedActivityInfo.amount) }}</span> per term per subscriber
            </div>
        </div>
    </div>

    <template v-if="selectedActivity">
      <!-- Subscribe a student -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Subscribe a Student</h2>
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Search</label>
                  <input v-model="studentSearch" type="text" placeholder="Name, admission no. or class…"
                         class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
              </div>
              <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Student</label>
                  <select v-model="subscribeStudentId" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                      <option value="">Select student</option>
                      <option v-for="s in filteredStudents" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }} · {{ s.grade_level }})</option>
                  </select>
              </div>
              <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Owes from</label>
                  <select v-model="subscribeTerm" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                      <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
                  </select>
              </div>
              <button @click="subscribe" :disabled="subscribing || !subscribeStudentId"
                      class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">
                  {{ subscribing ? 'Subscribing…' : 'Subscribe' }}
              </button>
          </div>
      </div>

      <!-- Roster & arrears -->
      <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
          <h2 class="text-xl font-bold text-navy p-6 pb-3">{{ selectedActivity }} — Subscribers & Arrears</h2>
          <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                  <tr>
                      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Class</th>
                      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscribed Since</th>
                      <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                      <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                      <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Arrears</th>
                      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Record Payment</th>
                      <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                  <tr v-for="e in roster?.entries || []" :key="e.enrollment_id" class="hover:bg-gray-50" :class="e.is_active ? '' : 'opacity-50'">
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-900">
                          {{ e.student_name }} <span class="text-xs text-gray-400">{{ e.admission_number }}</span>
                          <span v-if="!e.is_active" class="ml-1 px-2 py-0.5 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">Unsubscribed</span>
                      </td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ e.grade_level }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-gray-500">{{ e.enrolled_term }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-500">{{ money(e.expected) }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-green-600 font-semibold">{{ money(e.paid) }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right font-bold" :class="e.outstanding > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(e.outstanding) }}</td>
                      <td class="px-6 py-3 whitespace-nowrap">
                          <div class="flex gap-2 items-center">
                              <input v-model="payAmount[e.enrollment_id]" type="number" min="0" step="0.01" placeholder="Amount"
                                     class="border border-gray-300 p-1.5 rounded-md w-28 text-sm focus:ring-navy focus:border-navy" />
                              <button @click="pay(e)" :disabled="paying[e.enrollment_id] || !payAmount[e.enrollment_id]"
                                      class="bg-green-600 text-white px-3 py-1.5 rounded-md hover:bg-green-700 disabled:opacity-50 text-sm">
                                  Pay
                              </button>
                          </div>
                      </td>
                      <td class="px-6 py-3 whitespace-nowrap text-right text-sm font-medium">
                          <button v-if="e.is_active" @click="unsubscribe(e)" class="text-red-accent hover:text-red-hover font-bold underline">Unsubscribe</button>
                      </td>
                  </tr>
                  <tr v-if="!loadingRoster && (!roster || roster.entries.length === 0)">
                      <td colspan="8" class="px-6 py-8 text-center text-gray-500 text-sm">No students subscribed to {{ selectedActivity }} yet.</td>
                  </tr>
                  <tr v-if="loadingRoster">
                      <td colspan="8" class="px-6 py-8 text-center text-gray-400 text-sm">Loading…</td>
                  </tr>
              </tbody>
              <tfoot v-if="roster && roster.entries.length" class="bg-gray-50 font-bold">
                  <tr>
                      <td colspan="3" class="px-6 py-3 text-sm text-navy">TOTAL</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-gray-700">{{ money(roster.total_expected) }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right text-green-600">{{ money(roster.total_paid) }}</td>
                      <td class="px-6 py-3 whitespace-nowrap text-sm text-right" :class="roster.total_outstanding > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(roster.total_outstanding) }}</td>
                      <td colspan="2"></td>
                  </tr>
              </tfoot>
          </table>
      </div>
    </template>

    <ReceiptModal v-if="receipt" :payment="receipt" @close="receipt = null" />
  </div>
</template>
