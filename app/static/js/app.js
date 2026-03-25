/**
 * app/static/js/app.js
 * LectureLensAI — Frontend Logic
 *
 * Features:
 *  - Status polling with animated stepper
 *  - Tab switching
 *  - Notes rendering with clickable timestamps
 *  - 3D flashcard flip + live search + clickable timestamps
 *  - YouTube IFrame API seek-to-timestamp
 *  - HTML5 video seek-to-timestamp (local files)
 *  - Copy-to-clipboard on note bullets
 *  - PDF download
 */

"use strict";

/* =========================================================
   Global video state
   ========================================================= */
let ytPlayer      = null;   // YouTube IFrame player instance
let ytReady       = false;  // IFrame API loaded
let videoType     = null;   // "youtube" | "local" | null
let videoPanelOpen = false;

// Called by YouTube IFrame API when ready
window.onYouTubeIframeAPIReady = function () {
  ytReady = true;
};

/* =========================================================
   Results Page — Main Entry Point
   ========================================================= */
function initResultsPage(jobId) {
  if (!jobId) return;
  pollStatus(jobId);
}

/* =========================================================
   Status Polling
   ========================================================= */
const STEP_THRESHOLDS = [
  { min: 0,  max: 20,  stepIndex: 0 },
  { min: 20, max: 45,  stepIndex: 1 },
  { min: 45, max: 65,  stepIndex: 2 },
  { min: 65, max: 82,  stepIndex: 3 },
  { min: 82, max: 100, stepIndex: 4 },
];

let pollInterval = null;

function pollStatus(jobId) {
  pollInterval = setInterval(async () => {
    try {
      const res  = await fetch(`/api/status/${jobId}`);
      const data = await res.json();

      if (data.status === "not_found" || res.status === 404) {
        clearInterval(pollInterval);
        showError("Job not found. Please re-process the lecture.");
        return;
      }

      updateStepper(data.progress || 0, data.step || "");

      if (data.status === "done") {
        clearInterval(pollInterval);
        await loadResults(jobId);
      } else if (data.status === "error") {
        clearInterval(pollInterval);
        showError(data.error || "Processing failed.");
      }
    } catch (e) {
      console.error("Poll error:", e);
    }
  }, 1500);
}

/* =========================================================
   Stepper UI
   ========================================================= */
function updateStepper(progress, stepText) {
  const bar = document.getElementById("progressBar");
  if (bar) bar.style.width = `${progress}%`;

  const label = document.getElementById("currentStep");
  if (label) label.textContent = stepText;

  const steps = document.querySelectorAll(".step-item");
  const threshold = STEP_THRESHOLDS.find(t => progress >= t.min && progress < t.max);
  const activeIdx = threshold ? threshold.stepIndex : (progress >= 100 ? 4 : 0);

  steps.forEach((step, i) => {
    step.classList.remove("active", "done");
    if (i < activeIdx) step.classList.add("done");
    else if (i === activeIdx) step.classList.add("active");
  });
}

/* =========================================================
   Load & Render Results
   ========================================================= */
async function loadResults(jobId) {
  try {
    const res  = await fetch(`/api/results/${jobId}`);
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Failed to load results.");
      return;
    }

    // Mark all steps done
    document.querySelectorAll(".step-item").forEach(s => {
      s.classList.remove("active");
      s.classList.add("done");
    });
    const bar = document.getElementById("progressBar");
    if (bar) bar.style.width = "100%";

    await sleep(500);
    document.getElementById("stepperSection").classList.add("hidden");
    document.getElementById("resultsSection").classList.remove("hidden");

    // Header title
    const titleEl = document.getElementById("lectureTitle");
    if (titleEl) titleEl.textContent = data.title || "Lecture";

    // Init video player
    initVideoPlayer(data.video_url, data.video_type, jobId);

    // Render content
    renderNotes(data.notes || []);
    renderFlashcards(data.flashcards || []);
    setupExport(jobId, data);
    initTabs();
    initFlashcardSearch();
    initChat(jobId);

  } catch (e) {
    showError("Failed to load results. Please refresh.");
    console.error(e);
  }
}

/* =========================================================
   Video Player
   ========================================================= */

