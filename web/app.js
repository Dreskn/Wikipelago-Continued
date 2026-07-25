const APP_VERSION = "2026.07.25.5";
console.log("Wikipelago web version", APP_VERSION);

const DISPLAY_LOCKS = [
  { unlockedKey: "tables_unlocked", lockClass: "lock-tables", label: "Tables" },
  { unlockedKey: "pictures_unlocked", lockClass: "lock-pictures", label: "Pictures" },
  { unlockedKey: "incipit_unlocked", lockClass: "lock-incipit", label: "Lead" },
  { unlockedKey: "infoboxes_unlocked", lockClass: "lock-infoboxes", label: "Infoboxes" },
  { unlockedKey: "toc_unlocked", lockClass: "lock-toc", label: "Contents" },
  { unlockedKey: "navboxes_unlocked", lockClass: "lock-navboxes", label: "Navboxes" },
  { unlockedKey: "hatnotes_unlocked", lockClass: "lock-hatnotes", label: "Hatnotes" },
  { unlockedKey: "references_unlocked", lockClass: "lock-references", label: "References" },
];

const DEBUG_DISPLAY = new URLSearchParams(window.location.search).has("debug");

const SCROLL_SPEED_FACTORS = [0.18, 0.28, 0.42, 0.6, 0.8, 1];
const CONNECTION_STORAGE_KEY = "wikipelago_connection";
const DEFAULT_SERVER = "archipelago.gg:";
const DEFAULT_SLOT = "WikiTester";

const state = {
  sessionId: localStorage.getItem("wikipelago_session_id") || "",
  status: null,
  currentTitle: "",
  baseArticleHtml: "",
  clicksUsed: 0,
  announcedGoalComplete: false,
  restoringArticle: false,
  searchOpen: false,
  debugUnlocks: null,
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
  roundText: document.getElementById("roundText"),
  targetText: document.getElementById("targetText"),
  targetHover: document.getElementById("targetHover"),
  targetTooltip: document.getElementById("targetTooltip"),
  rerollTargetBtn: document.getElementById("rerollTargetBtn"),
  rerollTargetMeta: document.getElementById("rerollTargetMeta"),
  goalText: document.getElementById("goalText"),
  clicksText: document.getElementById("clicksText"),
  fragmentsText: document.getElementById("fragmentsText"),
  playableRoundsText: document.getElementById("playableRoundsText"),
  compassHint: document.getElementById("compassHint"),
  roundProgress: document.getElementById("roundProgress"),
  roundAccessItem: document.getElementById("roundAccessItem"),
  backItem: document.getElementById("backItem"),
  searchItem: document.getElementById("searchItem"),
  searchLettersItem: document.getElementById("searchLettersItem"),
  scrollItem: document.getElementById("scrollItem"),
  compassItem: document.getElementById("compassItem"),
  lensesItem: document.getElementById("lensesItem"),
  toast: document.getElementById("toast"),
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

function requireApConnection() {
  if (isApConnected()) return true;
  toast("Connect to Archipelago to play", "warn");
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
  const key = normalizeTitle(title);
  if (!key || key === "..." || key === "goal complete") return "";
  if (state.targetSummaryCache.has(key)) return state.targetSummaryCache.get(key);

  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title.replace(/ /g, "_"))}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`summary HTTP ${res.status}`);
  const data = await res.json();
  const summary = formatTargetSummary(data) || "No short description available.";
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
  const canReroll = Boolean(status?.can_reroll_target) && !state.rerollBusy;
  el.rerollTargetBtn.disabled = !canReroll;
  if (status?.boss_completed || !status?.connected_to_ap) {
    el.rerollTargetMeta.textContent = "";
    return;
  }
  if (Number(status?.round) >= Number(status?.check_count)) {
    el.rerollTargetMeta.textContent = "Goal round";
    return;
  }
  if (Number.isFinite(remaining)) {
    el.rerollTargetMeta.textContent = `${Math.max(0, remaining)}/${max} left`;
  } else {
    el.rerollTargetMeta.textContent = "";
  }
}

