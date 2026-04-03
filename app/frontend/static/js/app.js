/**
 * IA Juridica - JavaScript Principal v2.1
 * Modern UI utilities, toast notifications, accessibility
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    API_BASE_URL: '/api',
    TOKEN_KEY: 'ia_juridica_token',
    USER_KEY: 'ia_juridica_user',
    TOAST_DURATION: 5000,
    DATE_LOCALE: 'pt-BR'
};

// ============================================
// Authentication
// ============================================
const Auth = {
    getToken() {
        return localStorage.getItem(CONFIG.TOKEN_KEY);
    },
    setToken(token) {
        localStorage.setItem(CONFIG.TOKEN_KEY, token);
    },
    removeToken() {
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        localStorage.removeItem(CONFIG.USER_KEY);
    },
    getUser() {
        const user = localStorage.getItem(CONFIG.USER_KEY);
        return user ? JSON.parse(user) : null;
    },
    setUser(user) {
        localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
    },
    isAuthenticated() {
        return !!this.getToken();
    },
    async login(email, senha) {
        const response = await API.post('/auth/login', { email, senha });
        if (response.access_token) {
            this.setToken(response.access_token);
            this.setUser(response.user);
        }
        return response;
    },
    logout() {
        this.removeToken();
        window.location.href = '/login';
    },
    checkAuth() {
        if (!this.isAuthenticated() && !window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
    }
};

// ============================================
// API Client
// ============================================
const API = {
    async request(method, endpoint, data = null, options = {}) {
        const url = `${CONFIG.API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        const token = Auth.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = { method, headers };

        if (data && method !== 'GET') {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);

            if (response.status === 401) {
                Auth.logout();
                return null;
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
                throw new Error(error.detail || `Erro ${response.status}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return response;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },
    get(endpoint, options = {}) { return this.request('GET', endpoint, null, options); },
    post(endpoint, data, options = {}) { return this.request('POST', endpoint, data, options); },
    put(endpoint, data, options = {}) { return this.request('PUT', endpoint, data, options); },
    patch(endpoint, data, options = {}) { return this.request('PATCH', endpoint, data, options); },
    delete(endpoint, options = {}) { return this.request('DELETE', endpoint, null, options); },
    async upload(endpoint, formData, options = {}) {
        const url = `${CONFIG.API_BASE_URL}${endpoint}`;
        const headers = { ...options.headers };

        const token = Auth.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Erro no upload' }));
            throw new Error(error.detail);
        }

        return await response.json();
    }
};

// ============================================
// Toast Notification System (Bootstrap 5)
// ============================================
const Toast = {
    container: null,

    init() {
        this.container = document.querySelector('.toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
            this.container.style.zIndex = '1055';
            document.body.appendChild(this.container);
        }

        // Initialize existing toasts (server-side rendered)
        const toastElList = [].slice.call(document.querySelectorAll('.toast'));
        toastElList.map(function (toastEl) {
            return new bootstrap.Toast(toastEl, { delay: CONFIG.TOAST_DURATION });
        });
    },

    show(message, type = 'info', duration = CONFIG.TOAST_DURATION) {
        if (!this.container) this.init();

        const icons = {
            success: 'bi-check-circle-fill',
            danger: 'bi-exclamation-triangle-fill',
            warning: 'bi-exclamation-circle-fill',
            info: 'bi-info-circle-fill'
        };

        const bgClass = type === 'danger' ? 'danger' : 
                       type === 'success' ? 'success' : 
                       type === 'warning' ? 'warning' : 'primary';

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${bgClass} border-0 fade show`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${icons[type] || icons.info} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        this.container.appendChild(toastEl);
        
        const bsToast = new bootstrap.Toast(toastEl, { delay: duration });
        bsToast.show();

        // Clean up DOM after hidden
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });

        return bsToast;
    },

    success(message, duration) { return this.show(message, 'success', duration); },
    error(message, duration) { return this.show(message, 'danger', duration); },
    warning(message, duration) { return this.show(message, 'warning', duration); },
    info(message, duration) { return this.show(message, 'info', duration); }
};

// ============================================
// UI Utilities
// ============================================
const UI = {
    showAlert(message, type = 'info', duration = CONFIG.TOAST_DURATION) {
        return Toast.show(message, type, duration);
    },
    
    // Add loading state to buttons
    setLoading(btn, isLoading, loadingText = 'Carregando...') {
        if (isLoading) {
            btn.dataset.originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${loadingText}`;
        } else {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
        }
    }
};

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    Toast.init();
    
    // Global tooltip initialization
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
});
