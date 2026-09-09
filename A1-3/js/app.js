"use strict";

// Hash navigation also works with the browser's Back and Forward buttons.
const pages = [...document.querySelectorAll(".page")];
const routes = new Set(pages.map((page) => page.id));
let currentPage = "home";
function renderRoute() {
  const route = location.hash.slice(1) || "home";
  const nextPage = routes.has(route) ? route : "home";
  if (currentPage === "breathe" && nextPage !== "breathe") pauseSession();
  if (currentPage === "care" && nextPage !== "care") cancelRecommendation();
  currentPage = nextPage;
  document.body.dataset.page = nextPage;
  for (const page of pages) page.hidden = page.id !== nextPage;
  for (const link of document.querySelectorAll("[data-nav]")) {
    const active = link.dataset.nav === (nextPage === "breathe" ? "relax" : nextPage);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  window.scrollTo({ top: 0, behavior: "instant" });
  document.querySelector("#main").focus({ preventScroll: true });
}
window.addEventListener("hashchange", renderRoute);

// These are the only courses, shared in meaning with the server's allowlist.
const courses = {
  focus: { title: "기본 집중 호흡", audio: "audio/focus.mp3", icon: "leaf" },
  sleep: { title: "편안한 수면 호흡", audio: "audio/sleep.mp3", icon: "moon" },
  relax: { title: "긴장을 푸는 호흡", audio: "audio/relax.mp3", icon: "heart" },
};
let selectedCourse = "focus";
const $ = (selector) => document.querySelector(selector);
const audio = $("#breathing-audio");
const DURATION_MS = 180_000;
const BREATH_MS = 10_000; // A gentle suggestion: 4 seconds in, 6 seconds out.
let elapsedMs = 0;
let startedAt = null;
let timerId = null;
let endTimerId = null;
let playPending = false;
let wantsPlayback = false;
let playVersion = 0;
let completed = false;
// A gain deadline also silences the audio when a background tab's timers are throttled.
let audioContext = null;
let volumeGain = null;
let deadlineGain = null;

function elapsedNow() {
  return Math.min(DURATION_MS, elapsedMs + (startedAt === null ? 0 : performance.now() - startedAt));
}
function formatTime(ms) {
  const seconds = Math.floor(ms / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
function updateGuide(ms) {
  const breathing = startedAt !== null;
  const phase = ms % BREATH_MS;
  const inhaling = phase < 4000;
  const label = completed ? "쉼을 마쳤어요" : breathing ? (inhaling ? "천천히 들이마세요" : "편안하게 내쉬세요") : (ms > 0 ? "잠시 쉬어가는 중" : "준비되면 시작해요");
  // Change the live region only when the phase changes, not on every timer tick.
  if ($("#breath-instruction").textContent !== label) $("#breath-instruction").textContent = label;
  $("#breath-caption").textContent = breathing ? "편안한 만큼, 천천히" : "나만의 속도로";
  $("#breath-count").textContent = breathing ? String(Math.ceil((inhaling ? 4000 - phase : BREATH_MS - phase) / 1000)) : "RE:ST";
  const progress = inhaling ? phase / 4000 : 1 - (phase - 4000) / 6000;
  const eased = (1 - Math.cos(Math.PI * progress)) / 2;
  $("#breath-orb").style.setProperty("--breath-scale", String(1 + eased * 0.18));
}
function renderPlayer() {
  const ms = elapsedNow();
  $("#elapsed").textContent = formatTime(ms);
  $("#session-progress").value = ms / 1000;
  $("#play-label").textContent = playPending ? "사운드 준비 중" : wantsPlayback ? "일시정지" : elapsedMs > 0 ? "이어서 호흡하기" : "호흡 시작";
  $("#play-symbol").textContent = wantsPlayback ? "Ⅱ" : "▷";
  $("#toggle-play").disabled = playPending || completed;
  updateGuide(ms);
}
function silenceDeadline() {
  if (!deadlineGain) return;
  deadlineGain.gain.cancelScheduledValues(audioContext.currentTime);
  deadlineGain.gain.setValueAtTime(0, audioContext.currentTime);
}
function freezeClock() {
  if (startedAt !== null) elapsedMs = elapsedNow();
  startedAt = null;
  clearInterval(timerId);
  clearTimeout(endTimerId);
  timerId = null;
  endTimerId = null;
  silenceDeadline();
}
function completeSession() {
  freezeClock();
  elapsedMs = DURATION_MS;
  completed = true;
  wantsPlayback = false;
  playPending = false;
  playVersion += 1;
  audio.pause();
  audio.currentTime = 0;
  renderPlayer();
  $("#completion").hidden = false;
  // The overlay must not leave covered controls reachable by keyboard.
  for (const selector of ["#toggle-play", "#restart-session", "#mute-audio", "#volume"]) $(selector).disabled = true;
  if (currentPage === "breathe") $("#completion").focus({ preventScroll: true });
}
function startClock() {
  if (!wantsPlayback || completed || startedAt !== null) return;
  startedAt = performance.now();
  const remainingMs = DURATION_MS - elapsedMs;
  if (deadlineGain) {
    const now = audioContext.currentTime;
    deadlineGain.gain.cancelScheduledValues(now);
    deadlineGain.gain.setValueAtTime(1, now);
    deadlineGain.gain.setValueAtTime(1, now + Math.max(0, (remainingMs - 500) / 1000));
    deadlineGain.gain.linearRampToValueAtTime(0, now + remainingMs / 1000);
  }
  timerId = setInterval(() => {
    if (elapsedNow() >= DURATION_MS) completeSession();
    else renderPlayer();
  }, 100);
  endTimerId = setTimeout(completeSession, remainingMs);
  renderPlayer();
}
function pauseSession() {
  playVersion += 1; // Invalidates a pending audio.play() when leaving or resetting.
  wantsPlayback = false;
  playPending = false;
  freezeClock();
  audio.pause();
  renderPlayer();
}
function resetSession() {
  pauseSession();
  elapsedMs = 0;
  completed = false;
  audio.currentTime = 0;
  $("#completion").hidden = true;
  $("#player-error").textContent = "";
  for (const selector of ["#toggle-play", "#restart-session", "#mute-audio", "#volume"]) $(selector).disabled = false;
  renderPlayer();
}
function applyVolume() {
  const value = Number($("#volume").value) / 100;
  // Use a gain node on browsers where HTMLAudioElement volume is restricted.
  if (volumeGain) volumeGain.gain.value = audio.muted ? 0 : value;
  else audio.volume = value;
  $("#volume-value").textContent = `${Math.round(value * 100)}%`;
  $("#mute-audio").setAttribute("aria-pressed", String(audio.muted));
  $("#mute-audio").setAttribute("aria-label", audio.muted ? "음소거 해제" : "음소거");
}
function prepareAudioGraph() {
  if (!audioContext && (window.AudioContext || window.webkitAudioContext)) {
    const Context = window.AudioContext || window.webkitAudioContext;
    audioContext = new Context();
    volumeGain = audioContext.createGain();
    deadlineGain = audioContext.createGain();
    audioContext.createMediaElementSource(audio).connect(volumeGain).connect(deadlineGain).connect(audioContext.destination);
    audio.volume = 1;
    applyVolume();
  }
  return audioContext?.resume();
}
async function playSession() {
  if (playPending || completed) return;
  const version = ++playVersion;
  wantsPlayback = true;
  playPending = true;
  $("#player-error").textContent = "";
  renderPlayer();
  // Call both from the click event; don't wait for an API or fetch before audio.play().
  let loadingTimeout;
  try {
    if (audio.error) audio.load();
    const resumed = prepareAudioGraph();
    const playing = audio.play();
    await Promise.race([
      Promise.all([resumed, playing]),
      new Promise((_, reject) => { loadingTimeout = setTimeout(() => reject(new Error("AudioLoadTimeout")), 15000); }),
    ]);
    if (version !== playVersion) return;
    playPending = false;
    startClock();
    renderPlayer();
  } catch (error) {
    if (version !== playVersion) return;
    pauseSession();
    $("#player-error").textContent = "사운드를 불러오지 못했어요. 연결을 확인하고 다시 시작해주세요.";
    console.warn("[RE:ST audio]", { kind: error.name || "AudioError" });
  } finally {
    clearTimeout(loadingTimeout);
  }
}
function chooseCourse(id) {
  if (!Object.hasOwn(courses, id)) return;
  if (id !== selectedCourse || completed) resetSession();
  selectedCourse = id;
  $(`input[name="course"][value="${id}"]`).checked = true;
  $("#breathe-title").textContent = courses[id].title;
  if (audio.getAttribute("src") !== courses[id].audio) audio.src = courses[id].audio;
}
for (const radio of document.querySelectorAll('input[name="course"]')) {
  radio.addEventListener("change", () => chooseCourse(radio.value));
}
$("#open-player").addEventListener("click", () => {
  resetSession();
  chooseCourse(selectedCourse);
  location.hash = "breathe";
});
$("#toggle-play").addEventListener("click", () => wantsPlayback ? pauseSession() : playSession());
$("#restart-session").addEventListener("click", () => { resetSession(); playSession(); });
$("#repeat-session").addEventListener("click", () => { resetSession(); $("#toggle-play").focus(); playSession(); });
$("#mute-audio").addEventListener("click", () => { audio.muted = !audio.muted; applyVolume(); });
$("#volume").addEventListener("input", () => { audio.muted = false; applyVolume(); });
audio.addEventListener("playing", startClock);
audio.addEventListener("waiting", () => { if (wantsPlayback) { freezeClock(); renderPlayer(); } });
audio.addEventListener("pause", () => { if (wantsPlayback) pauseSession(); });
audio.addEventListener("error", () => {
  pauseSession();
  $("#player-error").textContent = "사운드를 불러오지 못했어요. 연결을 확인하고 다시 시작해주세요.";
  console.warn("[RE:ST audio]", { mediaErrorCode: audio.error?.code });
});
window.addEventListener("pagehide", pauseSession);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && wantsPlayback && elapsedNow() >= DURATION_MS) completeSession();
});

