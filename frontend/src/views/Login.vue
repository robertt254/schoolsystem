<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
import SchoolBadge from '../components/SchoolBadge.vue';
import PasswordInput from '../components/PasswordInput.vue';

const authStore = useAuthStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const error = ref('');

// One-time notice explaining why the user was signed out (idle / expired)
const notice = ref(sessionStorage.getItem('logout_reason') || '');
sessionStorage.removeItem('logout_reason');

const handleLogin = async () => {
    error.value = '';
    const success = await authStore.login(username.value, password.value);
    if (success) {
        router.push('/');
    } else {
        error.value = 'Invalid username or password';
    }
};
</script>

<template>
  <div class="min-h-screen bg-gray-bg flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-xl shadow-lg border border-gray-200">
      <div>
        <div class="flex justify-center">
          <SchoolBadge :size="110" />
        </div>
        <h2 class="mt-4 text-center text-3xl font-extrabold text-navy">
          THE BONA SCHOOL
        </h2>
        <p class="mt-1 text-center text-xs font-semibold uppercase tracking-widest text-red-accent">
          In Truth We Excel
        </p>
        <p class="mt-3 text-center text-sm text-gray-600">
          School Management System — sign in to your account
        </p>
      </div>
      <div v-if="notice" class="rounded-md bg-yellow-100 border border-yellow-200 px-4 py-3 text-sm text-yellow-800 text-center">
        {{ notice }}
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="username" class="sr-only">Username</label>
            <input id="username" name="username" type="text" required v-model="username" class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-navy focus:border-navy focus:z-10 sm:text-sm" placeholder="Username">
          </div>
          <div>
            <label for="password" class="sr-only">Password</label>
            <PasswordInput v-model="password" required placeholder="Password"
                input-class="appearance-none rounded-none relative block w-full px-3 py-2 pr-14 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-navy focus:border-navy focus:z-10 sm:text-sm" />
          </div>
        </div>

        <div v-if="error" class="text-red-accent text-sm text-center font-medium">
            {{ error }}
        </div>

        <div>
          <button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-navy hover:bg-navy-light focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-navy transition-colors">
            Sign in
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
