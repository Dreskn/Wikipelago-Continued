const APP_VERSION = "2026.08.03.5";
console.log("Wikipelago web version", APP_VERSION);

/** Hover-prefetch: keep a few parsed pages ready for the next click. */
const WIKI_PREFETCH_MAX_CACHE = 8;
const WIKI_PREFETCH_CONCURRENCY = 2;
const WIKI_PREFETCH_HOVER_MS = 200;

function wikipediaLanguage() {
  const lang = String(state.status?.wikipedia_language || "en").trim().toLowerCase();
  return lang || "en";
}

function wikipediaOrigin() {
  return `https://${wikipediaLanguage()}.wikipedia.org`;
}

/** Non-article namespaces blocked for navigation (toast; never leave the SPA). */
const BLOCKED_WIKI_NAMESPACES = new Set([
  "file", "category", "help", "template", "special", "portal", "talk", "user",
  "wikipedia", "module", "book", "draft", "mediawiki",
]);

/** Plain segment min width + gap used to estimate how many bars fit in the side panel. */
const TRACK_SEG_MIN_PX = 4;
const TRACK_SEG_GAP_PX = 2;
/** Current-round / emphasis segment — matches a typical +N overflow chip. */
const TRACK_EMPHASIS_MIN_PX = 28;
/** Horizontal track padding (each side) — keep outline / end chips uncropped. */
const TRACK_PAD_X_PX = 4;

const DISPLAY_LOCKS = [
  { unlockedKey: "tables_unlocked", randomizeKey: "randomize_tables", lockClass: "lock-tables", label: "Tables", glyph: "Tbl" },
  { unlockedKey: "pictures_unlocked", randomizeKey: "randomize_pictures", lockClass: "lock-pictures", label: "Pictures", glyph: "Pic" },
  { unlockedKey: "incipit_unlocked", randomizeKey: "randomize_incipit", lockClass: "lock-incipit", label: "Lead", glyph: "Led" },
  { unlockedKey: "infoboxes_unlocked", randomizeKey: "randomize_infoboxes", lockClass: "lock-infoboxes", label: "Infoboxes", glyph: "Inf" },
  { unlockedKey: "toc_unlocked", randomizeKey: "randomize_toc", lockClass: "lock-toc", label: "Contents", glyph: "Toc" },
  { unlockedKey: "navboxes_unlocked", randomizeKey: "randomize_navboxes", lockClass: "lock-navboxes", label: "Navboxes", glyph: "Nav" },
  { unlockedKey: "hatnotes_unlocked", randomizeKey: "randomize_hatnotes", lockClass: "lock-hatnotes", label: "Hatnotes", glyph: "Hat" },
  { unlockedKey: "references_unlocked", randomizeKey: "randomize_references", lockClass: "lock-references", label: "References", glyph: "Ref" },
];

const TOOL_ICON_SVGS = {
  back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11H7.8l4.6-4.6L11 5l-7 7 7 7 1.4-1.4L7.8 13H20v-2z"/></svg>',
  reroll: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.1A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.8l-.3-.3A6.5 6.5 0 1 0 14 15.5l.3.3v.8l5 5 1.5-1.5-5-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"/></svg>',
  compass: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm3.7 14.3-2.8-6.3-6.3-2.8 2.8 6.3 6.3 2.8zM12 13.2A1.2 1.2 0 1 1 13.2 12 1.2 1.2 0 0 1 12 13.2z"/></svg>',
  scroll: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 7 9h3v6H7l5 5 5-5h-3V9h3L12 4z"/></svg>',
  searchsanity: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h10v2H4V6zm0 5h16v2H4v-2zm0 5h12v2H4v-2z"/></svg>',
  scrollsanity: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 7 9h3v6H7l5 5 5-5h-3V9h3L12 4z"/></svg>',
  deaths: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a5 5 0 0 0-5 5v1H5v3h1v8h12v-8h1V8h-2V7a5 5 0 0 0-5-5zm-1 10h2v5h-2v-5z"/></svg>',
  deathlink: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 7a4 4 0 1 1 0 8H7v2h1a6 6 0 1 0 0-12h1v2H8zm8 0h-1V5h1a6 6 0 1 1 0 12h-1v-2h1a4 4 0 1 0 0-8z"/></svg>',
  traplink: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 3h2v6h6v2h-6v6h-2v-6H5V9h6V3zm-7 14h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4z"/></svg>',
  bombs: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.7 4.3 13 6H9L7.3 4.3 5.9 5.7 7.2 7H6a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3h12a3 3 0 0 0 3-3v-8a3 3 0 0 0-3-3h-1.2l1.3-1.3-1.4-1.4zM9 11h6v2H9v-2z"/></svg>',
  traps: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 7l10 5 10-5-10-5zm0 9L4.5 7.8 12 4.1l7.5 3.7L12 11zm0 2.2L4 9.5V17l8 4 8-4V9.5l-8 3.7z"/></svg>',
};

const TRAP_TYPE_LABELS = {
  0: "Foggy + Missing Links",
  1: "Foggy Links only",
  2: "Missing Links only",
};

const BOMB_DENSITY_LABELS = {
  0: "few",
  1: "more",
  2: "insane",
};

let debugDisplayEnabled = new URLSearchParams(window.location.search).has("debug");
let debugPanelReady = false;

const SCROLL_SPEED_FACTORS = [0.18, 0.28, 0.42, 0.6, 0.8, 1];
const CONNECTION_STORAGE_KEY = "wikipelago_connection";
const DEFAULT_SERVER = "archipelago.gg:";
const DEFAULT_SLOT = "WikiTester";

const state = {
  sessionId: localStorage.getItem("wikipelago_session_id") || "",
  status: null,
  currentTitle: "",
  /** Lazy DOM clone for Ctrl+F highlight restore (avoids serializing huge pages on every open). */
  baseArticleClone: null,
  clicksUsed: 0,
  announcedGoalComplete: false,
  restoringArticle: false,
  bingoStampSyncKey: "",
  bingoRemoteStampCount: 0,
  bingoUi: null,
  searchOpen: false,
  roundVisitSet: new Set(),
  roundVisitRound: 0,
  rerollBusy: false,
  targetSummaryCache: new Map(),
  targetSummaryTitle: "",
  targetTooltipVisible: false,
  trapQueue: [],
  activeFoggy: false,
  activeMissing: false,
  bombTitles: new Set(),
  handlingDeath: false,
  /** After slot/language switch, open current_start instead of sticky hash/last_page. */
  forceResumeStart: false,
  resumeIdentity: "",
  /** lang::title → { html } (LRU via Map insertion order). */
  wikiHtmlCache: new Map(),
  /** lang::title → in-flight fetch Promise */
  wikiHtmlInflight: new Map(),
  wikiPrefetchQueue: [],
  wikiPrefetchActive: 0,
  wikiPrefetchHoverTimer: null,
  wikiPrefetchHoverTitle: "",
  wikiCacheLanguage: "",
};

const el = {
  connBadge: document.getElementById("connBadge"),
  buildBadge: document.getElementById("buildBadge"),
  articleTitle: document.getElementById("articleTitle"),
  articleBody: document.getElementById("articleBody"),
  searchOverlay: document.getElementById("searchOverlay"),
  pageSearchInput: document.getElementById("pageSearchInput"),
  closeSearchBtn: document.getElementById("closeSearchBtn"),
  searchStatus: document.getElementById("searchStatus"),
  searchLetters: document.getElementById("searchLetters"),
  serverInput: document.getElementById("serverInput"),
  slotInput: document.getElementById("slotInput"),
  passwordInput: document.getElementById("passwordInput"),
  connectBtn: document.getElementById("connectBtn"),
  practiceBtn: document.getElementById("practiceBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  connectionForm: document.getElementById("connectionForm"),
  connectionSummary: document.getElementById("connectionSummary"),
  connectionSummaryLabel: document.getElementById("connectionSummaryLabel"),
  connectedServerText: document.getElementById("connectedServerText"),
  roundsBlock: document.getElementById("roundsBlock"),
  roundText: document.getElementById("roundText"),
  roundsTrack: document.getElementById("roundsTrack"),
  targetText: document.getElementById("targetText"),
  targetHover: document.getElementById("targetHover"),
  targetTooltip: document.getElementById("targetTooltip"),
  rerollTargetBtn: document.getElementById("rerollTargetBtn"),
  rerollTargetMeta: document.getElementById("rerollTargetMeta"),
  goalRow: document.getElementById("goalRow"),
  goalText: document.getElementById("goalText"),
  clicksText: document.getElementById("clicksText"),
  fragmentsBlock: document.getElementById("fragmentsBlock"),
  fragmentsText: document.getElementById("fragmentsText"),
  fragmentsTrack: document.getElementById("fragmentsTrack"),
  compassHint: document.getElementById("compassHint"),
  toolIconsRow: document.getElementById("toolIconsRow"),
  lensesCard: document.getElementById("lensesCard"),
  lensIconsRow: document.getElementById("lensIconsRow"),
  sanityCard: document.getElementById("sanityCard"),
  scrollIconsRow: document.getElementById("scrollIconsRow"),
  letterIconsRow: document.getElementById("letterIconsRow"),
  difficultyCard: document.getElementById("difficultyCard"),
  difficultyIconsRow: document.getElementById("difficultyIconsRow"),
  bingoCard: document.getElementById("bingoCard"),
  bingoBoards: document.getElementById("bingoBoards"),
  bingoMeta: document.getElementById("bingoMeta"),
  lensesItem: document.getElementById("lensesItem"),
  toast: document.getElementById("toast"),
  stuckToggleBtn: document.getElementById("stuckToggleBtn"),
  stuckPanel: document.getElementById("stuckPanel"),
  enableDebugMenuChk: document.getElementById("enableDebugMenuChk"),
};

function loadSavedConnection() {
  try {
    const raw = localStorage.getItem(CONNECTION_STORAGE_KEY);
    if (!raw) return { server: DEFAULT_SERVER, slot: DEFAULT_SLOT };
    const parsed = JSON.parse(raw);
    return {
      server: String(parsed?.server || "").trim() || DEFAULT_SERVER,
      slot: String(parsed?.slot || "").trim() || DEFAULT_SLOT,
    };
  } catch {
    return { server: DEFAULT_SERVER, slot: DEFAULT_SLOT };
  }
}

function saveConnection(server, slot) {
  localStorage.setItem(CONNECTION_STORAGE_KEY, JSON.stringify({
    server: String(server || "").trim(),
    slot: String(slot || "").trim(),
  }));
}

function formatBuildLabel(info) {
  const branch = String(info?.branch || "").trim() || "unknown";
  const commit = String(info?.commit || "").trim();
  const version = String(info?.version || "").trim();
  const isMain = branch === "main" || branch === "master";

  // Production: quiet version tag only. Staging: branch + commit (+ version).
  if (isMain) {
    return version || branch;
  }

  const parts = [branch];
  if (commit) parts.push(commit);
  if (version) parts.push(version);
  return parts.join(" · ");
}

function readEmbeddedBuildInfo() {
  const node = document.getElementById("build-info");
  if (!node?.textContent) return null;
  try {
    return JSON.parse(node.textContent);
  } catch {
    return null;
  }
}

function applyBuildBadge(info) {
  if (!el.buildBadge || !info) return;
  const branch = String(info.branch || "").trim();
  const staging = Boolean(info.staging) || (branch !== "" && !["main", "master"].includes(branch));
  el.buildBadge.textContent = formatBuildLabel(info);
  el.buildBadge.classList.toggle("staging", staging);
  const hoverBits = [
    info.service && `service: ${info.service}`,
    info.commit_full && `commit: ${info.commit_full}`,
    info.version && `client: ${info.version}`,
    `web: ${APP_VERSION}`,
  ].filter(Boolean);
  el.buildBadge.title = hoverBits.join("\n") || "Deploy build";
  if (staging && branch) {
    document.title = `Wikipelago [${branch}]`;
  }
}

async function fetchBuildInfoWithRetry() {
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch("/health", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const info = await response.json();
      if (info?.branch) return info;
      lastError = new Error("health response missing branch");
    } catch (err) {
      lastError = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 350 * (attempt + 1)));
  }
  throw lastError || new Error("build info unavailable");
}

async function loadBuildBadge() {
  if (!el.buildBadge) return;
  const embedded = readEmbeddedBuildInfo();
  if (embedded?.branch && embedded.branch !== "local") {
    applyBuildBadge(embedded);
    return;
  }
  try {
    applyBuildBadge(await fetchBuildInfoWithRetry());
  } catch (err) {
    if (embedded) {
      applyBuildBadge(embedded);
      return;
    }
    el.buildBadge.textContent = "unknown";
    el.buildBadge.title = `Could not load build info (${err})`;
  }
}

