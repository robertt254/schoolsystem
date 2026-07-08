<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const staff = ref([]);
const message = ref('');

const PORTAL_ROLES = ['admin', 'principal', 'secretary', 'accountant', 'senior_teacher'];
const ROLES = [
    { value: 'teacher', label: 'Teacher' },
    { value: 'senior_teacher', label: 'Senior Teacher' },
    { value: 'secretary', label: 'Secretary' },
    { value: 'accountant', label: 'Accountant' },
    { value: 'principal', label: 'Principal' },
    { value: 'support_staff', label: 'Support Staff' },
    { value: 'admin', label: 'System Admin' }
];
const roleLabel = (r) => (ROLES.find(x => x.value === r)?.label) || r;
const isPortal = (r) => PORTAL_ROLES.includes(r);

const blankForm = () => ({
    name: '', role: 'teacher', job_title: '', username: '', password: '',
    contract_type: '', date_of_hire: '', kra_pin: '', nssf_number: '', nhif_number: '',
    basic_salary: 0, allowances: 0, deductions: 0, accrued_leave_days: 21
});
const form = ref(blankForm());
const isModalOpen = ref(false);
const editingId = ref(null);

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;

const load = async () => {
    try {
        const res = await api.getStaff();
        staff.value = res.data;
    } catch (e) { console.error(e); }
};

const openCreate = () => {
    editingId.value = null;
    form.value = blankForm();
    isModalOpen.value = true;
};

const openEdit = (s) => {
    editingId.value = s.id;
    form.value = {
        name: s.name, role: s.role, job_title: s.job_title || '',
        username: s.username, password: '',
        contract_type: s.contract_type || '', date_of_hire: s.date_of_hire || '',
        kra_pin: s.kra_pin || '', nssf_number: s.nssf_number || '', nhif_number: s.nhif_number || '',
        basic_salary: s.basic_salary || 0, allowances: s.allowances || 0, deductions: s.deductions || 0,
        accrued_leave_days: s.accrued_leave_days ?? 21
    };
    isModalOpen.value = true;
};

const save = async () => {
    message.value = '';
    const f = form.value;
    try {
        if (editingId.value) {
            const payload = {
                name: f.name, role: f.role, job_title: f.job_title || null,
                contract_type: f.contract_type || null, date_of_hire: f.date_of_hire || null,
                kra_pin: f.kra_pin || null, nssf_number: f.nssf_number || null, nhif_number: f.nhif_number || null,
                basic_salary: parseFloat(f.basic_salary) || 0,
                allowances: parseFloat(f.allowances) || 0,
                deductions: parseFloat(f.deductions) || 0,
                accrued_leave_days: parseInt(f.accrued_leave_days) || 21
            };
            if (f.password) payload.password = f.password;
            if (f.username) payload.username = f.username;
            await api.updateStaff(editingId.value, payload);
        } else {
            // Non-portal staff get an auto-generated username server-side; the
            // schema still requires a placeholder value.
            const username = isPortal(f.role)
                ? f.username
                : `${f.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_${Date.now().toString(36)}`.slice(0, 50);
            await api.createStaff({
                username,
                name: f.name,
                role: f.role,
                ...(isPortal(f.role) ? { password: f.password } : {}),
                job_title: f.job_title || null,
                contract_type: f.contract_type || null,
                date_of_hire: f.date_of_hire || null,
                kra_pin: f.kra_pin || null,
                nssf_number: f.nssf_number || null,
                nhif_number: f.nhif_number || null,
                basic_salary: parseFloat(f.basic_salary) || 0,
                allowances: parseFloat(f.allowances) || 0,
                deductions: parseFloat(f.deductions) || 0,
                accrued_leave_days: parseInt(f.accrued_leave_days) || 21
            });
        }
        isModalOpen.value = false;
        load();
    } catch (e) {
        console.error(e);
        message.value = e.response?.data?.detail || 'Failed to save staff member.';
    }
};

const resetPassword = async (s) => {
    const pw = window.prompt(`New password for ${s.name} (min 8 characters):`);
    if (!pw) return;
    try {
        await api.resetStaffPassword(s.id, pw);
        window.alert(`Password for ${s.name} has been reset.`);
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to reset password.');
    }
};

