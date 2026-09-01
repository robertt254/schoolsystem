<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';
import ReceiptModal from '../components/ReceiptModal.vue';

const authStore = useAuthStore();

const academicYear = ref(new Date().getFullYear());
const term = ref('Term 1');           // arrears computed up to and including this term
const terms = ["Term 1", "Term 2", "Term 3"];

// Zone A is for students closer to the school, Zone B for those further
// away — each priced and subscribed to independently.
const zones = ref([]);                // [{activity_name: 'Transport - Zone A', amount, category}, ...]
const selectedZone = ref('');
const zoneAmountInput = ref('');
const savingZone = ref(false);

const roster = ref(null);
const loadingRoster = ref(false);
const message = ref('');

const students = ref([]);
const studentSearch = ref('');
const subscribeStudentId = ref('');
const subscribeTerm = ref('Term 1');
const subscribing = ref(false);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const zoneShortLabel = (name) => (name || '').replace('Transport - ', '');

const selectedZoneInfo = computed(() => zones.value.find(z => z.activity_name === selectedZone.value) || null);

const filteredStudents = computed(() => {
    const q = studentSearch.value.trim().toLowerCase();
    const subscribedIds = new Set((roster.value?.entries || []).filter(e => e.is_active).map(e => e.student_id));
    let pool = students.value.filter(s => !subscribedIds.has(s.id));
    if (!q) return pool;
    return pool.filter(s =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.admission_number || '').toLowerCase().includes(q) ||
        (s.grade_level || '').toLowerCase().includes(q));
});

// ── Zone catalogue & pricing (admin/principal set prices; everyone else sees them) ─
const settingUpZones = ref(false);

const loadZones = async () => {
    try {
        const res = await api.getActivities(parseInt(academicYear.value), 'Transport');
        zones.value = res.data;
        // The previously selected zone may not exist for a newly picked year —
        // fall back to the first available zone (or clear it) rather than
        // silently keeping a stale selection.
        if (!zones.value.find(z => z.activity_name === selectedZone.value)) {
            selectedZone.value = zones.value.length ? zones.value[0].activity_name : '';
        }
    } catch (e) { console.error(e); }
};

// One-click fix for the common case: no "Transport - Zone A/B" price rows
// exist yet for this year (nobody has been through Fee Structure -> Load
// Template -> Save Structure), so the zone dropdown has nothing to show.
// Creates both zones at KES 0 — price them below once created.
const setUpZones = async () => {
    settingUpZones.value = true;
    message.value = '';
    const existing = new Set(zones.value.map(z => z.activity_name));
    const missing = ['Transport - Zone A', 'Transport - Zone B'].filter(name => !existing.has(name));
    let created = 0;
    const failures = [];
    // Independent requests — one already existing (e.g. a prior partial
    // setup) must not stop the other from being created.
    for (const name of missing) {
        try {
            await api.createFeeStructureEntry({
                grade_level: 'General', term: 'Transport', fee_type: name,
                amount: 0, academic_year: parseInt(academicYear.value),
            });
            created += 1;
        } catch (e) {
            failures.push(`${zoneShortLabel(name)} (${e.response?.data?.detail || 'failed'})`);
        }
    }
    if (created) message.value = `${created} zone(s) created — set their fees below.`;
    if (failures.length) message.value = `${message.value} Failed: ${failures.join(', ')}.`.trim();
    if (!created && !failures.length) message.value = 'Both zones already exist.';
    await loadZones();
    await loadFeeStructureRow();
    settingUpZones.value = false;
};

const feeStructureRow = ref(null);   // the actual FeeStructure row backing selectedZone, for editing

const loadFeeStructureRow = async () => {
    if (!selectedZone.value) { feeStructureRow.value = null; return; }
    try {
        const res = await api.getFeeStructure();
        feeStructureRow.value = res.data.find(r =>
            r.grade_level === 'General' && r.term === 'Transport' &&
            r.fee_type === selectedZone.value && r.academic_year === parseInt(academicYear.value)) || null;
        zoneAmountInput.value = feeStructureRow.value ? feeStructureRow.value.amount : (selectedZoneInfo.value?.amount ?? '');
    } catch (e) { console.error(e); }
};

const saveZoneFee = async () => {
    const amount = parseFloat(zoneAmountInput.value);
    if (!(amount >= 0) || !selectedZone.value) return;
    savingZone.value = true;
    message.value = '';
    try {
        if (feeStructureRow.value) {
            await api.updateFeeStructureEntry(feeStructureRow.value.id, {
                grade_level: 'General', term: 'Transport', fee_type: selectedZone.value,
                amount, academic_year: parseInt(academicYear.value),
            });
        } else {
            await api.createFeeStructureEntry({
                grade_level: 'General', term: 'Transport', fee_type: selectedZone.value,
                amount, academic_year: parseInt(academicYear.value),
            });
        }
        message.value = `${zoneShortLabel(selectedZone.value)} fee saved.`;
        await loadZones();
        await loadFeeStructureRow();
        loadRoster();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to save the zone fee.';
    }
    savingZone.value = false;
};

