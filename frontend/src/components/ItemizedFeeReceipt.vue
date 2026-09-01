<script setup>
// Mirrors the school's paper fee-receipt book: one form, itemized by fee
// type, one student at a time. "Being Payment Of" items with no arrears
// concept (Admission, Diary, Lunch, Computer, Tour, Medical, Graduation,
// Miscellaneous) go through the flat /api/fees/other endpoint, same idea as
// Uniforms already did. Tuition and Examination go through the existing
// tuition waterfall. School Bus and each Activity Fee line only accept an
// amount if the student is already subscribed (Transport/Activities pages) —
// paying for something nobody signed up for would silently create no
// record of what it was for, so it's blocked here with a clear reason
// rather than guessed at.
import { ref, computed, watch } from 'vue';
import api from '../api';

const props = defineProps({
    students: { type: Array, required: true },
    currentTerm: { type: String, required: true },
    academicYear: { type: [String, Number], required: true },
});
const emit = defineEmits(['recorded']);

const studentSearch = ref('');
const selectedStudentId = ref('');
const paymentDate = ref('');
const message = ref('');
const saving = ref(false);
const loadingContext = ref(false);

const filteredStudents = computed(() => {
    const q = studentSearch.value.trim().toLowerCase();
    if (!q) return props.students;
    return props.students.filter(s =>
        `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
        (s.admission_number || '').toLowerCase().includes(q) ||
        (s.grade_level || '').toLowerCase().includes(q));
});
const selectedStudent = computed(() =>
    props.students.find(s => s.id === parseInt(selectedStudentId.value)) || null);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const round2 = (v) => Math.round((v + Number.EPSILON) * 100) / 100;

// "Being Payment Of" — fixed items besides Tuition/Examination, matching the
// receipt book. Price hints come from the Fee Structure page when set.
const OTHER_ITEMS = ["Admission", "Diary", "Lunch", "Computer", "Tour", "Medical", "Graduation", "Miscellaneous"];

const tuitionBalance = ref(null);
const otherPriceHints = ref({});     // {fee_item: amount}
const standing = ref([]);            // this student's active Transport/Activity subscriptions + arrears
const activityCatalogue = ref([]);   // every configured Optional (co-curricular) item

const lines = ref([]);   // built from the above once a student is selected

const buildLines = () => {
    const standingByName = Object.fromEntries(standing.value.map(s => [s.activity_name, s]));
    const busEntry = standing.value.find(s => s.category === 'Transport');

    const rows = [];
    rows.push({ key: 'tuition', kind: 'tuition', label: 'School Fees', amount: '',
                outstanding: tuitionBalance.value?.outstanding_balance ?? null });
    rows.push({ key: 'bus', kind: 'activity', label: 'School Bus', amount: '',
                activityName: busEntry?.activity_name || null,
                subscribed: !!busEntry, outstanding: busEntry?.outstanding ?? null });
    for (const item of OTHER_ITEMS) {
        rows.push({ key: `other-${item}`, kind: 'other', label: item, feeItem: item, amount: '',
                    priceHint: otherPriceHints.value[item] });
    }
    rows.push({ key: 'exam', kind: 'exam', label: 'Examination', amount: '' });

    for (const a of activityCatalogue.value) {
        const s = standingByName[a.activity_name];
        rows.push({
            key: `activity-${a.activity_name}`, kind: 'activity', label: a.activity_name,
            amount: '', activityName: a.activity_name, subscribed: !!s,
            outstanding: s?.outstanding ?? null, compulsory: s?.compulsory || false,
        });
    }
    lines.value = rows;
};

const loadStudentContext = async () => {
    if (!selectedStudentId.value) { lines.value = []; return; }
    loadingContext.value = true;
    const id = parseInt(selectedStudentId.value);
    const year = parseInt(props.academicYear);
    try {
        const [balRes, standingRes, catalogueRes, structureRes] = await Promise.all([
            api.getStudentFeeBalance(id, props.currentTerm),
            api.getStudentActivityStanding(id, props.currentTerm, year),
            api.getActivities(year, 'Optional'),
            api.getFeeStructure(),
        ]);
        tuitionBalance.value = balRes.data;
        standing.value = standingRes.data;
        activityCatalogue.value = catalogueRes.data;
        otherPriceHints.value = Object.fromEntries(
            structureRes.data
                .filter(r => r.grade_level === 'General' && r.academic_year === year &&
                             (OTHER_ITEMS.includes(r.fee_type)))
                .map(r => [r.fee_type, r.amount])
        );
    } catch (e) {
        console.error(e);
    }
    buildLines();
    loadingContext.value = false;
};

watch(selectedStudentId, loadStudentContext);

const enteredLines = computed(() => lines.value.filter(l => l.amount !== '' && parseFloat(l.amount) > 0));
const total = computed(() => enteredLines.value.reduce((s, l) => s + parseFloat(l.amount), 0));

const submit = async () => {
    if (!enteredLines.value.length) return;
    saving.value = true;
    message.value = '';
    const recorded = [];
    const failed = [];

    for (const line of enteredLines.value) {
        const amount = parseFloat(line.amount);
        try {
            let res;
            if (line.kind === 'tuition') {
                res = await api.recordFeePayment({
                    student_id: selectedStudentId.value, amount, payment_type: 'Tuition',
                    term: props.currentTerm, current_term: props.currentTerm,
                    ...(paymentDate.value ? { payment_date: paymentDate.value } : {}),
                });
            } else if (line.kind === 'exam') {
                res = await api.recordFeePayment({
                    student_id: selectedStudentId.value, amount, payment_type: 'Exam Fees',
                    term: props.currentTerm, current_term: props.currentTerm,
                    ...(paymentDate.value ? { payment_date: paymentDate.value } : {}),
                });
            } else if (line.kind === 'activity') {
                res = await api.recordActivityPayment({
                    student_id: selectedStudentId.value, activity_name: line.activityName, amount,
                    term: props.currentTerm, academic_year: parseInt(props.academicYear),
                });
            } else {
                res = await api.recordOtherPayment({
                    student_id: selectedStudentId.value, fee_item: line.feeItem, amount,
                    term: props.currentTerm,
                    ...(paymentDate.value ? { payment_date: paymentDate.value } : {}),
                });
            }
            recorded.push({ label: line.label, amount, receipt_number: res.data.receipt_number });
        } catch (e) {
            failed.push(`${line.label} (${e.response?.data?.detail || 'failed'})`);
        }
    }

    saving.value = false;
    if (recorded.length) {
        message.value = `Recorded ${recorded.length} line(s) totalling ${money(recorded.reduce((s, r) => s + r.amount, 0))}.`;
        if (failed.length) message.value += ` Could not record: ${failed.join(', ')}.`;
        // Re-fetch the post-payment tuition + activity/transport arrears so
        // the printed receipt's "Balance" section shows what's still owed,
        // categorized per activity, plus one grand total — not just tuition.
        const year = parseInt(props.academicYear);
        let balanceAfter = tuitionBalance.value;
        let standingAfter = standing.value;
        try {
            const [balRes, standingRes] = await Promise.all([
                api.getStudentFeeBalance(selectedStudentId.value, props.currentTerm),
                api.getStudentActivityStanding(selectedStudentId.value, props.currentTerm, year),
            ]);
            balanceAfter = balRes.data;
            standingAfter = standingRes.data;
        } catch (e) { /* keep the pre-payment figures */ }

        const balanceBreakdown = [];
        if ((balanceAfter?.outstanding_balance ?? 0) > 0) {
            balanceBreakdown.push({ label: 'Tuition', outstanding: balanceAfter.outstanding_balance });
        }
        for (const a of (standingAfter || [])) {
            if (a.outstanding > 0) {
                balanceBreakdown.push({ label: a.category === 'Transport' ? a.activity_name : `${a.activity_name} (Activity)`, outstanding: a.outstanding });
            }
        }
        const totalArrears = round2(balanceBreakdown.reduce((s, b) => s + b.outstanding, 0));

        emit('recorded', {
            student: selectedStudent.value,
            date: paymentDate.value || new Date().toISOString(),
            term: props.currentTerm,
            lines: recorded,
            balance: balanceAfter?.outstanding_balance ?? null,
            balanceBreakdown,
            totalArrears,
        });
        loadStudentContext();
    } else if (failed.length) {
        message.value = `Nothing recorded — ${failed.join(', ')}.`;
    }
};
</script>

<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
    <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Record Fees</h2>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end mb-4">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Search</label>
            <input v-model="studentSearch" type="text" placeholder="Name, admission no. or class…"
                   class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Pupil's Name ({{ filteredStudents.length }} match{{ filteredStudents.length === 1 ? '' : 'es' }})</label>
            <select v-model="selectedStudentId" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                <option value="">Select student</option>
                <option v-for="s in filteredStudents" :key="s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.admission_number }} · {{ s.grade_level }})</option>
            </select>
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Date (blank = today)</label>
            <input v-model="paymentDate" type="date" class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
        </div>
    </div>

    <p v-if="message" class="text-sm font-medium mb-3" :class="message.startsWith('Nothing') ? 'text-red-accent' : 'text-green-600'">{{ message }}</p>

    <template v-if="selectedStudent">
        <div v-if="loadingContext" class="text-sm text-gray-400 py-4">Loading…</div>
        <template v-else>
            <p class="text-sm text-gray-500 mb-2">
                Grade: <span class="font-semibold text-navy">{{ selectedStudent.grade_level }}</span> ·
                Admission No.: <span class="font-semibold text-navy">{{ selectedStudent.admission_number }}</span>
                <span v-if="tuitionBalance" class="ml-3">
                    Tuition outstanding ({{ currentTerm }}):
                    <span class="font-semibold" :class="tuitionBalance.outstanding_balance > 0 ? 'text-red-accent' : 'text-green-600'">{{ money(tuitionBalance.outstanding_balance) }}</span>
                </span>
            </p>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                <!-- Activity Fees — on the left; the list runs long, so it sits
                     beside "Being Payment Of" rather than stacked below it. -->
                <div class="order-2 md:order-1">
                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mt-4 mb-1">Activity Fees</p>
                    <table class="min-w-full divide-y divide-gray-200 mb-4">
                        <tbody class="divide-y divide-gray-100">
                            <tr v-for="l in lines.filter(l => l.kind === 'activity' && l.key !== 'bus')" :key="l.key">
                                <td class="py-1.5 pr-4 text-sm text-gray-700 w-1/2">
                                    {{ l.label }}
                                    <span v-if="l.compulsory" class="ml-1 px-1.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">Compulsory</span>
                                    <span v-if="!l.subscribed" class="block text-xs text-gray-400">Not subscribed — use the Activities page</span>
                                    <span v-else-if="l.outstanding !== null" class="block text-xs" :class="l.outstanding > 0 ? 'text-red-accent' : 'text-green-600'">
                                        {{ l.outstanding > 0 ? `${money(l.outstanding)} owing` : 'Fully settled' }}
                                    </span>
                                </td>
                                <td class="py-1.5">
                                    <input v-model="l.amount" type="number" min="0" step="0.01"
                                           :disabled="!l.subscribed"
                                           placeholder="Shs."
                                           class="border border-gray-300 p-1.5 rounded-md w-32 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg disabled:text-gray-300" />
                                </td>
                            </tr>
                            <tr v-if="lines.filter(l => l.kind === 'activity' && l.key !== 'bus').length === 0">
                                <td class="py-3 text-sm text-gray-400 text-center">No co-curricular activities configured yet.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div class="order-1 md:order-2">
                    <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mt-4 mb-1">Being Payment Of</p>
                    <table class="min-w-full divide-y divide-gray-200 mb-2">
                        <tbody class="divide-y divide-gray-100">
                            <tr v-for="l in lines.filter(l => l.kind !== 'activity' || l.key === 'bus')" :key="l.key">
                                <td class="py-1.5 pr-4 text-sm text-gray-700 w-1/2">
                                    {{ l.label }}
                                    <span v-if="l.kind === 'activity' && !l.subscribed" class="block text-xs text-gray-400">Not subscribed — use the Transport page</span>
                                    <span v-else-if="l.outstanding !== null && l.outstanding !== undefined" class="block text-xs" :class="l.outstanding > 0 ? 'text-red-accent' : 'text-green-600'">
                                        {{ l.outstanding > 0 ? `${money(l.outstanding)} owing` : 'Fully settled' }}
                                    </span>
                                    <span v-else-if="l.priceHint" class="block text-xs text-gray-400">Usual: {{ money(l.priceHint) }}</span>
                                </td>
                                <td class="py-1.5">
                                    <input v-model="l.amount" type="number" min="0" step="0.01"
                                           :disabled="l.kind === 'activity' && !l.subscribed"
                                           placeholder="Shs."
                                           class="border border-gray-300 p-1.5 rounded-md w-32 text-sm text-right focus:ring-navy focus:border-navy disabled:bg-gray-bg disabled:text-gray-300" />
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="flex justify-between items-center border-t-2 border-navy pt-3">
                <span class="font-bold text-navy">Total: {{ money(total) }}</span>
                <button @click="submit" :disabled="saving || enteredLines.length === 0"
                        class="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 disabled:opacity-50">
                    {{ saving ? 'Recording…' : `Record ${enteredLines.length || ''} Payment(s)` }}
                </button>
            </div>
        </template>
    </template>
    <p v-else class="text-sm text-gray-400 italic py-6 text-center">Select a student to itemize their payment.</p>
  </div>
</template>