// RE:ST Care: a real server response only. No fallback recommendation or browser key.
const careForm = $("#care-form");
const careButton = $("#recommend-button");
const careStatus = $("#care-status");
let requestController = null;
let recommendedCourse = null;
function setCareStatus(message, state = "") {
  careStatus.textContent = message;
  careStatus.className = `form-status ${state}`;
}
function cancelRecommendation() {
  if (!requestController) return;
  requestController.abort();
  requestController = null;
  careButton.disabled = false;
  careForm.removeAttribute("aria-busy");
  setCareStatus("");
}
$("#situation").addEventListener("input", () => {
  $("#situation-count").textContent = `${$("#situation").value.length} / 300`;
});
for (const suggestion of document.querySelectorAll("[data-need]")) {
  suggestion.addEventListener("click", () => { $("#need").value = suggestion.dataset.need; $("#need").focus(); });
}
careForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (requestController) return;
  const formData = new FormData(careForm);
  const payload = Object.fromEntries(["environment", "situation", "need"].map((field) => [field, String(formData.get(field) || "").trim()]));
  const limits = { environment: 40, situation: 300, need: 150 };
  const invalid = Object.keys(limits).find((key) => !payload[key] || payload[key].length > limits[key]);
  if (invalid) {
    setCareStatus("조금만 더 알려주시면 지금 필요한 쉼을 찾아드릴게요.", "error");
    careForm.querySelector(`[name="${invalid}"]`).focus();
    return;
  }
  const controller = new AbortController();
  requestController = controller;
  careButton.disabled = true;
  careForm.setAttribute("aria-busy", "true");
  setCareStatus("당신에게 맞는 쉼을 찾고 있어요...", "loading");
  let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 25000);
  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
      cache: "no-store",
    });
    const data = await response.json();
    if (controller.signal.aborted || requestController !== controller) return;
    if (!response.ok) {
      console.warn("[RE:ST Care]", { status: response.status, code: data.error?.code || "API_ERROR", requestId: data.request_id });
      if (data.error?.code === "NOT_CONFIGURED") {
        setCareStatus("RE:ST Care 연결을 준비하고 있어요. 지금은 Personal에서 원하는 호흡을 직접 골라주세요.", "error");
      } else if (data.error?.code === "TIMEOUT") {
        setCareStatus("쉼을 찾는 데 시간이 조금 걸리고 있어요. 잠시 후 다시 시도해주세요.", "error");
      } else {
        setCareStatus("잠시 연결이 고요해졌어요. 조금 뒤 다시 시도해주세요.", "error");
      }
      return;
    }
    if (!Object.hasOwn(courses, data.course_id) || typeof data.reason !== "string" || !data.reason.trim() || data.reason.length > 240 || data.course !== courses[data.course_id].title) {
      throw new Error("InvalidRecommendation");
    }
    recommendedCourse = data.course_id;
    $("#result-title").textContent = `${courses[data.course_id].title}을 추천해요.`;
    $("#result-reason").textContent = data.reason;
    $("#result-symbol").setAttribute("href", `#i-${courses[data.course_id].icon}`);
    $("#care-input").hidden = true;
    $("#care-result").hidden = false;
    $("#care-result").focus({ preventScroll: true });
    setCareStatus("");
  } catch (error) {
    if (requestController !== controller) return;
    if (timedOut) {
      setCareStatus("쉼을 찾는 데 시간이 조금 걸리고 있어요. 잠시 후 다시 시도해주세요.", "error");
    } else if (error.name !== "AbortError") {
      setCareStatus("잠시 연결이 고요해졌어요. 조금 뒤 다시 시도해주세요.", "error");
    }
    console.warn("[RE:ST Care]", { kind: timedOut ? "Timeout" : error.name });
  } finally {
    clearTimeout(timeout);
    if (requestController === controller) {
      requestController = null;
      careButton.disabled = false;
      careForm.removeAttribute("aria-busy");
    }
  }
});
$("#accept-recommendation").addEventListener("click", () => {
  if (recommendedCourse) { chooseCourse(recommendedCourse); location.hash = "relax"; }
});
$("#edit-care").addEventListener("click", () => {
  $("#care-result").hidden = true;
  $("#care-input").hidden = false;
  $("#situation").focus();
});

chooseCourse(selectedCourse);
applyVolume();
renderPlayer();
renderRoute();
