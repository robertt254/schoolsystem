<script setup>
const props = defineProps({
    // { receipt_number, student_name, admission_number, grade_level, amount,
    //   payment_type, term, payment_date, recorded_by, allocation? }
    payment: { type: Object, required: true }
});
const emit = defineEmits(['close']);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;
const dateFmt = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : '—';
const printReceipt = () => window.print();
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
            <h2 class="text-2xl font-extrabold text-navy">BONA SCHOOL KENYA</h2>
            <p class="text-xs uppercase tracking-widest text-gray-500">Official Fee Receipt</p>
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
