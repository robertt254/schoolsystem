import { defineStore } from 'pinia';
import api from '../api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user_info') || 'null'),
    token: localStorage.getItem('token') || null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    isAdmin: (state) => ['admin', 'principal'].includes(state.user?.role),
    isTeacher: (state) => ['teacher', 'senior_teacher'].includes(state.user?.role),
    isFinance: (state) => state.user?.role === 'accountant',
    isSecretary: (state) => state.user?.role === 'secretary',
    // Composite permissions mirroring backend role checks
    canFinance: (state) => ['admin', 'principal', 'accountant'].includes(state.user?.role),
    canComms: (state) => ['admin', 'principal', 'secretary'].includes(state.user?.role),
    canManageStudents: (state) => ['admin', 'principal', 'secretary'].includes(state.user?.role),
    isSystemAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    async login(username, password) {
      try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await api.login(formData);
        this.token = response.data.access_token;
        // The backend embeds { name, role } in the login response; keep the
        // typed username too for the sidebar greeting.
        this.user = { username, ...response.data.user_info };
        localStorage.setItem('token', this.token);
        localStorage.setItem('user_info', JSON.stringify(this.user));
        return { ok: true };
      } catch (error) {
        console.error('Login failed', error);
        // Surface the real cause — a blanket "invalid credentials" hides
        // rate-limiting (429), revoked portal access (403) and outages.
        let message = 'Invalid username or password';
        if (error.response?.status === 429) {
          message = 'Too many attempts — wait a minute and try again.';
        } else if (error.response?.data?.detail) {
          message = error.response.data.detail;
        } else if (!error.response) {
          message = 'Cannot reach the server — check the connection.';
        }
        return { ok: false, message };
      }
    },
    async fetchUser() {
      // User info is delivered with the login response and cached locally —
      // there is no separate /me endpoint in this API.
      if (!this.token) return;
      if (!this.user) {
        const cached = localStorage.getItem('user_info');
        if (cached) {
          this.user = JSON.parse(cached);
        } else {
          this.logout();
        }
      }
    },
    logout(reason) {
      this.user = null;
      this.token = null;
      localStorage.removeItem('token');
      localStorage.removeItem('user_info');
      // Shown once on the login page (e.g. "signed out due to inactivity").
      // Guard against DOM event objects when used directly as a click handler.
      if (typeof reason === 'string' && reason) {
        sessionStorage.setItem('logout_reason', reason);
      }
    }
  }
});