async function rerollCurrentTarget() {
  if (!requireApConnection() || state.rerollBusy) return;
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
  const url = "https://en.wikipedia.org/w/api.php?action=query&list=random&rnnamespace=0&rnlimit=1&format=json&origin=*";
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

function applyFoggyLinks(root) {
  root.querySelectorAll("a[data-title]").forEach((a) => {
    a.textContent = "[Link]";
    a.title = "";
  });
}

function applyMissingLinks(root) {
  const links = [...root.querySelectorAll("a[data-title]")];
  if (links.length <= 1) return;
  const removeCount = Math.max(1, Math.min(links.length - 1, Math.floor(links.length * 0.3)));
  for (let i = links.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [links[i], links[j]] = [links[j], links[i]];
  }
  for (let i = 0; i < removeCount; i += 1) {
    const a = links[i];
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
    }
  }
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
  el.searchLettersItem.textContent = letters.length ? `${letters.length}/26` : (state.status?.searchsanity ? "0/26" : "Free");

  if (!state.status?.ctrl_f_unlocked) {
    el.searchStatus.textContent = "Ctrl+F Lens required";
  } else if (state.status?.searchsanity) {
    el.searchStatus.textContent = "Letter-limited search";
  } else {
    el.searchStatus.textContent = "Search ready";
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

function clearSearchHighlights() {
  if (state.baseArticleHtml) {
    el.articleBody.innerHTML = state.baseArticleHtml;
  }
}

function applySearchHighlights(query) {
  clearSearchHighlights();
  rewriteLinks(el.articleBody);
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

function storageKey(suffix) {
  return `wikipelago_${suffix}_${state.sessionId || "pending"}`;
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
  const hashTitle = decodeURIComponent((window.location.hash || "").replace(/^#/, "")).trim();
  if (hashTitle) return hashTitle;
  if (state.status?.last_page) return state.status.last_page;
  const savedTitle = loadSavedTitle();
  if (savedTitle) return savedTitle;
  if (state.status?.current_start) return state.status.current_start;
  return "Wikipedia";
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
  state.status = status;
  state.clicksUsed = Number.isFinite(status.clicks_used) ? status.clicks_used : state.clicksUsed;
  syncRoundVisitTracking(status);
  el.connBadge.textContent = status.connected_to_ap ? "Connected" : "Offline";
  el.connBadge.className = status.connected_to_ap ? "badge online" : "badge offline";

  if (wasConnected && !status.connected_to_ap) {
    toastSticky("Disconnected. Browsing only until you reconnect.", "warn");
  }
  if (!wasConnected && status.connected_to_ap) {
    clearStickyConnectionError();
    toast("Connected to Archipelago", "ok", 4500);
  }
  if (status.boss_completed) {
    el.roundText.textContent = "COMPLETE";
    el.targetText.textContent = "GOAL COMPLETE";
    el.goalText.textContent = `${status.goal_article || "..."} (Complete)`;
    setTargetSummaryTitle("");
  } else {
    el.roundText.textContent = `${status.round}/${status.check_count}`;
    el.targetText.textContent = status.current_target || "...";
    el.goalText.textContent = status.goal_article || "...";
    setTargetSummaryTitle(status.current_target || "");
  }
  updateRerollTargetControls(status);

  el.clicksText.textContent = String(state.clicksUsed);
  el.fragmentsText.textContent = `${status.fragments}/${status.required_fragments}`;
  el.playableRoundsText.textContent = `${status.unlocked_rounds}/${status.check_count}`;
  el.compassHint.textContent = status.compass_unlocked ? (status.warmer_colder || "Calibrating") : "Locked";
  el.roundProgress.style.width = `${Math.max(0, Math.min(100, (status.round / Math.max(status.check_count, 1)) * 100))}%`;
  el.roundAccessItem.textContent = String(status.round_access_count);
  el.backItem.textContent = status.back_button_unlocked ? "Unlocked" : "Locked";
  el.searchItem.textContent = status.ctrl_f_unlocked ? "Unlocked" : "Locked";
  renderSearchStatus();
  if (status.scrollsanity) {
    el.scrollItem.textContent = `${status.scroll_speed_level}/${status.scroll_speed_upgrades}`;
  } else {
    el.scrollItem.textContent = "Off";
  }
  el.compassItem.textContent = status.compass_unlocked ? "Unlocked" : "Locked";
  renderLensStatus(status);
  applyDisplayLocks();

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
  if (state.debugUnlocks && typeof state.debugUnlocks[unlockedKey] === "boolean") {
    return state.debugUnlocks[unlockedKey];
  }
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

function initDebugDisplayPanel() {
  if (!DEBUG_DISPLAY) return;
  state.debugUnlocks = Object.fromEntries(DISPLAY_LOCKS.map((lock) => [lock.unlockedKey, false]));

  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = "<h2>Debug Lenses</h2>";
  const list = document.createElement("div");
  list.className = "debug-lens-list";

  for (const lock of DISPLAY_LOCKS) {
    const label = document.createElement("label");
    label.className = "debug-lens-row";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = false;
    input.addEventListener("change", () => {
      state.debugUnlocks[lock.unlockedKey] = input.checked;
      applyDisplayLocks();
      renderLensStatus({ ...(state.status || {}), ...state.debugUnlocks });
    });
    label.appendChild(input);
    label.appendChild(document.createTextNode(` ${lock.label}`));
    list.appendChild(label);
  }

  const unlockAll = document.createElement("button");
  unlockAll.type = "button";
  unlockAll.textContent = "Unlock all";
  unlockAll.style.marginTop = "8px";
  unlockAll.addEventListener("click", () => {
    for (const lock of DISPLAY_LOCKS) state.debugUnlocks[lock.unlockedKey] = true;
    list.querySelectorAll("input[type=checkbox]").forEach((input) => { input.checked = true; });
    applyDisplayLocks();
    renderLensStatus({ ...(state.status || {}), ...state.debugUnlocks });
  });

  card.appendChild(list);
  card.appendChild(unlockAll);
  document.querySelector(".side-panel")?.appendChild(card);
  applyDisplayLocks();
  renderLensStatus({ ...(state.status || {}), ...state.debugUnlocks });
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

function stripExternalLinks(root) {
  root.querySelectorAll("a[href]").forEach((a) => {
    if (isExternalHref(a.getAttribute("href"))) unwrapElement(a);
  });
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

function prepareArticleHtml(root) {
  sanitizeHtml(root);
  stripExternalLinks(root);
  markLeadSection(root);
  markNamedSections(root, ["see also"], "wiki-section-seealso");
  markNamedSections(root, ["external links", "external link"], "wiki-section-external");
  markNamedSections(root, ["references", "notes", "citations"], "wiki-section-references");
  wrapTables(root);
  rewriteLinks(root);
  applyDisplayLocks();
}

function wrapTables(root) {
  root.querySelectorAll("table").forEach((table) => {
    table.removeAttribute("width");
    if (table.style) {
      table.style.removeProperty("width");
      table.style.removeProperty("min-width");
      table.style.removeProperty("max-width");
    }
    if (table.parentElement?.classList.contains("table-scroll")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    table.replaceWith(wrap);
    wrap.appendChild(table);
  });
}

function rewriteLinks(root) {
  root.querySelectorAll("a").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (isExternalHref(href)) {
      unwrapElement(a);
      return;
    }
    if (!href.startsWith("/wiki/")) return;
    const wikiPart = href.replace("/wiki/", "");
    if (!wikiPart) return;
    const title = decodeURIComponent(wikiPart).replace(/_/g, " ");
    const ns = title.split(":", 1)[0].toLowerCase();
    const blockedNamespaces = new Set(["file", "category", "help", "template", "special", "portal", "talk", "user", "wikipedia", "module", "book", "draft", "mediawiki"]);
    if (title.includes(":") && blockedNamespaces.has(ns)) return;
    a.dataset.title = title;
    a.href = "#";
  });
}

async function fetchWikiHtml(title) {
  const url = `https://en.wikipedia.org/w/api.php?action=parse&page=${encodeURIComponent(title)}&prop=text&formatversion=2&format=json&origin=*`;
  const res = await fetch(url);
  const data = await res.json();
  if (!data.parse || !data.parse.text) throw new Error("Article unavailable");
  return data.parse.text;
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
  if (requireConnection && !requireApConnection()) return;

  try {
    const html = await fetchWikiHtml(title);
    state.currentTitle = title;
    el.articleTitle.textContent = title;
    el.articleBody.innerHTML = html;
    prepareArticleHtml(el.articleBody);
    consumeTrapQueueForPage(title, state.status);
    if (state.activeFoggy) applyFoggyLinks(el.articleBody);
    if (state.activeMissing) applyMissingLinks(el.articleBody);
    armBombsOnPage(el.articleBody, state.status);
    if (countAsClick || !state.roundVisitSet.size) {
      state.roundVisitSet.add(normalizeTitle(title));
    } else if (!submitCheck) {
      state.roundVisitSet.add(normalizeTitle(title));
    }
    state.baseArticleHtml = el.articleBody.innerHTML;
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

    // Display-only paths (restore/hash/back) stop here — no scoring.
    if (!submitCheck) return;

    // Checks only while connected — browse is allowed if the link drops mid-run.
    if (!isApConnected()) {
      if (countAsClick) toast("Disconnected — reconnect to send checks", "warn");
      return;
    }

    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/check`, "POST", {
      page_title: title,
      clicks_used: state.clicksUsed,
      submit_check: true,
    });

    if (result.matched) {
      let msg = `Target hit: ${result.target}`;
      if (result.sent_text) msg += ` — ${result.sent_text}`;
      toast(msg, "ok", 7500);
      // Next round starts from its start article — visit set refreshes on round change via HUD.
    }
    if (result.locked) toast("Round locked. Find Round Access items.", "warn", 6500);
    if (result.not_connected) toast("Disconnected — reconnect to send checks", "warn", 6500);
    if (result.status) updateHUD(result.status);
  } catch {
    toast(`Could not open article: ${title}`, "warn");
  }
}

async function restoreArticleView(force = false) {
  if (!state.status || !isApConnected()) return;
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

el.articleBody.addEventListener("click", async (e) => {
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

el.connectBtn.addEventListener("click", async () => {
  try {
    const server = el.serverInput.value.trim();
    const slotName = el.slotInput.value.trim();
    saveConnection(server, slotName);
    clearStickyConnectionError();
    await ensureSession();
    await api(`/api/session/${state.sessionId}/connect`, "POST", {
      server,
      slot_name: slotName,
      password: el.passwordInput.value,
    });
    toast("Connecting to Archipelago...", "ok", 4500);
    await pollStatus();
    await restoreArticleView(true);
  } catch (err) {
    toastSticky(err.message || "Connect failed", "warn");
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
    if (state.status && !state.status.back_button_unlocked) {
      e.preventDefault();
      toast("Back Button is locked", "warn");
    }
  }
  if (e.key === "Backspace") {
    const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
    if (!typing && state.status && !state.status.back_button_unlocked) {
      e.preventDefault();
      toast("Back Button is locked", "warn");
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

window.addEventListener("popstate", (e) => {
  if (state.status && !state.status.back_button_unlocked) {
    history.pushState({ title: state.currentTitle }, "", `#${encodeURIComponent(state.currentTitle)}`);
    toast("Back Button is locked", "warn");
    return;
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

bindTargetTooltip();
initDebugDisplayPanel();
setInterval(pollStatus, 1500);

(async () => {
  await loadBuildBadge();
  await ensureSession();
  await pollStatus();
  if (isApConnected()) await restoreArticleView(true);
})();