// ── Roster & arrears ─────────────────────────────────────────────────────────
const loadRoster = async () => {
    if (!selectedZone.value) { roster.value = null; return; }
    loadingRoster.value = true;
    message.value = '';
    try {
        const res = await api.getActivityRoster(selectedZone.value, term.value, academicYear.value);
        roster.value = res.data;
    } catch (e) {
        console.error(e);
        roster.value = null;
        message.value = e.response?.data?.detail || 'Failed to load the transport roster.';
    }
    loadingRoster.value = false;
};

watch(term, loadRoster);
watch(selectedZone, () => { loadFeeStructureRow(); loadRoster(); });

const load = async () => {
    try {
        const termRes = await api.getCurrentTerm();
        term.value = termRes.data.term;
        subscribeTerm.value = termRes.data.term;
        academicYear.value = termRes.data.academic_year;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
    await loadZones();
    await loadFeeStructureRow();
    loadRoster();
};

// ── Subscriptions ────────────────────────────────────────────────────────────
const subscribe = async () => {
    if (!subscribeStudentId.value || !selectedZone.value) return;
    subscribing.value = true;
    message.value = '';
    try {
        await api.subscribeToActivity({
            student_id: parseInt(subscribeStudentId.value),
            activity_name: selectedZone.value,
            academic_year: parseInt(academicYear.value),
            enrolled_term: subscribeTerm.value,
        });
        subscribeStudentId.value = '';
        studentSearch.value = '';
        message.value = `Student subscribed to ${zoneShortLabel(selectedZone.value)}.`;
        loadRoster();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to subscribe student.';
    }
    subscribing.value = false;
};

const unsubscribe = async (entry) => {
    if (!window.confirm(`Take ${entry.student_name} off school transport? Any arrears already owed stay on record.`)) return;
    try {
        await api.unsubscribeFromActivity(entry.enrollment_id);
        loadRoster();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to unsubscribe student.');
    }
};

// ── Payments ─────────────────────────────────────────────────────────────────
const payAmount = ref({});
const paying = ref({});
const receipt = ref(null);

const pay = async (entry) => {
    const amount = parseFloat(payAmount.value[entry.enrollment_id]);
    if (!(amount > 0)) return;
    paying.value = { ...paying.value, [entry.enrollment_id]: true };
    message.value = '';
    try {
        const res = await api.recordActivityPayment({
            student_id: entry.student_id,
            activity_name: selectedZone.value,
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
            <h1 class="text-3xl font-bold text-navy">Transport</h1>
            <p class="text-sm text-gray-500">Subscriptions, payments and arrears by zone — Zone A for students closer to the school, Zone B for those further away</p>
        </div>
        <input v-model.number="academicYear" @change="loadZones(); loadFeeStructureRow(); loadRoster();" type="number"
               class="px-3 py-1 text-sm font-semibold rounded-full bg-blue-100 text-blue-800 w-24 text-center border-0 focus:ring-2 focus:ring-navy" />
    </div>

    <p v-if="message" class="text-sm font-medium" :class="message.includes('Failed') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <!-- Zone selector + fee -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div v-if="zones.length === 0" class="text-sm text-gray-500">
            <p>No transport zones configured yet for {{ academicYear }}.</p>
            <button v-if="authStore.isAdmin" @click="setUpZones" :disabled="settingUpZones"
                    class="mt-3 bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">
                {{ settingUpZones ? 'Setting up…' : 'Set Up Zone A & Zone B' }}
            </button>
            <p v-else class="mt-1">Ask an admin or the principal to set them up.</p>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Zone</label>
                <select v-model="selectedZone" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="z in zones" :key="z.activity_name" :value="z.activity_name">{{ zoneShortLabel(z.activity_name) }} ({{ money(z.amount) }}/term)</option>
                </select>
            </div>
            <template v-if="authStore.isAdmin">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Amount per term (KES)</label>
                    <input v-model="zoneAmountInput" type="number" min="0" step="0.01"
                           class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
                </div>
                <button @click="saveZoneFee" :disabled="savingZone || zoneAmountInput === '' || !selectedZone" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">
                    {{ savingZone ? 'Saving…' : (feeStructureRow ? 'Update Fee' : 'Set Fee') }}
                </button>
            </template>
            <div v-else class="md:col-span-2 text-sm text-gray-500">
                {{ selectedZoneInfo ? `${money(selectedZoneInfo.amount)} per term` : 'Ask an admin or the principal to set this zone\'s fee.' }}
            </div>
        </div>
    </div>

    <template v-if="selectedZone">
      <!-- Term selector -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <label class="block text-sm font-medium text-gray-700 mb-1">Arrears up to term</label>
          <select v-model="term" class="border border-gray-300 p-2 rounded-md w-full md:w-64 bg-white focus:ring-navy focus:border-navy">
              <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
          </select>
      </div>

      <!-- Subscribe a student -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Subscribe a Student to {{ zoneShortLabel(selectedZone) }}</h2>
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
          <p class="text-xs text-gray-400 mt-2">Only students not already on this zone are listed — check the other zone if you can't find someone.</p>
      </div>

      <!-- Roster & arrears -->
      <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
          <h2 class="text-xl font-bold text-navy p-6 pb-3">{{ zoneShortLabel(selectedZone) }} — Subscribers & Arrears</h2>
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
                      <td colspan="8" class="px-6 py-8 text-center text-gray-500 text-sm">No students subscribed to {{ zoneShortLabel(selectedZone) }} yet.</td>
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
