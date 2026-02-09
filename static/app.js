// === API Base ===
const API = "/api";

// === Helpers ===
const $ = (sel) => document.querySelector(sel);

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/&/g, "&amp;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

// === DOM Refs ===
const healthDot = $("#healthDot");
const healthLabel = $("#healthLabel");
const activeCallsBadge = $("#activeCallsBadge");
const groqStatus = $("#groqStatus");
const twilioStatus = $("#twilioStatus");
const activeCalls = $("#activeCalls");
const overallStatus = $("#overallStatus");
const callTableBody = $("#callTableBody");
const prevPage = $("#prevPage");
const nextPage = $("#nextPage");
const pageInfo = $("#pageInfo");
const configForm = $("#configForm");
const configMsg = $("#configMsg");
const modalBackdrop = $("#modalBackdrop");
const modalBody = $("#modalBody");
const modalTitle = $("#modalTitle");
const modalClose = $("#modalClose");
const lastUpdated = $("#lastUpdated");
const searchInput = $("#searchInput");
const statusFilter = $("#statusFilter");
const callCount = $("#callCount");
const phoneNumber = $("#phoneNumber");
const hoursStatus = $("#hoursStatus");
const authBackdrop = $("#authBackdrop");
const authClose = $("#authClose");
const authForm = $("#authForm");
const authToken = $("#authToken");
const authMsg = $("#authMsg");

// === State ===
let currentPage = 0;
const PAGE_SIZE = 20;
let originalConfig = {};     // Track original config to detect real changes
let authRequired = false;    // Whether server requires a token
let pendingConfigSave = null; // Config body waiting for auth
let activeCallTimers = [];   // Intervals for live duration counters

// === Auth ===
function getToken() {
  return sessionStorage.getItem("dashboard_token") || "";
}

function setToken(token) {
  sessionStorage.setItem("dashboard_token", token);
}

function showAuthModal() {
  authBackdrop.classList.add("open");
  authToken.value = "";
  authMsg.textContent = "";
  authToken.focus();
}

function hideAuthModal() {
  authBackdrop.classList.remove("open");
  pendingConfigSave = null;
}

authClose.addEventListener("click", hideAuthModal);

authBackdrop.addEventListener("click", (e) => {
  if (e.target === authBackdrop) hideAuthModal();
});

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const token = authToken.value.trim();
  if (!token) return;

  setToken(token);

  // Retry the pending config save
  if (pendingConfigSave) {
    hideAuthModal();
    await saveConfig(pendingConfigSave);
  } else {
    hideAuthModal();
  }
});

// === Last Updated ===
function updateTimestamp() {
  const now = new Date();
  lastUpdated.textContent = "Updated " + now.toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// === Health ===
async function fetchHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();

    healthDot.className = "health-indicator " + data.status;
    healthLabel.textContent = data.status === "healthy" ? "Healthy" : "Degraded";

    // Badge: teal when active calls > 0, gray when 0
    activeCallsBadge.textContent = data.active_calls + " active";
    activeCallsBadge.className = "badge " + (data.active_calls > 0 ? "active" : "inactive");

    const groqOk = data.groq === "connected";
    const groqDot = groqOk ? "green" : "red";
    groqStatus.innerHTML = `<span class="status-dot ${groqDot}"></span>${escapeHtml(groqOk ? "Connected" : "Error")}`;
    groqStatus.className = "status-value " + (groqOk ? "ok" : "err");

    const twilioDot = data.twilio_configured ? "green" : "orange";
    twilioStatus.innerHTML = `<span class="status-dot ${twilioDot}"></span>${escapeHtml(data.twilio_configured ? "Configured" : "Not configured")}`;
    twilioStatus.className = "status-value " + (data.twilio_configured ? "ok" : "warn");

    activeCalls.textContent = data.active_calls;
    activeCalls.className = "status-value";

    const overallDot = data.status === "healthy" ? "green" : "orange";
    overallStatus.innerHTML = `<span class="status-dot ${overallDot}"></span>${escapeHtml(data.status === "healthy" ? "Healthy" : "Degraded")}`;
    overallStatus.className = "status-value " + (data.status === "healthy" ? "ok" : "warn");

    updateTimestamp();
  } catch {
    healthDot.className = "health-indicator error";
    healthLabel.textContent = "Offline";
    overallStatus.textContent = "Unreachable";
    overallStatus.className = "status-value err";
  }
}

