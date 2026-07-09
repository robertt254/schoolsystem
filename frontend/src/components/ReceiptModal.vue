<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import SchoolBadge from './SchoolBadge.vue';

const props = defineProps({
    // { receipt_number, student_id, student_name, admission_number, grade_level,
    //   amount, payment_type, term, payment_date, recorded_by, allocation? }
    payment: { type: Object, required: true }
});
const emit = defineEmits(['close']);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : '—';
const printReceipt = () => window.print();

// Remaining balance for the school's current term, fetched live so the
// receipt always reflects the position after this payment.
const balance = ref(null);
onMounted(async () => {
    if (!props.payment.student_id) return;
    try {
        const termRes = await api.getCurrentTerm();
        const res = await api.getStudentFeeBalance(props.payment.student_id, termRes.data.term);
        balance.value = res.data;
    } catch (e) {
        console.error('Could not load current-term balance for receipt', e);
    }
});
</script>

<template>
  <div class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
    <div class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-8 print-area">
        <div class="flex justify-between items-center mb-4 no-print">
            <button @click="printReceipt" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light text-sm">Print Receipt</button>
            <button @click="emit('close')" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
        </div>

        <!-- Branded receipt -->
        <div class="text-center border-b-2 border-navy pb-4 mb-4">
            <div class="flex justify-center mb-2">
                <SchoolBadge :size="72" />
            </div>
            <h2 class="text-2xl font-extrabold text-navy">THE BONA SCHOOL</h2>
            <p class="text-xs font-semibold uppercase tracking-widest text-gray-500">In Truth We Excel</p>
            <p class="text-xs uppercase tracking-widest text-gray-500 mt-1">Official Fee Receipt</p>
        </div>

        <div class="flex justify-between text-sm mb-4">
            <div>
                <p class="text-gray-500">Receipt No.</p>
                <p class="font-bold text-navy">{{ payment.receipt_number || '—' }}</p>
            </div>
            <div class="text-right">
                <p class="text-gray-500">Date</p>
                <p class="font-semibold text-gray-900">{{ dateFmt(payment.payment_date) }}</p>
            </div>
        </div>

        <div class="bg-gray-bg rounded-md p-4 mb-4 text-sm space-y-1">
            <p><span class="text-gray-500">Received from:</span> <span class="font-semibold text-gray-900">{{ payment.student_name }}</span></p>
            <p><span class="text-gray-500">Admission No.:</span> <span class="font-semibold text-gray-900">{{ payment.admission_number }}</span></p>
            <p v-if="payment.grade_level"><span class="text-gray-500">Class:</span> <span class="font-semibold text-gray-900">{{ payment.grade_level }}</span></p>
            <p><span class="text-gray-500">Payment for:</span> <span class="font-semibold text-gray-900">{{ payment.payment_type }} · {{ payment.term }}</span></p>
        </div>

        <div class="flex justify-between items-center border-t-2 border-b-2 border-navy py-3 mb-4">
            <span class="font-bold text-navy uppercase text-sm">Amount Paid</span>
            <span class="text-2xl font-extrabold text-navy">{{ money(payment.amount) }}</span>
        </div>

        <div v-if="balance" class="flex justify-between items-center bg-gray-bg rounded-md p-3 mb-4 text-sm">
            <span class="text-gray-600">Remaining balance — {{ balance.term_checked }}</span>
            <span v-if="balance.outstanding_balance > 0" class="font-bold text-red-accent">{{ money(balance.outstanding_balance) }}</span>
            <span v-else class="px-2 py-0.5 text-xs font-semibold rounded-full bg-green-100 text-green-800">Fully settled</span>
        </div>

        <div v-if="payment.allocation && payment.allocation.length" class="mb-4 text-sm">
            <p class="text-gray-500 mb-1">Applied as:</p>
            <div class="space-y-1">
                <div v-for="(a, i) in payment.allocation" :key="i" class="flex justify-between">
                    <span class="text-gray-700">{{ a.term }} <span class="text-xs text-gray-400">({{ a.kind }})</span></span>
                    <span class="font-semibold text-gray-900">{{ money(a.amount) }}</span>
                </div>
            </div>
        </div>

        <div class="text-xs text-gray-500 border-t pt-3 flex justify-between">
            <span>Served by: {{ payment.recorded_by }}</span>
            <span>Thank you</span>
        </div>
    </div>
  </div>
</template>