const terminate = async (s) => {
    if (!window.confirm(`Terminate ${s.name}'s account? This removes the staff record.`)) return;
    try {
        await api.terminateStaff(s.id);
        load();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to terminate staff.');
    }
};

onMounted(load);
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto relative">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold text-navy">Staff & HR</h1>
        <button v-if="authStore.isAdmin" @click="openCreate" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Add Staff Member</button>
    </div>
    <p v-if="message" class="mb-4 text-sm font-medium text-red-accent">{{ message }}</p>

    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Job Title</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Portal</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Net Salary</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Leave Left</th>
            <th v-if="authStore.isAdmin" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="s in staff" :key="s.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap">
                <p class="text-sm font-medium text-gray-900">{{ s.name }}</p>
                <p class="text-xs text-gray-500">@{{ s.username }}</p>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">{{ roleLabel(s.role) }}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ s.job_title || '—' }}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                      :class="s.can_login ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'">
                    {{ s.can_login ? 'Login' : 'No login' }}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">
                {{ money((s.basic_salary || 0) + (s.allowances || 0) - (s.deductions || 0)) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{{ s.leave_days_left }} / {{ s.accrued_leave_days }}</td>
            <td v-if="authStore.isAdmin" class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button @click="openEdit(s)" class="text-navy hover:text-navy-light mx-1 font-bold underline">Edit</button>
                <button v-if="s.can_login" @click="resetPassword(s)" class="text-navy hover:text-navy-light mx-1 font-bold underline">Reset PW</button>
                <button @click="terminate(s)" class="text-red-accent hover:text-red-hover mx-1 font-bold underline">Terminate</button>
            </td>
          </tr>
          <tr v-if="staff.length === 0">
            <td :colspan="authStore.isAdmin ? 7 : 6" class="px-6 py-8 text-center text-gray-500 text-sm">No staff found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Staff Modal -->
    <div v-if="isModalOpen" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
        <div class="relative w-full max-w-2xl bg-white rounded-xl shadow-lg p-8 my-8 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-2xl font-bold text-navy">{{ editingId ? 'Edit Staff Member' : 'Add Staff Member' }}</h3>
                <button @click="isModalOpen = false" class="text-gray-400 hover:text-gray-600 text-2xl font-bold">&times;</button>
            </div>
            <form @submit.prevent="save" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Full Name</label>
                        <input v-model="form.name" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Role</label>
                        <select v-model="form.role" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option v-for="r in ROLES" :key="r.value" :value="r.value">{{ r.label }}</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Job Title / Department</label>
                        <input v-model="form.job_title" type="text" placeholder="e.g. Mathematics" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Date of Hire</label>
                        <input v-model="form.date_of_hire" type="date" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>

                <div v-if="isPortal(form.role)" class="grid grid-cols-2 gap-4 border-t pt-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Username (portal login)</label>
                        <input v-model="form.username" type="text" :required="!editingId" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">{{ editingId ? 'New Password (optional)' : 'Password (min 8 chars)' }}</label>
                        <input v-model="form.password" type="password" :required="!editingId" minlength="8" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <p v-else class="text-xs text-gray-500 border-t pt-4">This role has no portal access — no login credentials are needed.</p>

                <div class="grid grid-cols-3 gap-4 border-t pt-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Basic Salary</label>
                        <input v-model="form.basic_salary" type="number" min="0" step="0.01" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Allowances</label>
                        <input v-model="form.allowances" type="number" min="0" step="0.01" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Deductions</label>
                        <input v-model="form.deductions" type="number" min="0" step="0.01" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>

                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 border-t pt-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Contract</label>
                        <input v-model="form.contract_type" type="text" placeholder="Permanent" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">KRA PIN</label>
                        <input v-model="form.kra_pin" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">NSSF No.</label>
                        <input v-model="form.nssf_number" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">NHIF No.</label>
                        <input v-model="form.nhif_number" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>

                <div class="flex justify-between items-center pt-4">
                    <div class="w-40">
                        <label class="block text-sm font-medium text-gray-700">Leave Days / Year</label>
                        <input v-model="form.accrued_leave_days" type="number" min="0" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <button type="submit" class="bg-red-accent text-white px-6 py-2 rounded-md hover:bg-red-hover">{{ editingId ? 'Save Changes' : 'Add Staff' }}</button>
                </div>
            </form>
        </div>
    </div>
  </div>
</template>
