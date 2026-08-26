<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import api from '../api';
import { printElement } from '../utils/printFrame';
import SchoolBadge from '../components/SchoolBadge.vue';

const term = ref('Term 1');
const academicYear = ref(String(new Date().getFullYear()));
const defaulters = ref([]);
const loaded = ref(false);
const terms = ["Term 1", "Term 2", "Term 3"];

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const today = () => new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
const totalOutstanding = computed(() =>
    defaulters.value.reduce((sum, d) => sum + (d.outstanding_balance || 0), 0));

const load = async () => {
    try {
        const res = await api.getDefaulters(term.value, academicYear.value);
        defaulters.value = res.data;
        loaded.value = true;
    } catch (e) { console.error(e); }
};

const exportCsv = () => {
    const header = 'Admission No,Student,Grade,Expected,Paid,Outstanding\n';
    const body = defaulters.value.map(d =>
        `${d.admission_number},"${d.student_name}",${d.grade_level},${d.expected_fee},${d.total_paid},${d.outstanding_balance}`
    ).join('\n');
    const blob = new Blob([header + body], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `defaulters_${term.value.replace(' ', '_')}_${academicYear.value}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
};

// ── Arrears invoices — printed as one card per student, page-break between
// them, so a whole stack of "take home to your parent" slips can be run off
// in one print job. `invoiceRoot` stays mounted (possibly empty) so its ref
// is always available; we just swap which students it renders before printing.
const invoiceRoot = ref(null);
const invoiceTargets = ref([]);

const printInvoice = async (d) => {
    invoiceTargets.value = [d];
    await nextTick();
    printElement(invoiceRoot.value, `Arrears Invoice — ${d.student_name}`);
};

const printAllInvoices = async () => {
    if (!defaulters.value.length) return;
    invoiceTargets.value = defaulters.value;
    await nextTick();
    printElement(invoiceRoot.value, `Arrears Invoices — ${term.value} ${academicYear.value}`);
};

onMounted(async () => {
    try {
        const res = await api.getCurrentTerm();
        term.value = res.data.term;
        academicYear.value = String(res.data.academic_year);
    } catch (e) { console.error(e); }
    load();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Fee Defaulters</h1>
        <div class="flex gap-4 items-center">
            <select v-model="term" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
                <option v-for="t in terms" :key="t" :value="t">{{ t }}</option>
            </select>
            <button @click="printAllInvoices" :disabled="defaulters.length === 0" class="bg-red-accent text-white px-4 py-2 rounded-md hover:bg-red-hover disabled:opacity-50">
                Print All Arrears ({{ defaulters.length }})
            </button>
            <button @click="exportCsv" :disabled="defaulters.length === 0" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light disabled:opacity-50">Export CSV</button>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Defaulters · {{ term }}</h3>
            <p class="text-3xl font-bold text-red-accent">{{ defaulters.length }}</p>
            <div class="absolute right-0 bottom-0 h-1 bg-red-accent w-full"></div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Total Outstanding</h3>
            <p class="text-3xl font-bold text-navy">{{ money(totalOutstanding) }}</p>
        </div>
    </div>

    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Adm No.</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Outstanding</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="d in defaulters" :key="d.student_id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ d.admission_number }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ d.student_name }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ d.grade_level }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(d.expected_fee + (d.carry_forward || 0)) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ money(d.total_paid + (d.rollover_credit || 0)) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-red-accent">{{ money(d.outstanding_balance) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                        <button @click="printInvoice(d)" class="text-navy hover:text-navy-light font-bold underline">Invoice</button>
                        <router-link :to="`/students/${d.student_id}`" class="text-navy hover:text-navy-light font-bold underline">Profile</router-link>
                    </td>
                </tr>
                <tr v-if="loaded && defaulters.length === 0">
                    <td colspan="7" class="px-6 py-8 text-center text-gray-500 text-sm">No defaulters for {{ term }}. 🎉</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Printable arrears invoices — off-screen; only rendered into the
         isolated print frame via printElement(), never shown on screen.
         `hidden` sits on the outer wrapper, not the node passed to
         printElement() — that node's own outerHTML gets cloned verbatim
         into the print frame, and a `hidden` (display:none) class on it
         would print a blank page. -->
    <div class="hidden">
      <div ref="invoiceRoot">
        <div v-for="d in invoiceTargets" :key="d.student_id" class="arrears-card p-8">
            <div class="text-center border-b-2 border-navy pb-4 mb-6">
                <div class="flex justify-center mb-2">
                    <SchoolBadge :size="80" />
                </div>
                <h2 class="text-2xl font-extrabold text-navy">THE BONA SCHOOL</h2>
                <p class="text-xs font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
                <p class="text-sm uppercase tracking-widest text-red-accent font-bold mt-1">Fee Arrears Invoice</p>
            </div>

            <div class="flex justify-between text-sm mb-6">
                <div>
                    <p class="text-gray-500">Student</p>
                    <p class="font-bold text-navy text-lg">{{ d.student_name }}</p>
                    <p class="text-gray-500">{{ d.admission_number }} · {{ d.grade_level }}</p>
                </div>
                <div class="text-right">
                    <p class="text-gray-500">Date Issued</p>
                    <p class="font-semibold text-gray-900">{{ today() }}</p>
                    <p class="text-gray-500 mt-1">As at</p>
                    <p class="font-semibold text-gray-900">{{ term }} {{ academicYear }}</p>
                </div>
            </div>

            <table class="min-w-full divide-y divide-gray-200 mb-4">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Term</th>
                        <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                        <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                        <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Arrears</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="row in d.term_breakdown" :key="row.term">
                        <td class="px-4 py-2 text-sm font-medium text-navy">{{ row.term }}</td>
                        <td class="px-4 py-2 text-sm text-right text-gray-500">{{ money(row.expected + (row.carry_forward || 0)) }}</td>
                        <td class="px-4 py-2 text-sm text-right text-gray-500">{{ money(row.paid) }}</td>
                        <td class="px-4 py-2 text-sm text-right font-bold text-red-accent">{{ money(row.outstanding) }}</td>
                    </tr>
                    <tr v-if="!d.term_breakdown || d.term_breakdown.length === 0">
                        <td colspan="4" class="px-4 py-3 text-center text-gray-500 text-sm">{{ money(d.outstanding_balance) }} outstanding for {{ term }}.</td>
                    </tr>
                </tbody>
            </table>

            <div class="flex justify-between items-center border-t-2 border-b-2 border-navy py-3 mb-6">
                <span class="font-bold text-navy uppercase text-sm">Total Arrears</span>
                <span class="text-2xl font-extrabold text-red-accent">{{ money(d.total_arrears ?? d.outstanding_balance) }}</span>
            </div>

            <p class="text-sm text-gray-600 leading-relaxed">
                Dear Parent/Guardian, the above balance remains outstanding on {{ d.student_name }}'s school fees
                account. Kindly clear this arrears at your earliest convenience. For any queries, please contact
                the school's finance office.
            </p>
            <p class="text-xs text-gray-400 mt-6 border-t pt-3">This is a computer-generated invoice — The Bona School Finance Office.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* One card per printed page, except the very last (avoid a trailing blank page). */
.arrears-card:not(:last-child) {
    page-break-after: always;
}
</style>
