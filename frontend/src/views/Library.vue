<script setup>
import { ref, onMounted } from 'vue';
import api from '../api';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const books = ref([]);
const borrows = ref([]);
const students = ref([]);
const staff = ref([]);
const search = ref('');
const activeOnly = ref(true);
const message = ref('');

const newBook = ref({ title: '', author: '', isbn: '', category: '', quantity: 1 });
const newBorrow = ref({ book_id: '', borrower_type: 'student', borrower_id: '', due_date: '' });

const money = (v) => `KES ${Number(v || 0).toLocaleString()}`;

const loadBooks = async () => {
    try {
        const res = await api.getBooks(search.value ? { search: search.value } : {});
        books.value = res.data;
    } catch (e) { console.error(e); }
};

const loadBorrows = async () => {
    try {
        const res = await api.getBorrows(activeOnly.value);
        borrows.value = res.data;
    } catch (e) { console.error(e); }
};

const loadPeople = async () => {
    try {
        const res = await api.getStudents();
        students.value = res.data;
    } catch (e) { console.error(e); }
    try {
        const res = await api.getStaff();
        staff.value = res.data;
    } catch (e) { /* non-admins may not see staff */ }
};

const addBook = async () => {
    const f = newBook.value;
    if (!f.title) return;
    message.value = '';
    try {
        await api.addBook({
            title: f.title,
            author: f.author || null,
            isbn: f.isbn || null,
            category: f.category || null,
            quantity: parseInt(f.quantity) || 1
        });
        newBook.value = { title: '', author: '', isbn: '', category: '', quantity: 1 };
        loadBooks();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to add book.';
    }
};

const issueBook = async () => {
    const f = newBorrow.value;
    if (!f.book_id || !f.borrower_id || !f.due_date) return;
    message.value = '';
    const pool = f.borrower_type === 'student' ? students.value : staff.value;
    const person = pool.find(p => p.id === parseInt(f.borrower_id));
    const name = f.borrower_type === 'student'
        ? `${person?.first_name || ''} ${person?.last_name || ''}`.trim()
        : person?.name || '';
    try {
        await api.createBorrow({
            book_id: parseInt(f.book_id),
            borrower_type: f.borrower_type,
            borrower_id: parseInt(f.borrower_id),
            borrower_name: name || 'Unknown',
            due_date: f.due_date
        });
        newBorrow.value = { book_id: '', borrower_type: 'student', borrower_id: '', due_date: '' };
        loadBooks();
        loadBorrows();
    } catch (e) {
        message.value = e.response?.data?.detail || 'Failed to issue book.';
    }
};

const doReturn = async (borrow) => {
    try {
        const res = await api.returnBook(borrow.id);
        if (res.data.fine_amount > 0) {
            window.alert(`Book returned late — fine of ${money(res.data.fine_amount)} applies.`);
        }
        loadBooks();
        loadBorrows();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to return book.');
    }
};

const removeBook = async (book) => {
    if (!window.confirm(`Delete "${book.title}" from the catalogue?`)) return;
    try {
        await api.deleteBook(book.id);
        loadBooks();
    } catch (e) {
        window.alert(e.response?.data?.detail || 'Failed to delete book.');
    }
};