// === Config ===
async function fetchConfig() {
  try {
    const res = await fetch(`${API}/config`);
    const data = await res.json();

    authRequired = data.auth_required || false;

    originalConfig = {
      business_hours_start: data.business_hours_start || "",
      business_hours_end: data.business_hours_end || "",
      business_timezone: data.business_timezone || "",
      sales_phone_number: data.sales_phone_number || "",
      support_phone_number: data.support_phone_number || "",
    };

    $("#hoursStart").value = originalConfig.business_hours_start;
    $("#hoursEnd").value = originalConfig.business_hours_end;
    $("#timezone").value = originalConfig.business_timezone;
    $("#salesNumber").value = originalConfig.sales_phone_number;
    $("#supportNumber").value = originalConfig.support_phone_number;

    // Populate status card extras
    phoneNumber.textContent = data.twilio_phone_number
      ? formatPhone(data.twilio_phone_number)
      : "Not set";

    // Check if currently within business hours
    updateHoursStatus(data.business_hours_start, data.business_hours_end, data.business_timezone);
  } catch {
    console.error("Failed to load config");
  }
}

async function saveConfig(body) {
  configMsg.textContent = "";

  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API}/config`, {
      method: "PUT",
      headers,
      body: JSON.stringify(body),
    });

    if (res.status === 401) {
      pendingConfigSave = body;
      showAuthModal();
      return;
    }

    if (res.ok) {
      configMsg.textContent = "Saved!";
      configMsg.className = "config-msg success";
      // Update original config so same values aren't re-sent
      Object.assign(originalConfig, body);
    } else {
      const err = await res.json();
      configMsg.textContent = err.detail || "Save failed";
      configMsg.className = "config-msg error";
    }
  } catch {
    configMsg.textContent = "Network error";
    configMsg.className = "config-msg error";
  }

  setTimeout(() => { configMsg.textContent = ""; }, 3000);
}

configForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Only send fields that actually changed from original
  const body = {};
  const fields = {
    business_hours_start: $("#hoursStart").value.trim(),
    business_hours_end: $("#hoursEnd").value.trim(),
    business_timezone: $("#timezone").value.trim(),
    sales_phone_number: $("#salesNumber").value.trim(),
    support_phone_number: $("#supportNumber").value.trim(),
  };

  for (const [key, val] of Object.entries(fields)) {
    if (val && val !== originalConfig[key]) {
      body[key] = val;
    }
  }

  if (Object.keys(body).length === 0) {
    configMsg.textContent = "No changes to save";
    configMsg.className = "config-msg error";
    setTimeout(() => { configMsg.textContent = ""; }, 3000);
    return;
  }

  await saveConfig(body);
});

// === Hours Status ===
function updateHoursStatus(startStr, endStr, tz) {
  try {
    const now = new Date();
    // Get current time in the business timezone
    const timeInTz = now.toLocaleTimeString("en-US", {
      timeZone: tz, hour12: false, hour: "2-digit", minute: "2-digit",
    });
    const isOpen = timeInTz >= startStr && timeInTz < endStr;
    const dot = isOpen ? "green" : "gray";
    const label = isOpen ? `Open (${startStr}\u2013${endStr})` : `Closed (${startStr}\u2013${endStr})`;
    hoursStatus.innerHTML = `<span class="status-dot ${dot}"></span>${escapeHtml(label)}`;
    hoursStatus.className = "status-value " + (isOpen ? "ok" : "dim");
  } catch {
    hoursStatus.textContent = `${startStr}\u2013${endStr}`;
    hoursStatus.className = "status-value dim";
  }
}

// === Call Log ===
function formatTime(isoStr) {
  if (!isoStr) return "--";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

function formatDuration(startStr, endStr) {
  if (!startStr || !endStr) return null;
  try {
    const ms = new Date(endStr) - new Date(startStr);
    if (ms <= 0 || isNaN(ms)) return null; // 0s = bogus data, show "--"
    return formatMs(ms);
  } catch {
    return null;
  }
}

function formatMs(ms) {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatDateOnly(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "";
  }
}

function formatTimeOnly(isoStr) {
  if (!isoStr) return "--";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return isoStr;
  }
}

function formatPhone(num) {
  if (!num) return "Unknown";
  const match = num.match(/^\+1(\d{3})(\d{3})(\d{4})$/);
  if (match) return `(${match[1]}) ${match[2]}-${match[3]}`;
  return num;
}

function clearActiveTimers() {
  activeCallTimers.forEach(clearInterval);
  activeCallTimers = [];
}

async function fetchCalls() {
  try {
    const offset = currentPage * PAGE_SIZE;
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset });

    const search = searchInput.value.trim();
    const status = statusFilter.value;
    if (search) params.set("search", search);
    if (status) params.set("status", status);

    const res = await fetch(`${API}/calls?${params}`);
    const data = await res.json();

    clearActiveTimers();

    // Total count display
    callCount.textContent = data.count > 0 ? `(${data.count}${data.count >= PAGE_SIZE ? "+" : ""})` : "";

    if (data.calls.length === 0) {
      const msg = (search || status) ? "No calls match filters" : "No calls yet";
      callTableBody.innerHTML = `<tr><td colspan="5" class="empty-msg">${escapeHtml(msg)}</td></tr>`;
      prevPage.disabled = true;
      nextPage.disabled = data.count < PAGE_SIZE;
      pageInfo.textContent = `Page ${currentPage + 1}`;
      return;
    }

    // Build rows with date separators
    let lastDate = "";
    const rows = [];
    data.calls.forEach((call, i) => {
      const dateStr = formatDateOnly(call.started_at);
      if (dateStr && dateStr !== lastDate) {
        rows.push(`<tr class="date-separator"><td colspan="5">${escapeHtml(dateStr)}</td></tr>`);
        lastDate = dateStr;
      }

      const isActive = call.status === "active";
      const dur = formatDuration(call.started_at, call.ended_at);
      const durCell = isActive
        ? `<span class="duration-live" id="dur-${i}">0s</span>`
        : escapeHtml(dur || "--");

      rows.push(`<tr>
        <td>${escapeHtml(formatTimeOnly(call.started_at))}</td>
        <td>${escapeHtml(formatPhone(call.from_number))}</td>
        <td><span class="status-badge ${escapeAttr(call.status)}">${escapeHtml(call.status)}</span></td>
        <td>${durCell}</td>
        <td><button class="btn-detail" data-sid="${escapeAttr(call.call_sid)}">View</button></td>
      </tr>`);
    });
    callTableBody.innerHTML = rows.join("");

    // Start live timers for active calls
    data.calls.forEach((call, i) => {
      if (call.status === "active" && call.started_at) {
        const startMs = new Date(call.started_at).getTime();
        const el = $(`#dur-${i}`);
        if (el && !isNaN(startMs)) {
          const update = () => { el.textContent = formatMs(Date.now() - startMs); };
          update();
          activeCallTimers.push(setInterval(update, 1000));
        }
      }
    });

    // Event delegation for View buttons
    callTableBody.onclick = (e) => {
      const btn = e.target.closest(".btn-detail");
      if (btn) showTranscript(btn.dataset.sid);
    };

    prevPage.disabled = currentPage === 0;
    nextPage.disabled = data.count < PAGE_SIZE;
    pageInfo.textContent = `Page ${currentPage + 1}`;

    updateTimestamp();
  } catch {
    callTableBody.innerHTML = '<tr><td colspan="5" class="empty-msg">Failed to load calls</td></tr>';
  }
}