const savedConnection = loadSavedConnection();
el.serverInput.value = savedConnection.server;
el.slotInput.value = savedConnection.slot;

let toastTimer = null;
let stickyToastActive = false;
let lastStickyError = "";

function toast(text, kind = "ok", durationMs = 5500) {
  el.toast.textContent = text;
  el.toast.className = `toast ${kind}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = null;
  // durationMs <= 0 keeps the toast visible until the next toast replaces it.
  if (durationMs <= 0) {
    stickyToastActive = true;
    return;
  }
  stickyToastActive = false;
  toastTimer = setTimeout(() => {
    el.toast.className = "toast hidden";
    toastTimer = null;
  }, durationMs);
}

function toastSticky(text, kind = "warn") {
  toast(text, kind, 0);
}

function clearStickyConnectionError() {
  lastStickyError = "";
  if (stickyToastActive && el.toast.classList.contains("warn")) {
    el.toast.className = "toast hidden";
    stickyToastActive = false;
  }
}

function isApConnected() {
  return state.status?.connected_to_ap === true;
}

function isPracticeMode() {
  return state.status?.practice === true;
}

function isPlayable() {
  return isApConnected() || isPracticeMode();
}

function updateConnectionPanel(status) {
  const connected = Boolean(status?.connected_to_ap);
  const practice = Boolean(status?.practice);
  const active = connected || practice;
  if (el.connectionForm) el.connectionForm.classList.toggle("hidden", active);
  if (el.connectionSummary) el.connectionSummary.classList.toggle("hidden", !active);
  if (el.connectionSummaryLabel) {
    el.connectionSummaryLabel.textContent = practice ? "Mode:" : "Server:";
  }
  if (el.connectedServerText) {
    if (practice) el.connectedServerText.textContent = "Practice (no Archipelago)";
    else if (connected) el.connectedServerText.textContent = status.ap_server || el.serverInput?.value?.trim() || "—";
    else el.connectedServerText.textContent = "-";
  }
  if (el.disconnectBtn) {
    el.disconnectBtn.disabled = !active;
    el.disconnectBtn.textContent = practice ? "Exit practice" : "Disconnect";
  }
}

function requireApConnection() {
  if (isApConnected()) return true;
  toast("Connect to Archipelago to play", "warn");
  return false;
}

function requirePlayable() {
  if (isPlayable()) return true;
  toast("Connect to Archipelago or start Practice", "warn");
  return false;
}

function normalizeTitle(title) {
  return String(title || "").replace(/_/g, " ").trim().replace(/\s+/g, " ").toLowerCase();
}

function deathsEnabled() {
  return Boolean(state.status?.deaths);
}

function firstLeadParagraph(text, maxLen = 320) {
  const cleaned = String(text || "").replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  // REST summary extract is already the lead; keep the first paragraph-worth.
  if (cleaned.length <= maxLen) return cleaned;
  const cut = cleaned.slice(0, maxLen);
  const lastStop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  if (lastStop >= 80) return `${cut.slice(0, lastStop + 1).trim()}`;
  return `${cut.trim()}…`;
}

function formatTargetSummary(data) {
  // Plain text only: short description + lead paragraph (no HTML/images).
  const description = String(data?.description || "").replace(/\s+/g, " ").trim();
  const lead = firstLeadParagraph(data?.extract || "");
  if (description && lead) {
    if (normalizeTitle(lead).startsWith(normalizeTitle(description))) return lead;
    return `${description}\n\n${lead}`;
  }
  return description || lead || "";
}

async function fetchTargetSummary(title) {
  const norm = normalizeTitle(title);
  if (!norm || norm === "..." || norm === "goal complete") return "";
  const lang = wikipediaLanguage();
  const key = `${lang}:${norm}`;
  if (state.targetSummaryCache.has(key)) return state.targetSummaryCache.get(key);

  // Prefer action API (same CORS path as article parse; works for all language wikis).
  const params = new URLSearchParams({
    action: "query",
    format: "json",
    formatversion: "2",
    origin: "*",
    redirects: "1",
    prop: "extracts|description",
    exintro: "1",
    explaintext: "1",
    titles: title,
  });
  const res = await fetch(`${wikipediaOrigin()}/w/api.php?${params}`);
  if (!res.ok) throw new Error(`summary HTTP ${res.status}`);
  const payload = await res.json();
  const page = payload?.query?.pages?.[0];
  if (!page || page.missing) throw new Error("summary missing");
  const summary = formatTargetSummary({
    description: page.description || "",
    extract: page.extract || "",
  }) || "No short description available.";
  state.targetSummaryCache.set(key, summary);
  return summary;
}

function hideTargetTooltip() {
  state.targetTooltipVisible = false;
  if (!el.targetTooltip) return;
  el.targetTooltip.classList.add("hidden");
  el.targetTooltip.classList.remove("loading");
  el.targetTooltip.textContent = "";
}

async function showTargetTooltip(title) {
  if (!el.targetTooltip || !title) return;
  state.targetTooltipVisible = true;
  el.targetTooltip.classList.remove("hidden");
  el.targetTooltip.classList.add("loading");
  el.targetTooltip.textContent = "Loading…";
  try {
    const summary = await fetchTargetSummary(title);
    if (!state.targetTooltipVisible || normalizeTitle(title) !== normalizeTitle(state.targetSummaryTitle)) {
      return;
    }
    el.targetTooltip.classList.remove("loading");
    el.targetTooltip.textContent = summary || "No short description available.";
  } catch {
    if (!state.targetTooltipVisible) return;
    el.targetTooltip.classList.remove("loading");
    el.targetTooltip.textContent = "Could not load description.";
  }
}

function bindTargetTooltip() {
  if (!el.targetHover || !el.targetTooltip) return;
  el.targetHover.addEventListener("mouseenter", () => {
    const title = state.targetSummaryTitle;
    if (!title) return;
    showTargetTooltip(title);
  });
  el.targetHover.addEventListener("mouseleave", () => {
    hideTargetTooltip();
  });
  el.targetHover.addEventListener("focusin", () => {
    const title = state.targetSummaryTitle;
    if (!title) return;
    showTargetTooltip(title);
  });
  el.targetHover.addEventListener("focusout", () => {
    hideTargetTooltip();
  });
}

function setTargetSummaryTitle(title) {
  const next = String(title || "").trim();
  if (next === "GOAL COMPLETE" || next === "..." || !next) {
    state.targetSummaryTitle = "";
    hideTargetTooltip();
    if (el.targetHover) el.targetHover.removeAttribute("tabindex");
    return;
  }
  const changed = normalizeTitle(next) !== normalizeTitle(state.targetSummaryTitle);
  state.targetSummaryTitle = next;
  if (el.targetHover) el.targetHover.tabIndex = 0;
  if (changed) {
    hideTargetTooltip();
    // Prefetch so hover feels instant.
    fetchTargetSummary(next).catch(() => {});
  }
}

function updateRerollTargetControls(status) {
  if (!el.rerollTargetBtn || !el.rerollTargetMeta) return;
  const max = Number(status?.target_rerolls_max) || 3;
  const remaining = Number(status?.target_rerolls_remaining);
  const playable = Boolean(status?.connected_to_ap || status?.practice);
  const canReroll = Boolean(status?.can_reroll_target) && !state.rerollBusy;
  el.rerollTargetBtn.disabled = !canReroll;
  if (status?.boss_completed || !playable) {
    el.rerollTargetMeta.textContent = "";
    return;
  }
  if (Number.isFinite(remaining)) {
    el.rerollTargetMeta.textContent = `${Math.max(0, remaining)}/${max} left`;
  } else {
    el.rerollTargetMeta.textContent = "";
  }
}

async function rerollCurrentTarget() {
  if (!requirePlayable() || state.rerollBusy) return;
  if (!state.status?.can_reroll_target) {
    toast("No target rerolls available right now", "warn", 4500);
    return;
  }
  state.rerollBusy = true;
  updateRerollTargetControls(state.status);
  try {
    const result = await api(`/api/session/${state.sessionId}/reroll-target`, "POST", {});
    if (result.status) updateHUD(result.status);
    toast(`Target rerolled → ${result.new_target}`, "ok", 6500);
  } catch (err) {
    toast(`Could not reroll target: ${err.message || err}`, "warn", 6500);
    try { await pollStatus(); } catch { /* ignore */ }
  } finally {
    state.rerollBusy = false;
    if (state.status) updateRerollTargetControls(state.status);
  }
}

function deathLinkEnabled() {
  return Boolean(state.status?.death_link);
}

function linkBombsEnabled() {
  return deathsEnabled() && Boolean(state.status?.link_bombs);
}

function resetRoundVisits(seedTitle = "") {
  state.roundVisitSet = new Set();
  if (seedTitle) state.roundVisitSet.add(normalizeTitle(seedTitle));
}

function syncRoundVisitTracking(status) {
  const roundNum = Number(status?.round) || 0;
  if (roundNum !== state.roundVisitRound) {
    state.roundVisitRound = roundNum;
    // Seed with this round's start only. currentTitle may still be the previous target.
    resetRoundVisits(status?.current_start || "");
  }
}

function titlesMatch(a, b) {
  return normalizeTitle(a) === normalizeTitle(b);
}

async function fetchRandomWikiTitle() {
  const url = `${wikipediaOrigin()}/w/api.php?action=query&list=random&rnnamespace=0&rnlimit=1&format=json&origin=*`;
  const res = await fetch(url);
  const data = await res.json();
  const title = data?.query?.random?.[0]?.title;
  if (!title) throw new Error("No random article");
  return title;
}

async function notifyDeathLink(cause) {
  if (!deathLinkEnabled() || !state.sessionId || !isApConnected()) return;
  try {
    await api(`/api/session/${state.sessionId}/death`, "POST", { cause: cause || "" });
  } catch {
    // Non-fatal: local death still applied.
  }
}

async function applyDeathEffect(reasonText) {
  if (state.handlingDeath) return;
  state.handlingDeath = true;
  // Clear visit tracking immediately so async fetch latency cannot chain more
  // loop-deaths / no-op clicks while handlingDeath blocks applyDeathEffect.
  resetRoundVisits("");
  state.bombTitles = new Set();
  try {
    toast(reasonText || "Death! Jumping to a random article…", "warn", 7000);
    const title = await fetchRandomWikiTitle();
    resetRoundVisits(title);
    await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
  } catch {
    // Still leave visits cleared; seed current page if we never left it.
    resetRoundVisits(state.currentTitle || "");
    toast("Death effect failed to load a random page", "warn");
  } finally {
    state.handlingDeath = false;
  }
}

function queueTrap(trapName) {
  if (trapName !== "Foggy Links" && trapName !== "Missing Links") return;
  state.trapQueue.push(trapName);
  toast(`Trap: ${trapName} (next page)`, "warn", 6500);
}

function consumeTrapQueueForPage(title, status) {
  state.activeFoggy = false;
  state.activeMissing = false;
  if (!state.trapQueue.length) return;
  const target = status?.current_target || "";
  if (titlesMatch(title, target)) return;
  const queued = state.trapQueue.splice(0, state.trapQueue.length);
  state.activeFoggy = queued.includes("Foggy Links");
  state.activeMissing = queued.includes("Missing Links");
}

function applyMissingToLinks(links) {
  if (!Array.isArray(links) || links.length <= 1) return;
  const removeCount = Math.max(1, Math.min(links.length - 1, Math.floor(links.length * 0.3)));
  for (let i = links.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [links[i], links[j]] = [links[j], links[i]];
  }
  for (let i = 0; i < removeCount; i += 1) {
    const a = links[i];
    if (!a?.isConnected) continue;
    const span = document.createElement("span");
    span.textContent = a.textContent;
    span.className = "missing-link";
    a.replaceWith(span);
  }
}

function armBombsOnPage(root, status) {
  state.bombTitles = new Set();
  if (!linkBombsEnabled()) return;
  const target = status?.current_target || "";
  const goal = status?.goal_article || "";
  const eligible = [...root.querySelectorAll("a[data-title]")].filter((a) => {
    const dest = a.dataset.title || "";
    if (!dest) return false;
    if (titlesMatch(dest, target) || titlesMatch(dest, goal)) return false;
    return true;
  });
  if (!eligible.length) return;
  const requested = Number(status?.link_bomb_count) || 1;
  const capped = Math.min(requested, Math.floor(eligible.length / 2));
  if (capped <= 0) return;
  for (let i = eligible.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [eligible[i], eligible[j]] = [eligible[j], eligible[i]];
  }
  for (let i = 0; i < capped; i += 1) {
    state.bombTitles.add(normalizeTitle(eligible[i].dataset.title));
  }
}

async function processPendingEvents(events) {
  if (!Array.isArray(events) || !events.length) return;
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    if (event.type === "death") {
      const who = event.source ? ` (${event.source})` : "";
      await applyDeathEffect(`DeathLink${who}!`);
    } else if (event.type === "trap") {
      queueTrap(event.trap);
    } else if (event.type === "bingo_stamps_updated") {
      // DataStorage Retrieved/SetNotify arrived — unlock merge and repaint from status.
      state.bingoStampSyncKey = "";
      if (state.status) {
        renderBingoHud(state.status);
        saveLocalBingoStamps(state.status);
        void syncBingoStampsToBridge(state.status);
      }
    }
  }
}

function bingoStampCount(map) {
  return Object.values(map || {}).reduce((n, pairs) => n + (Array.isArray(pairs) ? pairs.length : 0), 0);
}

function ownedSearchLetters() {
  return new Set((state.status?.search_letters || []).map((letter) => String(letter).toUpperCase()));
}

function canUseSearch() {
  if (!state.status?.ctrl_f_unlocked) return false;
  return true;
}

function sanitizeSearchInput(raw) {
  const letters = ownedSearchLetters();
  let output = "";
  for (const ch of String(raw || "")) {
    const upper = ch.toUpperCase();
    if (/[A-Z]/.test(upper)) {
      if (!state.status?.searchsanity || letters.has(upper)) {
        output += ch;
      }
    } else {
      output += ch;
    }
  }
  return output;
}

function renderSearchStatus() {
  const letters = [...ownedSearchLetters()].sort();
  el.searchLetters.textContent = `Letters: ${letters.length ? letters.join("") : "-"}`;

  if (!state.status?.ctrl_f_unlocked) {
    el.searchStatus.textContent = "Ctrl+F Lens required";
  } else if (state.status?.searchsanity) {
    el.searchStatus.textContent = "Letter-limited search";
  } else {
    el.searchStatus.textContent = "Search ready";
  }
}

function setIconState(node, stateName) {
  node.classList.remove("item-icon--ok", "item-icon--locked", "item-icon--off");
  node.classList.add(`item-icon--${stateName}`);
}

function makeIconNode({ id, title, svg, extraClass = "" }) {
  const node = document.createElement("div");
  node.className = `item-icon item-icon--locked ${extraClass}`.trim();
  node.dataset.tool = id;
  node.title = title;
  node.innerHTML = `${svg}<span class="item-icon-badge hidden"></span>`;
  return node;
}

function ensureToolIcons() {
  if (!el.toolIconsRow || el.toolIconsRow.dataset.ready === "3") return;
  const tools = [
    { id: "back", title: "Progressive Back", svg: TOOL_ICON_SVGS.back },
    { id: "reroll", title: "Progressive Reroll", svg: TOOL_ICON_SVGS.reroll },
    { id: "search", title: "Ctrl+F Lens", svg: TOOL_ICON_SVGS.search },
    { id: "compass", title: "Wiki Compass", svg: TOOL_ICON_SVGS.compass },
  ];
  el.toolIconsRow.innerHTML = "";
  for (const tool of tools) el.toolIconsRow.appendChild(makeIconNode(tool));
  el.toolIconsRow.dataset.ready = "3";
}

function overflowChipWidthPx(count) {
  // Padding/border (~12px) + "+123" at ~7px/char — keep full labels visible.
  return 12 + (1 + String(Math.max(0, count)).length) * 7;
}

function trackChipMinPx(plan) {
  let width = TRACK_EMPHASIS_MIN_PX;
  for (const p of plan) {
    if (p.overflow > 0) width = Math.max(width, overflowChipWidthPx(p.overflow));
  }
  return width;
}

function estimatePlanWidthPx(plan, chipMinPx = TRACK_EMPHASIS_MIN_PX) {
  let parts = 0;
  let width = 0;
  for (const p of plan) {
    for (let i = 0; i < p.individuals; i += 1) {
      if (parts > 0) width += TRACK_SEG_GAP_PX;
      // Current round uses the same footprint as a +N chip so its outline stays visible.
      width += p.run.current ? chipMinPx : TRACK_SEG_MIN_PX;
      parts += 1;
    }
    if (p.overflow > 0) {
      if (parts > 0) width += TRACK_SEG_GAP_PX;
      width += Math.max(chipMinPx, overflowChipWidthPx(p.overflow));
      parts += 1;
    }
  }
  return width;
}

function rleTrackItems(items) {
  const runs = [];
  for (const item of items) {
    const prev = runs[runs.length - 1];
    const same =
      prev &&
      prev.state === item.state &&
      !prev.current &&
      !item.current;
    if (same) {
      prev.count += 1;
      prev.endLabel = item.label;
    } else {
      runs.push({
        state: item.state,
        current: Boolean(item.current),
        count: 1,
        startLabel: item.label,
        endLabel: item.label,
      });
    }
  }
  return runs;
}

/**
 * Fit run-length groups into the track width. Start fully compressed (one +N
 * chip per multi-item run), then expand individuals while the row still fits.
 */
function trackContentWidthPx(trackEl) {
  const raw = trackEl?.clientWidth || 300;
  let padX = TRACK_PAD_X_PX * 2;
  if (trackEl && typeof getComputedStyle === "function") {
    const style = getComputedStyle(trackEl);
    const left = parseFloat(style.paddingLeft) || 0;
    const right = parseFloat(style.paddingRight) || 0;
    padX = left + right;
  }
  return Math.max(40, raw - padX);
}

function buildTrackPlan(items, trackEl) {
  const avail = trackContentWidthPx(trackEl);
  const runs = rleTrackItems(items);
  const plan = runs.map((run) => {
    if (run.current || run.count === 1) {
      return { run, individuals: run.count, overflow: 0 };
    }
    return { run, individuals: 0, overflow: run.count };
  });

  const expandPriority = (p) => {
    if (p.overflow <= 0) return -1;
    if (p.run.state === "open" || p.run.state === "filled") return 3;
    if (p.run.state === "done") return 2;
    if (p.run.state === "locked" || p.run.state === "empty") return 1;
    return 0;
  };

  const blocked = new Set();
  while (true) {
    let best = -1;
    let bestScore = -1;
    for (let i = 0; i < plan.length; i += 1) {
      if (blocked.has(i)) continue;
      const score = expandPriority(plan[i]);
      if (score > bestScore) {
        bestScore = score;
        best = i;
      }
    }
    if (best < 0) break;
    const p = plan[best];
    p.individuals += 1;
    p.overflow -= 1;
    if (estimatePlanWidthPx(plan, trackChipMinPx(plan)) > avail) {
      p.individuals -= 1;
      p.overflow += 1;
      blocked.add(best);
      continue;
    }
  }

  return { plan, chipMinPx: trackChipMinPx(plan) };
}

function appendTrackSeg(trackEl, { state, current = false, overflowCount = 0, title = "" }) {
  const seg = document.createElement("div");
  seg.className = "seg";
  if (state) seg.classList.add(state);
  if (current) seg.classList.add("current");
  if (overflowCount > 0) {
    seg.classList.add("overflow");
    seg.textContent = `+${overflowCount}`;
  }
  if (title) seg.title = title;
  trackEl.appendChild(seg);
}

function renderPlannedTrack(trackEl, plan, kind, chipMinPx = TRACK_EMPHASIS_MIN_PX) {
  trackEl.innerHTML = "";
  trackEl.style.setProperty("--track-chip-min", `${chipMinPx}px`);
  for (const p of plan) {
    const { run, individuals, overflow } = p;
    // Cleared/filled: keep individuals near the right edge; overflow chip on the left.
    // Locked/empty: individuals on the left; overflow chip on the right.
    const expandFromEnd = run.state === "done" || run.state === "filled";
    const startNum = Number(String(run.startLabel).match(/\d+/)?.[0] || 1);
    const endNum = Number(String(run.endLabel).match(/\d+/)?.[0] || startNum + run.count - 1);

    const appendOverflow = () => {
      if (overflow <= 0) return;
      const hiddenStart = expandFromEnd ? startNum : startNum + individuals;
      const hiddenEnd = expandFromEnd ? endNum - individuals : endNum;
      appendTrackSeg(trackEl, {
        state: run.state,
        overflowCount: overflow,
        title: `${kind}s ${hiddenStart}–${hiddenEnd} (+${overflow} more like this)`,
      });
    };
    const appendIndividuals = () => {
      const individualStart = expandFromEnd ? endNum - individuals + 1 : startNum;
      for (let i = 0; i < individuals; i += 1) {
        appendTrackSeg(trackEl, {
          state: run.state,
          current: Boolean(run.current),
          title: `${kind} ${individualStart + i}`,
        });
      }
    };

    if (expandFromEnd) {
      appendOverflow();
      appendIndividuals();
    } else {
      appendIndividuals();
      appendOverflow();
    }
  }
}

function renderRoundsTrack(status) {
  if (!el.roundsTrack) return;
  if (status?.practice) {
    if (el.roundsBlock) el.roundsBlock.classList.add("hidden");
    el.roundsTrack.innerHTML = "";
    if (el.roundText) el.roundText.textContent = "";
    return;
  }
  if (el.roundsBlock) el.roundsBlock.classList.remove("hidden");
  const total = Math.max(0, Number(status.check_count) || 0);
  const current = Math.max(1, Number(status.round) || 1);
  const completed = Math.max(0, Number(status.rounds_completed) || 0);
  const unlocked = Math.max(0, Number(status.unlocked_rounds) || 0);
  const complete = Boolean(status.boss_completed);
  const items = [];
  for (let i = 1; i <= total; i += 1) {
    let state = "locked";
    if (complete || i <= completed) state = "done";
    else if (i <= unlocked) state = "open";
    items.push({
      state,
      current: !complete && i === current && i > completed,
      label: `Round ${i}`,
    });
  }
  el.roundsTrack.style.gap = `${TRACK_SEG_GAP_PX}px`;
  const roundsPlan = buildTrackPlan(items, el.roundsTrack);
  renderPlannedTrack(el.roundsTrack, roundsPlan.plan, "Round", roundsPlan.chipMinPx);
  if (el.roundText) {
    el.roundText.textContent = complete ? "Complete" : `${current}/${total}`;
  }
}

function renderFragmentsTrack(status) {
  if (!el.fragmentsTrack) return;
  if (status?.practice) {
    if (el.fragmentsBlock) el.fragmentsBlock.classList.add("hidden");
    if (el.goalRow) el.goalRow.classList.add("hidden");
    el.fragmentsTrack.innerHTML = "";
    if (el.fragmentsText) el.fragmentsText.textContent = "";
    return;
  }
  const required = Math.max(0, Number(status.required_fragments) || 0);
  const have = Math.max(0, Math.min(required, Number(status.fragments) || 0));
  // Grand Goal replaces the fragment bar once enough fragments are unlocked.
  const showGoal = Boolean(status.boss_ready) || Boolean(status.boss_completed) || (required > 0 && have >= required);
  if (el.fragmentsBlock) el.fragmentsBlock.classList.toggle("hidden", showGoal);
  if (el.goalRow) el.goalRow.classList.toggle("hidden", !showGoal);
  if (el.goalText && showGoal) {
    const goal = status.goal_article || "...";
    el.goalText.textContent = status.boss_completed ? `${goal} (Complete)` : goal;
  }
  if (showGoal) return;

  const items = [];
  for (let i = 1; i <= required; i += 1) {
    items.push({
      state: i <= have ? "filled" : "empty",
      label: `Fragment ${i}`,
    });
  }
  el.fragmentsTrack.style.gap = `${TRACK_SEG_GAP_PX}px`;
  const fragPlan = buildTrackPlan(items, el.fragmentsTrack);
  renderPlannedTrack(el.fragmentsTrack, fragPlan.plan, "Fragment", fragPlan.chipMinPx);
  if (el.fragmentsText) el.fragmentsText.textContent = `${have}/${required}`;
}

function setToolBadge(node, text) {
  const badge = node?.querySelector(".item-icon-badge");
  if (!badge) return;
  if (text) {
    badge.textContent = text;
    badge.classList.remove("hidden");
  } else {
    badge.textContent = "";
    badge.classList.add("hidden");
  }
}

function renderToolIcons(status) {
  ensureToolIcons();
  if (!el.toolIconsRow) return;
  const back = el.toolIconsRow.querySelector('[data-tool="back"]');
  const reroll = el.toolIconsRow.querySelector('[data-tool="reroll"]');
  const search = el.toolIconsRow.querySelector('[data-tool="search"]');
  const compass = el.toolIconsRow.querySelector('[data-tool="compass"]');

  const backMax = Math.max(0, Number(status.back_depth_max) || 0);
  const backsRemaining = Number(status.backs_remaining);
  const backLeft = Number.isFinite(backsRemaining) ? Math.max(0, backsRemaining) : backMax;
  if (back) {
    setIconState(back, backMax > 0 ? "ok" : "locked");
    setToolBadge(back, backMax > 0 ? `${backLeft}/${backMax}` : "");
    back.title = backMax > 0 ? `Progressive Back ${backLeft}/${backMax}` : "Progressive Back";
  }

  const rerollMax = Math.max(0, Number(status.target_rerolls_max) || 0);
  const rerollRemaining = Number(status.target_rerolls_remaining);
  const rerollLeft = Number.isFinite(rerollRemaining) ? Math.max(0, rerollRemaining) : rerollMax;
  if (reroll) {
    setIconState(reroll, rerollMax > 0 ? "ok" : "locked");
    setToolBadge(reroll, rerollMax > 0 ? `${rerollLeft}/${rerollMax}` : "");
    reroll.title = rerollMax > 0 ? `Progressive Reroll ${rerollLeft}/${rerollMax}` : "Progressive Reroll";
  }

  if (search) setIconState(search, status.ctrl_f_unlocked ? "ok" : "locked");
  if (compass) setIconState(compass, status.compass_unlocked ? "ok" : "locked");
}

function renderLensIcons(status) {
  if (!el.lensIconsRow || !el.lensesCard) return;
  const active = DISPLAY_LOCKS.filter((lock) => Boolean(status?.[lock.randomizeKey]));
  if (!active.length) {
    el.lensesCard.classList.add("hidden");
    el.lensIconsRow.innerHTML = "";
    return;
  }
  el.lensesCard.classList.remove("hidden");
  el.lensIconsRow.innerHTML = "";
  for (const lock of active) {
    const node = document.createElement("div");
    node.className = "item-icon";
    node.title = lock.label;
    setIconState(node, status?.[lock.unlockedKey] ? "ok" : "locked");
    node.textContent = lock.glyph;
    el.lensIconsRow.appendChild(node);
  }
}

function renderSanityUnlocks(status) {
  if (!el.sanityCard) return;
  const showScroll = Boolean(status?.scrollsanity);
  const showLetters = Boolean(status?.searchsanity);
  if (!showScroll && !showLetters) {
    el.sanityCard.classList.add("hidden");
    if (el.scrollIconsRow) el.scrollIconsRow.innerHTML = "";
    if (el.letterIconsRow) el.letterIconsRow.innerHTML = "";
    return;
  }
  el.sanityCard.classList.remove("hidden");

  if (el.scrollIconsRow) {
    if (!showScroll) {
      el.scrollIconsRow.classList.add("hidden");
      el.scrollIconsRow.innerHTML = "";
    } else {
      el.scrollIconsRow.classList.remove("hidden");
      el.scrollIconsRow.innerHTML = "";
      const scroll = makeIconNode({
        id: "scroll",
        title: "Progressive Scroll Speed",
        svg: TOOL_ICON_SVGS.scroll,
      });
      const level = Number(status.scroll_speed_level) || 0;
      setIconState(scroll, level > 0 ? "ok" : "locked");
      const badge = scroll.querySelector(".item-icon-badge");
      if (badge) {
        badge.textContent = `${level}/${status.scroll_speed_upgrades || 0}`;
        badge.classList.remove("hidden");
      }
      scroll.title = `Scroll Speed ${level}/${status.scroll_speed_upgrades || 0}`;
      el.scrollIconsRow.appendChild(scroll);
    }
  }

  if (el.letterIconsRow) {
    if (!showLetters) {
      el.letterIconsRow.classList.add("hidden");
      el.letterIconsRow.innerHTML = "";
    } else {
      el.letterIconsRow.classList.remove("hidden");
      const owned = new Set((status.search_letters || []).map((letter) => String(letter).toUpperCase()));
      el.letterIconsRow.innerHTML = "";
      for (const letter of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
        const chip = document.createElement("span");
        chip.className = "letter-chip";
        chip.textContent = letter;
        if (owned.has(letter)) chip.classList.add("on");
        el.letterIconsRow.appendChild(chip);
      }
    }
  }
}

function renderDifficultyIcons(status) {
  if (!el.difficultyCard || !el.difficultyIconsRow) return;
  const trapCount = Number(status?.trap_count) || 0;
  const bombsOn = Boolean(status?.link_bombs);
  const relevant = Boolean(
    status?.searchsanity
    || status?.scrollsanity
    || status?.deaths
    || status?.death_link
    || status?.trap_link
    || bombsOn
    || trapCount > 0
  );
  if (!relevant) {
    el.difficultyCard.classList.add("hidden");
    el.difficultyIconsRow.innerHTML = "";
    return;
  }
  el.difficultyCard.classList.remove("hidden");
  el.difficultyIconsRow.innerHTML = "";

  const addDiffIcon = ({ id, title, svg, on, extraClass = "", badge = "" }) => {
    const node = makeIconNode({ id, title, svg, extraClass });
    setIconState(node, on ? "ok" : "locked");
    if (!on) node.classList.add("item-icon--dim");
    if (badge) {
      const badgeEl = node.querySelector(".item-icon-badge");
      if (badgeEl) {
        badgeEl.textContent = badge;
        badgeEl.classList.remove("hidden");
      }
    }
    el.difficultyIconsRow.appendChild(node);
  };

  addDiffIcon({
    id: "searchsanity",
    title: status.searchsanity ? "Searchsanity ON" : "Searchsanity off",
    svg: TOOL_ICON_SVGS.searchsanity,
    on: Boolean(status.searchsanity),
  });
  addDiffIcon({
    id: "scrollsanity",
    title: status.scrollsanity ? "Scrollsanity ON" : "Scrollsanity off",
    svg: TOOL_ICON_SVGS.scrollsanity,
    on: Boolean(status.scrollsanity),
  });
  addDiffIcon({
    id: "deaths",
    title: status.deaths ? "Loop deaths ON" : "Loop deaths off",
    svg: TOOL_ICON_SVGS.deaths,
    on: Boolean(status.deaths),
  });
  addDiffIcon({
    id: "deathlink",
    title: status.death_link ? "DeathLink ON" : "DeathLink off",
    svg: TOOL_ICON_SVGS.deathlink,
    on: Boolean(status.death_link),
  });
  addDiffIcon({
    id: "traplink",
    title: status.trap_link ? "TrapLink ON" : "TrapLink off",
    svg: TOOL_ICON_SVGS.traplink,
    on: Boolean(status.trap_link),
  });

  const bombDensity = Number(status.link_bomb_density) || 0;
  const bombCount = Number(status.link_bomb_count) || 0;
  const bombLabel = BOMB_DENSITY_LABELS[bombDensity] || "few";
  const bombNode = makeIconNode({
    id: "bombs",
    title: bombsOn
      ? `Link bombs ON (${bombLabel}, ~${bombCount}/page)`
      : "Link bombs off",
    svg: TOOL_ICON_SVGS.bombs,
    extraClass: bombsOn ? `item-icon--bomb-${bombLabel}` : "",
  });
  setIconState(bombNode, bombsOn ? "ok" : "locked");
  if (!bombsOn) bombNode.classList.add("item-icon--dim");
  if (bombsOn) {
    const badge = bombNode.querySelector(".item-icon-badge");
    if (badge) {
      badge.textContent = String(bombCount);
      badge.classList.remove("hidden");
    }
  }
  el.difficultyIconsRow.appendChild(bombNode);

  const trapType = Number(status.trap_type) || 0;
  const trapTypeLabel = TRAP_TYPE_LABELS[trapType] || TRAP_TYPE_LABELS[0];
  const trapsOn = trapCount > 0;
  addDiffIcon({
    id: "traps",
    title: trapsOn
      ? `Traps: ${trapCount}× (${trapTypeLabel})`
      : "Traps off (0 in pool)",
    svg: TOOL_ICON_SVGS.traps,
    on: trapsOn,
    badge: trapsOn ? String(trapCount) : "",
  });
}

function formatBingoCompletionParts(bingoCompleted) {
  if (!Array.isArray(bingoCompleted) || !bingoCompleted.length) return [];
  return bingoCompleted.map((line) => {
    const label = String(line?.label || "Bingo line").trim() || "Bingo line";
    const sent = String(line?.sent_text || "").trim();
    return sent ? `${label} complete — ${sent}` : `${label} complete`;
  });
}

function toastBingoCompletions(bingoCompleted) {
  const parts = formatBingoCompletionParts(bingoCompleted);
  if (!parts.length) return;
  toast(parts.join(" · "), "ok", 7500);
}

function bingoCellInCompletedLine(row, col, gridSize, lines) {
  if (!lines || typeof lines !== "object") return false;
  if (lines.full) return true;
  if (lines[`row_${row + 1}`]) return true;
  if (lines[`col_${col + 1}`]) return true;
  if (lines.diag && row === col) return true;
  if (lines.anti && col === gridSize - 1 - row) return true;
  return false;
}

function bingoBoardsFromStatus(status) {
  if (Array.isArray(status?.bingo_letterpairs_boards) && status.bingo_letterpairs_boards.length) {
    return status.bingo_letterpairs_boards;
  }
  if (Array.isArray(status?.bingo_letterpairs_board) && status.bingo_letterpairs_board.length) {
    return [status.bingo_letterpairs_board];
  }
  return [];
}

function normalizeBingoPairList(raw) {
  if (!Array.isArray(raw)) return [];
  return [...new Set(raw.map((pair) => String(pair || "").trim().toUpperCase()).filter(Boolean))];
}

/** Normalize stamped pairs to { boardKey: string[] }. Legacy flat list → board "1". */
function normalizeBingoStampedPairs(raw) {
  if (Array.isArray(raw)) return { "1": normalizeBingoPairList(raw) };
  if (!raw || typeof raw !== "object") return {};
  const out = {};
  for (const [key, value] of Object.entries(raw)) {
    out[String(key)] = normalizeBingoPairList(value);
  }
  return out;
}

/** Normalize stamped cells to { boardKey: [[r,c], ...] }. Legacy flat list → board "1". */
function normalizeBingoStampedCells(raw) {
  const asCells = (list) => (Array.isArray(list) ? list : [])
    .filter((cell) => Array.isArray(cell) && cell.length >= 2)
    .map((cell) => [Number(cell[0]), Number(cell[1])]);
  if (Array.isArray(raw)) return { "1": asCells(raw) };
  if (!raw || typeof raw !== "object") return {};
  const out = {};
  for (const [key, value] of Object.entries(raw)) {
    out[String(key)] = asCells(value);
  }
  return out;
}

/** Normalize line checks to { boardKey: { row_1: bool, ... } }. Flat bool map → board "1". */
function normalizeBingoLinesChecked(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const values = Object.values(raw);
  if (!values.length) return {};
  const looksNested = values.every((value) => value && typeof value === "object" && !Array.isArray(value));
  if (looksNested) {
    const out = {};
    for (const [key, value] of Object.entries(raw)) out[String(key)] = value;
    return out;
  }
  return { "1": raw };
}

function mergeBingoStampMaps(...maps) {
  const out = {};
  for (const map of maps) {
    if (!map || typeof map !== "object") continue;
    for (const [key, pairs] of Object.entries(map)) {
      const boardKey = String(key);
      const merged = new Set([...(out[boardKey] || []), ...normalizeBingoPairList(pairs)]);
      out[boardKey] = [...merged].sort();
    }
  }
  return out;
}

function renderBingoBoardGrid(board, stampedPairs, stampedCells, lines) {
  const n = board.length;
  const pairSet = new Set(normalizeBingoPairList(stampedPairs));
  const cellSet = new Set(
    (stampedCells || [])
      .filter((cell) => Array.isArray(cell) && cell.length >= 2)
      .map((cell) => `${Number(cell[0])},${Number(cell[1])}`)
  );
  const lineMap = lines && typeof lines === "object" ? lines : {};

  const grid = document.createElement("div");
  grid.className = "bingo-grid";
  grid.style.gridTemplateColumns = `repeat(${Math.max(n, 1)}, minmax(0, 1fr))`;
  for (let row = 0; row < n; row += 1) {
    for (let col = 0; col < n; col += 1) {
      const pair = String(board[row]?.[col] || "").toUpperCase();
      const cell = document.createElement("div");
      cell.className = "bingo-cell";
      cell.textContent = pair || "·";
      cell.title = pair || "";
      const stamped = (pair && pairSet.has(pair)) || cellSet.has(`${row},${col}`);
      const lineDone = bingoCellInCompletedLine(row, col, n, lineMap);
      if (lineDone) cell.classList.add("line-complete");
      else if (stamped) cell.classList.add("stamped");
      grid.appendChild(cell);
    }
  }
  return { grid, n, lines: lineMap };
}

function bingoUiStorageKey(status) {
  const server = String(status?.ap_server || "").trim().toLowerCase();
  const slot = String(status?.slot_name || "").trim().toLowerCase();
  if (!server || !slot) return "";
  return `wikipelago_bingo_ui:${server}:${slot}`;
}

function defaultBingoUiState() {
  return { boards: {} };
}

function loadBingoUiState(status) {
  const key = bingoUiStorageKey(status);
  if (!key) return defaultBingoUiState();
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return defaultBingoUiState();
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return defaultBingoUiState();
    const boards = parsed.boards && typeof parsed.boards === "object" ? parsed.boards : {};
    const normalized = {};
    for (const [boardKey, entry] of Object.entries(boards)) {
      if (!entry || typeof entry !== "object") continue;
      normalized[String(boardKey)] = {
        collapsed: Boolean(entry.collapsed),
        autoHidden: Boolean(entry.autoHidden),
      };
    }
    return { boards: normalized };
  } catch {
    return defaultBingoUiState();
  }
}

function saveBingoUiState(status, ui) {
  const key = bingoUiStorageKey(status);
  if (!key || !ui) return;
  localStorage.setItem(key, JSON.stringify({
    boards: ui.boards || {},
  }));
}

function ensureBingoUiState(status) {
  if (!state.bingoUi) state.bingoUi = loadBingoUiState(status);
  return state.bingoUi;
}

function isBingoBoardFullyComplete(lines) {
  return Boolean(lines && lines.full);
}

function setBingoBoardCollapsed(status, boardKey, collapsed) {
  const ui = ensureBingoUiState(status);
  const key = String(boardKey);
  const prev = ui.boards[key] || { collapsed: false, autoHidden: false };
  ui.boards[key] = { ...prev, collapsed: Boolean(collapsed) };
  saveBingoUiState(status, ui);
}

function applyBingoAutoHide(status, boardKey, complete) {
  const ui = ensureBingoUiState(status);
  const key = String(boardKey);
  const prev = ui.boards[key] || { collapsed: false, autoHidden: false };
  if (complete && !prev.autoHidden) {
    ui.boards[key] = { collapsed: true, autoHidden: true };
    saveBingoUiState(status, ui);
    return true;
  }
  return Boolean(prev.collapsed);
}

function renderBingoHud(status) {
  if (!el.bingoCard || !el.bingoBoards) return;
  const enabled = Boolean(status?.bingo_letterpairs);
  el.bingoCard.classList.toggle("hidden", !enabled);
  if (!enabled) {
    el.bingoBoards.innerHTML = "";
    if (el.bingoMeta) el.bingoMeta.textContent = "";
    state.bingoUi = null;
    return;
  }

  // Reload UI prefs when slot/server identity changes.
  const uiKey = bingoUiStorageKey(status);
  if (!state.bingoUi || state.bingoUi._key !== uiKey) {
    state.bingoUi = loadBingoUiState(status);
    state.bingoUi._key = uiKey;
  }

  const boards = bingoBoardsFromStatus(status);
  const unlockedRaw = Number(status.bingo_unlocked_boards);
  const unlocked = Number.isFinite(unlockedRaw)
    ? Math.max(0, Math.min(boards.length, unlockedRaw))
    : boards.length;
  const stampedMap = normalizeBingoStampedPairs(status.bingo_stamped_pairs);
  const cellsMap = normalizeBingoStampedCells(status.bingo_stamped_cells);
  const linesMap = normalizeBingoLinesChecked(status.bingo_lines_checked);

  el.bingoBoards.innerHTML = "";
  let totalChecked = 0;
  let totalLines = 0;
  let anySize = 0;

  for (let i = 0; i < unlocked; i += 1) {
    const boardKey = String(i + 1);
    const board = boards[i] || [];
    const lines = linesMap[boardKey] || {};
    const complete = isBingoBoardFullyComplete(lines);
    const collapsed = applyBingoAutoHide(status, boardKey, complete);

    const block = document.createElement("div");
    block.className = `bingo-board-block${collapsed ? " collapsed" : ""}`;
    block.dataset.board = boardKey;

    const header = document.createElement("div");
    header.className = "bingo-board-header";

    const label = document.createElement("p");
    label.className = "bingo-board-label";
    label.textContent = complete ? `Board ${boardKey} · complete` : `Board ${boardKey}`;
    header.appendChild(label);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn-quiet bingo-board-toggle";
    toggle.textContent = collapsed ? "Show" : "Hide";
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.addEventListener("click", () => {
      setBingoBoardCollapsed(status, boardKey, !collapsed);
      renderBingoHud(state.status || status);
    });
    header.appendChild(toggle);
    block.appendChild(header);

    const { grid, n, lines: lineMap } = renderBingoBoardGrid(
      board,
      stampedMap[boardKey] || [],
      cellsMap[boardKey] || [],
      lines
    );
    block.appendChild(grid);
    el.bingoBoards.appendChild(block);

    anySize = Math.max(anySize, n);
    const lineKeys = Object.keys(lineMap);
    totalChecked += lineKeys.filter((key) => Boolean(lineMap[key])).length;
    totalLines += lineKeys.length || (n > 0 ? (2 * n + 3) : 0);
  }

  if (el.bingoMeta) {
    if (!unlocked) {
      el.bingoMeta.textContent = "No boards unlocked";
    } else if (unlocked === 1 && anySize) {
      el.bingoMeta.textContent = `${anySize}×${anySize} · ${totalChecked}/${totalLines} lines`;
    } else if (unlocked > 1) {
      el.bingoMeta.textContent = `${unlocked} boards · ${totalChecked}/${totalLines} lines`;
    } else {
      el.bingoMeta.textContent = "";
    }
  }
}

function scrollLevel() {
  return Math.max(0, Math.min(state.status?.scroll_speed_level || 0, state.status?.scroll_speed_upgrades || 5));
}

function scrollFactor() {
  const level = Math.max(0, Math.min(scrollLevel(), SCROLL_SPEED_FACTORS.length - 1));
  return state.status?.scrollsanity ? SCROLL_SPEED_FACTORS[level] : 1;
}

function closeSearchOverlay() {
  state.searchOpen = false;
  el.searchOverlay.classList.add("hidden");
}

function openSearchOverlay() {
  if (!canUseSearch()) {
    if (!state.status?.ctrl_f_unlocked) toast("Ctrl+F Lens is locked", "warn");
    else toast("Search is locked", "warn");
    return;
  }
  state.searchOpen = true;
  el.searchOverlay.classList.remove("hidden");
  renderSearchStatus();
  el.pageSearchInput.focus();
  el.pageSearchInput.select();
}

function ensureArticleSearchSnapshot() {
  if (state.baseArticleClone || !el.articleBody) return;
  state.baseArticleClone = el.articleBody.cloneNode(true);
}

function clearSearchHighlights() {
  if (!state.baseArticleClone || !el.articleBody) return;
  // Keep the stored snapshot pristine; restore from a fresh copy.
  const restored = state.baseArticleClone.cloneNode(true);
  el.articleBody.replaceChildren();
  while (restored.firstChild) {
    el.articleBody.appendChild(restored.firstChild);
  }
}

function applySearchHighlights(query) {
  ensureArticleSearchSnapshot();
  clearSearchHighlights();
  if (!query) return 0;

  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(escaped, "ig");
  const walker = document.createTreeWalker(el.articleBody, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    if (node.parentElement && node.parentElement.closest("mark")) continue;
    textNodes.push(node);
  }

  let count = 0;
  for (const textNode of textNodes) {
    const text = textNode.nodeValue;
    if (!text || !regex.test(text)) continue;
    regex.lastIndex = 0;

    const frag = document.createDocumentFragment();
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      const mark = document.createElement("mark");
      mark.className = "wiki-search-hit";
      mark.textContent = match[0];
      frag.appendChild(mark);
      lastIndex = match.index + match[0].length;
      count += 1;
    }
    if (lastIndex < text.length) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  }

  const firstHit = el.articleBody.querySelector(".wiki-search-hit");
  if (firstHit) firstHit.scrollIntoView({ block: "center" });
  return count;
}

function progressIdentity() {
  const server = String(state.status?.ap_server || el.serverInput?.value || "").trim().toLowerCase();
  const slot = String(state.status?.slot_name || el.slotInput?.value || "").trim().toLowerCase();
  const lang = wikipediaLanguage();
  if (server && slot) return `${server}::${slot}::${lang}`;
  return `session::${state.sessionId || "pending"}::${lang}`;
}

function storageKey(suffix) {
  return `wikipelago_${suffix}_${progressIdentity()}`;
}

function clearStickyArticleResume() {
  state.forceResumeStart = true;
  state.currentTitle = "";
  state.baseArticleClone = null;
  clearWikiHtmlCache();
  state.targetSummaryCache.clear();
  hideTargetTooltip();
  const path = `${window.location.pathname}${window.location.search}`;
  history.replaceState({ title: "" }, "", path);
}

function bingoStampStorageKey(status) {
  const server = String(status?.ap_server || "").trim().toLowerCase();
  const slot = String(status?.slot_name || "").trim().toLowerCase();
  const boards = bingoBoardsFromStatus(status);
  if (!server || !slot || !boards.length) return "";
  const boardKey = boards
    .map((board) => (Array.isArray(board) ? board.map((row) => (Array.isArray(row) ? row.join("") : "")).join("/") : ""))
    .join("||");
  return `wikipelago_bingo_stamps:${server}:${slot}:${boardKey}`;
}

function loadLocalBingoStamps(storageKeyValue) {
  if (!storageKeyValue) return {};
  try {
    const raw = localStorage.getItem(storageKeyValue);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return normalizeBingoStampedPairs(parsed);
  } catch {
    return {};
  }
}

function saveLocalBingoStamps(status) {
  if (!status?.bingo_letterpairs) return;
  const key = bingoStampStorageKey(status);
  if (!key) return;
  const remote = normalizeBingoStampedPairs(status.bingo_stamped_pairs);
  const local = loadLocalBingoStamps(key);
  const merged = mergeBingoStampMaps(local, remote);
  localStorage.setItem(key, JSON.stringify(merged));
}

async function syncBingoStampsToBridge(status) {
  if (!status?.bingo_letterpairs || !status.connected_to_ap || !state.sessionId) return;
  const key = bingoStampStorageKey(status);
  if (!key) return;

  const local = loadLocalBingoStamps(key);
  const remote = normalizeBingoStampedPairs(status.bingo_stamped_pairs);
  const remoteCount = bingoStampCount(remote);
  // Other device / SetNotify grew remote — allow another local merge pass.
  if (remoteCount > (state.bingoRemoteStampCount || 0)) {
    state.bingoStampSyncKey = "";
  }
  state.bingoRemoteStampCount = Math.max(state.bingoRemoteStampCount || 0, remoteCount);

  const boards = bingoBoardsFromStatus(status);
  const unlockedRaw = Number(status.bingo_unlocked_boards);
  const unlocked = Number.isFinite(unlockedRaw)
    ? Math.max(0, Math.min(boards.length, unlockedRaw))
    : boards.length;
  const payload = {};
  let needsPush = false;
  for (let i = 1; i <= unlocked; i += 1) {
    const boardKey = String(i);
    const localPairs = local[boardKey] || [];
    const remotePairs = new Set(remote[boardKey] || []);
    if (localPairs.some((pair) => !remotePairs.has(pair))) needsPush = true;
    payload[boardKey] = [...new Set([...(remote[boardKey] || []), ...localPairs])].sort();
  }
  for (const boardKey of Object.keys(remote)) {
    if (!payload[boardKey]) payload[boardKey] = [...(remote[boardKey] || [])];
  }

  const storageReady = Boolean(status.bingo_storage_ready);
  // Before DataStorage Retrieved, never push — replace would wipe room stamps.
  if (!storageReady) {
    saveLocalBingoStamps(status);
    return;
  }

  if (state.bingoStampSyncKey === key && !needsPush) {
    saveLocalBingoStamps(status);
    return;
  }

  if (!needsPush) {
    state.bingoStampSyncKey = key;
    saveLocalBingoStamps(status);
    return;
  }

  state.bingoStampSyncKey = key;
  try {
    const result = await api(`/api/session/${state.sessionId}/bingo-stamps`, "POST", {
      stamped_pairs: payload,
    });
    toastBingoCompletions(result.bingo_completed);
    if (result.status) updateHUD(result.status);
  } catch {
    // Allow a later poll/connect to retry.
    state.bingoStampSyncKey = "";
  }
}

function saveLocalProgress() {
  if (!state.sessionId) return;
  if (state.currentTitle) localStorage.setItem(storageKey("last_title"), state.currentTitle);
  localStorage.setItem(storageKey("clicks"), String(state.clicksUsed || 0));
}

function loadSavedTitle() {
  if (!state.sessionId) return "";
  return localStorage.getItem(storageKey("last_title")) || "";
}

function loadSavedClicks() {
  if (!state.sessionId) return 0;
  const raw = localStorage.getItem(storageKey("clicks")) || "0";
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function preferredResumeTitle() {
  if (state.forceResumeStart) {
    state.forceResumeStart = false;
    return state.status?.current_start || "";
  }
  const hashTitle = decodeURIComponent((window.location.hash || "").replace(/^#/, "")).trim();
  if (hashTitle) return hashTitle;
  if (state.status?.last_page) return state.status.last_page;
  if (state.status?.current_start) return state.status.current_start;
  const savedTitle = loadSavedTitle();
  if (savedTitle) return savedTitle;
  // Wait for AP round data — never invent a hard-coded default article.
  return "";
}

function noteResumeIdentityFromStatus(status) {
  const server = String(status?.ap_server || "").trim().toLowerCase();
  const slot = String(status?.slot_name || "").trim().toLowerCase();
  const lang = String(status?.wikipedia_language || "en").trim().toLowerCase() || "en";
  if (!server || !slot) return;
  const identity = `${server}::${slot}::${lang}`;
  if (state.resumeIdentity && state.resumeIdentity !== identity) {
    clearStickyArticleResume();
  }
  state.resumeIdentity = identity;
}

async function api(path, method = "GET", body = null, retryOnInvalidSession = true) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (body) options.body = JSON.stringify(body);
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    const errText = data.error || `HTTP ${res.status}`;
    if (retryOnInvalidSession && String(errText).toLowerCase() === "invalid session") {
      state.sessionId = "";
      localStorage.removeItem("wikipelago_session_id");
      await ensureSession();
      const fixedPath = path.replace(/\/api\/session\/[^/]+/, `/api/session/${state.sessionId}`);
      return api(fixedPath, method, body, false);
    }
    throw new Error(errText);
  }
  return data;
}

async function ensureSession() {
  if (state.sessionId) return;
  const data = await api("/api/session", "POST", {});
  state.sessionId = data.session_id;
  localStorage.setItem("wikipelago_session_id", state.sessionId);
  state.clicksUsed = loadSavedClicks();
}

function updateHUD(status) {
  const wasComplete = state.status?.boss_completed === true;
  const wasConnected = state.status?.connected_to_ap === true;
  const wasPractice = state.status?.practice === true;
  noteResumeIdentityFromStatus(status);
  state.status = status;
  state.clicksUsed = Number.isFinite(status.clicks_used) ? status.clicks_used : state.clicksUsed;
  syncRoundVisitTracking(status);
  if (status.practice) {
    el.connBadge.textContent = "Practice";
    el.connBadge.className = "badge practice";
  } else if (status.connected_to_ap) {
    el.connBadge.textContent = "Connected";
    el.connBadge.className = "badge online";
  } else {
    el.connBadge.textContent = "Offline";
    el.connBadge.className = "badge offline";
  }
  updateConnectionPanel(status);

  if (wasConnected && !status.connected_to_ap && !status.practice) {
    toastSticky("Disconnected. Browsing only until you reconnect.", "warn");
    state.bingoStampSyncKey = "";
    state.bingoRemoteStampCount = 0;
    state.bingoUi = null;
  }
  if (wasPractice && !status.practice && !status.connected_to_ap) {
    clearStickyConnectionError();
  }
  if (!wasConnected && status.connected_to_ap) {
    clearStickyConnectionError();
    toast("Connected to Archipelago", "ok", 4500);
    // /connect returns before AP handshake finishes; restore once we are actually online.
    void restoreArticleView(true);
  }
  if (status.boss_completed) {
    el.targetText.textContent = "GOAL COMPLETE";
    setTargetSummaryTitle("");
  } else {
    el.targetText.textContent = status.current_target || "...";
    setTargetSummaryTitle(status.current_target || "");
  }
  updateRerollTargetControls(status);
  renderRoundsTrack(status);
  renderFragmentsTrack(status);

  el.clicksText.textContent = String(state.clicksUsed);
  el.compassHint.textContent = status.compass_unlocked ? (status.warmer_colder || "Calibrating") : "Locked";
  renderSearchStatus();
  renderToolIcons(status);
  renderLensIcons(status);
  renderSanityUnlocks(status);
  renderDifficultyIcons(status);
  renderBingoHud(status);
  saveLocalBingoStamps(status);
  void syncBingoStampsToBridge(status);
  renderLensStatus(status);
  applyDisplayLocks();
  syncDebugOptionToggles(document.getElementById("debugMenuCard"));

  if (status.boss_completed && !wasComplete && !state.announcedGoalComplete) {
    toast("GOAL COMPLETE! Seed finished.", "ok", 8000);
    state.announcedGoalComplete = true;
  }
  // Connection/auth errors: toast once and keep visible (poll must not spam).
  if (status.last_error) {
    if (status.last_error !== lastStickyError) {
      lastStickyError = status.last_error;
      toastSticky(status.last_error, "warn");
    }
  } else if (status.connected_to_ap) {
    lastStickyError = "";
  }
  saveLocalProgress();
  if (Array.isArray(status.pending_events) && status.pending_events.length) {
    processPendingEvents(status.pending_events);
  }
}

function isDisplayUnlocked(unlockedKey) {
  const status = state.status;
  if (!status || typeof status[unlockedKey] !== "boolean") return true;
  return status[unlockedKey];
}

function applyDisplayLocks() {
  for (const lock of DISPLAY_LOCKS) {
    el.articleBody.classList.toggle(lock.lockClass, !isDisplayUnlocked(lock.unlockedKey));
  }
}

function renderLensStatus(status) {
  if (!el.lensesItem) return;
  const parts = DISPLAY_LOCKS.map((lock) => {
    const unlocked = status?.[lock.unlockedKey];
    if (typeof unlocked !== "boolean") return null;
    return `${lock.label}: ${unlocked ? "On" : "Off"}`;
  }).filter(Boolean);
  el.lensesItem.textContent = parts.length ? parts.join(" · ") : "Native wiki";
}

function setDebugQueryParam(enabled) {
  const url = new URL(window.location.href);
  if (enabled) url.searchParams.set("debug", "");
  else url.searchParams.delete("debug");
  // Keep hash (current article) while toggling debug mode.
  const next = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(window.history.state, "", next);
}

function enableDebugDisplayMenu() {
  debugDisplayEnabled = true;
  setDebugQueryParam(true);
  if (el.enableDebugMenuChk) el.enableDebugMenuChk.checked = true;
  initDebugDisplayPanel();
}

function disableDebugDisplayMenu() {
  debugDisplayEnabled = false;
  debugPanelReady = false;
  setDebugQueryParam(false);
  document.getElementById("debugMenuCard")?.remove();
  if (el.enableDebugMenuChk) el.enableDebugMenuChk.checked = false;
}

async function runDebugAction(action, payload = {}) {
  if (!state.sessionId) await ensureSession();
  if (!isApConnected()) {
    toast("Connect to Archipelago before using debug", "warn");
    return null;
  }
  try {
    const result = await api(`/api/session/${state.sessionId}/debug`, "POST", { action, ...payload });
    if (result.status) updateHUD(result.status);
    if (result.sent_text) toast(result.sent_text, "ok", 6500);
    else toast(`Debug: ${action}`, "ok", 3000);
    return result;
  } catch (err) {
    toast(err?.message || `Debug failed: ${action}`, "warn", 6500);
    return null;
  }
}

function debugBtn(label, onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-quiet debug-btn";
  btn.textContent = label;
  btn.addEventListener("click", onClick);
  return btn;
}

function debugRow(children) {
  const row = document.createElement("div");
  row.className = "debug-row";
  for (const child of children) row.appendChild(child);
  return row;
}

function debugSection(title) {
  const wrap = document.createElement("div");
  wrap.className = "debug-section";
  const h = document.createElement("h3");
  h.textContent = title;
  wrap.appendChild(h);
  return wrap;
}

function syncDebugOptionToggles(card) {
  if (!card || !state.status) return;
  const status = state.status;
  for (const key of ["deaths", "death_link", "link_bombs", "trap_link", "searchsanity", "scrollsanity"]) {
    const input = card.querySelector(`[data-debug-opt="${key}"]`);
    if (input) input.checked = Boolean(status[key]);
  }
  const density = card.querySelector("[data-debug-opt='link_bomb_density']");
  if (density) density.value = String(Number(status.link_bomb_density) || 0);
}

function initDebugDisplayPanel() {
  if (!debugDisplayEnabled || debugPanelReady) return;
  debugPanelReady = true;

  const card = document.createElement("div");
  card.id = "debugMenuCard";
  card.className = "card debug-menu-card";
  card.innerHTML = "<h2>Debug (AP)</h2>";
  const warn = document.createElement("p");
  warn.className = "debug-warn";
  warn.textContent = "Mutates this slot and can send real Archipelago checks / DeathLink / TrapLink. No auth in 0.4.";
  card.appendChild(warn);

  const progress = debugSection("Progress");
  progress.appendChild(debugRow([
    debugBtn("Complete round", () => runDebugAction("complete_round")),
    debugBtn("Fill fragments", () => runDebugAction("fill_fragments")),
  ]));
  progress.appendChild(debugRow([
    debugBtn("Unlock all rounds", () => runDebugAction("unlock_all_rounds")),
    debugBtn("Finish Grand Goal", () => runDebugAction("finish_boss")),
    debugBtn("Reset rerolls", () => runDebugAction("reset_rerolls")),
  ]));
  card.appendChild(progress);

  const items = debugSection("Items / sanities");
  items.appendChild(debugRow([
    debugBtn("Tools", () => runDebugAction("grant_tools")),
    debugBtn("Lenses", () => runDebugAction("grant_lenses")),
    debugBtn("Letters A–Z", () => runDebugAction("grant_letters")),
    debugBtn("Max scroll", () => runDebugAction("grant_scroll")),
  ]));
  const itemSelect = document.createElement("select");
  itemSelect.className = "debug-input";
  for (const name of [
    "Progressive Back", "Progressive Reroll", "Progressive Bingo Card",
    "Wiki Compass", "Ctrl+F Lens",
    "Table Lens", "Picture Lens", "Lead Lens", "Infobox Lens",
    "Contents Lens", "Navbox Lens", "Hatnote Lens", "Reference Lens",
    "Knowledge Fragment", "Round Access", "Progressive Scroll Speed",
    "Foggy Links", "Missing Links",
  ]) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    itemSelect.appendChild(opt);
  }
  items.appendChild(debugRow([
    itemSelect,
    debugBtn("Grant", () => runDebugAction("grant_item", { item: itemSelect.value })),
  ]));
  card.appendChild(items);

  const travel = debugSection("Travel");
  travel.appendChild(debugRow([
    debugBtn("Start", async () => {
      const title = state.status?.current_start;
      if (title) await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
    debugBtn("Target", async () => {
      const title = state.status?.current_target;
      if (title) await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
    debugBtn("Grand Goal", async () => {
      const title = state.status?.goal_article;
      if (title) await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
  ]));
  const targetInput = document.createElement("input");
  targetInput.type = "text";
  targetInput.className = "debug-input debug-input-wide";
  targetInput.placeholder = "Set target title…";
  travel.appendChild(debugRow([
    targetInput,
    debugBtn("Set target", () => runDebugAction("set_target", { title: targetInput.value.trim() })),
  ]));
  travel.appendChild(debugRow([
    debugBtn("Clear visits", () => {
      resetRoundVisits(state.currentTitle || "");
      toast("Visit tracking cleared", "ok", 3000);
    }),
  ]));
  card.appendChild(travel);

  const challenge = debugSection("Challenge toggles");
  const optGrid = document.createElement("div");
  optGrid.className = "debug-opt-grid";
  for (const [key, label] of [
    ["deaths", "Deaths"],
    ["death_link", "DeathLink"],
    ["link_bombs", "Bombs"],
    ["trap_link", "TrapLink"],
    ["searchsanity", "Searchsanity"],
    ["scrollsanity", "Scrollsanity"],
  ]) {
    const lab = document.createElement("label");
    lab.className = "debug-lens-row";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.debugOpt = key;
    input.addEventListener("change", () => {
      runDebugAction("set_options", { [key]: input.checked });
    });
    lab.appendChild(input);
    lab.appendChild(document.createTextNode(` ${label}`));
    optGrid.appendChild(lab);
  }
  challenge.appendChild(optGrid);
  const density = document.createElement("select");
  density.className = "debug-input";
  density.dataset.debugOpt = "link_bomb_density";
  for (const [value, label] of [["0", "Bombs: few"], ["1", "Bombs: more"], ["2", "Bombs: insane"]]) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    density.appendChild(opt);
  }
  density.addEventListener("change", () => {
    runDebugAction("set_options", { link_bomb_density: Number(density.value) || 0 });
  });
  challenge.appendChild(debugRow([density]));
  challenge.appendChild(debugRow([
    debugBtn("Foggy trap", () => runDebugAction("queue_trap", { trap: "Foggy Links" })),
    debugBtn("Missing trap", () => runDebugAction("queue_trap", { trap: "Missing Links" })),
  ]));
  challenge.appendChild(debugRow([
    debugBtn("Send DeathLink", () => runDebugAction("send_death_link", { cause: "Debug DeathLink" })),
    debugBtn("Receive death", () => runDebugAction("receive_death", { cause: "Debug death" })),
  ]));
  card.appendChild(challenge);

  document.querySelector(".side-panel")?.appendChild(card);
  syncDebugOptionToggles(card);
}

function bindStuckHelper() {
  if (el.stuckToggleBtn && el.stuckPanel) {
    el.stuckToggleBtn.addEventListener("click", () => {
      const open = el.stuckPanel.classList.toggle("hidden") === false;
      el.stuckToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    el.stuckToggleBtn.setAttribute("aria-expanded", "false");
  }
  if (el.enableDebugMenuChk) {
    el.enableDebugMenuChk.addEventListener("change", () => {
      if (el.enableDebugMenuChk.checked) {
        enableDebugDisplayMenu();
        toast("Debug menu enabled", "ok", 4000);
      } else {
        disableDebugDisplayMenu();
        toast("Debug menu disabled", "warn", 3500);
      }
    });
  }
  if (debugDisplayEnabled) {
    if (el.stuckPanel) el.stuckPanel.classList.remove("hidden");
    if (el.stuckToggleBtn) el.stuckToggleBtn.setAttribute("aria-expanded", "true");
    enableDebugDisplayMenu();
  }
}


async function pollStatus() {
  try {
    await ensureSession();
    const data = await api(`/api/session/${state.sessionId}/status`);
    updateHUD(data.status);
    if (!state.searchOpen) closeSearchOverlay();
  } catch {
    el.connBadge.textContent = "Offline";
    el.connBadge.className = "badge offline";
  }
}

function sanitizeHtml(root) {
  root.querySelectorAll("script,style,noscript,.mw-editsection").forEach((n) => n.remove());
}

function isExternalHref(href) {
  const value = String(href || "").trim();
  if (!value || value.startsWith("#") || value.startsWith("/wiki/") || value.startsWith("/w/")) return false;
  if (value.startsWith("//")) return !/^\/\/([a-z0-9-]+\.)?wikipedia\.org\//i.test(value);
  if (/^https?:\/\//i.test(value)) return !/^https?:\/\/([a-z0-9-]+\.)?wikipedia\.org\//i.test(value);
  return false;
}

function unwrapElement(node) {
  const parent = node.parentNode;
  if (!parent) {
    node.remove();
    return;
  }
  while (node.firstChild) parent.insertBefore(node.firstChild, node);
  node.remove();
}

function headingLabel(node) {
  return String(node.textContent || "")
    .replace(/\[\s*edit\s*\]/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function isSectionBreak(node) {
  if (!(node instanceof Element)) return false;
  if (node.matches("h2, h3")) return true;
  if (node.classList.contains("mw-heading")) return true;
  if (node.id === "toc" || node.classList.contains("toc") || node.classList.contains("mw-table-of-contents")) return true;
  return false;
}

function markLeadSection(root) {
  root.querySelectorAll(".wiki-lead").forEach((node) => node.classList.remove("wiki-lead"));
  const output = root.querySelector(".mw-parser-output") || root;
  for (const child of [...output.children]) {
    if (isSectionBreak(child)) break;
    if (child.matches(".hatnote, .dablink, .rellink, .infobox, .infobox_v2, table.infobox, table.infobox_v2, .mw-empty-elt, .shortdescription")) {
      continue;
    }
    child.classList.add("wiki-lead");
  }
}

function markNamedSections(root, names, className) {
  root.querySelectorAll(`.${className}`).forEach((node) => node.classList.remove(className));
  const output = root.querySelector(".mw-parser-output") || root;
  const wanted = new Set(names.map((name) => name.toLowerCase()));
  let marking = false;
  for (const child of [...output.children]) {
    if (isSectionBreak(child)) {
      const label = headingLabel(child);
      marking = [...wanted].some((name) => label === name || label.startsWith(`${name} `));
    }
    if (marking) child.classList.add(className);
  }
}

function prepareArticleHtml(root, options = {}) {
  sanitizeHtml(root);
  markLeadSection(root);
  markNamedSections(root, ["see also"], "wiki-section-seealso");
  markNamedSections(root, ["external links", "external link"], "wiki-section-external");
  markNamedSections(root, ["references", "notes", "citations"], "wiki-section-references");
  wrapTables(root);
  processArticleLinks(root, options);
  applyDisplayLocks();
}

function neutralizeTableChromeColors(el) {
  // Drop wiki hard-coded colors so the dark client theme controls contrast.
  el.removeAttribute("bgcolor");
  el.removeAttribute("background");
  el.removeAttribute("color");
  if (!el.style) return;
  el.style.removeProperty("background");
  el.style.removeProperty("background-color");
  el.style.removeProperty("background-image");
  el.style.removeProperty("color");
}

function wrapTables(root) {
  root.querySelectorAll("table").forEach((table) => {
    table.removeAttribute("width");
    if (table.style) {
      table.style.removeProperty("width");
      table.style.removeProperty("min-width");
      table.style.removeProperty("max-width");
    }
    neutralizeTableChromeColors(table);
    table
      .querySelectorAll("caption, colgroup, col, thead, tbody, tfoot, tr, th, td")
      .forEach(neutralizeTableChromeColors);
    if (table.parentElement?.classList.contains("table-scroll")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    table.replaceWith(wrap);
    wrap.appendChild(table);
  });
}

function wikiTitleFromHref(href) {
  // Path only — fragments/queries are not part of the article title, and
  // section anchors sometimes contain bare "%" that break decodeURIComponent.
  const wikiPart = href.replace(/^\/wiki\//, "").split("#", 1)[0].split("?", 1)[0];
  if (!wikiPart) return "";
  let decoded;
  try {
    decoded = decodeURIComponent(wikiPart);
  } catch {
    decoded = wikiPart.replace(/%[0-9A-Fa-f]{2}/g, (m) => {
      try {
        return decodeURIComponent(m);
      } catch {
        return m;
      }
    });
  }
  return decoded.replace(/_/g, " ");
}

function wikiNamespace(title) {
  if (!String(title || "").includes(":")) return "";
  return title.split(":", 1)[0].toLowerCase();
}

function isBlockedWikiTitle(title) {
  const ns = wikiNamespace(title);
  return Boolean(ns && BLOCKED_WIKI_NAMESPACES.has(ns));
}

function toastBlockedWikiPage() {
  toast("That type of page is not allowed in Wikipelago", "warn");
}

function processArticleLinks(root, options = {}) {
  // One pass: strip externals, rewrite /wiki links, optional foggy/missing traps.
  const foggy = Boolean(options.foggy);
  const missing = Boolean(options.missing);
  const playable = missing ? [] : null;

  root.querySelectorAll("a").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (isExternalHref(href)) {
      unwrapElement(a);
      return;
    }
    // /w/... must not keep a host-relative href (would leave the SPA).
    if (href.startsWith("/w/")) {
      a.removeAttribute("data-title");
      a.dataset.blockedNs = "1";
      a.href = "#";
      return;
    }
    if (!href.startsWith("/wiki/")) return;
    const title = wikiTitleFromHref(href);
    if (!title) {
      unwrapElement(a);
      return;
    }
    // Never leave raw /wiki/... hrefs — browser would hit a host 404.
    a.href = "#";
    if (isBlockedWikiTitle(title)) {
      a.removeAttribute("data-title");
      a.dataset.blockedNs = "1";
      return;
    }
    a.removeAttribute("data-blocked-ns");
    a.dataset.title = title;
    if (foggy) {
      a.textContent = "[Link]";
      a.title = "";
    }
    if (playable) playable.push(a);
  });

  if (playable) applyMissingToLinks(playable);
}

function wikiHtmlCacheKey(title) {
  return `${wikipediaLanguage()}::${normalizeTitle(title)}`;
}

function clearWikiHtmlCache() {
  state.wikiHtmlCache.clear();
  state.wikiHtmlInflight.clear();
  state.wikiPrefetchQueue = [];
  state.wikiPrefetchActive = 0;
  state.wikiPrefetchHoverTitle = "";
  if (state.wikiPrefetchHoverTimer) {
    clearTimeout(state.wikiPrefetchHoverTimer);
    state.wikiPrefetchHoverTimer = null;
  }
  state.wikiCacheLanguage = wikipediaLanguage();
}

function ensureWikiHtmlCacheLanguage() {
  const lang = wikipediaLanguage();
  if (state.wikiCacheLanguage && state.wikiCacheLanguage !== lang) {
    clearWikiHtmlCache();
    return;
  }
  if (!state.wikiCacheLanguage) state.wikiCacheLanguage = lang;
}

function storeWikiHtmlCache(title, html) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title);
  if (state.wikiHtmlCache.has(key)) state.wikiHtmlCache.delete(key);
  state.wikiHtmlCache.set(key, { html: String(html || "") });
  while (state.wikiHtmlCache.size > WIKI_PREFETCH_MAX_CACHE) {
    const oldest = state.wikiHtmlCache.keys().next().value;
    state.wikiHtmlCache.delete(oldest);
  }
}

function takeWikiHtmlCache(title) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title);
  const hit = state.wikiHtmlCache.get(key);
  if (!hit) return null;
  // Refresh LRU order.
  state.wikiHtmlCache.delete(key);
  state.wikiHtmlCache.set(key, hit);
  return hit.html;
}

async function fetchWikiHtmlUncached(title) {
  const params = new URLSearchParams({
    action: "parse",
    page: title,
    prop: "text",
    formatversion: "2",
    format: "json",
    origin: "*",
    redirects: "true",
  });
  const url = `${wikipediaOrigin()}/w/api.php?${params}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Wikipedia HTTP ${res.status} (${wikipediaLanguage()})`);
  const data = await res.json();
  if (data?.error) {
    const info = data.error.info || data.error.code || "Article unavailable";
    throw new Error(`${info} [${wikipediaLanguage()}]`);
  }
  if (!data.parse || !data.parse.text) throw new Error(`Article unavailable [${wikipediaLanguage()}]`);
  return data.parse.text;
}

async function fetchWikiHtml(title) {
  ensureWikiHtmlCacheLanguage();
  const cached = takeWikiHtmlCache(title);
  if (cached != null) return cached;

  const key = wikiHtmlCacheKey(title);
  let inflight = state.wikiHtmlInflight.get(key);
  if (!inflight) {
    inflight = (async () => {
      try {
        const html = await fetchWikiHtmlUncached(title);
        storeWikiHtmlCache(title, html);
        return html;
      } finally {
        state.wikiHtmlInflight.delete(key);
      }
    })();
    state.wikiHtmlInflight.set(key, inflight);
  }
  return inflight;
}

function pumpWikiPrefetchQueue() {
  while (
    state.wikiPrefetchActive < WIKI_PREFETCH_CONCURRENCY
    && state.wikiPrefetchQueue.length
  ) {
    const title = state.wikiPrefetchQueue.shift();
    if (!title || isBlockedWikiTitle(title)) continue;
    if (normalizeTitle(title) === normalizeTitle(state.currentTitle)) continue;
    const key = wikiHtmlCacheKey(title);
    if (state.wikiHtmlCache.has(key) || state.wikiHtmlInflight.has(key)) continue;
    state.wikiPrefetchActive += 1;
    fetchWikiHtml(title)
      .catch(() => {})
      .finally(() => {
        state.wikiPrefetchActive = Math.max(0, state.wikiPrefetchActive - 1);
        pumpWikiPrefetchQueue();
      });
  }
}

function prefetchWikiHtml(title) {
  const clean = String(title || "").trim();
  if (!clean || isBlockedWikiTitle(clean)) return;
  if (normalizeTitle(clean) === normalizeTitle(state.currentTitle)) return;
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(clean);
  if (state.wikiHtmlCache.has(key) || state.wikiHtmlInflight.has(key)) return;
  if (state.wikiPrefetchQueue.some((queued) => normalizeTitle(queued) === normalizeTitle(clean))) {
    return;
  }
  state.wikiPrefetchQueue.push(clean);
  // Bound queue so rapid hover doesn't pile up stale titles.
  while (state.wikiPrefetchQueue.length > WIKI_PREFETCH_MAX_CACHE) {
    state.wikiPrefetchQueue.shift();
  }
  pumpWikiPrefetchQueue();
}

function scheduleWikiPrefetchFromHover(title) {
  const clean = String(title || "").trim();
  if (!clean) return;
  if (state.wikiPrefetchHoverTitle === clean && state.wikiPrefetchHoverTimer) return;
  state.wikiPrefetchHoverTitle = clean;
  if (state.wikiPrefetchHoverTimer) clearTimeout(state.wikiPrefetchHoverTimer);
  state.wikiPrefetchHoverTimer = setTimeout(() => {
    state.wikiPrefetchHoverTimer = null;
    prefetchWikiHtml(clean);
  }, WIKI_PREFETCH_HOVER_MS);
}

async function openArticle(title, options = {}) {
  if (!title) return;
  // submitCheck defaults to countAsClick: only in-article wiki clicks may score.
  // Restore/reconnect/hash/back must never complete a round.
  const {
    countAsClick = false,
    submitCheck = countAsClick,
    replaceHistory = false,
    requireConnection = false,
  } = options;
  if (requireConnection && !requirePlayable()) return;
  if (isBlockedWikiTitle(title)) {
    toastBlockedWikiPage();
    return;
  }

  let html;
  try {
    html = await fetchWikiHtml(title);
  } catch (err) {
    const detail = err?.message ? ` (${err.message})` : "";
    toast(`Could not open article: ${title}${detail}`, "warn");
    return;
  }

  try {
    state.currentTitle = title;
    el.articleTitle.textContent = title;
    el.articleBody.innerHTML = html;
    consumeTrapQueueForPage(title, state.status);
    prepareArticleHtml(el.articleBody, {
      foggy: state.activeFoggy,
      missing: state.activeMissing,
    });
    armBombsOnPage(el.articleBody, state.status);
    if (countAsClick || !state.roundVisitSet.size) {
      state.roundVisitSet.add(normalizeTitle(title));
    } else if (!submitCheck) {
      state.roundVisitSet.add(normalizeTitle(title));
    }
    // Drop prior page snapshot; a new one is cloned lazily if Ctrl+F is used.
    state.baseArticleClone = null;
    if (state.searchOpen && el.pageSearchInput.value) {
      const sanitized = sanitizeSearchInput(el.pageSearchInput.value);
      if (sanitized !== el.pageSearchInput.value) el.pageSearchInput.value = sanitized;
      applySearchHighlights(sanitized);
    }

    if (countAsClick) state.clicksUsed += 1;
    el.clicksText.textContent = String(state.clicksUsed);
    saveLocalProgress();

    if (replaceHistory) {
      history.replaceState({ title }, "", `#${encodeURIComponent(title)}`);
    } else {
      history.pushState({ title }, "", `#${encodeURIComponent(title)}`);
    }

    // Always visit/stamp when playable. Only intentional wiki clicks score rounds.
    if (!isPlayable()) {
      if (countAsClick && submitCheck) toast("Disconnected — reconnect to send checks", "warn");
      return;
    }

    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/check`, "POST", {
      page_title: title,
      clicks_used: state.clicksUsed,
      submit_check: Boolean(submitCheck),
    });

    if (submitCheck) {
      if (result.matched && (result.status?.practice || result.practice_rolled)) {
        // Unlimited practice: new target only — stay on this page (AP-style chaining).
        if (result.status) updateHUD(result.status);
        resetRoundVisits(title);
        state.clicksUsed = Number(result.status?.clicks_used) || 0;
        el.clicksText.textContent = String(state.clicksUsed);
        saveLocalProgress();
        return;
      }
      if (result.matched) {
        let msg = `Target hit: ${result.target}`;
        if (result.sent_text) msg += ` — ${result.sent_text}`;
        const bingoParts = formatBingoCompletionParts(result.bingo_completed);
        if (bingoParts.length) msg += ` · ${bingoParts.join(" · ")}`;
        toast(msg, "ok", 8000);
        // Next round starts from its start article — visit set refreshes on round change via HUD.
      } else {
        toastBingoCompletions(result.bingo_completed);
      }
      if (result.locked) toast("Round locked. Find Round Access items.", "warn", 6500);
      if (result.not_connected) toast("Disconnected — reconnect to send checks", "warn", 6500);
    } else {
      toastBingoCompletions(result.bingo_completed);
    }
    if (result.status) updateHUD(result.status);
  } catch (err) {
    // Page is already visible; do not pretend the Wikipedia fetch failed.
    toast(err?.message || "Connected page sync failed", "warn");
  }
}

async function restoreArticleView(force = false) {
  if (!state.status || !isPlayable()) return;
  if (state.handlingDeath) return;
  const desiredTitle = preferredResumeTitle();
  if (!desiredTitle) return;
  if (!force && normalizeTitle(desiredTitle) === normalizeTitle(state.currentTitle)) return;
  if (state.restoringArticle) return;
  state.restoringArticle = true;
  try {
    await openArticle(desiredTitle, { countAsClick: false, replaceHistory: true, requireConnection: true });
  } finally {
    state.restoringArticle = false;
  }
}

el.articleBody.addEventListener("pointerover", (e) => {
  const a = e.target.closest?.("a[data-title]");
  if (!a || !el.articleBody.contains(a)) return;
  // Only fire when entering the link (not bubbling across children repeatedly).
  const related = e.relatedTarget;
  if (related && a.contains(related)) return;
  scheduleWikiPrefetchFromHover(a.dataset.title || "");
});

el.articleBody.addEventListener("click", async (e) => {
  const blocked = e.target.closest("a[data-blocked-ns]");
  if (blocked) {
    e.preventDefault();
    toastBlockedWikiPage();
    return;
  }
  const a = e.target.closest("a[data-title]");
  if (!a) return;
  e.preventDefault();
  if (state.handlingDeath) return;
  const dest = a.dataset.title || "";
  const destNorm = normalizeTitle(dest);
  const target = state.status?.current_target || "";

  // Bomb hit (only on forward wiki clicks).
  if (linkBombsEnabled() && state.bombTitles.has(destNorm) && !titlesMatch(dest, target)) {
    await notifyDeathLink(`${state.status?.slot_name || "Player"} hit a link bomb`);
    await applyDeathEffect("Boom! Link bomb — random page.");
    return;
  }

  // Loop-death: forward revisit of a page already visited this round.
  if (
    deathsEnabled()
    && state.roundVisitSet.has(destNorm)
    && !titlesMatch(dest, target)
  ) {
    await notifyDeathLink(`${state.status?.slot_name || "Player"} looped on Wikipedia`);
    await applyDeathEffect("Loop death! Already visited this round.");
    return;
  }

  openArticle(dest, { countAsClick: true });
});

el.articleBody.addEventListener("wheel", (e) => {
  if (!state.status?.scrollsanity) return;
  e.preventDefault();
  el.articleBody.scrollTop += e.deltaY * scrollFactor();
}, { passive: false });

el.rerollTargetBtn?.addEventListener("click", () => {
  rerollCurrentTarget();
});

async function waitForApConnection(timeoutMs = 10000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    await pollStatus();
    if (isApConnected()) return true;
    if (state.status?.last_error) return false;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  await pollStatus();
  return isApConnected();
}

el.connectBtn.addEventListener("click", async () => {
  try {
    const server = el.serverInput.value.trim();
    const slotName = el.slotInput.value.trim();
    const prevIdentity = state.resumeIdentity;
    saveConnection(server, slotName);
    clearStickyConnectionError();
    await ensureSession();
    await api(`/api/session/${state.sessionId}/connect`, "POST", {
      server,
      slot_name: slotName,
      password: el.passwordInput.value,
    });
    toast("Connecting to Archipelago...", "ok", 4500);
    const online = await waitForApConnection();
    if (!online) {
      toastSticky(state.status?.last_error || "Could not connect to Archipelago", "warn");
      return;
    }
    const nextIdentity = progressIdentity();
    if (prevIdentity && prevIdentity !== nextIdentity) {
      clearStickyArticleResume();
    }
    state.resumeIdentity = nextIdentity;
    await restoreArticleView(true);
  } catch (err) {
    toastSticky(err.message || "Connect failed", "warn");
  }
});

el.practiceBtn?.addEventListener("click", async () => {
  try {
    clearStickyConnectionError();
    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/practice`, "POST", {
      wikipedia_language: "en",
    });
    if (result.status) updateHUD(result.status);
    else await pollStatus();
    const start = state.status?.current_start;
    if (start) {
      await openArticle(start, {
        replaceHistory: true,
        countAsClick: false,
        submitCheck: false,
        requireConnection: true,
      });
    }
  } catch (err) {
    toastSticky(err.message || "Could not start Practice", "warn");
  }
});