function initVideoPlayer(vUrl, vType, jobId) {
  videoType = vType;

  const toggleBtn = document.getElementById("videoToggleBtn");

  if (!vUrl && vType !== "local") {
    // No video available — hide the button
    if (toggleBtn) toggleBtn.style.display = "none";
    return;
  }

  if (vType === "youtube" && vUrl) {
    // Extract video ID from embed URL
    const match = vUrl.match(/embed\/([a-zA-Z0-9_-]{11})/);
    const videoId = match ? match[1] : null;
    if (!videoId) return;

    // Store for later (player created when panel opens)
    window._ytVideoId = videoId;

  } else if (vType === "local") {
    const src = `/api/video/${jobId}`;
    const vid = document.getElementById("localVideo");
    if (vid) vid.src = src;
  }

  if (toggleBtn) toggleBtn.style.display = "inline-flex";
}

function toggleVideoPanel() {
  const panel   = document.getElementById("videoPanel");
  const btn     = document.getElementById("videoToggleBtn");
  if (!panel) return;

  videoPanelOpen = !videoPanelOpen;
  panel.classList.toggle("hidden", !videoPanelOpen);

  if (btn) {
    btn.innerHTML = videoPanelOpen
      ? `<i class="fa-solid fa-eye-slash"></i> Hide Video`
      : `<i class="fa-solid fa-play-circle"></i> Watch Lecture`;
  }

  if (videoPanelOpen) {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });

    if (videoType === "youtube" && window._ytVideoId) {
      _ensureYTPlayer(window._ytVideoId);
    } else if (videoType === "local") {
      document.getElementById("ytPlayerWrap").classList.add("hidden");
      document.getElementById("localVideoWrap").classList.remove("hidden");
    }
  }
}

function _ensureYTPlayer(videoId) {
  const wrap = document.getElementById("ytPlayerWrap");
  const localWrap = document.getElementById("localVideoWrap");
  if (wrap) wrap.classList.remove("hidden");
  if (localWrap) localWrap.classList.add("hidden");

  if (ytPlayer) return; // already created

  const createPlayer = () => {
    ytPlayer = new YT.Player("ytPlayer", {
      videoId: videoId,
      playerVars: { autoplay: 0, rel: 0, modestbranding: 1 },
      events: {
        onReady: () => { console.log("[LectureLens] YouTube player ready"); }
      }
    });
  };

  if (ytReady) {
    createPlayer();
  } else {
    // Poll until API is ready
    const check = setInterval(() => {
      if (ytReady) {
        clearInterval(check);
        createPlayer();
      }
    }, 200);
  }
}

/* ──────────────────────────────────────────────
   seekVideo(seconds) — called by timestamp clicks
   ────────────────────────────────────────────── */
function seekVideo(seconds) {
  // Open panel first if closed
  if (!videoPanelOpen) toggleVideoPanel();

  // Highlight all matching timestamps
  document.querySelectorAll(".ts-btn, .card-ts-btn").forEach(btn => {
    btn.classList.toggle("video-active", parseFloat(btn.dataset.ts) === seconds);
  });

  if (videoType === "youtube") {
    if (ytPlayer && typeof ytPlayer.seekTo === "function") {
      ytPlayer.seekTo(seconds, true);
      ytPlayer.playVideo();
    } else {
      // Player not ready yet — wait and retry
      const retry = setInterval(() => {
        if (ytPlayer && typeof ytPlayer.seekTo === "function") {
          clearInterval(retry);
          ytPlayer.seekTo(seconds, true);
          ytPlayer.playVideo();
        }
      }, 300);
    }
  } else if (videoType === "local") {
    const vid = document.getElementById("localVideo");
    if (vid) {
      vid.currentTime = seconds;
      vid.play();
    }
  }
}

/* =========================================================
   Notes — with clickable timestamp badge
   ========================================================= */