// Search & filter: reset to page 0 and re-fetch
let searchDebounce = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    currentPage = 0;
    fetchCalls();
  }, 400);
});

statusFilter.addEventListener("change", () => {
  currentPage = 0;
  fetchCalls();
});

prevPage.addEventListener("click", () => {
  if (currentPage > 0) { currentPage--; fetchCalls(); }
});

nextPage.addEventListener("click", () => {
  currentPage++;
  fetchCalls();
});

// === Transcript Modal ===
async function showTranscript(callSid) {
  modalBackdrop.classList.add("open");
  modalBody.innerHTML = '<p class="no-transcript"><span class="spinner"></span> Loading...</p>';
  modalTitle.textContent = "Call Transcript";

  try {
    const res = await fetch(`${API}/calls/${encodeURIComponent(callSid)}`);
    const call = await res.json();

    modalTitle.textContent = `Call from ${escapeHtml(formatPhone(call.from_number))} \u2014 ${escapeHtml(formatTime(call.started_at))}`;

    const transcript = call.transcript || [];

    if (transcript.length === 0) {
      modalBody.innerHTML = '<p class="no-transcript">No transcript recorded for this call</p>';
      return;
    }

    modalBody.innerHTML = transcript.map((turn) => {
      const roleClass = turn.role === "caller" ? "caller" : "assistant";
      const label = turn.role === "caller" ? "Caller" : "AI Assistant";
      return `<div class="chat-bubble ${roleClass}">
        <div class="chat-label">${escapeHtml(label)}</div>
        <div>${escapeHtml(turn.content)}</div>
        ${turn.timestamp ? `<div class="bubble-time">${escapeHtml(formatTime(turn.timestamp))}</div>` : ""}
      </div>`;
    }).join("");
  } catch {
    modalBody.innerHTML = '<p class="no-transcript">Failed to load transcript</p>';
  }
}

modalClose.addEventListener("click", () => {
  modalBackdrop.classList.remove("open");
});

modalBackdrop.addEventListener("click", (e) => {
  if (e.target === modalBackdrop) modalBackdrop.classList.remove("open");
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    modalBackdrop.classList.remove("open");
    authBackdrop.classList.remove("open");
  }
});

// === Init & Auto-refresh ===
function init() {
  fetchHealth();
  fetchConfig();
  fetchCalls();

  setInterval(fetchHealth, 10000);
  setInterval(fetchCalls, 15000);
}

init();
