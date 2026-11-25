function updateJoinSummary(form) {
  const chosen = [...form.querySelectorAll('input[name="service_ids"]:checked')];
  const minutes = chosen.reduce((total, input) => total + Number(input.dataset.minutes), 0);
  const price = chosen.reduce((total, input) => total + Number(input.dataset.price), 0);
  const selectedBarber = form.querySelector('input[name="barber_id"]:checked');
  document.getElementById('summary-minutes').textContent = minutes;
  document.getElementById('summary-price').textContent = price;
  document.getElementById('summary-wait').textContent = selectedBarber?.dataset.wait || '0';
  document.getElementById('selected-count').textContent = chosen.length;
}

function setLiveText(element, value) {
  if (!element || element.textContent.trim() === String(value)) return;
  element.classList.add('is-updating');
  element.textContent = value;
  window.setTimeout(() => element.classList.remove('is-updating'), 360);
}

function flashRefresh(element) {
  element.classList.remove('live-refresh');
  window.requestAnimationFrame(() => {
    element.classList.add('live-refresh');
    element.addEventListener('animationend', () => element.classList.remove('live-refresh'), { once: true });
  });
}

function initEditorialMotion() {
  document.body.classList.add('ui-ready');
  const header = document.querySelector('.topbar');
  const updateHeader = () => header?.classList.toggle('is-scrolled', window.scrollY > 8);
  updateHeader();
  window.addEventListener('scroll', updateHeader, { passive: true });

  const toggle = document.getElementById('mobile-menu-toggle');
  const menu = document.getElementById('mobile-menu');
  const close = document.getElementById('mobile-menu-close');
  if (toggle && menu) {
    const syncExpanded = () => toggle.setAttribute('aria-expanded', String(menu.open));
    toggle.addEventListener('click', () => {
      if (!menu.open) menu.showModal();
      syncExpanded();
    });
    close?.addEventListener('click', () => menu.close());
    menu.addEventListener('close', syncExpanded);
    menu.addEventListener('cancel', () => toggle.setAttribute('aria-expanded', 'false'));
    menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => menu.close()));
  }

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll('[data-count-up]').forEach((element) => {
    const target = Number(element.textContent.trim());
    if (!Number.isFinite(target) || target === 0) return;
    const start = performance.now();
    const duration = 600;
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = String(Math.round(target * eased));
      if (progress < 1) window.requestAnimationFrame(tick);
    };
    window.requestAnimationFrame(tick);
  });
}