onMounted(() => {
    loadBooks();
    loadBorrows();
    loadPeople();
});
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto space-y-8">
    <div class="flex justify-between items-center">
        <h1 class="text-3xl font-bold text-navy">Library</h1>
        <div class="flex gap-4">
            <input v-model="search" @keyup.enter="loadBooks" type="text" placeholder="Search title, author, ISBN…" class="border border-gray-300 p-2 rounded-md w-64 focus:ring-navy focus:border-navy" />
            <button @click="loadBooks" class="bg-navy text-white px-4 py-2 rounded-md hover:bg-navy-light">Search</button>
        </div>
    </div>
    <p v-if="message" class="text-sm font-medium text-red-accent">{{ message }}</p>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Add book — admin/principal/secretary manage the catalogue -->
        <div v-if="authStore.canComms" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Add Book</h2>
            <form @submit.prevent="addBook" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Title</label>
                        <input v-model="newBook.title" type="text" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Author</label>
                        <input v-model="newBook.author" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">ISBN</label>
                        <input v-model="newBook.isbn" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Category</label>
                        <input v-model="newBook.category" type="text" placeholder="e.g. Storybook" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                </div>
                <div class="flex items-end gap-4">
                    <div class="w-32">
                        <label class="block text-sm font-medium text-gray-700">Copies</label>
                        <input v-model="newBook.quantity" type="number" min="1" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                    </div>
                    <button type="submit" class="bg-navy text-white px-6 py-2 rounded-md hover:bg-navy-light">Add to Catalogue</button>
                </div>
            </form>
        </div>

        <!-- Issue book -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 class="text-xl font-bold text-navy mb-4 border-b pb-2">Issue Book</h2>
            <form @submit.prevent="issueBook" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Book</label>
                    <select v-model="newBorrow.book_id" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                        <option value="">Select book</option>
                        <option v-for="b in books.filter(b => b.available > 0)" :key="b.id" :value="b.id">{{ b.title }} ({{ b.available }} available)</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Borrower Type</label>
                        <select v-model="newBorrow.borrower_type" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option value="student">Student</option>
                            <option value="staff">Staff</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Borrower</label>
                        <select v-model="newBorrow.borrower_id" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white focus:ring-navy focus:border-navy sm:text-sm">
                            <option value="">Select borrower</option>
                            <option v-if="newBorrow.borrower_type === 'student'" v-for="s in students" :key="'s' + s.id" :value="s.id">{{ s.first_name }} {{ s.last_name }} ({{ s.grade_level }})</option>
                            <option v-if="newBorrow.borrower_type === 'staff'" v-for="s in staff" :key="'t' + s.id" :value="s.id">{{ s.name }}</option>
                        </select>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Due Date</label>
                    <input v-model="newBorrow.due_date" type="date" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-navy focus:border-navy sm:text-sm" />
                </div>
                <button type="submit" class="w-full py-2 px-4 rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700">Issue Book</button>
            </form>
        </div>
    </div>

    <!-- Catalogue -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <h2 class="text-xl font-bold text-navy p-6 pb-3">Catalogue</h2>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Author</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Available</th>
                    <th v-if="authStore.isAdmin" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="b in books" :key="b.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ b.title }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ b.author || '—' }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ b.category || '—' }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="b.available > 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
                            {{ b.available }} / {{ b.quantity }}
                        </span>
                    </td>
                    <td v-if="authStore.isAdmin" class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button @click="removeBook(b)" class="text-red-accent hover:text-red-hover font-bold underline">Delete</button>
                    </td>
                </tr>
                <tr v-if="books.length === 0">
                    <td :colspan="authStore.isAdmin ? 5 : 4" class="px-6 py-8 text-center text-gray-500 text-sm">No books in the catalogue.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Borrows -->
    <div class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex justify-between items-center p-6 pb-3">
            <h2 class="text-xl font-bold text-navy">Borrowed Books</h2>
            <label class="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" v-model="activeOnly" @change="loadBorrows" class="h-4 w-4 rounded border-gray-300 text-navy focus:ring-navy" />
                Active only
            </label>
        </div>
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Book</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Borrower</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Due</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Fine</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="b in borrows" :key="b.id" class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy">{{ b.book_title }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ b.borrower_name }} <span class="text-xs text-gray-400">({{ b.borrower_type }})</span></td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ b.due_date }}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold" :class="b.fine_amount > 0 ? 'text-red-accent' : 'text-gray-500'">{{ money(b.fine_amount) }}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full"
                              :class="b.return_date ? 'bg-green-100 text-green-800' : b.is_overdue ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'">
                            {{ b.return_date ? 'Returned' : b.is_overdue ? 'Overdue' : 'Out' }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button v-if="!b.return_date" @click="doReturn(b)" class="text-navy hover:text-navy-light font-bold underline">Return</button>
                    </td>
                </tr>
                <tr v-if="borrows.length === 0">
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500 text-sm">No borrow records.</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
