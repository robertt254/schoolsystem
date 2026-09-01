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
    const header = 'Admission No,Student,Grade,Tuition Arrears,Activity/Transport Arrears,Total Outstanding,Breakdown\n';
    const body = defaulters.value.map(d => {
        const breakdown = (d.activity_breakdown || [])
            .map(a => `${a.activity_name}: ${a.outstanding}`).join('; ');
        return `${d.admission_number},"${d.student_name}",${d.grade_level},${d.tuition_arrears ?? d.outstanding_balance},${d.activity_arrears ?? 0},${d.outstanding_balance},"${breakdown}"`;
    }).join('\n');
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
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Owing On</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total Outstanding</th>
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
                    <td class="px-6 py-4 text-sm">
                        <div class="flex flex-wrap gap-1 max-w-xs">
                            <span v-if="(d.tuition_arrears ?? 0) > 0" class="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-accent whitespace-nowrap">
                                Tuition: {{ money(d.tuition_arrears) }}
                            </span>
                            <span v-for="a in d.activity_breakdown" :key="a.activity_name"
                                  class="px-2 py-0.5 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 whitespace-nowrap">
                                {{ a.activity_name }}: {{ money(a.outstanding) }}
                            </span>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-red-accent">{{ money(d.outstanding_balance) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                        <button @click="printInvoice(d)" class="text-navy hover:text-navy-light font-bold underline">Invoice</button>
                        <router-link :to="`/students/${d.student_id}`" class="text-navy hover:text-navy-light font-bold underline">Profile</router-link>
                    </td>
                </tr>
                <tr v-if="loaded && defaulters.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No defaulters for {{ term }}. 🎉</td>
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
        <div v-for="d in invoiceTargets" :key="d.student_id" class="arrears-card p-5 text-sm">
            <div class="text-center border-b-2 border-navy pb-2 mb-3">
                <div class="flex justify-center mb-1">
                    <SchoolBadge :size="48" />
                </div>
                <h2 class="text-lg font-extrabold text-navy leading-tight">THE BONA SCHOOL</h2>
                <p class="text-[10px] font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
                <p class="text-xs uppercase tracking-widest text-red-accent font-bold mt-0.5">Fee Arrears Invoice</p>
            </div>

            <div class="flex justify-between text-xs mb-3">
                <div>
                    <p class="text-gray-500">Student</p>
                    <p class="font-bold text-navy text-sm">{{ d.student_name }}</p>
                    <p class="text-gray-500">{{ d.admission_number }} · {{ d.grade_level }}</p>
                </div>
                <div class="text-right">
                    <p class="text-gray-500">Date Issued</p>
                    <p class="font-semibold text-gray-900">{{ today() }}</p>
                    <p class="text-gray-500 mt-0.5">As at</p>
                    <p class="font-semibold text-gray-900">{{ term }} {{ academicYear }}</p>
                </div>
            </div>

            <p v-if="d.term_breakdown && d.term_breakdown.length" class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Tuition</p>
            <table v-if="d.term_breakdown && d.term_breakdown.length" class="min-w-full divide-y divide-gray-200 mb-2 text-xs">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-2 py-1 text-left font-medium text-gray-500 uppercase tracking-wider">Term</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Arrears</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="row in d.term_breakdown" :key="row.term">
                        <td class="px-2 py-1 font-medium text-navy">{{ row.term }}</td>
                        <td class="px-2 py-1 text-right text-gray-500">{{ money(row.expected + (row.carry_forward || 0)) }}</td>
                        <td class="px-2 py-1 text-right text-gray-500">{{ money(row.paid) }}</td>
                        <td class="px-2 py-1 text-right font-bold text-red-accent">{{ money(row.outstanding) }}</td>
                    </tr>
                    <tr>
                        <td colspan="3" class="px-2 py-1 text-right font-semibold text-navy">Tuition subtotal</td>
                        <td class="px-2 py-1 text-right font-bold text-red-accent">{{ money(d.tuition_arrears) }}</td>
                    </tr>
                </tbody>
            </table>

            <p v-if="d.activity_breakdown && d.activity_breakdown.length" class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">Transport & Activities</p>
            <table v-if="d.activity_breakdown && d.activity_breakdown.length" class="min-w-full divide-y divide-gray-200 mb-2 text-xs">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-2 py-1 text-left font-medium text-gray-500 uppercase tracking-wider">Activity</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Expected</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Paid</th>
                        <th class="px-2 py-1 text-right font-medium text-gray-500 uppercase tracking-wider">Arrears</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="a in d.activity_breakdown" :key="a.activity_name">
                        <td class="px-2 py-1 font-medium text-navy">{{ a.activity_name }}</td>
                        <td class="px-2 py-1 text-right text-gray-500">{{ money(a.expected) }}</td>
                        <td class="px-2 py-1 text-right text-gray-500">{{ money(a.paid) }}</td>
                        <td class="px-2 py-1 text-right font-bold text-red-accent">{{ money(a.outstanding) }}</td>
                    </tr>
                    <tr>
                        <td colspan="3" class="px-2 py-1 text-right font-semibold text-navy">Transport/Activities subtotal</td>
                        <td class="px-2 py-1 text-right font-bold text-red-accent">{{ money(d.activity_arrears) }}</td>
                    </tr>
                </tbody>
            </table>

            <p v-if="(!d.term_breakdown || !d.term_breakdown.length) && (!d.activity_breakdown || !d.activity_breakdown.length)"
               class="text-xs text-gray-500 text-center py-2">{{ money(d.outstanding_balance) }} outstanding for {{ term }}.</p>

            <div class="flex justify-between items-center border-t-2 border-b-2 border-navy py-1.5 mb-3">
                <span class="font-bold text-navy uppercase text-xs">Grand Total Arrears</span>
                <span class="text-lg font-extrabold text-red-accent">{{ money(d.total_arrears ?? d.outstanding_balance) }}</span>
            </div>

            <p class="text-xs text-gray-600 leading-snug">
                Dear Parent/Guardian, the above balance remains outstanding on {{ d.student_name }}'s school fees
                account. Kindly clear this arrears at your earliest convenience. For any queries, please contact
                the school's finance office.
            </p>
            <p class="text-[10px] text-gray-400 mt-2 border-t pt-1.5">This is a computer-generated invoice — The Bona School Finance Office.</p>
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