function initJoinForm(form) {
  const serviceChecks = [...form.querySelectorAll('input[name="service_ids"]')];
  const phoneInput = form.querySelector('input[name="phone"]');
  const nameInput = form.querySelector('input[name="customer_name"]');
  const serviceError = document.getElementById('service-error');
  const maxServices = Number(form.dataset.maxServices);

  serviceChecks.forEach((input) => input.addEventListener('change', () => {
    const checked = serviceChecks.filter((item) => item.checked);
    serviceError.textContent = '';
    if (checked.length > maxServices) {
      input.checked = false;
      serviceError.textContent = form.dataset.tooMany;
    }
    updateJoinSummary(form);
  }));

  form.querySelectorAll('input[name="barber_id"]').forEach((input) => {
    input.addEventListener('change', () => updateJoinSummary(form));
  });

  form.addEventListener('submit', (event) => {
    let valid = true;
    serviceError.textContent = '';
    phoneInput.removeAttribute('aria-invalid');
    nameInput.removeAttribute('aria-invalid');
    if (!nameInput.value.trim()) {
      nameInput.setAttribute('aria-invalid', 'true');
      valid = false;
    }
    if (!/^[0-9]{10}$/.test(phoneInput.value.trim())) {
      phoneInput.setAttribute('aria-invalid', 'true');
      valid = false;
    }
    const count = serviceChecks.filter((item) => item.checked).length;
    if (count === 0) {
      serviceError.textContent = form.dataset.serviceRequired;
      valid = false;
    } else if (count > maxServices) {
      serviceError.textContent = form.dataset.tooMany;
      valid = false;
    }
    if (!valid) {
      event.preventDefault();
      if (!nameInput.value.trim()) nameInput.focus();
      else if (!/^[0-9]{10}$/.test(phoneInput.value.trim())) phoneInput.focus();
      else document.getElementById('service-grid').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
  updateJoinSummary(form);
}

async function refreshQueueData() {
  const homeSummary = document.getElementById('queue-summary');
  const joinPage = document.getElementById('join-page');
  const joinForm = document.querySelector('.join-layout[data-summary-url]');
  const url = homeSummary?.dataset.summaryUrl || joinPage?.dataset.summaryUrl || joinForm?.dataset.summaryUrl;
  if (!url) return;
  try {
    const response = await fetch(url, { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!response.ok) return;
    const data = await response.json();
    const count = document.getElementById('waiting-count');
    if (count) setLiveText(count, data.waiting_count);
    const overall = document.getElementById('overall-wait');
    if (overall) setLiveText(overall, data.overall_wait === null ? '-' : `~${data.overall_wait}`);
    const openBadge = document.getElementById('queue-open-badge');
    if (openBadge && typeof data.queue_open === 'boolean') {
      openBadge.classList.toggle('is-closed', !data.queue_open);
      setLiveText(document.getElementById('queue-open-label'), data.queue_open ? openBadge.dataset.openLabel : openBadge.dataset.closedLabel);
    }
    const homeCta = document.getElementById('home-join-cta');
    if (homeCta && typeof data.queue_open === 'boolean') {
      setLiveText(document.getElementById('home-join-label'), data.queue_open ? homeCta.dataset.openLabel : homeCta.dataset.closedLabel);
    }
    if (joinPage && typeof data.queue_open === 'boolean') {
      joinPage.dataset.queueOpen = String(data.queue_open);
      const closedBanner = document.getElementById('queue-closed-banner');
      if (closedBanner) closedBanner.hidden = data.queue_open;
      if (joinForm) joinForm.hidden = !data.queue_open;
    }
    const waits = data.barbers.filter((barber) => barber.available).map((barber) => barber.wait);
    data.barbers.forEach((barber) => {
      const element = document.getElementById(`barber-wait-${barber.id}`);
      if (element && element.dataset.available === 'true') element.textContent = `${barber.wait} ${homeSummary?.dataset.minuteLabel || joinForm?.dataset.minuteLabel || ''}`.trim();
    });
    if (joinForm) {
      const activeServiceIds = new Set((data.active_service_ids || []).map(String));
      let servicesChanged = false;
      joinForm.querySelectorAll('input[name="service_ids"]').forEach((input) => {
        const active = activeServiceIds.has(input.value);
        const option = input.closest('.service-option');
        if (option) option.hidden = !active;
        if (!active && input.checked) {
          input.checked = false;
          servicesChanged = true;
        }
        input.disabled = !active;
      });
      const anyWait = waits.length ? Math.min(...waits) : 0;
      const anyRadio = joinForm.querySelector('input[name="barber_id"][value=""]');
      if (anyRadio) {
        anyRadio.dataset.wait = anyWait;
        anyRadio.closest('.barber-choice').querySelector('.wait-value').textContent = anyWait;
      }
      data.barbers.forEach((barber) => {
        const radio = joinForm.querySelector(`input[name="barber_id"][value="${barber.id}"]`);
        if (radio && barber.available) {
          radio.dataset.wait = barber.wait;
          radio.closest('.barber-choice').querySelector('.wait-value').textContent = barber.wait;
        }
      });
      if (servicesChanged) document.getElementById('service-error').textContent = '';
      updateJoinSummary(joinForm);
    }
  } catch {
    // The server-rendered values remain usable if a refresh is unavailable.
  }
}

function initStatusPage(statusPage) {
  const labelsNode = document.getElementById('status-labels');
  const labels = labelsNode ? JSON.parse(labelsNode.textContent) : {};
  const title = document.getElementById('status-title');
  const message = document.getElementById('status-message');
  const position = document.getElementById('status-position');
  const wait = document.getElementById('status-wait');
  const startComing = document.getElementById('start-coming-banner');

  async function refreshStatus() {
    try {
      const response = await fetch(statusPage.dataset.statusUrl, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!response.ok) return;
      const data = await response.json();
      const isWaiting = data.status === 'waiting';
      const copyByStatus = {
        waiting: [labels.status_title, labels.status_waiting_message],
        called: [labels.called_title, data.barber_name ? `${labels.called_go_to} ${data.barber_name}` : labels.called_any_message],
        in_chair: [labels.in_chair_title, labels.in_chair_message],
        done: [labels.done_title, labels.done_message],
        cancelled: [labels.cancelled_title, labels.cancelled_message],
        no_show: [labels.no_show_title, labels.no_show_message],
      };
      const [titleText, messageText] = copyByStatus[data.status] || copyByStatus.waiting;
      setLiveText(title, titleText);
      setLiveText(message, isWaiting && data.barber_on_break
        ? `${data.barber_name} ${labels.barber_on_break_suffix}`
        : isWaiting && data.barber_off_duty
          ? `${data.barber_name} ${labels.barber_off_duty_suffix}`
          : messageText);
      setLiveText(position, isWaiting ? data.position : labels.not_available);
      setLiveText(wait, isWaiting ? `~${data.wait_minutes} ${labels.minutes}` : labels.not_available);
      startComing.hidden = !isWaiting || data.position !== 2;
      statusPage.dataset.state = data.status;
      statusPage.dataset.position = data.position;
      statusPage.dataset.barber = data.barber_name;
      statusPage.classList.toggle('barber-is-on-break', isWaiting && data.barber_on_break);
      document.body.dataset.queueState = data.status;
      document.title = `${titleText} - ${labels.brand}`;
    } catch {
      // The server-rendered queue details remain visible if a refresh is unavailable.
    }
  }

  document.body.dataset.queueState = statusPage.dataset.state;
  refreshStatus();
  window.setInterval(refreshStatus, 4000);
}

function initWalkinForm(form) {
  const checkboxes = [...form.querySelectorAll('input[name="service_ids"]')];
  const nameInput = form.querySelector('input[name="customer_name"]');
  const phoneInput = form.querySelector('input[name="phone"]');
  const error = document.getElementById('walkin-service-error');
  const maxServices = Number(form.dataset.maxServices);
  checkboxes.forEach((checkbox) => checkbox.addEventListener('change', () => {
    error.textContent = '';
    if (checkboxes.filter((item) => item.checked).length > maxServices) {
      checkbox.checked = false;
      error.textContent = form.dataset.limitError;
    }
  }));
  form.addEventListener('submit', (event) => {
    const phoneIsValid = /^[0-9]{10}$/.test(phoneInput.value.trim());
    const nameIsValid = Boolean(nameInput.value.trim());
    const servicesValid = checkboxes.filter((item) => item.checked).length > 0;
    nameInput.setAttribute('aria-invalid', String(!nameIsValid));
    phoneInput.setAttribute('aria-invalid', String(!phoneIsValid));
    error.textContent = servicesValid ? '' : form.dataset.serviceError;
    if (!servicesValid || !nameIsValid || !phoneIsValid) {
      event.preventDefault();
      if (!nameIsValid) nameInput.focus();
      else if (!phoneIsValid) phoneInput.focus();
      else document.querySelector('.walkin-services').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}

function initReceptionDashboard(dashboard) {
  const root = document.getElementById('reception-root');
  const openDialog = () => {
    const dialog = document.getElementById('walkin-dialog');
    if (dialog && !dialog.open) dialog.showModal();
  };
  const closeDialog = () => {
    const dialog = document.getElementById('walkin-dialog');
    if (dialog?.open) dialog.close();
  };
  root.addEventListener('click', (event) => {
    if (event.target.closest('#open-walkin')) openDialog();
    if (event.target.closest('#close-walkin, #cancel-walkin')) closeDialog();
  });
  const bindWalkinForm = () => {
    const form = document.getElementById('walkin-form');
    if (form) initWalkinForm(form);
  };
  bindWalkinForm();
  const initialDialog = document.getElementById('walkin-dialog');
  if (initialDialog?.dataset.openOnLoad === 'true') initialDialog.showModal();

  async function refreshReception() {
    try {
      const refreshUrl = `${dashboard.dataset.refreshUrl}${window.location.search}`;
      const response = await fetch(refreshUrl, { headers: { 'X-Requested-With': 'fetch' }, cache: 'no-store' });
      if (!response.ok) return;
      dashboard.innerHTML = await response.text();
      flashRefresh(dashboard);
      bindWalkinForm();
    } catch {
      // Keep the current dashboard visible if a refresh is unavailable.
    }
  }
  window.setInterval(refreshReception, 3000);
}

function initBarberView(barberView) {
  function updateElapsedTimer() {
    const timer = barberView.querySelector('[data-elapsed-timer]');
    if (!timer) return;
    const seconds = Number(timer.dataset.elapsedSeconds) + Math.floor((Date.now() - Number(timer.dataset.sampledAt)) / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainder = seconds % 60;
    timer.textContent = hours ? [hours, minutes, remainder].map((part) => String(part).padStart(2, '0')).join(':') : `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
  }

  function sampleTimer() {
    const timer = barberView.querySelector('[data-elapsed-timer]');
    if (timer) timer.dataset.sampledAt = Date.now();
    updateElapsedTimer();
  }
  sampleTimer();
  window.setInterval(updateElapsedTimer, 1000);

  async function refreshBarberView() {
    try {
      const response = await fetch(`${barberView.dataset.refreshUrl}${window.location.search}`, { cache: 'no-store' });
      if (!response.ok) return;
      barberView.innerHTML = await response.text();
      flashRefresh(barberView);
      sampleTimer();
    } catch {
      // Keep the current assignment visible if the refresh is unavailable.
    }
  }
  window.setInterval(refreshBarberView, 3000);
}

function initTvDashboard(dashboard) {
  const soundOnLabel = dashboard.dataset.soundOn;
  const soundOffLabel = dashboard.dataset.soundOff;
  let soundEnabled = false;
  let audioContext = null;
  try {
    soundEnabled = localStorage.getItem('tricky-heat-tv-sound') === 'true';
  } catch {
    soundEnabled = false;
  }

  function updateSoundButton() {
    const button = dashboard.querySelector('#sound-toggle');
    if (!button) return;
    button.textContent = soundEnabled ? soundOnLabel : soundOffLabel;
    button.setAttribute('aria-pressed', String(soundEnabled));
  }

  function playChime() {
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      if (!audioContext || audioContext.state === 'closed') audioContext = new AudioContextClass();
      audioContext.resume();
      const context = audioContext;
      const playTone = (frequency, delay) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = frequency;
        oscillator.type = 'sine';
        gain.gain.setValueAtTime(0.0001, context.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + delay + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + delay + 0.24);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(context.currentTime + delay);
        oscillator.stop(context.currentTime + delay + 0.25);
      };
      playTone(740, 0);
      playTone(988, 0.2);
    } catch {
      // Some TV browsers block audio until sound is enabled from a user gesture.
    }
  }

  dashboard.addEventListener('click', (event) => {
    if (!event.target.closest('#sound-toggle')) return;
    soundEnabled = !soundEnabled;
    if (soundEnabled) {
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass && !audioContext) audioContext = new AudioContextClass();
        audioContext?.resume();
      } catch {
        audioContext = null;
      }
    }
    try {
      localStorage.setItem('tricky-heat-tv-sound', String(soundEnabled));
    } catch {
      // Sound preference can remain temporary if storage is unavailable.
    }
    updateSoundButton();
  });
  updateSoundButton();

  async function refreshTv() {
    try {
      const response = await fetch(dashboard.dataset.refreshUrl, { cache: 'no-store' });
      if (!response.ok) return;
      const html = await response.text();
      const parsed = new DOMParser().parseFromString(html, 'text/html');
      const freshContent = parsed.querySelector('.tv-content');
      if (!freshContent) return;
      const oldCalls = new Map([...dashboard.querySelectorAll('.tv-lane')].map((lane) => [lane.dataset.barberId, lane.dataset.calledToken]));
      const newCalls = [...freshContent.querySelectorAll('.tv-lane')].filter((lane) => lane.dataset.calledToken && lane.dataset.calledToken !== oldCalls.get(lane.dataset.barberId));
      dashboard.innerHTML = freshContent.innerHTML;
      flashRefresh(dashboard);
      newCalls.forEach((lane) => {
        dashboard.querySelector(`.tv-lane[data-barber-id="${lane.dataset.barberId}"] .tv-called-ticket`)?.classList.add('tv-called-new');
      });
      if (newCalls.length && soundEnabled) playChime();
      updateSoundButton();
    } catch {
      // Leave the current TV board on screen if an update is unavailable.
    }
  }
  window.setInterval(refreshTv, 3000);
}

document.addEventListener('DOMContentLoaded', () => {
  initEditorialMotion();
  const form = document.querySelector('.join-layout');
  if (form) initJoinForm(form);
  const statusPage = document.getElementById('status-page');
  if (statusPage) initStatusPage(statusPage);
  const receptionDashboard = document.getElementById('reception-dashboard');
  if (receptionDashboard) initReceptionDashboard(receptionDashboard);
  const barberView = document.getElementById('barber-view');
  if (barberView) initBarberView(barberView);
  const tvDashboard = document.getElementById('tv-dashboard');
  if (tvDashboard) initTvDashboard(tvDashboard);
  refreshQueueData();
  if (document.getElementById('queue-summary') || document.getElementById('join-page')) window.setInterval(refreshQueueData, 5000);
});