el.disconnectBtn?.addEventListener("click", async () => {
  try {
    const leavingPractice = isPracticeMode();
    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/disconnect`, "POST", {});
    if (result.status) updateHUD(result.status);
    else await pollStatus();
    toast(leavingPractice ? "Left Practice" : "Disconnected from Archipelago", "warn", 4500);
  } catch (err) {
    toastSticky(err.message || "Disconnect failed", "warn");
  }
});

el.closeSearchBtn.addEventListener("click", () => {
  el.pageSearchInput.value = "";
  clearSearchHighlights();
  closeSearchOverlay();
});

el.pageSearchInput.addEventListener("input", () => {
  const sanitized = sanitizeSearchInput(el.pageSearchInput.value);
  if (sanitized !== el.pageSearchInput.value) {
    const pos = sanitized.length;
    el.pageSearchInput.value = sanitized;
    el.pageSearchInput.setSelectionRange(pos, pos);
  }
  const hits = applySearchHighlights(el.pageSearchInput.value.trim());
  renderSearchStatus();
  if (el.pageSearchInput.value.trim()) {
    el.searchStatus.textContent = `${hits} match${hits === 1 ? "" : "es"}`;
  }
});

function backBlockedToast() {
  const max = Number(state.status?.back_depth_max) || 0;
  if (max <= 0) toast("Progressive Back is locked", "warn");
  else toast("No backs remaining this round", "warn");
}

function canGoBackNow() {
  return Boolean(state.status?.can_go_back);
}

function rePushCurrentHistory() {
  const title = state.currentTitle || "";
  history.pushState({ title }, "", title ? `#${encodeURIComponent(title)}` : "#");
}

async function consumeBackCharge() {
  if (!state.sessionId) throw new Error("no session");
  const result = await api(`/api/session/${state.sessionId}/use-back`, "POST", {});
  if (result.status) updateHUD(result.status);
  return result;
}

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
    e.preventDefault();
    if (state.searchOpen) {
      el.pageSearchInput.focus();
      el.pageSearchInput.select();
    } else {
      openSearchOverlay();
    }
  }
  if (e.altKey && e.key === "ArrowLeft") {
    if (state.status) {
      e.preventDefault();
      if (!canGoBackNow()) backBlockedToast();
      else history.back();
    }
  }
  if (e.key === "Backspace") {
    const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
    if (!typing && state.status) {
      e.preventDefault();
      if (!canGoBackNow()) backBlockedToast();
      else history.back();
    }
  }
  if (e.key === "Escape" && state.searchOpen) {
    e.preventDefault();
    closeSearchOverlay();
  }
  if (state.status?.scrollsanity && !["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
    const factor = scrollFactor();
    const keyToAmount = {
      ArrowDown: 40,
      ArrowUp: -40,
      PageDown: 320,
      PageUp: -320,
      Home: -1_000_000,
      End: 1_000_000,
      " ": e.shiftKey ? -320 : 320,
    };
    if (Object.prototype.hasOwnProperty.call(keyToAmount, e.key)) {
      e.preventDefault();
      const amount = keyToAmount[e.key];
      if (e.key === "Home") {
        el.articleBody.scrollTop = 0;
      } else if (e.key === "End") {
        el.articleBody.scrollTop = el.articleBody.scrollHeight;
      } else {
        el.articleBody.scrollTop += amount * factor;
      }
    }
  }
});