function renderNotes(notes) {
  const grid  = document.getElementById("notesGrid");
  const count = document.getElementById("notesCount");
  if (!grid) return;

  if (count) count.textContent = notes.length;

  if (notes.length === 0) {
    grid.innerHTML = `<p class="no-results-msg">No notes were generated.</p>`;
    return;
  }

  grid.innerHTML = notes.map((note, i) => {
    const seconds  = note.timestamp || 0;
    const tsLabel  = fmtTime(seconds);

    const bullets = (note.bullets || []).map(b => `
      <li>
        <span>${escHtml(b)}</span>
        <button class="bullet-copy" onclick="copyText(this, '${escAttr(b)}')" title="Copy">
          <i class="fa-regular fa-copy"></i>
        </button>
      </li>
    `).join("");

    const tldr = note.tldr
      ? `<div class="note-tldr"><strong>TL;DR &nbsp;</strong>${escHtml(note.tldr)}</div>`
      : "";

    return `
      <div class="note-card" style="animation-delay:${i * 60}ms">
        <div class="note-header">
          <h3 class="note-title">${escHtml(note.title || "Topic")}</h3>
          <button class="ts-btn" data-ts="${seconds}"
                  onclick="seekVideo(${seconds})"
                  title="Jump to ${tsLabel} in the lecture">
            <i class="fa-regular fa-clock"></i> ${tsLabel}
          </button>
        </div>
        <ul class="note-bullets">${bullets}</ul>
        ${tldr}
      </div>
    `;
  }).join("");
}

/* =========================================================
   Flashcards — with clickable timestamp on back
   ========================================================= */
