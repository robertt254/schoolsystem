import { defineStore } from 'pinia';
import api from '../api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: localStorage.getItem('token') || null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
    isTeacher: (state) => state.user?.role === 'teacher',
    isFinance: (state) => state.user?.role === 'finance_officer',
  },
  actions: {
    async login(username, password) {
      try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await api.login(formData);
        this.token = response.data.access_token;
        localStorage.setItem('token', this.token);

        await this.fetchUser();
        return true;
      } catch (error) {
        console.error('Login failed', error);
        return false;
      }
    },
    async fetchUser() {
      if (!this.token) return;
      try {
        const response = await api.getMe(this.token);
        this.user = response.data;
      } catch (error) {
        console.error('Fetch user failed', error);
        this.logout();
      }
    },
    logout() {
      this.user = null;
      this.token = null;
      localStorage.removeItem('token');
    }
  }
});
