const API = (() => {
  // Determine API base URL dynamically
  // If hosted on S3 and API is on EC2, user can configure or default to same origin
  const savedBase = localStorage.getItem('smart_med_api_url');
  let BASE_URL = savedBase || window.location.origin;
  if (!BASE_URL.endsWith('/api')) {
    BASE_URL = BASE_URL.replace(/\/$/, '') + '/api';
  }

  function getToken() {
    return localStorage.getItem('smart_med_token');
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem('smart_med_token', token);
    } else {
      localStorage.removeItem('smart_med_token');
    }
  }

  function getUser() {
    try {
      return JSON.parse(localStorage.getItem('smart_med_user'));
    } catch {
      return null;
    }
  }

  function setUser(user) {
    if (user) {
      localStorage.setItem('smart_med_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('smart_med_user');
    }
  }

  async function request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401 && !endpoint.includes('/login') && !endpoint.includes('/register')) {
          // Token expired or invalid
          setToken(null);
          setUser(null);
          window.dispatchEvent(new CustomEvent('auth:expired'));
        }
        const errorMsg = data.error || data.message || `Request failed with status ${response.status}`;
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  return {
    setBaseUrl: (url) => {
      let clean = url.trim().replace(/\/$/, '');
      if (!clean.endsWith('/api')) clean += '/api';
      BASE_URL = clean;
      localStorage.setItem('smart_med_api_url', clean);
    },
    getBaseUrl: () => BASE_URL,
    getToken,
    setToken,
    getUser,
    setUser,
    isAuthenticated: () => !!getToken(),

    // Auth
    register: (payload) => request('/register', { method: 'POST', body: JSON.stringify(payload) }),
    login: (payload) => request('/login', { method: 'POST', body: JSON.stringify(payload) }),
    getProfile: () => request('/profile'),
    updateProfile: (payload) => request('/profile', { method: 'PUT', body: JSON.stringify(payload) }),

    // Medicines
    getMedicines: () => request('/medicines'),
    getMedicine: (id) => request(`/medicines/${id}`),
    addMedicine: (payload) => request('/medicines', { method: 'POST', body: JSON.stringify(payload) }),
    updateMedicine: (id, payload) => request(`/medicines/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    deleteMedicine: (id) => request(`/medicines/${id}`, { method: 'DELETE' }),
    toggleMedicine: (id) => request(`/medicines/${id}/toggle`, { method: 'PATCH' }),

    // Doses
    getTodayDoses: () => request('/today'),
    markDoseTaken: (id) => request(`/doses/${id}/taken`, { method: 'PUT' }),
    markDoseMissed: (id) => request(`/doses/${id}/missed`, { method: 'PUT' }),

    // History & Stats
    getHistory: (filter = '7days') => request(`/history?filter=${filter}`),

    // Notifications & Tests
    getNotifications: () => request('/notifications'),
    testReminder: (message) => request('/notifications/test', { method: 'POST', body: JSON.stringify({ message }) }),
  };
})();