function renderFlashcards(cards) {
  const grid  = document.getElementById("cardsGrid");
  const count = document.getElementById("cardsCount");
  if (!grid) return;

  if (count) count.textContent = cards.length;

  if (cards.length === 0) {
    grid.innerHTML = `<p class="no-results-msg">No flashcards were generated.</p>`;
    return;
  }

  grid.innerHTML = cards.map((card, i) => {
    const seconds = card.timestamp || 0;
    const tsLabel = fmtTime(seconds);

    return `
      <div class="flip-card"
           data-q="${escAttr(card.question || "")}"
           data-a="${escAttr(card.answer || "")}"
           onclick="handleCardClick(event, this)"
           style="animation-delay:${i * 50}ms">
        <div class="flip-card-inner">
          <div class="flip-card-front">
            <span class="card-label card-label-q"><i class="fa-solid fa-circle-question"></i> Question</span>
            <p class="card-text">${escHtml(card.question || "")}</p>
            <span class="card-hint"><i class="fa-solid fa-rotate"></i> Tap to reveal answer</span>
          </div>
          <div class="flip-card-back">
            <span class="card-label card-label-a"><i class="fa-solid fa-lightbulb"></i> Answer</span>
            <p class="card-text">${escHtml(card.answer || "")}</p>
            <button class="card-ts-btn" data-ts="${seconds}"
                    onclick="seekVideo(${seconds})"
                    title="Jump to ${tsLabel} in lecture">
              <i class="fa-regular fa-clock"></i> ${tsLabel} — Jump to lecture
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function handleCardClick(event, card) {
  // Prevent flip if user clicked the timestamp button
  if (event.target.closest(".card-ts-btn")) return;
  card.classList.toggle("flipped");
}

/* =========================================================
   Flashcard Search
   ========================================================= */
function initFlashcardSearch() {
  const input = document.getElementById("cardSearch");
  if (!input) return;

  input.addEventListener("input", () => {
    const q = input.value.toLowerCase().trim();
    const cards = document.querySelectorAll(".flip-card");
    let visible = 0;

    cards.forEach(card => {
      const question = (card.dataset.q || "").toLowerCase();
      const answer   = (card.dataset.a || "").toLowerCase();
      const match    = !q || question.includes(q) || answer.includes(q);
      card.style.display = match ? "" : "none";
      if (match) visible++;
    });

    let msg = document.getElementById("noCardsMsg");
    if (visible === 0 && q) {
      if (!msg) {
        msg = document.createElement("p");
        msg.id = "noCardsMsg";
        msg.className = "no-results-msg";
        msg.style.gridColumn = "1 / -1";
        document.getElementById("cardsGrid").appendChild(msg);
      }
      msg.textContent = `No flashcards match "${input.value}"`;
      msg.style.display = "";
    } else if (msg) {
      msg.style.display = "none";
    }
  });
}

/* =========================================================
   Export
   ========================================================= */
function setupExport(jobId, data) {
  const btn = document.getElementById("downloadBtn");
  if (btn) {
    if (data.pdf_ready) {
      btn.href = `/api/export/${jobId}`;
      btn.style.opacity = "";
      btn.style.pointerEvents = "";
    } else {
      btn.innerHTML = `<i class="fa-solid fa-xmark-circle"></i> PDF Not Available`;
      btn.style.opacity = "0.5";
      btn.style.pointerEvents = "none";
    }
  }

  const stats = document.getElementById("exportStats");
  if (stats) {
    stats.innerHTML = `
      <span class="stat-item">
        <i class="fa-solid fa-file-lines"></i>
        <span class="stat-value">${(data.notes || []).length}</span> topics
      </span>
      <span class="stat-item">
        <i class="fa-solid fa-cards-blank"></i>
        <span class="stat-value">${(data.flashcards || []).length}</span> flashcards
      </span>
    `;
  }
}

/* =========================================================
   Tabs
   ========================================================= */
function initTabs() {
  const btns   = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");

  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      btns.forEach(b => b.classList.remove("active"));
      panels.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = document.getElementById(`panel-${target}`);
      if (panel) panel.classList.add("active");
    });
  });
}

/* =========================================================
   Utility Functions
   ========================================================= */
function showError(msg) {
  const stepper = document.getElementById("stepperSection");
  const errSec  = document.getElementById("errorSection");
  const errMsg  = document.getElementById("errorMessage");

  if (stepper) stepper.classList.add("hidden");
  if (errSec)  errSec.classList.remove("hidden");
  if (errMsg)  errMsg.textContent = msg;
}

function fmtTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escAttr(str) {
  // For HTML attribute values — avoid breaking onclick/data attrs
  return String(str)
    .replace(/\\/g, "\\\\")
    .replace(/'/g, "\\'")
    .replace(/"/g, "&quot;");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function copyText(btn, text) {
  try {
    await navigator.clipboard.writeText(text);
    const icon = btn.querySelector("i");
    if (icon) {
      icon.className = "fa-solid fa-check";
      setTimeout(() => { icon.className = "fa-regular fa-copy"; }, 1800);
    }
  } catch (e) {
    console.error("Copy failed:", e);
  }
}

/* =========================================================
   Chat Panel
   ========================================================= */
let _chatJobId = null;

// Called from initResultsPage to wire up the job id
function initChat(jobId) {
  _chatJobId = jobId;
}

async function sendChatMessage() {
  const input   = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSendBtn");
  const messages = document.getElementById("chatMessages");
  if (!input || !messages) return;

  const text = input.value.trim();
  if (!text || !_chatJobId) return;

  // Disable input while waiting
  input.value = "";
  input.disabled = true;
  if (sendBtn) sendBtn.disabled = true;

  // Append user bubble
  messages.appendChild(_makeBubble("user", escHtml(text)));
  messages.scrollTop = messages.scrollHeight;

  // Append typing indicator
  const typingEl = _makeTyping();
  messages.appendChild(typingEl);
  messages.scrollTop = messages.scrollHeight;

  try {
    const res = await fetch(`/api/chat/${_chatJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    const data = await res.json();
    typingEl.remove();

    if (!res.ok) {
      messages.appendChild(_makeBubble("ai",
        `<i class="fa-solid fa-triangle-exclamation"></i> ${escHtml(data.error || "Something went wrong")}`
      ));
    } else {
      const ts = parseInt(data.timestamp, 10);
      const tsLabel = (ts >= 0) ? fmtTime(ts) : null;

      let html = escHtml(data.answer || "");

      if (tsLabel && ts >= 0) {
        html += `<br><button class="chat-ts-btn" onclick="seekVideo(${ts})" data-ts="${ts}">
          <i class="fa-regular fa-clock"></i> ${tsLabel} — Jump to lecture
        </button>`;
      }

      messages.appendChild(_makeBubble("ai", html));
    }
  } catch (err) {
    typingEl.remove();
    messages.appendChild(_makeBubble("ai",
      `<i class="fa-solid fa-triangle-exclamation"></i> Network error — please try again.`
    ));
    console.error("[Chat] Error:", err);
  }

  input.disabled = false;
  if (sendBtn) sendBtn.disabled = false;
  input.focus();
  messages.scrollTop = messages.scrollHeight;
}

function _makeBubble(role, html) {
  const wrap = document.createElement("div");
  wrap.className = `chat-msg chat-msg--${role}`;
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.innerHTML = html;
  wrap.appendChild(bubble);
  return wrap;
}

function _makeTyping() {
  const wrap = document.createElement("div");
  wrap.className = "chat-msg chat-msg--ai chat-typing";
  wrap.innerHTML = `<div class="chat-bubble">
    <div class="chat-dot"></div>
    <div class="chat-dot"></div>
    <div class="chat-dot"></div>
  </div>`;
  return wrap;
}
