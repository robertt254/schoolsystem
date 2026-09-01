<script setup>
import { ref, computed } from 'vue';
import SchoolBadge from './SchoolBadge.vue';
import { printElement } from '../utils/printFrame';

const props = defineProps({
    // { student: {first_name,last_name,admission_number,grade_level}, date,
    //   term, lines: [{label, amount, receipt_number}], balance,
    //   balanceBreakdown: [{label, outstanding}], totalArrears }
    data: { type: Object, required: true },
});
const emit = defineEmits(['close']);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : '—';
const total = computed(() => props.data.lines.reduce((s, l) => s + l.amount, 0));
// One receipt number covers the whole itemized slip — the first line's.
const receiptNumber = computed(() => props.data.lines[0]?.receipt_number || '—');

const receiptRoot = ref(null);
const printReceipt = () => printElement(receiptRoot.value, `Receipt ${receiptNumber.value}`);
</script>

<template>
  <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
    <div ref="receiptRoot" class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-8 print-area">
        <div class="flex justify-between items-center mb-4 no-print">
            <button @click="printReceipt" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Print Receipt</button>
            <button @click="emit('close')" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
        </div>

        <div class="text-center border-b-2 border-navy pb-4 mb-4">
            <div class="flex justify-center mb-2">
                <SchoolBadge :size="72" />
            </div>
            <h2 class="text-2xl font-extrabold text-navy">THE BONA SCHOOL</h2>
            <p class="text-xs font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
            <p class="text-xs uppercase tracking-widest text-gray-500 mt-1">School Fees Receipt</p>
        </div>

        <div class="flex justify-between text-sm mb-4">
            <div>
                <p class="text-gray-500">Receipt No.</p>
                <p class="font-bold text-navy">{{ receiptNumber }}</p>
            </div>
            <div class="text-right">
                <p class="text-gray-500">Date</p>
                <p class="font-semibold text-gray-900">{{ dateFmt(data.date) }}</p>
            </div>
        </div>

        <div class="bg-gray-bg rounded-md p-4 mb-4 text-sm space-y-1">
            <p><span class="text-gray-500">Pupil's Name:</span> <span class="font-semibold text-gray-900">{{ data.student?.first_name }} {{ data.student?.last_name }}</span></p>
            <p><span class="text-gray-500">Admission No.:</span> <span class="font-semibold text-gray-900">{{ data.student?.admission_number }}</span></p>
            <p><span class="text-gray-500">Grade:</span> <span class="font-semibold text-gray-900">{{ data.student?.grade_level }}</span></p>
        </div>

        <div class="mb-4 text-sm">
            <p class="text-gray-500 font-semibold uppercase text-xs tracking-wide mb-1 border-b pb-1">Being Payment Of</p>
            <div v-for="(l, i) in data.lines" :key="i" class="flex justify-between py-0.5">
                <span class="text-gray-700">{{ l.label }}</span>
                <span class="font-semibold text-gray-900">{{ money(l.amount) }}</span>
            </div>
        </div>

        <div class="flex justify-between items-center border-t-2 border-b-2 border-navy py-3 mb-4">
            <span class="font-bold text-navy uppercase text-sm">Total Paid</span>
            <span class="text-2xl font-extrabold text-navy">{{ money(total) }}</span>
        </div>

        <div v-if="data.balanceBreakdown && data.balanceBreakdown.length" class="bg-gray-bg rounded-md p-3 mb-4 text-sm">
            <p class="text-gray-500 font-semibold uppercase text-xs tracking-wide mb-1.5">Outstanding Arrears — {{ data.term }}</p>
            <div v-for="(b, i) in data.balanceBreakdown" :key="i" class="flex justify-between py-0.5">
                <span class="text-gray-700">{{ b.label }}</span>
                <span class="font-semibold text-red-accent">{{ money(b.outstanding) }}</span>
            </div>
            <div class="flex justify-between items-center border-t border-navy mt-1.5 pt-1.5">
                <span class="font-bold text-navy text-xs uppercase">Total Arrears</span>
                <span class="font-extrabold text-red-accent">{{ money(data.totalArrears) }}</span>
            </div>
        </div>
        <div v-else-if="data.balance !== null && data.balance !== undefined" class="flex justify-between items-center bg-gray-bg rounded-md p-3 mb-4 text-sm">
            <span class="text-gray-600">Balance — {{ data.term }}</span>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-green-100 text-green-800">Fully settled</span>
        </div>

        <div class="text-xs text-gray-500 border-t pt-3 flex justify-between">
            <span>thebonaschool@gmail.com · +254 713 260 806</span>
            <span>Thank you</span>
        </div>
    </div>
  </div>
</template>
