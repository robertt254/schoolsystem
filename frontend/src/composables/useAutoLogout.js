import { onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';

// Sign the user out automatically when they stop using the system, so an
// unattended screen cannot be used by someone else. Two triggers:
//   1. No mouse/keyboard/touch activity for IDLE_LIMIT_MINUTES
//   2. The JWT itself has expired (server would reject it anyway)
const IDLE_LIMIT_MINUTES = 15;
const CHECK_EVERY_MS = 30 * 1000;

const IDLE_MESSAGE = `You were signed out after ${IDLE_LIMIT_MINUTES} minutes of inactivity.`;
const EXPIRED_MESSAGE = 'Your session expired — please sign in again.';

function tokenExpired(token) {
    if (!token) return false;
    try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        return Boolean(payload.exp) && payload.exp * 1000 < Date.now();
    } catch {
        return false;
    }
}

export function useAutoLogout() {
    const authStore = useAuthStore();
    const router = useRouter();

    let lastActivity = Date.now();
    let timer = null;
    const bump = () => { lastActivity = Date.now(); };
    const events = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click'];

    const check = () => {
        if (!authStore.isAuthenticated) return;
        const idle = Date.now() - lastActivity > IDLE_LIMIT_MINUTES * 60 * 1000;
        const expired = tokenExpired(authStore.token);
        if (idle || expired) {
            authStore.logout(idle ? IDLE_MESSAGE : EXPIRED_MESSAGE);
            router.push('/login');
        }
    };

    onMounted(() => {
        events.forEach(e => window.addEventListener(e, bump, { passive: true }));
        timer = setInterval(check, CHECK_EVERY_MS);
    });
    onBeforeUnmount(() => {
        events.forEach(e => window.removeEventListener(e, bump));
        clearInterval(timer);
    });
}
