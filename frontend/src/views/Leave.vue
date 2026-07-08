<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const requests = ref([]);
const filterStatus = ref('');
const message = ref('');
const newRequest = ref({
    leave_type: 'Annual',
    start_date: '',
    end_date: '',
    reason: ''
});
const leaveTypes = ['Annual', 'Sick', 'Maternity', 'Paternity', 'Compassionate', 'Study', 'Unpaid'];

const load = async () => {
    try {
        const res = await api.getLeaveRequests(filterStatus.value || undefined);
        requests.value = res.data;
    } catch (e) { console.error(e); }
};

const apply = async () => {
    const r = newRequest.value;
    if (!r.start_date || !r.end_date || !r.reason) return;
    message.value = '';
    try {
        await api.applyForLeave(r);
        newRequest.value = { leave_type: 'Annual', start_date: '', end_date: '', reason: '' };
        message.value = 'Leave request submitted.';
        load();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to submit request.';
    }
};

const review = async (req, action) => {
    try {
        await api.reviewLeaveRequest(req.id, action);
        load();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to review request.');
    }
};

const cancel = async (req) => {
    if (!window.confirm('Cancel this leave request?')) return;
    try {
        await api.cancelLeaveRequest(req.id);
        load();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to cancel request.');
    }
};

const days = (r) => Math.round((new Date(r.end_date) - new Date(r.start_date)) / 86400000) + 1;

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Leave Management</h1>
        <select v-model="filterStatus" @change="load" class="border border-gray-300 p-2 rounded-md bg-white focus:ring-navy focus:border-navy">
            <option value="">All Requests</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
        </select>
    </div>

    <!-- Apply -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Apply for Leave</h2>
        <form @submit.prevent="apply" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Leave Type</label>
                <select v-model="newRequest.leave_type" class="border border-gray-300 p-2 rounded-md w-full bg-white focus:ring-navy focus:border-navy">
                    <option v-for="t in leaveTypes" :key="t">{{ t }}</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">From</label>
                <input v-model="newRequest.start_date" type="date" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">To</label>
                <input v-model="newRequest.end_date" type="date" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <input v-model="newRequest.reason" type="text" required class="border border-gray-300 p-2 rounded-md w-full focus:ring-navy focus:border-navy" />
            </div>
            <div class="md:col-span-4">
                <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light w-full md:w-auto">Submit Request</button>
                <span v-if="message" class="ml-4 text-sm font-medium" :class="message.startsWith('Leave') ? 'text-green-600' : 'text-red-accent'">{{ message }}</span>
            </div>
        </form>
    </div>

    <!-- Requests -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Staff</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dates</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Days</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="r in requests" :key="r.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <p class="text-sm font-medium text-gray-900">{{ r.staff_name }}</p>
                        <p class="text-xs text-gray-500">{{ r.reason }}</p>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ r.leave_type }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ r.start_date }} → {{ r.end_date }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">{{ days(r) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="{ 'bg-yellow-100 text-yellow-800': r.status === 'pending', 'bg-green-100 text-green-800': r.status === 'approved', 'bg-red-100 text-red-800': r.status === 'rejected' }">
                            {{ r.status }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <template v-if="r.status === 'pending'">
                            <button v-if="authStore.isAdmin" @click="review(r, 'approve')" class="text-green-600 hover:text-green-700 mx-1 font-bold underline">Approve</button>
                            <button v-if="authStore.isAdmin" @click="review(r, 'reject')" class="text-red-accent hover:text-red-hover mx-1 font-bold underline">Reject</button>
                            <button @click="cancel(r)" class="text-gray-500 hover:text-gray-700 mx-1 font-bold underline">Cancel</button>
                        </template>
                    </td>
                </tr>
                <tr v-if="requests.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No leave requests.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
