// Smart Medicine Reminder Application Controller

const App = (() => {
  // Sound synthesizer for elderly-friendly auditory feedback (Web Audio API)
  function playChime(success = true) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      
      if (success) {
        // High pleasant ding
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      } else {
        // Warning chime
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(330, ctx.currentTime + 0.2);
      }
      
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
      console.warn("Audio not supported or blocked by user gesture:", e);
    }
  }

  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '🔔';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '⚠';

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Navigation and Views
  function navigateTo(viewId) {
    document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));

    const targetSection = document.getElementById(`view-${viewId}`);
    if (targetSection) {
      targetSection.classList.add('active');
    }

    const navLink = document.querySelector(`.nav-link[data-view="${viewId}"]`);
    if (navLink) navLink.classList.add('active');

    // Update UI according to auth status
    updateAuthUI();

    // Trigger view-specific data loads
    if (API.isAuthenticated()) {
      if (viewId === 'dashboard') loadDashboard();
      if (viewId === 'medicines') loadMedicines();
      if (viewId === 'history') loadHistory('7days');
      if (viewId === 'notifications') loadNotifications();
      if (viewId === 'profile') loadProfile();
    }
  }

  function updateAuthUI() {
    const isAuth = API.isAuthenticated();
    const user = API.getUser();

    document.querySelectorAll('.auth-only').forEach(el => el.style.display = isAuth ? '' : 'none');
    document.querySelectorAll('.guest-only').forEach(el => el.style.display = isAuth ? 'none' : '');

    if (isAuth && user) {
      const userGreeting = document.getElementById('user-display-name');
      if (userGreeting) userGreeting.textContent = user.name || user.email;
    }
  }

  // Live Clock
  function startLiveClock() {
    function tick() {
      const clockEl = document.getElementById('live-clock');
      if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
    }
    tick();
    setInterval(tick, 1000);
  }

  // Format 24-hr time to 12-hr format
  function formatTime(hhmm) {
    if (!hhmm) return '--:--';
    const [h, m] = hhmm.split(':').map(Number);
    const period = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    return `${String(h12).padStart(2, '0')}:${String(m).padStart(2, '0')} ${period}`;
  }

  // --------------------------------------------------------------------------
  // Dashboard Logic
  // --------------------------------------------------------------------------
  async function loadDashboard() {
    try {
      const user = API.getUser();
      const bannerName = document.getElementById('dashboard-user-name');
      if (bannerName && user) bannerName.textContent = user.name;

      const data = await API.getTodayDoses();
      const summary = data.summary || {};

      document.getElementById('stat-total-today').textContent = summary.total || 0;
      document.getElementById('stat-taken-today').textContent = summary.taken || 0;
      document.getElementById('stat-missed-today').textContent = summary.missed || 0;
      document.getElementById('stat-next-reminder').textContent = summary.next_reminder_time ? formatTime(summary.next_reminder_time) : 'None';

      renderTodayDoses(data.doses || []);
    } catch (err) {
      showToast(`Error loading dashboard: ${err.message}`, 'error');
    }
  }

  function renderTodayDoses(doses) {
    const listEl = document.getElementById('today-doses-list');
    const emptyEl = document.getElementById('today-empty-state');

    if (!listEl) return;

    if (!doses || doses.length === 0) {
      listEl.innerHTML = '';
      if (emptyEl) emptyEl.style.display = 'block';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    listEl.innerHTML = doses.map(dose => {
      const statusClass = `status-${dose.status}`;
      const statusLabel = dose.status.charAt(0).toUpperCase() + dose.status.slice(1);
      
      const isPending = dose.status === 'pending';
      const isTaken = dose.status === 'taken';

      return `
        <div class="dose-card">
          <div class="dose-time">⏰ ${formatTime(dose.scheduled_time)}</div>
          <div class="dose-info">
            <h3>${escapeHtml(dose.medicine_name)}</h3>
            <p><strong>Dose:</strong> ${escapeHtml(dose.dosage)} • <em>${escapeHtml(dose.instructions || 'As advised')}</em></p>
            ${dose.taken_time ? `<p style="font-size:0.9rem; color:#16a34a; margin-top:4px;">✓ Taken at: ${new Date(dose.taken_time).toLocaleTimeString()}</p>` : ''}
          </div>
          <div>
            <span class="status-badge ${statusClass}">
              ${statusLabel}
            </span>
          </div>
          <div class="dose-actions">
            ${isPending ? `
              <button class="btn btn-success btn-sm btn-mark-taken" data-id="${dose.id}">
                ✓ Mark as Taken
              </button>
              <button class="btn btn-danger btn-sm btn-mark-missed" data-id="${dose.id}">
                ✕ Missed
              </button>
            ` : isTaken ? `
              <button class="btn btn-outline btn-sm" disabled style="color:#16a34a; border-color:#16a34a;">
                ✓ Completed
              </button>
            ` : `
              <button class="btn btn-outline btn-sm btn-mark-taken" data-id="${dose.id}" title="Mark as taken if taken late">
                Mark as Taken
              </button>
            `}
          </div>
        </div>
      `;
    }).join('');

    // Attach action listeners
    listEl.querySelectorAll('.btn-mark-taken').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.dataset.id;
        try {
          await API.markDoseTaken(id);
          playChime(true);
          showToast('Medicine marked as Taken!', 'success');
          loadDashboard();
        } catch (err) {
          showToast(`Action failed: ${err.message}`, 'error');
        }
      });
    });

    listEl.querySelectorAll('.btn-mark-missed').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.dataset.id;
        try {
          await API.markDoseMissed(id);
          playChime(false);
          showToast('Dose recorded as Missed.', 'info');
          loadDashboard();
        } catch (err) {
          showToast(`Action failed: ${err.message}`, 'error');
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // Medicines Management Logic
  // --------------------------------------------------------------------------
  async function loadMedicines() {
    try {
      const data = await API.getMedicines();
      renderMedicinesList(data.medicines || []);
    } catch (err) {
      showToast(`Error loading medicines: ${err.message}`, 'error');
    }
  }

  function renderMedicinesList(medicines) {
    const container = document.getElementById('medicines-card-grid');
    const emptyEl = document.getElementById('medicines-empty-state');
    if (!container) return;

    if (!medicines || medicines.length === 0) {
      container.innerHTML = '';
      if (emptyEl) emptyEl.style.display = 'block';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    container.innerHTML = medicines.map(med => {
      const scheduleBadges = med.schedules.map(s => 
        `<span style="background:#e0f2fe; color:#0369a1; padding:4px 8px; border-radius:6px; font-size:0.9rem; font-weight:600;">⏰ ${formatTime(s.scheduled_time)}</span>`
      ).join(' ');

      return `
        <div class="feature-card" style="position:relative;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
            <div>
              <h3 style="font-size:1.35rem; color:#0f172a; margin-bottom:4px;">${escapeHtml(med.medicine_name)}</h3>
              <span style="font-size:0.85rem; text-transform:uppercase; font-weight:700; color:#64748b; background:#f1f5f9; padding:2px 8px; border-radius:4px;">${escapeHtml(med.medicine_type)}</span>
            </div>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.9rem; font-weight:600;">
              <input type="checkbox" class="med-toggle-active" data-id="${med.id}" ${med.active ? 'checked' : ''}>
              ${med.active ? '<span style="color:#16a34a">Active</span>' : '<span style="color:#94a3b8">Paused</span>'}
            </label>
          </div>
          
          <p style="margin-bottom:8px;"><strong>Dosage:</strong> ${escapeHtml(med.dosage)}</p>
          <p style="margin-bottom:8px;"><strong>Instructions:</strong> ${escapeHtml(med.instructions || 'None')}</p>
          <p style="margin-bottom:12px;"><strong>Remaining Quantity:</strong> ${med.quantity} units</p>
          
          <div style="margin-bottom:16px;">
            <div style="font-size:0.9rem; font-weight:600; color:#475569; margin-bottom:6px;">Scheduled Dose Timings:</div>
            <div style="display:flex; flex-wrap:wrap; gap:6px;">
              ${scheduleBadges || '<em>No schedules</em>'}
            </div>
          </div>

          <div style="display:flex; gap:10px; border-top:1px solid var(--border); padding-top:12px;">
            <button class="btn btn-secondary btn-sm btn-edit-med" data-id="${med.id}" style="flex:1;">✏ Edit</button>
            <button class="btn btn-danger btn-sm btn-delete-med" data-id="${med.id}">🗑 Delete</button>
          </div>
        </div>
      `;
    }).join('');

    // Toggle active listeners
    container.querySelectorAll('.med-toggle-active').forEach(chk => {
      chk.addEventListener('change', async (e) => {
        const id = e.target.dataset.id;
        try {
          await API.toggleMedicine(id);
          showToast('Medicine status updated.', 'info');
          loadMedicines();
        } catch (err) {
          showToast(`Failed: ${err.message}`, 'error');
        }
      });
    });

    // Delete listeners
    container.querySelectorAll('.btn-delete-med').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.dataset.id;
        if (confirm('Are you sure you want to delete this medicine and all its schedule logs?')) {
          try {
            await API.deleteMedicine(id);
            showToast('Medicine deleted.', 'success');
            loadMedicines();
          } catch (err) {
            showToast(`Failed: ${err.message}`, 'error');
          }
        }
      });
    });

    // Edit listeners
    container.querySelectorAll('.btn-edit-med').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.dataset.id;
        openMedicineModal(id);
      });
    });
  }

  // --------------------------------------------------------------------------
  // Add / Edit Medicine Modal
  // --------------------------------------------------------------------------
  function openMedicineModal(editId = null) {
    const modal = document.getElementById('modal-medicine');
    const form = document.getElementById('form-medicine');
    form.reset();

    const titleEl = document.getElementById('modal-medicine-title');
    const medIdInput = document.getElementById('med-input-id');
    const timeSlotContainer = document.getElementById('time-slots-container');
    timeSlotContainer.innerHTML = '';

    if (editId) {
      titleEl.textContent = 'Edit Medicine Schedule';
      medIdInput.value = editId;
      API.getMedicine(editId).then(res => {
        const med = res.medicine;
        document.getElementById('med-input-name').value = med.medicine_name;
        document.getElementById('med-input-type').value = med.medicine_type;
        document.getElementById('med-input-dosage').value = med.dosage;
        document.getElementById('med-input-quantity').value = med.quantity;
        document.getElementById('med-input-instructions').value = med.instructions;
        document.getElementById('med-input-start-date').value = med.start_date || '';
        document.getElementById('med-input-end-date').value = med.end_date || '';
        
        if (med.schedules && med.schedules.length > 0) {
          med.schedules.forEach(s => addTimeSlotRow(s.scheduled_time, s.reminder_method));
        } else {
          addTimeSlotRow('08:00');
        }
      }).catch(err => showToast(`Error fetching medicine: ${err.message}`, 'error'));
    } else {
      titleEl.textContent = 'Add New Medicine';
      medIdInput.value = '';
      document.getElementById('med-input-start-date').value = new Date().toISOString().split('T')[0];
      addTimeSlotRow('08:00');
      addTimeSlotRow('20:00');
    }

    modal.classList.add('open');
  }

  function addTimeSlotRow(timeVal = '08:00', methodVal = 'both') {
    const container = document.getElementById('time-slots-container');
    const row = document.createElement('div');
    row.className = 'time-slot-item';
    row.innerHTML = `
      <input type="time" class="form-control med-time-input" value="${timeVal}" required style="width:140px;">
      <select class="form-control med-method-input" style="width:120px;">
        <option value="both" ${methodVal === 'both' ? 'selected' : ''}>SMS & Email</option>
        <option value="sms" ${methodVal === 'sms' ? 'selected' : ''}>SMS Only</option>
        <option value="email" ${methodVal === 'email' ? 'selected' : ''}>Email Only</option>
      </select>
      <button type="button" class="btn btn-outline btn-sm remove-time-btn" style="color:#dc2626; border-color:#dc2626;">✕</button>
    `;
    row.querySelector('.remove-time-btn').addEventListener('click', () => {
      if (container.children.length > 1) {
        row.remove();
      } else {
        showToast('At least one dose timing is required.', 'error');
      }
    });
    container.appendChild(row);
  }

  // --------------------------------------------------------------------------
  // History & Statistics Logic
  // --------------------------------------------------------------------------
  async function loadHistory(filter = '7days') {
    try {
      document.querySelectorAll('.btn-history-filter').forEach(btn => {
        btn.classList.toggle('btn-primary', btn.dataset.filter === filter);
        btn.classList.toggle('btn-outline', btn.dataset.filter !== filter);
      });

      const data = await API.getHistory(filter);
      const stats = data.statistics || {};

      document.getElementById('hist-stat-total').textContent = stats.total_doses || 0;
      document.getElementById('hist-stat-taken').textContent = stats.taken_doses || 0;
      document.getElementById('hist-stat-missed').textContent = stats.missed_doses || 0;
      
      const adherence = stats.adherence_percentage !== undefined ? stats.adherence_percentage : 100;
      document.getElementById('hist-stat-adherence').textContent = `${adherence}%`;

      renderHistoryTable(data.logs || []);
    } catch (err) {
      showToast(`Error loading history: ${err.message}`, 'error');
    }
  }

  function renderHistoryTable(logs) {
    const tbody = document.getElementById('history-table-body');
    const emptyEl = document.getElementById('history-empty-state');
    if (!tbody) return;

    if (!logs || logs.length === 0) {
      tbody.innerHTML = '';
      if (emptyEl) emptyEl.style.display = 'block';
      return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    tbody.innerHTML = logs.map(l => {
      const statusClass = `status-${l.status}`;
      const statusLabel = l.status.charAt(0).toUpperCase() + l.status.slice(1);
      const takenDisplay = l.taken_time ? new Date(l.taken_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-';

      return `
        <tr>
          <td><strong>${escapeHtml(l.medicine_name)}</strong></td>
          <td>${l.scheduled_date}</td>
          <td>${formatTime(l.scheduled_time)}</td>
          <td>${escapeHtml(l.dosage)}</td>
          <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
          <td>${takenDisplay}</td>
        </tr>
      `;
    }).join('');
  }

  // --------------------------------------------------------------------------
  // Notifications Feed Logic
  // --------------------------------------------------------------------------
  async function loadNotifications() {
    try {
      const data = await API.getNotifications();
      const listEl = document.getElementById('notifications-feed-list');
      const emptyEl = document.getElementById('notifications-empty-state');
      if (!listEl) return;

      const notifs = data.notifications || [];
      if (notifs.length === 0) {
        listEl.innerHTML = '';
        if (emptyEl) emptyEl.style.display = 'block';
        return;
      }

      if (emptyEl) emptyEl.style.display = 'none';

      listEl.innerHTML = notifs.map(n => {
        let icon = '🔔';
        let borderColor = '#0284c7';
        if (n.notification_type === 'missed') {
          icon = '⚠️';
          borderColor = '#dc2626';
        } else if (n.notification_type === 'alert') {
          icon = '✓';
          borderColor = '#16a34a';
        }

        const sentDate = n.sent_at ? new Date(n.sent_at).toLocaleString() : '';

        return `
          <div style="background:var(--surface); border-left: 4px solid ${borderColor}; border-radius:8px; padding:16px 20px; box-shadow:var(--shadow-sm); margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span style="font-size:1.1rem; font-weight:700;">${icon} ${escapeHtml(n.notification_type.toUpperCase())}</span>
              <span style="font-size:0.85rem; color:#64748b;">${sentDate}</span>
            </div>
            <p style="font-size:1.05rem; color:#1e293b;">${escapeHtml(n.message)}</p>
            <div style="margin-top:6px; font-size:0.8rem; color:#64748b;">
              Status: <span style="font-weight:600; text-transform:uppercase;">${n.status}</span>
            </div>
          </div>
        `;
      }).join('');
    } catch (err) {
      showToast(`Error loading notifications: ${err.message}`, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Profile Logic
  // --------------------------------------------------------------------------
  async function loadProfile() {
    try {
      const data = await API.getProfile();
      const user = data.user;
      document.getElementById('prof-input-name').value = user.name || '';
      document.getElementById('prof-input-email').value = user.email || '';
      document.getElementById('prof-input-phone').value = user.phone || '';
      document.getElementById('prof-input-pref').value = user.notification_preference || 'both';
      
      // Update local storage
      API.setUser(user);
    } catch (err) {
      showToast(`Error loading profile: ${err.message}`, 'error');
    }
  }

  // Helper to escape HTML tags
  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --------------------------------------------------------------------------
  // Initialization & Event Binding
  // --------------------------------------------------------------------------
  function init() {
    startLiveClock();

    // Setup navigation clicks
    document.querySelectorAll('[data-view]').forEach(elem => {
      elem.addEventListener('click', (e) => {
        e.preventDefault();
        const view = elem.dataset.view;
        navigateTo(view);
      });
    });

    // Auto-login or initial route
    if (API.isAuthenticated()) {
      navigateTo('dashboard');
      // Periodic refresh of dashboard every 30 seconds
      setInterval(() => {
        const dashboardActive = document.getElementById('view-dashboard')?.classList.contains('active');
        if (dashboardActive && API.isAuthenticated()) {
          loadDashboard();
        }
      }, 30000);
    } else {
      navigateTo('landing');
    }

    // Modal close buttons
    document.querySelectorAll('.close-modal-btn, .modal-backdrop').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target === el) {
          document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('open'));
        }
      });
    });

    // Auth Form Handlers
    const loginForm = document.getElementById('form-login');
    if (loginForm) {
      loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        try {
          const res = await API.login({ email, password });
          API.setToken(res.token);
          API.setUser(res.user);
          showToast('Welcome back, ' + res.user.name + '!', 'success');
          document.getElementById('modal-login').classList.remove('open');
          navigateTo('dashboard');
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    }

    const registerForm = document.getElementById('form-register');
    if (registerForm) {
      registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('reg-name').value;
        const email = document.getElementById('reg-email').value;
        const phone = document.getElementById('reg-phone').value;
        const password = document.getElementById('reg-password').value;
        const confirm_password = document.getElementById('reg-confirm').value;
        const notification_preference = document.getElementById('reg-pref').value;

        if (password !== confirm_password) {
          showToast('Passwords do not match.', 'error');
          return;
        }

        try {
          const res = await API.register({ name, email, phone, password, confirm_password, notification_preference });
          API.setToken(res.token);
          API.setUser(res.user);
          showToast('Account registered successfully!', 'success');
          document.getElementById('modal-register').classList.remove('open');
          navigateTo('dashboard');
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    }

    // Logout
    document.querySelectorAll('.btn-logout').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        API.setToken(null);
        API.setUser(null);
        showToast('Logged out successfully.', 'info');
        navigateTo('landing');
      });
    });

    // Add Time Slot Button
    const addSlotBtn = document.getElementById('btn-add-time-slot');
    if (addSlotBtn) {
      addSlotBtn.addEventListener('click', () => addTimeSlotRow('12:00'));
    }

    // Medicine Form Submit
    const medForm = document.getElementById('form-medicine');
    if (medForm) {
      medForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const medId = document.getElementById('med-input-id').value;
        
        // Collect schedules
        const timeRows = document.querySelectorAll('#time-slots-container .time-slot-item');
        const schedules = [];
        timeRows.forEach(row => {
          const t = row.querySelector('.med-time-input').value;
          const m = row.querySelector('.med-method-input').value;
          if (t) schedules.push({ scheduled_time: t, reminder_method: m });
        });

        const payload = {
          medicine_name: document.getElementById('med-input-name').value,
          medicine_type: document.getElementById('med-input-type').value,
          dosage: document.getElementById('med-input-dosage').value,
          quantity: parseInt(document.getElementById('med-input-quantity').value) || 30,
          instructions: document.getElementById('med-input-instructions').value,
          start_date: document.getElementById('med-input-start-date').value,
          end_date: document.getElementById('med-input-end-date').value || null,
          schedules: schedules
        };

        try {
          if (medId) {
            await API.updateMedicine(medId, payload);
            showToast('Medicine schedule updated successfully!', 'success');
          } else {
            await API.addMedicine(payload);
            showToast('New medicine added with automatic reminders!', 'success');
          }
          document.getElementById('modal-medicine').classList.remove('open');
          loadMedicines();
          loadDashboard();
        } catch (err) {
          showToast(`Save failed: ${err.message}`, 'error');
        }
      });
    }

    // Open Add Medicine Modal Button
    document.querySelectorAll('.btn-open-add-med').forEach(btn => {
      btn.addEventListener('click', () => openMedicineModal());
    });

    // History Filters
    document.querySelectorAll('.btn-history-filter').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const filter = e.target.dataset.filter;
        loadHistory(filter);
      });
    });

    // Profile Form
    const profForm = document.getElementById('form-profile');
    if (profForm) {
      profForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          name: document.getElementById('prof-input-name').value,
          phone: document.getElementById('prof-input-phone').value,
          notification_preference: document.getElementById('prof-input-pref').value,
        };
        const newPass = document.getElementById('prof-input-pass').value;
        if (newPass) payload.password = newPass;

        try {
          const res = await API.updateProfile(payload);
          API.setUser(res.user);
          showToast('Profile updated successfully!', 'success');
          updateAuthUI();
        } catch (err) {
          showToast(`Update failed: ${err.message}`, 'error');
        }
      });
    }

    // Test SNS Reminder Button
    const testReminderBtn = document.getElementById('btn-test-reminder');
    if (testReminderBtn) {
      testReminderBtn.addEventListener('click', async () => {
        try {
          testReminderBtn.disabled = true;
          testReminderBtn.textContent = 'Sending Alert...';
          const res = await API.testReminder();
          playChime(true);
          showToast(res.message || 'Test reminder dispatched!', 'success');
          loadNotifications();
        } catch (err) {
          showToast(`Test failed: ${err.message}`, 'error');
        } finally {
          testReminderBtn.disabled = false;
          testReminderBtn.textContent = '🔔 Send Test Reminder Now';
        }
      });
    }

    // Auth expiration listener
    window.addEventListener('auth:expired', () => {
      showToast('Your session has expired. Please log in again.', 'info');
      navigateTo('landing');
    });
  }

  return {
    init,
    navigateTo,
    openMedicineModal,
    showToast
  };
})();

// Start App upon DOM content load
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
