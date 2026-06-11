/* ============================================================
   La Porra del Bar — App JS
   ============================================================ */

const AUTH_API = '/auth';

/* ── Token helpers ─────────────────────────────────────────── */
function getToken()        { return localStorage.getItem('token'); }
function setToken(t)       { localStorage.setItem('token', t); }
function getUser()         { try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; } }
function setUser(u)        { localStorage.setItem('user', JSON.stringify(u)); }
function clearSession()    { localStorage.removeItem('token'); localStorage.removeItem('user'); }

/* ── Fetch wrapper ─────────────────────────────────────────── */
async function api(url, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    const isFormData = options.body instanceof FormData;
    if (!isFormData && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) { clearSession(); window.location.href = '/login'; return null; }
    return res;
}

/* ── Auth functions ────────────────────────────────────────── */
async function login(name, password) {
    const res = await api(AUTH_API + '/login', {
        method: 'POST',
        body: JSON.stringify({ name, password })
    });
    if (!res || !res.ok) {
        const e = await res.json();
        throw new Error(e.detail || 'Error al iniciar sesión');
    }
    const data = await res.json();
    setToken(data.token);
    setUser(data.user);
    window.location.href = '/dashboard';
}

async function register(name, password) {
    const res = await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, password })
    });
    if (!res || !res.ok) {
        const e = await res.json();
        throw new Error(e.detail || 'Error al registrarse');
    }
    await login(name, password);
}

function logout() {
    clearSession();
    window.location.href = '/';
}

/* ── Auth check ────────────────────────────────────────────── */
function checkAuth() {
    const token = getToken();
    const publicPaths = ['/', '/login', '/register'];
    const isPublic = publicPaths.includes(location.pathname);
    if (!token && !isPublic) {
        window.location.href = '/login';
        return false;
    }
    if (token && isPublic && location.pathname !== '/') {
        // redirect authenticated users away from login/register
        window.location.href = '/dashboard';
        return false;
    }
    if (token) {
        loadAndRenderUserNav();
    }
    return !!token;
}

/* ── Load user info ────────────────────────────────────────── */
async function loadAndRenderUserNav() {
    try {
        const res = await api(AUTH_API + '/me');
        if (!res || !res.ok) return;
        const data = await res.json();
        setUser(data);
        renderUserNav(data);
    } catch (e) {
        const cached = getUser();
        if (cached && cached.name) renderUserNav(cached);
    }
}

function renderUserNav(user) {
    // Update any nav avatar/name elements
    document.querySelectorAll('[data-user-name]').forEach(el => { el.textContent = user.name; });
    document.querySelectorAll('[data-user-avatar]').forEach(el => {
        if (user.img) { el.src = user.img; el.classList.remove('hidden'); }
    });
    document.querySelectorAll('[data-user-initial]').forEach(el => {
        el.textContent = (user.name || '?')[0].toUpperCase();
    });
}

/* ── Toast notifications ───────────────────────────────────── */
function showToast(message, type = 'success', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'all .3s';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ── Active nav ────────────────────────────────────────────── */
function setActiveNav() {
    const path = location.pathname;
    document.querySelectorAll('.bottom-nav__item').forEach(item => {
        const href = item.getAttribute('href');
        const isActive = href && (path === href || (href !== '/' && path.startsWith(href)));
        item.classList.toggle('active', isActive);
    });
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setActiveNav();
});
