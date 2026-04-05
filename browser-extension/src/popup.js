/* Lintel Browser Extension — Popup Controller */

const $ = (sel) => document.querySelector(sel);

let config = { apiUrl: "", projectId: "" };
let selectedElement = null;
let currentModificationId = null;
let pollTimer = null;

// --- Lifecycle ---

document.addEventListener("DOMContentLoaded", async () => {
  const stored = await chrome.storage.local.get(["apiUrl", "projectId"]);
  if (stored.apiUrl && stored.projectId) {
    config.apiUrl = stored.apiUrl;
    config.projectId = stored.projectId;
    $("#api-url").value = config.apiUrl;
    $("#project-id").value = config.projectId;
    showSection("select");
  }

  $("#save-config").addEventListener("click", saveConfig);
  $("#start-select").addEventListener("click", startSelection);
  $("#submit-modification").addEventListener("click", submitModification);

  // Listen for element selection from content script
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "ELEMENT_SELECTED") {
      selectedElement = msg.payload;
      showSelectedInfo(msg.payload);
    }
  });
});

// --- Config ---

async function saveConfig() {
  const apiUrl = $("#api-url").value.replace(/\/+$/, "");
  const projectId = $("#project-id").value.trim();
  if (!apiUrl || !projectId) return;

  config = { apiUrl, projectId };
  await chrome.storage.local.set({ apiUrl, projectId });
  showSection("select");
}

// --- Element Selection ---

async function startSelection() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;

  chrome.tabs.sendMessage(tab.id, { type: "START_SELECTION" });
  $("#start-select").textContent = "Click an element on the page...";
  $("#start-select").disabled = true;
}

function showSelectedInfo(payload) {
  const info = `${payload.tagName}${payload.selector ? ` (${payload.selector})` : ""}`;
  $("#selected-info").textContent = info;
  $("#selected-info").classList.remove("hidden");
  $("#start-select").textContent = "Select Element";
  $("#start-select").disabled = false;
  showSection("modify");
}

// --- Modification Submission ---

async function submitModification() {
  const instructions = $("#instructions").value.trim();
  if (!instructions || !selectedElement) return;

  $("#submit-modification").disabled = true;
  $("#submit-modification").textContent = "Submitting...";

  const body = {
    project_id: config.projectId,
    component_path: selectedElement.componentPath || selectedElement.selector || "",
    instructions,
    screenshot_url: selectedElement.screenshotUrl || "",
    selector: selectedElement.selector || "",
    page_url: selectedElement.pageUrl || "",
  };

  try {
    const resp = await fetch(
      `${config.apiUrl}/api/v1/browser-extension/modifications`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();
    currentModificationId = data.id;
    showStatus(data);
    startPolling();
  } catch (err) {
    showError(err.message);
  } finally {
    $("#submit-modification").disabled = false;
    $("#submit-modification").textContent = "Submit";
  }
}

// --- Status Polling ---

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollStatus, 3000);
}

async function pollStatus() {
  if (!currentModificationId) return;
  try {
    const resp = await fetch(
      `${config.apiUrl}/api/v1/browser-extension/modifications/${currentModificationId}`
    );
    if (!resp.ok) return;
    const data = await resp.json();
    showStatus(data);

    // Stop polling on terminal states
    if (["applied", "failed", "rejected"].includes(data.status)) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch {
    // Silently retry on network errors
  }
}

// --- UI Helpers ---

function showSection(name) {
  if (name === "select" || name === "modify") {
    $("#select-section").classList.remove("hidden");
  }
  if (name === "modify") {
    $("#modify-section").classList.remove("hidden");
  }
}

function showStatus(data) {
  const section = $("#status-section");
  section.classList.remove("hidden");

  const badge = $("#status-badge");
  badge.className = data.status;
  badge.textContent = data.status.replace("_", " ");

  if (data.diff) {
    $("#diff-view").textContent = data.diff;
    $("#diff-view").classList.remove("hidden");
  }

  if (data.preview_url) {
    $("#preview-link").innerHTML = `<a href="${data.preview_url}" target="_blank">View Preview</a>`;
    $("#preview-link").classList.remove("hidden");
  }
}

function showError(message) {
  const section = $("#status-section");
  section.classList.remove("hidden");
  const badge = $("#status-badge");
  badge.className = "failed";
  badge.textContent = "error";
  $("#status-message").textContent = message;
}