window.addEventListener("popstate", async (e) => {
  if (state.status && !canGoBackNow()) {
    rePushCurrentHistory();
    backBlockedToast();
    return;
  }
  if (state.status && canGoBackNow()) {
    try {
      await consumeBackCharge();
    } catch (err) {
      rePushCurrentHistory();
      toast(`Could not use back: ${err.message || err}`, "warn");
      return;
    }
  }
  const title = e.state?.title;
  if (title) openArticle(title, { countAsClick: false });
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((err) => {
      console.warn("Service worker registration failed", err);
    });
  });
}

ensureToolIcons();
bindTargetTooltip();
bindStuckHelper();
if (typeof ResizeObserver !== "undefined") {
  let trackResizeTimer = 0;
  const rerenderTracks = () => {
    if (!state.status) return;
    renderRoundsTrack(state.status);
    renderFragmentsTrack(state.status);
  };
  const trackResizeObserver = new ResizeObserver(() => {
    window.clearTimeout(trackResizeTimer);
    trackResizeTimer = window.setTimeout(rerenderTracks, 50);
  });
  if (el.roundsTrack) trackResizeObserver.observe(el.roundsTrack);
  if (el.fragmentsTrack) trackResizeObserver.observe(el.fragmentsTrack);
}
setInterval(pollStatus, 1500);

(async () => {
  await loadBuildBadge();
  await ensureSession();
  await pollStatus();
  if (isPlayable()) await restoreArticleView(true);
})();
