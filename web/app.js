const APP_VERSION = "1.0-beta1";
console.log("Wikipelago web version", APP_VERSION);

const I18n = window.WikipelagoI18n;
function t(key, vars) {
  return I18n?.t ? I18n.t(key, vars) : key;
}
function trapLabel(name) {
  return I18n?.localizeTrapName ? I18n.localizeTrapName(name) : name;
}
function uiLanguage() {
  return I18n?.uiLanguage ? I18n.uiLanguage() : "en";
}

/** Hover-prefetch: keep a few parsed pages ready for the next click. */
const WIKI_PREFETCH_MAX_CACHE = 8;
const WIKI_PREFETCH_CONCURRENCY = 2;
const WIKI_PREFETCH_HOVER_MS = 200;
/** After a longer hover, DOM-prepare the prefetched HTML so open skips the heavy pass. */
const WIKI_PREPARE_HOVER_MS = 800;

/** Wikipedia edition for article fetches (AP slot language, or practice pool language). */
function wikipediaLanguage() {
  const lang = String(state.status?.wikipedia_language || "en").trim().toLowerCase();
  return lang || "en";
}

function wikipediaOrigin(lang = wikipediaLanguage()) {
  return `https://${lang}.wikipedia.org`;
}

function articleLanguage() {
  return state.articleLang || wikipediaLanguage();
}

/**
 * Non-article namespaces blocked for navigation (toast; never leave the SPA).
 * Includes English + localized prefixes/aliases for en/fr/de/es/it/pt/nl/sv/pl.
 * Matching uses the title segment before the first ":".
 * Keep in sync with world/APWorldSource/wikipelago/article_pool.py BLOCKED_WIKI_NAMESPACES.
 */
const BLOCKED_WIKI_NAMESPACES = new Set([
  // English / canonical
  "file", "image", "category", "help", "template", "special", "portal", "portal talk",
  "talk", "user", "user talk", "wikipedia", "wp", "project", "module", "book", "draft",
  "mediawiki", "timedtext", "event",
  // French
  "spécial", "discussion", "discuter", "utilisateur", "utilisatrice",
  "discussion utilisateur", "discussion utilisatrice",
  "wikipédia", "fichier", "modèle", "aide", "catégorie", "portail", "discussion portail",
  "projet", "référence",
  // German
  "spezial", "diskussion", "benutzer", "benutzerin", "benutzer diskussion",
  "benutzerin diskussion", "bd", "datei", "bild", "vorlage", "hilfe", "kategorie",
  "portal diskussion", "pd",
  // Spanish
  "especial", "discusión", "usuario", "usuaria", "usuario discusión", "usuaria discusión",
  "archivo", "imagen", "plantilla", "ayuda", "categoría", "portal discusión",
  // Italian
  "speciale", "discussione", "utente", "discussioni utente", "immagine", "aiuto",
  "categoria", "portale", "discussioni portale",
  // Portuguese
  "especial", "discussão", "usuário(a)", "usuário", "usuária", "utilizador",
  "utilizador(a)", "utilizadora", "usuário(a) discussão", "usuário discussão",
  "usuária discussão", "utilizador discussão", "utilizador(a) discussão",
  "utilizadora discussão", "wikipédia", "ficheiro", "arquivo", "imagem",
  "predefinição", "ajuda", "categoria", "portal discussão", "discussão portal",
  // Dutch
  "speciaal", "overleg", "gebruiker", "overleg gebruiker", "bestand", "afbeelding",
  "sjabloon", "categorie", "portaal", "overleg portaal",
  // Swedish
  "användare", "användardiskussion", "fil", "mall", "hjälp", "kategori",
  "portaldiskussion",
  // Polish
  "specjalna", "dyskusja", "wikipedysta", "wikipedystka", "dyskusja wikipedysty",
  "dyskusja wikipedystki", "plik", "grafika", "szablon", "pomoc", "kategoria",
  "dyskusja portalu",
]);

/** Localized appendix section titles → CSS marker class (union across supported wikis). */
const WIKI_SECTION_HEADINGS = {
  "wiki-section-seealso": [
    "see also",
    "voir aussi", "articles connexes", "articles liés",
    "siehe auch",
    "véase también", "vease tambien",
    "vedi anche", "voci correlate",
    "ver também", "ver tambem", "artigos relacionados",
    "zie ook",
    "se även", "se aven",
    "zobacz też", "zobacz tez", "zobacz także", "zobacz takze",
  ],
  "wiki-section-external": [
    "external links", "external link",
    "liens externes", "lien externe",
    "weblinks", "weblink",
    "enlaces externos", "enlace externo",
    "collegamenti esterni", "collegamento esterno",
    "ligações externas", "ligacoes externas", "links externos",
    "externe links", "externe link",
    "externa länkar", "externa lank",
    "linki zewnętrzne", "linki zewnetrzne",
  ],
  "wiki-section-references": [
    "references", "notes", "citations", "notes and references", "further reading", "bibliography",
    "références", "notes et références", "notes et references", "bibliographie", "sources",
    "einzelnachweise", "literatur", "anmerkungen", "referenzen", "belege",
    "referencias", "notas", "bibliografía", "bibliografia",
    "note", "riferimenti",
    "referências",
    "referenties", "noten", "voetnoten", "literatuur",
    "referenser", "källor", "kallor", "noter", "litteratur",
    "przypisy", "uwagi", "źródła", "zrodla", "przypisy i bibliografia",
  ],
};

/** Plain segment min width + gap used to estimate how many bars fit in the side panel. */
const TRACK_SEG_MIN_PX = 4;
/** Idle bars may grow to fill, but never past this — current stays visually larger. */
const TRACK_SEG_MAX_PX = 16;
const TRACK_SEG_GAP_PX = 2;
/** Do not squash a run into +N unless at least this many like-segments would hide. */
const TRACK_OVERFLOW_MIN = 5;
/** Fork spurs are short, so they may collapse from 3 like-segments. */
const TRACK_FORK_OVERFLOW_MIN = 3;
/** Current-round / +N chip width. */
const TRACK_EMPHASIS_MIN_PX = 24;
/** Crossroad chip width on the main road. */
const TRACK_CROSSROAD_PX = 48;
/** Horizontal track padding (each side) — keep outline / end chips uncropped. */
const TRACK_PAD_X_PX = 4;

const DISPLAY_LOCKS = [
  { unlockedKey: "tables_unlocked", randomizeKey: "randomize_tables", lockClass: "lock-tables", i18nKey: "lens.tables", glyph: "Tbl" },
  { unlockedKey: "pictures_unlocked", randomizeKey: "randomize_pictures", lockClass: "lock-pictures", i18nKey: "lens.pictures", glyph: "Pic" },
  { unlockedKey: "incipit_unlocked", randomizeKey: "randomize_incipit", lockClass: "lock-incipit", i18nKey: "lens.lead", glyph: "Led" },
  { unlockedKey: "infoboxes_unlocked", randomizeKey: "randomize_infoboxes", lockClass: "lock-infoboxes", i18nKey: "lens.infoboxes", glyph: "Inf" },
  { unlockedKey: "toc_unlocked", randomizeKey: "randomize_toc", lockClass: "lock-toc", i18nKey: "lens.contents", glyph: "Toc" },
  { unlockedKey: "navboxes_unlocked", randomizeKey: "randomize_navboxes", lockClass: "lock-navboxes", i18nKey: "lens.navboxes", glyph: "Nav" },
  { unlockedKey: "hatnotes_unlocked", randomizeKey: "randomize_hatnotes", lockClass: "lock-hatnotes", i18nKey: "lens.hatnotes", glyph: "Hat" },
  { unlockedKey: "references_unlocked", randomizeKey: "randomize_references", lockClass: "lock-references", i18nKey: "lens.references", glyph: "Ref" },
];

function lucideIcon(inner) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
}

// Official Lucide glyphs (https://lucide.dev). Mapping and licenses: LICENSE.
const TOOL_ICON_SVGS = {
  back: lucideIcon('<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11"/>'),
  reroll: lucideIcon('<rect width="12" height="12" x="2" y="10" rx="2" ry="2"/><path d="m17.92 14 3.5-3.5a2.24 2.24 0 0 0 0-3l-5-4.92a2.24 2.24 0 0 0-3 0L10 6"/><path d="M6 18h.01"/><path d="M10 14h.01"/><path d="M15 6h.01"/><path d="M18 9h.01"/>'),
  search: lucideIcon('<path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/>'),
  compass: lucideIcon('<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"/>'),
  key: lucideIcon('<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>'),
  scroll: lucideIcon('<rect x="5" y="2" width="14" height="20" rx="7"/><path d="M12 6v4"/>'),
  searchsanity: lucideIcon('<path d="m15 16 2.536-7.328a1.02 1.02 1 0 1 1.928 0L22 16"/><path d="M15.697 14h5.606"/><path d="m2 16 4.039-9.69a.5.5 0 0 1 .923 0L11 16"/><path d="M3.304 13h6.392"/>'),
  scrollsanity: lucideIcon('<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>'),
  deaths: lucideIcon('<path d="m12.5 17-.5-1-.5 1h1z"/><path d="M15 22a1 1 0 0 0 1-1v-1a2 2 0 0 0 1.56-3.25 8 8 0 1 0-11.12 0A2 2 0 0 0 8 20v1a1 1 0 0 0 1 1z"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="12" r="1"/>'),
  deathlink: lucideIcon('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>'),
  traplink: lucideIcon('<path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22"/><path d="M2 6h1.972a4 4 0 0 1 3.6 2.2"/><path d="M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45"/>'),
  bombs: lucideIcon('<circle cx="11" cy="13" r="9"/><path d="M14.35 4.65 16.3 2.7a2.41 2.41 0 0 1 3.4 0l1.6 1.6a2.4 2.4 0 0 1 0 3.4l-1.95 1.95"/><path d="m22 2-1.5 1.5"/>'),
  traps: lucideIcon('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'),
};

function trapTypeLabel(trapType) {
  const key = {
    0: "diff.trapType.all",
    1: "diff.trapType.foggy",
    2: "diff.trapType.missing",
    3: "diff.trapType.wrongWiki",
  }[Number(trapType) || 0] || "diff.trapType.all";
  return t(key);
}

function bombDensityKey(density) {
  return {
    0: "few",
    1: "more",
    2: "insane",
  }[Number(density) || 0] || "few";
}

function bombDensityLabel(density) {
  return t(`diff.density.${bombDensityKey(density)}`);
}

let debugDisplayEnabled = false;
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
  bingoStampPickMode: false,
  bingoStampBusy: false,
  /** Expanded bingo board overlay: { boardKey, zoom, panX, panY }. */
  bingoOverlay: null,
  bingoOverlayDrag: null,
  searchOpen: false,
  roundVisitSet: new Set(),
  roundVisitRound: 0,
  roundVisitPath: "",
  journeyOpen: false,
  journeyPayload: null,
  journeyLayoutKey: "",
  announcedJourneyCredits: false,
  victoryOpen: false,
  rerollBusy: false,
  targetSummaryCache: new Map(),
  targetSummaryTitle: "",
  targetTooltipTitle: "",
  targetTooltipAnchor: null,
  targetTooltipVisible: false,
  trapQueue: [],
  activeFoggy: false,
  activeMissing: false,
  articleLang: "",
  bombTitles: new Set(),
  handlingDeath: false,
  /** After slot/language switch, open current_start instead of sticky hash/last_page. */
  forceResumeStart: false,
  resumeIdentity: "",
  /** lang::title → { html } (LRU via Map insertion order). */
  wikiHtmlCache: new Map(),
  /** lang::title → in-flight fetch Promise */
  wikiHtmlInflight: new Map(),
  /** lang::title → detached Element with prepared children (LRU). */
  wikiPreparedCache: new Map(),
  /** lang::title → in-flight prepare Promise */
  wikiPrepareInflight: new Map(),
  wikiPrefetchQueue: [],
  wikiPrefetchActive: 0,
  wikiPrefetchHoverTimer: null,
  wikiPrefetchHoverTitle: "",
  wikiPrepareHoverTimer: null,
  wikiPrepareHoverTitle: "",
  wikiCacheLanguage: "",
  articleLoadingToken: 0,
};

const el = {
  connBadge: document.getElementById("connBadge"),
  buildBadge: document.getElementById("buildBadge"),
  articleTitle: document.getElementById("articleTitle"),
  articleStage: document.getElementById("articleStage"),
  articleBody: document.getElementById("articleBody"),
  articleLoading: document.getElementById("articleLoading"),
  articleLoadingText: document.getElementById("articleLoadingText"),
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
  connectionCard: document.getElementById("connectionCard"),
  connectionForm: document.getElementById("connectionForm"),
  connectionSummary: document.getElementById("connectionSummary"),
  connectedServerText: document.getElementById("connectedServerText"),
  connectedSlotText: document.getElementById("connectedSlotText"),
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
  goalHover: document.getElementById("goalHover"),
  goalAnswer: document.getElementById("goalAnswer"),
  journeyBtn: document.getElementById("journeyBtn"),
  branchTracks: document.getElementById("branchTracks"),
  branchTargets: document.getElementById("branchTargets"),
  crossroadBadge: document.getElementById("crossroadBadge"),
  journeyOverlay: document.getElementById("journeyOverlay"),
  journeyOverlayBackdrop: document.getElementById("journeyOverlayBackdrop"),
  journeyOverlayTitle: document.getElementById("journeyOverlayTitle"),
  journeyOverlayClose: document.getElementById("journeyOverlayClose"),
  journeyPath: document.getElementById("journeyPath"),
  journeyTip: document.getElementById("journeyTip"),
  victoryOverlay: document.getElementById("victoryOverlay"),
  victoryOverlayBackdrop: document.getElementById("victoryOverlayBackdrop"),
  victoryOverlayTitle: document.getElementById("victoryOverlayTitle"),
  victoryQuestion: document.getElementById("victoryQuestion"),
  victoryAnswer: document.getElementById("victoryAnswer"),
  victoryMessage: document.getElementById("victoryMessage"),
  victoryJourneyBtn: document.getElementById("victoryJourneyBtn"),
  victoryCloseBtn: document.getElementById("victoryCloseBtn"),
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
  bingoStampControls: document.getElementById("bingoStampControls"),
  bingoStampMeta: document.getElementById("bingoStampMeta"),
  bingoStampBtn: document.getElementById("bingoStampBtn"),
  bingoStampHint: document.getElementById("bingoStampHint"),
  bingoBoards: document.getElementById("bingoBoards"),
  bingoMeta: document.getElementById("bingoMeta"),
  bingoOverlay: document.getElementById("bingoOverlay"),
  bingoOverlayBackdrop: document.getElementById("bingoOverlayBackdrop"),
  bingoOverlayTitle: document.getElementById("bingoOverlayTitle"),
  bingoOverlayClose: document.getElementById("bingoOverlayClose"),
  bingoOverlayStage: document.getElementById("bingoOverlayStage"),
  bingoOverlayWorld: document.getElementById("bingoOverlayWorld"),
  bingoZoomIn: document.getElementById("bingoZoomIn"),
  bingoZoomOut: document.getElementById("bingoZoomOut"),
  bingoZoomReset: document.getElementById("bingoZoomReset"),
  lensesItem: document.getElementById("lensesItem"),
  toast: document.getElementById("toast"),
  stuckToggleBtn: document.getElementById("stuckToggleBtn"),
  stuckPanel: document.getElementById("stuckPanel"),
  enableDebugMenuChk: document.getElementById("enableDebugMenuChk"),
  debugConsentPanel: document.getElementById("debugConsentPanel"),
  showDebugMenuBtn: document.getElementById("showDebugMenuBtn"),
  uiLangSelect: document.getElementById("uiLangSelect"),
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
  applyDebugMenuAvailability(info);
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
    el.buildBadge.textContent = t("build.unknown");
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
  if (el.connectionCard) el.connectionCard.classList.toggle("is-active", active);
  if (el.connectionForm) el.connectionForm.classList.toggle("hidden", active);
  if (el.connectionSummary) el.connectionSummary.classList.toggle("hidden", !active);
  if (el.connectedServerText) {
    const server = practice
      ? t("conn.practiceMode")
      : connected
        ? (status.ap_server || el.serverInput?.value?.trim() || "—")
        : "-";
    el.connectedServerText.textContent = server;
    el.connectedServerText.title = server;
  }
  if (el.connectedSlotText) {
    const slot = connected && !practice
      ? (status.slot_name || el.slotInput?.value?.trim() || "")
      : "";
    el.connectedSlotText.textContent = slot;
    el.connectedSlotText.title = slot;
    el.connectedSlotText.classList.toggle("hidden", !slot);
  }
  if (el.disconnectBtn) {
    el.disconnectBtn.classList.toggle("hidden", !active);
    el.disconnectBtn.disabled = !active;
    el.disconnectBtn.textContent = practice ? t("conn.exitPractice") : t("conn.disconnect");
  }
}

function requireApConnection() {
  if (isApConnected()) return true;
  toast(t("toast.connectToPlay"), "warn");
  return false;
}

function requirePlayable() {
  if (isPlayable()) return true;
  toast(t("toast.connectOrPractice"), "warn");
  return false;
}

function syncUiLanguageSelect() {
  if (el.uiLangSelect) el.uiLangSelect.value = uiLanguage();
}

function onUiLanguageChanged(code) {
  if (I18n?.setUiLanguage) I18n.setUiLanguage(code);
  else if (I18n?.applyStaticI18n) I18n.applyStaticI18n();
  syncUiLanguageSelect();
  if (state.status) updateHUD(state.status);
  else {
    updateConnectionPanel(null);
    if (el.connBadge && !state.status) {
      el.connBadge.textContent = t("badge.offline");
      el.connBadge.className = "badge offline";
    }
  }
  if (state.victoryOpen) fillVictoryOverlay(state.status);
  refreshSearchChrome();
  refreshSidePanelToggles();
}

function bindUiLanguageControls() {
  if (I18n?.fillLanguageSelect) I18n.fillLanguageSelect(el.uiLangSelect);
  syncUiLanguageSelect();
  el.uiLangSelect?.addEventListener("change", (e) => onUiLanguageChanged(e.target.value));
  if (I18n?.applyStaticI18n) I18n.applyStaticI18n();
}

function refreshSearchChrome() {
  if (typeof renderSearchStatus === "function") {
    try { renderSearchStatus(); } catch { /* not ready yet */ }
  }
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
  }) || t("hud.noDescription");
  state.targetSummaryCache.set(key, summary);
  return summary;
}

function positionTargetTooltip() {
  const anchorEl = state.targetTooltipAnchor;
  if (!el.targetTooltip || !anchorEl || el.targetTooltip.classList.contains("hidden")) return;
  const anchor = anchorEl.getBoundingClientRect();
  const tip = el.targetTooltip;
  const margin = 8;
  const width = Math.min(tip.offsetWidth || 320, window.innerWidth - margin * 2);
  let left = anchor.left;
  left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

  // Prefer above the target; flip below if there isn't enough room.
  tip.style.left = `${left}px`;
  tip.style.top = "0px";
  tip.style.right = "auto";
  tip.style.bottom = "auto";
  const tipHeight = tip.offsetHeight || 0;
  let top = anchor.top - tipHeight - margin;
  if (top < margin) {
    top = Math.min(anchor.bottom + margin, window.innerHeight - tipHeight - margin);
    top = Math.max(margin, top);
  }
  tip.style.top = `${top}px`;
}

function hideTargetTooltip() {
  state.targetTooltipVisible = false;
  state.targetTooltipTitle = "";
  state.targetTooltipAnchor = null;
  if (!el.targetTooltip) return;
  el.targetTooltip.classList.add("hidden");
  el.targetTooltip.classList.remove("loading");
  el.targetTooltip.textContent = "";
  el.targetTooltip.style.left = "";
  el.targetTooltip.style.top = "";
}

async function showTargetTooltip(title, anchorEl) {
  if (!el.targetTooltip || !title || !anchorEl) return;
  state.targetTooltipVisible = true;
  state.targetTooltipTitle = title;
  state.targetTooltipAnchor = anchorEl;
  if (el.targetTooltip.parentElement !== document.body) {
    document.body.appendChild(el.targetTooltip);
  }
  el.targetTooltip.classList.remove("hidden");
  el.targetTooltip.classList.add("loading");
  el.targetTooltip.textContent = t("hud.loadingEllipsis");
  positionTargetTooltip();
  try {
    const summary = await fetchTargetSummary(title);
    if (!state.targetTooltipVisible || normalizeTitle(title) !== normalizeTitle(state.targetTooltipTitle)) {
      return;
    }
    el.targetTooltip.classList.remove("loading");
    el.targetTooltip.textContent = summary || t("hud.noDescription");
    positionTargetTooltip();
  } catch {
    if (!state.targetTooltipVisible) return;
    el.targetTooltip.classList.remove("loading");
    el.targetTooltip.textContent = t("hud.descriptionFailed");
    positionTargetTooltip();
  }
}

function hoverWikiTitle(hoverEl) {
  const raw = String(hoverEl?.dataset?.wikiTitle || "").trim();
  if (!raw || raw === "..." || raw === "GOAL COMPLETE") return "";
  return raw;
}

function enterTargetHover(hover) {
  const title = hoverWikiTitle(hover);
  if (!title) return;
  if (
    state.targetTooltipVisible
    && state.targetTooltipAnchor === hover
    && normalizeTitle(state.targetTooltipTitle) === normalizeTitle(title)
  ) {
    return;
  }
  showTargetTooltip(title, hover);
}

function leaveTargetHover(hover, related) {
  if (related && hover.contains(related)) return;
  if (state.targetTooltipAnchor === hover) hideTargetTooltip();
}

function bindTargetTooltip() {
  if (!el.targetTooltip) return;
  if (el.targetTooltip.parentElement !== document.body) {
    document.body.appendChild(el.targetTooltip);
  }
  const root = document.querySelector(".side-panel") || document;
  root.addEventListener("mouseover", (event) => {
    const hover = event.target.closest?.(".target-hover");
    if (!hover || !root.contains(hover)) return;
    const from = event.relatedTarget;
    if (from && hover.contains(from)) return;
    enterTargetHover(hover);
  });
  root.addEventListener("mouseout", (event) => {
    const hover = event.target.closest?.(".target-hover");
    if (!hover) return;
    leaveTargetHover(hover, event.relatedTarget);
  });
  root.addEventListener("focusin", (event) => {
    const hover = event.target.closest?.(".target-hover");
    if (hover) enterTargetHover(hover);
  });
  root.addEventListener("focusout", (event) => {
    const hover = event.target.closest?.(".target-hover");
    if (hover) leaveTargetHover(hover, event.relatedTarget);
  });
  window.addEventListener("resize", () => {
    if (state.targetTooltipVisible) positionTargetTooltip();
  });
  // Side panel scroll would otherwise leave a stale fixed position.
  root.addEventListener("scroll", () => {
    if (state.targetTooltipVisible) positionTargetTooltip();
  }, { passive: true });
}

function setHoverWikiTitle(hoverEl, title) {
  if (!hoverEl) return;
  const next = String(title || "").trim();
  if (!next || next === "..." || next === "GOAL COMPLETE") {
    hoverEl.dataset.wikiTitle = "";
    hoverEl.removeAttribute("tabindex");
    return;
  }
  hoverEl.dataset.wikiTitle = next;
  hoverEl.tabIndex = 0;
  fetchTargetSummary(next).catch(() => {});
}

function setTargetSummaryTitle(title) {
  const next = String(title || "").trim();
  if (next === "GOAL COMPLETE" || next === "..." || !next) {
    state.targetSummaryTitle = "";
    setHoverWikiTitle(el.targetHover, "");
    if (state.targetTooltipAnchor === el.targetHover) hideTargetTooltip();
    return;
  }
  const changed = normalizeTitle(next) !== normalizeTitle(state.targetSummaryTitle);
  state.targetSummaryTitle = next;
  setHoverWikiTitle(el.targetHover, next);
  if (changed && state.targetTooltipAnchor === el.targetHover) hideTargetTooltip();
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
    el.rerollTargetMeta.textContent = t("hud.rerollLeft", { n: Math.max(0, remaining), max });
  } else {
    el.rerollTargetMeta.textContent = "";
  }
}

async function rerollCurrentTarget() {
  if (!requirePlayable() || state.rerollBusy) return;
  if (!state.status?.can_reroll_target) {
    toast(t("toast.noRerolls"), "warn", 4500);
    return;
  }
  state.rerollBusy = true;
  updateRerollTargetControls(state.status);
  try {
    const result = await api(`/api/session/${state.sessionId}/reroll-target`, "POST", {});
    if (result.status) updateHUD(result.status);
    const changes = Array.isArray(result.changes) ? result.changes : [];
    if (changes.length > 1) {
      toast(t("toast.rerolledAll", { n: changes.length }), "ok", 6500);
    } else {
      toast(t("toast.rerolled", { title: result.new_target || changes[0]?.new_target || "" }), "ok", 6500);
    }
  } catch (err) {
    toast(t("toast.rerollFailed", { error: err.message || err }), "warn", 6500);
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

function formatThemeTag(tag) {
  const raw = String(tag || "").trim();
  return raw ? raw.replace(/_/g, " ") : "";
}

function pathLabel(path) {
  if (!path) return t("path.main");
  if (path.id === "main") return t("path.main");
  return t("hud.forkTarget", { n: forkNumber(path) });
}

function forkNumber(item) {
  const n = Number(item?.fork);
  if (Number.isFinite(n) && n > 0) return Math.trunc(n);
  const rawId = item?.id;
  if (typeof rawId === "number" && Number.isFinite(rawId)) return Math.trunc(rawId) + 1;
  const match = String(rawId || "").match(/branch:(\d+)/);
  if (match) return Number(match[1]) + 1;
  const branchId = Number(item?.branch_id);
  if (Number.isFinite(branchId)) return Math.trunc(branchId) + 1;
  return 1;
}

function forkProgressTitle(item) {
  return t("hud.forkTarget", { n: forkNumber(item) });
}

function liveTargetTitles(status) {
  const titles = [status?.current_target];
  if (status?.boss_completed) titles.push(status?.goal_article);
  const live = Array.isArray(status?.live_branch_targets) ? status.live_branch_targets : [];
  for (const item of live) titles.push(item?.target);
  return titles.filter(Boolean);
}

function isLiveTargetTitle(title, status) {
  return liveTargetTitles(status).some((item) => titlesMatch(title, item));
}

function isGoalArticleTitle(title, status) {
  return Boolean(status?.goal_article) && titlesMatch(title, status.goal_article);
}

function isProtectedNavTitle(title, status) {
  return isLiveTargetTitle(title, status) || isGoalArticleTitle(title, status);
}

function unlockedBranchPaths(status) {
  const paths = Array.isArray(status?.paths) ? status.paths : [];
  return paths.filter((path) => path && path.id && path.id !== "main" && path.unlocked);
}

function renderBranchTargets(status) {
  if (!el.branchTargets) return;
  const live = Array.isArray(status?.live_branch_targets) ? status.live_branch_targets : [];
  const show = !status?.practice && !status?.boss_completed && live.length > 0;
  el.branchTargets.classList.toggle("hidden", !show);
  el.branchTargets.innerHTML = "";
  if (!show) return;
  for (const item of live) {
    const row = document.createElement("p");
    row.className = "target-row branch-target-row";
    const label = document.createElement("strong");
    label.textContent = t("hud.forkTarget", { n: forkNumber(item) });
    const title = document.createElement("span");
    title.className = "target-hover target-page";
    title.textContent = item.target || "…";
    setHoverWikiTitle(title, item.target || "");
    row.appendChild(label);
    row.appendChild(title);
    el.branchTargets.appendChild(row);
  }
}

function renderBranchTracks(status) {
  if (el.branchTracks) el.branchTracks.innerHTML = "";
}

function forkProgressByNumber(status) {
  const map = new Map();
  for (const path of unlockedBranchPaths(status)) {
    const fork = forkNumber(path);
    const total = Math.max(0, Number(path.length) || 0);
    const current = Math.max(1, Number(path.round) || 1);
    const completed = Math.max(0, Number(path.completed) || 0);
    map.set(fork, {
      total,
      current,
      completed,
      done: total > 0 && completed >= total,
    });
  }
  return map;
}

function renderForkSpur(parentSeg, progress, fork) {
  const total = Math.max(0, Number(progress?.total) || 0);
  if (!parentSeg || total <= 0) return;
  const current = Math.max(1, Number(progress.current) || 1);
  const completed = Math.max(0, Number(progress.completed) || 0);
  const done = Boolean(progress.done) || completed >= total;
  const items = [];
  for (let i = 1; i <= total; i += 1) {
    let stateName = "open";
    if (done || i <= completed) stateName = "done";
    items.push({
      state: stateName,
      current: !done && i === current && i > completed,
      label: String(i),
    });
  }
  const spur = document.createElement("div");
  spur.className = "fork-spur";
  const kind = forkProgressTitle({ fork });
  spur.setAttribute("aria-label", done ? `${kind} ${t("hud.complete")}` : `${kind} ${current}/${total}`);
  const runs = rleTrackItems(items);
  for (const run of runs) {
    const startNum = Number(String(run.startLabel).match(/\d+/)?.[0] || 1);
    if (run.current || run.count < TRACK_FORK_OVERFLOW_MIN) {
      for (let i = 0; i < run.count; i += 1) {
        appendTrackSeg(spur, {
          state: run.state,
          current: Boolean(run.current) && i === 0,
          title: `${kind} ${startNum + i}`,
        });
      }
    } else {
      appendTrackSeg(spur, {
        state: run.state,
        overflowCount: run.count,
        title: t("track.moreLikeThis", {
          kind, start: run.startLabel, end: run.endLabel, overflow: run.count,
        }),
      });
    }
  }
  parentSeg.appendChild(spur);
}

function syncCrossroadTrackSpace(trackEl) {
  if (!trackEl) return;
  const labelTop = 18;
  let extra = 12;
  trackEl.querySelectorAll(".fork-spur").forEach((spur) => {
    extra = Math.max(extra, 12 + spur.offsetHeight);
    const parent = spur.closest(".seg.crossroad") || spur.parentElement;
    if (parent) {
      parent.style.setProperty("--hook-thick", `${Math.max(24, spur.offsetWidth)}px`);
    }
  });
  if (trackEl.classList.contains("has-crossroads") || trackEl.querySelector(".seg.crossroad")) {
    trackEl.style.paddingTop = `${labelTop}px`;
    trackEl.style.paddingBottom = `${extra}px`;
    trackEl.style.minHeight = `${18 + labelTop + extra}px`;
  } else {
    trackEl.style.paddingTop = "";
    trackEl.style.paddingBottom = "";
    trackEl.style.minHeight = "";
  }
}

function renderCrossroadBadge(status) {
  if (!el.crossroadBadge) return;
  const info = status?.revealed_crossroad;
  if (!info || status?.practice) {
    el.crossroadBadge.classList.add("hidden");
    el.crossroadBadge.textContent = "";
    return;
  }
  el.crossroadBadge.classList.remove("hidden");
  el.crossroadBadge.classList.toggle("unlocked", Boolean(info.unlocked));
  const fork = Number(info.fork) > 0 ? Math.trunc(Number(info.fork)) : Number(info.branch_id) + 1;
  if (info.unlocked) {
    el.crossroadBadge.textContent = t("crossroad.unlocked", { n: fork });
  } else if (Number(status.branch_keys_available) > 0) {
    el.crossroadBadge.textContent = t("crossroad.ready", { n: fork });
  } else {
    el.crossroadBadge.textContent = t("crossroad.needKey");
  }
}

function journeyKindLabel(kind) {
  const key = `journey.kind.${kind}`;
  const label = t(key);
  return label === key ? kind : label;
}

function journeyEventPath(event) {
  return String(event?.path || event?.extra?.path || "main");
}

function journeyPageNodes(events) {
  const nodes = [];
  for (const event of events) {
    const title = String(event?.title || "").trim();
    const kind = String(event?.kind || "").trim();
    if (!title || kind === "branch_switch") continue;
    const last = nodes[nodes.length - 1];
    const node = last && last.title === title
      ? last
      : {
          title,
          kinds: new Set(),
          mainRound: false,
          forks: new Set(),
          stamp: false,
          grandGoal: false,
        };
    node.kinds.add(kind);
    if (kind === "round_complete") {
      const pathId = journeyEventPath(event);
      if (String(pathId).startsWith("branch:")) {
        node.forks.add(forkNumber({ id: pathId }));
      } else {
        node.mainRound = true;
      }
    }
    if (kind === "bingo_stamp" || kind === "bingo_cell") node.stamp = true;
    if (kind === "grand_goal") node.grandGoal = true;
    if (node !== last) nodes.push(node);
  }
  return nodes.map((node) => {
    const milestone = Boolean(node.mainRound || node.forks.size || node.stamp || node.grandGoal);
    return {
      title: node.title,
      kinds: node.kinds,
      mainRound: node.mainRound,
      forks: [...node.forks].sort((a, b) => a - b),
      stamp: node.stamp,
      grandGoal: node.grandGoal,
      milestone,
    };
  });
}

function layoutJourneyNodes(nodes, width) {
  const padX = 28;
  const padY = 44;
  const stepX = 54;
  const rowH = 78;
  const inner = Math.max(160, width - padX * 2);
  const cols = Math.max(3, Math.floor(inner / stepX) + 1);
  const gap = cols <= 1 ? 0 : inner / (cols - 1);
  return nodes.map((node, i) => {
    const row = Math.floor(i / cols);
    let col = i % cols;
    if (row % 2 === 1) col = cols - 1 - col;
    return {
      ...node,
      row,
      x: padX + col * gap,
      y: padY + row * rowH,
      r: node.milestone ? (node.grandGoal || (node.stamp && (node.mainRound || node.forks.length)) ? 11 : 9) : 4.5,
    };
  });
}

function journeyTrailD(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  const minX = Math.min(...points.map((p) => p.x));
  const maxX = Math.max(...points.map((p) => p.x));
  const midX = (minX + maxX) / 2;
  let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  for (let i = 1; i < points.length; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    // Horizontals keep the u/n chain (first hop is a "u"). Vertical wraps
    // bulge like "(" on the left and ")" on the right, independent of that chain.
    let sign = i % 2 === 0 ? -1 : 1;
    if (Math.abs(dy) >= Math.abs(dx)) {
      const onRight = mx >= midX;
      sign = onRight ? -1 : 1;
      if (dy < 0) sign = -sign;
    }
    const bend = sign * Math.min(18, len * 0.24);
    const cx = mx - (dy / len) * bend;
    const cy = my + (dx / len) * bend;
    d += ` Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
  }
  return d;
}

function journeyNodeFill(node) {
  if (node.grandGoal) return { fill: "#ffd76a", stroke: "#c4922a" };
  if (node.mainRound) return { fill: "#1ecb70", stroke: "#148a4c" };
  if (node.forks.length) return { fill: "#40c4ff", stroke: "#1a7aa0" };
  if (node.stamp) return { fill: "#b57bff", stroke: "#7a3fd4" };
  return { fill: "#0d1620", stroke: "#6a849c" };
}

function journeyNodeTipLines(node) {
  const lines = [];
  if (node.mainRound) lines.push(t("journey.roundMain"));
  for (const fork of node.forks) lines.push(t("journey.roundFork", { n: fork }));
  if (node.grandGoal) lines.push(t("journey.grandGoal"));
  if (node.stamp) lines.push(t("journey.stamp"));
  if (!lines.length && node.kinds.has("back")) lines.push(journeyKindLabel("back"));
  if (!lines.length && node.kinds.has("death")) lines.push(journeyKindLabel("death"));
  return lines;
}

function hideJourneyTip() {
  if (!el.journeyTip) return;
  el.journeyTip.classList.add("hidden");
  el.journeyTip.innerHTML = "";
}

function showJourneyTip(node, clientX, clientY) {
  if (!el.journeyTip || !el.journeyPath) return;
  const lines = journeyNodeTipLines(node);
  el.journeyTip.innerHTML = "";
  const title = document.createElement("strong");
  title.textContent = node.title;
  el.journeyTip.appendChild(title);
  for (const line of lines) {
    const kind = document.createElement("div");
    kind.className = "journey-tip-kind";
    kind.textContent = line;
    el.journeyTip.appendChild(kind);
  }
  el.journeyTip.classList.remove("hidden");
  const originEl = el.journeyPath.parentElement || el.journeyPath;
  const wrap = originEl.getBoundingClientRect();
  const tipW = el.journeyTip.offsetWidth || 160;
  const tipH = el.journeyTip.offsetHeight || 40;
  let left = clientX - wrap.left + originEl.scrollLeft + 12;
  let top = clientY - wrap.top + originEl.scrollTop + 12;
  const maxLeft = Math.max(8, originEl.clientWidth - tipW - 8);
  const maxTop = Math.max(8, originEl.scrollHeight - tipH - 8);
  left = Math.max(8, Math.min(left, maxLeft));
  top = Math.max(8, Math.min(top, maxTop));
  el.journeyTip.style.left = `${left}px`;
  el.journeyTip.style.top = `${top}px`;
}

function drawJourneyPath(payload) {
  const host = el.journeyPath;
  if (!host) return;
  const events = Array.isArray(payload?.events) ? payload.events : [];
  const nodes = journeyPageNodes(events);
  const width = Math.max(host.clientWidth || 0, 0);
  if (width < 40) {
    if (state.journeyOpen) requestAnimationFrame(() => drawJourneyPath(payload));
    return;
  }
  const lastTitle = nodes.length ? nodes[nodes.length - 1].title : "";
  const layoutKey = `${width}|${nodes.length}|${nodes[0]?.title || ""}|${lastTitle}|${nodes.filter((n) => n.milestone).length}`;
  if (layoutKey === state.journeyLayoutKey && host.querySelector("svg")) return;
  state.journeyLayoutKey = layoutKey;
  hideJourneyTip();
  host.innerHTML = "";
  if (!nodes.length) {
    const empty = document.createElement("p");
    empty.className = "journey-empty";
    empty.textContent = t("journey.empty");
    host.appendChild(empty);
    return;
  }

  const points = layoutJourneyNodes(nodes, width);
  const height = Math.max(...points.map((p) => p.y + p.r), 80) + 56;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "journey-path-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("aria-hidden", "true");

  const trail = document.createElementNS(NS, "path");
  trail.setAttribute("class", "journey-trail");
  trail.setAttribute("d", journeyTrailD(points));
  svg.appendChild(trail);

  const labels = document.createElement("div");
  labels.style.pointerEvents = "none";
  let milestoneLabel = 0;
  for (let i = 0; i < points.length; i += 1) {
    const node = points[i];
    const colors = journeyNodeFill(node);
    if (node.stamp && (node.mainRound || node.forks.length || node.grandGoal)) {
      const ring = document.createElementNS(NS, "circle");
      ring.setAttribute("cx", String(node.x));
      ring.setAttribute("cy", String(node.y));
      ring.setAttribute("r", String(node.r + 3));
      ring.setAttribute("fill", "none");
      ring.setAttribute("stroke", "#b57bff");
      ring.setAttribute("stroke-width", "2.5");
      svg.appendChild(ring);
    }
    const dot = document.createElementNS(NS, "circle");
    dot.setAttribute("cx", String(node.x));
    dot.setAttribute("cy", String(node.y));
    dot.setAttribute("r", String(node.r));
    dot.setAttribute("fill", colors.fill);
    dot.setAttribute("stroke", colors.stroke);
    dot.setAttribute("stroke-width", node.milestone ? "2" : "1.5");
    svg.appendChild(dot);
    const hit = document.createElementNS(NS, "circle");
    hit.setAttribute("class", "journey-node-hit");
    hit.setAttribute("cx", String(node.x));
    hit.setAttribute("cy", String(node.y));
    hit.setAttribute("r", String(Math.max(node.r + 6, 11)));
    hit.setAttribute("fill", "transparent");
    hit.setAttribute("tabindex", "0");
    hit.setAttribute("role", "img");
    hit.setAttribute("aria-label", [node.title, ...journeyNodeTipLines(node)].join(", "));
    hit.addEventListener("pointerenter", (ev) => showJourneyTip(node, ev.clientX, ev.clientY));
    hit.addEventListener("pointermove", (ev) => showJourneyTip(node, ev.clientX, ev.clientY));
    hit.addEventListener("pointerleave", hideJourneyTip);
    hit.addEventListener("focus", () => showJourneyTip(node, host.getBoundingClientRect().left + node.x, host.getBoundingClientRect().top + node.y));
    hit.addEventListener("blur", hideJourneyTip);
    svg.appendChild(hit);
    if (node.milestone) {
      const label = document.createElement("span");
      label.className = "journey-node-label";
      if (milestoneLabel % 2 === 1) label.classList.add("above");
      milestoneLabel += 1;
      label.textContent = node.title;
      label.style.left = `${node.x}px`;
      label.style.top = `${node.y}px`;
      labels.appendChild(label);
    }
  }
  host.appendChild(svg);
  host.appendChild(labels);
}

function renderJourneyView(payload) {
  state.journeyPayload = payload;
  state.journeyLayoutKey = "";
  drawJourneyPath(payload);
}

async function openJourneyOverlay({ credits = false } = {}) {
  if (!el.journeyOverlay || !state.sessionId) return;
  state.journeyOpen = true;
  el.journeyOverlay.classList.remove("hidden");
  if (el.journeyOverlayTitle) {
    el.journeyOverlayTitle.textContent = credits ? t("journey.credits") : t("journey.title");
  }
  try {
    const payload = await api(`/api/session/${state.sessionId}/journey`);
    renderJourneyView(payload);
  } catch {
    renderJourneyView({ events: [], visit_counts: {}, paths: [] });
  }
}

function closeJourneyOverlay() {
  state.journeyOpen = false;
  el.journeyOverlay?.classList.add("hidden");
}

function fillVictoryOverlay(status) {
  const question = String(status?.goal_question || "").trim();
  const title = status?.goal_article || "";
  if (el.victoryQuestion) {
    el.victoryQuestion.textContent = question;
    el.victoryQuestion.classList.toggle("hidden", !question);
  }
  if (el.victoryAnswer) {
    el.victoryAnswer.textContent = title ? t("victory.answer", { title }) : "";
    el.victoryAnswer.classList.toggle("hidden", !title);
  }
  if (el.victoryMessage) el.victoryMessage.textContent = t("victory.message");
  if (el.victoryOverlayTitle) el.victoryOverlayTitle.textContent = t("victory.title");
  if (el.victoryJourneyBtn) el.victoryJourneyBtn.textContent = t("victory.seeJourney");
  if (el.victoryCloseBtn) el.victoryCloseBtn.textContent = t("victory.continue");
}

function openVictoryOverlay(status) {
  if (!el.victoryOverlay) return;
  state.victoryOpen = true;
  fillVictoryOverlay(status || state.status);
  el.victoryOverlay.classList.remove("hidden");
}

function closeVictoryOverlay() {
  state.victoryOpen = false;
  el.victoryOverlay?.classList.add("hidden");
}

function bindVictoryOverlayUi() {
  el.victoryJourneyBtn?.addEventListener("click", () => {
    closeVictoryOverlay();
    void openJourneyOverlay({ credits: true });
  });
  el.victoryCloseBtn?.addEventListener("click", closeVictoryOverlay);
  el.victoryOverlayBackdrop?.addEventListener("click", closeVictoryOverlay);
}

function bindJourneyOverlayUi() {
  el.journeyBtn?.addEventListener("click", () => {
    void openJourneyOverlay({ credits: Boolean(state.status?.boss_completed) });
  });
  el.journeyOverlayClose?.addEventListener("click", closeJourneyOverlay);
  el.journeyOverlayBackdrop?.addEventListener("click", closeJourneyOverlay);
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

async function fetchLangLinks(title, fromLang) {
  const params = new URLSearchParams({
    action: "query",
    prop: "langlinks",
    lllimit: "500",
    titles: title,
    redirects: "true",
    format: "json",
    origin: "*",
    formatversion: "2",
  });
  const url = `${wikipediaOrigin(fromLang)}/w/api.php?${params}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  const page = data?.query?.pages?.[0];
  if (!page || page.missing) return [];
  const links = Array.isArray(page.langlinks) ? page.langlinks : [];
  return links
    .map((item) => ({
      lang: String(item?.lang || "").trim().toLowerCase(),
      title: String(item?.title || "").trim(),
    }))
    .filter((item) => item.lang && item.title);
}

function langLinkTitle(links, lang) {
  const want = String(lang || "").trim().toLowerCase();
  const hit = links.find((item) => item.lang === want);
  return hit?.title || "";
}

function takeQueuedTrap(name) {
  const idx = state.trapQueue.indexOf(name);
  if (idx < 0) return false;
  state.trapQueue.splice(idx, 1);
  return true;
}

async function resolveArticleNavigation(requestedTitle, { countAsClick = false } = {}) {
  const seedLang = wikipediaLanguage();
  let displayLang = state.articleLang || seedLang;
  let displayTitle = requestedTitle;
  let checkTitle = requestedTitle;

  if (displayLang !== seedLang) {
    const links = await fetchLangLinks(displayTitle, displayLang);
    const homeTitle = langLinkTitle(links, seedLang);
    if (homeTitle) {
      displayLang = seedLang;
      displayTitle = homeTitle;
      checkTitle = homeTitle;
      state.articleLang = "";
      toast(t("toast.wrongWikiBack", { lang: seedLang }), "ok", 5000);
    } else {
      toast(t("toast.wrongWikiStay", { lang: seedLang, current: displayLang }), "warn", 5000);
    }
  }

  let appliedWrongWiki = false;
  if (countAsClick && displayLang === seedLang && state.trapQueue[0] === "Wrong Wiki") {
    const links = await fetchLangLinks(displayTitle, seedLang);
    const others = links.filter((item) => item.lang !== seedLang);
    if (others.length) {
      takeQueuedTrap("Wrong Wiki");
      appliedWrongWiki = true;
      const pick = others[Math.floor(Math.random() * others.length)];
      state.articleLang = pick.lang;
      displayLang = pick.lang;
      displayTitle = pick.title;
      checkTitle = requestedTitle;
      toast(t("toast.wrongWiki", { lang: pick.lang }), "warn", 7000);
    }
  }

  return { displayLang, displayTitle, checkTitle, appliedWrongWiki };
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
  state.articleLang = "";
  try {
    toast(reasonText || t("toast.deathJump"), "warn", 7000);
    const title = await fetchRandomWikiTitle();
    resetRoundVisits(title);
    await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true, travelKind: "death" });
  } catch {
    // Still leave visits cleared; seed current page if we never left it.
    resetRoundVisits(state.currentTitle || "");
    toast(t("toast.deathFailed"), "warn");
  } finally {
    state.handlingDeath = false;
  }
}

function queueTrap(trapName) {
  if (trapName !== "Foggy Links" && trapName !== "Missing Links" && trapName !== "Wrong Wiki") return;
  state.trapQueue.push(trapName);
  toast(t("toast.trap", { name: trapLabel(trapName) }), "warn", 6500);
}

function consumeTrapQueueForPage(title, status, { skip = false } = {}) {
  state.activeFoggy = false;
  state.activeMissing = false;
  if (skip || !state.trapQueue.length) return;
  if (isProtectedNavTitle(title, status)) return;
  const next = state.trapQueue[0];
  if (next === "Foggy Links") {
    state.trapQueue.shift();
    state.activeFoggy = true;
  } else if (next === "Missing Links") {
    state.trapQueue.shift();
    state.activeMissing = true;
  }
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
  const eligible = [...root.querySelectorAll("a[data-title]")].filter((a) => {
    const dest = a.dataset.title || "";
    if (!dest) return false;
    if (isProtectedNavTitle(dest, status)) return false;
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
      const who = event.source ? String(event.source) : "";
      await applyDeathEffect(who ? t("toast.deathLinkFrom", { source: who }) : t("toast.deathLink"));
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
  el.searchLetters.textContent = t("search.letters", { letters: letters.length ? letters.join("") : "-" });

  if (!state.status?.ctrl_f_unlocked) {
    el.searchStatus.textContent = t("search.needLens");
  } else if (state.status?.searchsanity) {
    el.searchStatus.textContent = t("search.letterLimited");
  } else {
    el.searchStatus.textContent = t("search.ready");
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
  if (!el.toolIconsRow || el.toolIconsRow.dataset.ready === "4") return;
  const tools = [
    { id: "back", title: t("tool.back"), svg: TOOL_ICON_SVGS.back },
    { id: "reroll", title: t("tool.reroll"), svg: TOOL_ICON_SVGS.reroll },
    { id: "search", title: t("tool.search"), svg: TOOL_ICON_SVGS.search },
    { id: "compass", title: t("tool.compass"), svg: TOOL_ICON_SVGS.compass },
    { id: "key", title: t("tool.key"), svg: TOOL_ICON_SVGS.key },
  ];
  el.toolIconsRow.innerHTML = "";
  for (const tool of tools) el.toolIconsRow.appendChild(makeIconNode(tool));
  el.toolIconsRow.dataset.ready = "4";
}

function overflowChipWidthPx(count) {
  return Math.max(TRACK_EMPHASIS_MIN_PX, 12 + (1 + String(Math.max(0, count)).length) * 9);
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
      width += p.run.crossroad ? TRACK_CROSSROAD_PX : (p.run.current ? chipMinPx : TRACK_SEG_MIN_PX);
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
      !item.current &&
      !prev.crossroad &&
      !item.crossroad;
    if (same) {
      prev.count += 1;
      prev.endLabel = item.label;
    } else {
      runs.push({
        state: item.state,
        current: Boolean(item.current),
        crossroad: Boolean(item.crossroad),
        unlocked: Boolean(item.unlocked),
        fork: Number(item.fork) || 0,
        forkProgress: item.forkProgress || null,
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
    if (run.current || run.crossroad || run.count < TRACK_OVERFLOW_MIN) {
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

  for (const p of plan) {
    if (p.overflow > 0 && p.overflow < TRACK_OVERFLOW_MIN) {
      p.individuals += p.overflow;
      p.overflow = 0;
    }
  }

  return { plan, chipMinPx: trackChipMinPx(plan) };
}

function appendTrackSeg(trackEl, { state, current = false, overflowCount = 0, title = "", crossroad = false, unlocked = false, fork = 0, forkProgress = null }) {
  const seg = document.createElement("div");
  seg.className = "seg";
  if (state) seg.classList.add(state);
  if (current) seg.classList.add("current");
  if (crossroad) seg.classList.add("crossroad");
  if (crossroad && unlocked) seg.classList.add("unlocked");
  if (crossroad && fork > 0) seg.dataset.fork = String(fork);
  if (overflowCount > 0) {
    seg.classList.add("overflow");
    seg.textContent = `+${overflowCount}`;
  }
  if (title) seg.title = title;
  if (crossroad && forkProgress) renderForkSpur(seg, forkProgress, fork);
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
        title: t("track.moreLikeThis", {
          kind, start: hiddenStart, end: hiddenEnd, overflow,
        }),
      });
    };
    const appendIndividuals = () => {
      const individualStart = expandFromEnd ? endNum - individuals + 1 : startNum;
      for (let i = 0; i < individuals; i += 1) {
        appendTrackSeg(trackEl, {
          state: run.state,
          current: Boolean(run.current),
          crossroad: Boolean(run.crossroad),
          unlocked: Boolean(run.unlocked),
          fork: Number(run.fork) || 0,
          forkProgress: run.forkProgress || null,
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
    if (el.branchTracks) el.branchTracks.innerHTML = "";
    return;
  }
  if (el.roundsBlock) el.roundsBlock.classList.remove("hidden");
  const total = Math.max(0, Number(status.check_count) || 0);
  const current = Math.max(1, Number(status.round) || 1);
  const completed = Math.max(0, Number(status.rounds_completed) || 0);
  const unlocked = Math.max(0, Number(status.unlocked_rounds) || 0);
  const complete = Boolean(status.boss_completed);
  const crossroads = new Set(
    (Array.isArray(status.crossroad_rounds) ? status.crossroad_rounds : []).map((n) => Number(n))
  );
  const unlockedCross = new Set(
    (Array.isArray(status.unlocked_crossroad_rounds) ? status.unlocked_crossroad_rounds : []).map((n) => Number(n))
  );
  const forkByRound = new Map();
  for (const cr of Array.isArray(status.crossroads) ? status.crossroads : []) {
    const round = Number(cr?.main_round);
    if (!crossroads.has(round)) continue;
    const explicit = Number(cr?.fork);
    const fork = Number.isFinite(explicit) && explicit > 0
      ? Math.trunc(explicit)
      : Math.trunc(Number(cr?.branch_id)) + 1;
    if (fork > 0) forkByRound.set(round, fork);
  }
  const progressByFork = forkProgressByNumber(status);
  const items = [];
  for (let i = 1; i <= total; i += 1) {
    let stateName = "locked";
    if (complete || i <= completed) stateName = "done";
    else if (i <= unlocked) stateName = "open";
    const fork = forkByRound.get(i) || 0;
    items.push({
      state: stateName,
      current: !complete && i === current && i > completed,
      crossroad: crossroads.has(i),
      unlocked: unlockedCross.has(i),
      fork,
      forkProgress: fork ? (progressByFork.get(fork) || null) : null,
      label: `${t("track.kindRound")} ${i}`,
    });
  }
  el.roundsTrack.classList.toggle("has-crossroads", crossroads.size > 0);
  el.roundsTrack.style.gap = `${TRACK_SEG_GAP_PX}px`;
  const roundsPlan = buildTrackPlan(items, el.roundsTrack);
  renderPlannedTrack(el.roundsTrack, roundsPlan.plan, t("track.kindRound"), roundsPlan.chipMinPx);
  syncCrossroadTrackSpace(el.roundsTrack);
  if (el.roundText) {
    el.roundText.textContent = complete ? t("hud.complete") : `${current}/${total}`;
  }
  renderBranchTracks(status);
}

function renderFragmentsTrack(status) {
  if (!el.fragmentsTrack) return;
  if (status?.practice) {
    if (el.fragmentsBlock) el.fragmentsBlock.classList.add("hidden");
    if (el.goalRow) el.goalRow.classList.add("hidden");
    setHoverWikiTitle(el.goalHover, "");
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
    const question = String(status.goal_question || "").trim();
    const title = status.goal_article || "";
    if (question) {
      el.goalText.textContent = question;
      if (el.goalHover) el.goalHover.classList.toggle("hidden", !status.boss_completed);
      if (el.goalAnswer) {
        el.goalAnswer.textContent = status.boss_completed
          ? `${t("hud.goalAnswer", { title })} ${t("hud.goalCompleteSuffix")}`
          : "";
      }
      setHoverWikiTitle(el.goalHover, status.boss_completed ? title : "");
    } else {
      el.goalText.textContent = "";
      if (el.goalHover) el.goalHover.classList.remove("hidden");
      if (el.goalAnswer) {
        el.goalAnswer.textContent = status.boss_completed
          ? `${title || "..."} ${t("hud.goalCompleteSuffix")}`
          : (title || "...");
      }
      setHoverWikiTitle(el.goalHover, title);
    }
  } else {
    setHoverWikiTitle(el.goalHover, "");
  }
  if (showGoal) return;

  const items = [];
  for (let i = 1; i <= required; i += 1) {
    items.push({
      state: i <= have ? "filled" : "empty",
      label: `${t("track.kindFragment")} ${i}`,
    });
  }
  el.fragmentsTrack.style.gap = `${TRACK_SEG_GAP_PX}px`;
  const fragPlan = buildTrackPlan(items, el.fragmentsTrack);
  renderPlannedTrack(el.fragmentsTrack, fragPlan.plan, t("track.kindFragment"), fragPlan.chipMinPx);
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
    back.title = backMax > 0 ? `${t("tool.back")} ${backLeft}/${backMax}` : t("tool.back");
  }

  const rerollMax = Math.max(0, Number(status.target_rerolls_max) || 0);
  const rerollRemaining = Number(status.target_rerolls_remaining);
  const rerollLeft = Number.isFinite(rerollRemaining) ? Math.max(0, rerollRemaining) : rerollMax;
  if (reroll) {
    setIconState(reroll, rerollMax > 0 ? "ok" : "locked");
    setToolBadge(reroll, rerollMax > 0 ? `${rerollLeft}/${rerollMax}` : "");
    reroll.title = rerollMax > 0 ? `${t("tool.reroll")} ${rerollLeft}/${rerollMax}` : t("tool.reroll");
  }

  if (search) setIconState(search, status.ctrl_f_unlocked ? "ok" : "locked");
  if (compass) setIconState(compass, status.compass_unlocked ? "ok" : "locked");
  const key = el.toolIconsRow.querySelector('[data-tool="key"]');
  const hasBranches = Array.isArray(status.branches) && status.branches.length > 0;
  const keyCount = Math.max(0, Number(status.branch_keys_available) || 0);
  if (key) {
    key.classList.toggle("hidden", !hasBranches);
    setIconState(key, keyCount > 0 ? "ok" : "locked");
    setToolBadge(key, hasBranches ? String(keyCount) : "");
    key.title = hasBranches ? `${t("tool.key")} ×${keyCount}` : t("tool.key");
  }
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
    node.title = t(lock.i18nKey);
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
        title: t("tool.scroll"),
        svg: TOOL_ICON_SVGS.scroll,
      });
      const level = Number(status.scroll_speed_level) || 0;
      setIconState(scroll, level > 0 ? "ok" : "locked");
      const badge = scroll.querySelector(".item-icon-badge");
      if (badge) {
        badge.textContent = `${level}/${status.scroll_speed_upgrades || 0}`;
        badge.classList.remove("hidden");
      }
      scroll.title = t("hud.scrollLevel", {
        name: t("tool.scroll"),
        level,
        max: status.scroll_speed_upgrades || 0,
      });
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
    title: status.searchsanity ? t("diff.searchsanityOn") : t("diff.searchsanityOff"),
    svg: TOOL_ICON_SVGS.searchsanity,
    on: Boolean(status.searchsanity),
  });
  addDiffIcon({
    id: "scrollsanity",
    title: status.scrollsanity ? t("diff.scrollsanityOn") : t("diff.scrollsanityOff"),
    svg: TOOL_ICON_SVGS.scrollsanity,
    on: Boolean(status.scrollsanity),
  });
  addDiffIcon({
    id: "deaths",
    title: status.deaths ? t("diff.deathsOn") : t("diff.deathsOff"),
    svg: TOOL_ICON_SVGS.deaths,
    on: Boolean(status.deaths),
  });
  addDiffIcon({
    id: "deathlink",
    title: status.death_link ? t("diff.deathlinkOn") : t("diff.deathlinkOff"),
    svg: TOOL_ICON_SVGS.deathlink,
    on: Boolean(status.death_link),
  });
  addDiffIcon({
    id: "traplink",
    title: status.trap_link ? t("diff.traplinkOn") : t("diff.traplinkOff"),
    svg: TOOL_ICON_SVGS.traplink,
    on: Boolean(status.trap_link),
  });

  const bombDensity = Number(status.link_bomb_density) || 0;
  const bombCount = Number(status.link_bomb_count) || 0;
  const bombDensityCss = bombDensityKey(bombDensity);
  const bombNode = makeIconNode({
    id: "bombs",
    title: bombsOn
      ? t("diff.bombsOn", { density: bombDensityLabel(bombDensity), count: bombCount })
      : t("diff.bombsOff"),
    svg: TOOL_ICON_SVGS.bombs,
    extraClass: bombsOn ? `item-icon--bomb-${bombDensityCss}` : "",
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
  const trapsOn = trapCount > 0;
  addDiffIcon({
    id: "traps",
    title: trapsOn
      ? t("diff.trapsOn", { count: trapCount, type: trapTypeLabel(trapType) })
      : t("diff.trapsOff"),
    svg: TOOL_ICON_SVGS.traps,
    on: trapsOn,
    badge: trapsOn ? String(trapCount) : "",
  });
}

function formatBingoCompletionParts(bingoCompleted) {
  if (!Array.isArray(bingoCompleted) || !bingoCompleted.length) return [];
  return bingoCompleted.map((line) => {
    const label = String(line?.label || t("bingo.line")).trim() || t("bingo.line");
    const sent = String(line?.sent_text || "").trim();
    return sent
      ? t("bingo.lineCompleteSent", { label, sent })
      : t("bingo.lineComplete", { label });
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

/** Minimum readable cell size (px) before a sidebar board becomes a scaled preview. */
const BINGO_MIN_SIDE_CELL_PX = 22;
/** Preferred max board width in the sidebar for small grids (~12.6rem). */
const BINGO_SIDE_PREF_MAX_PX = 202;
/** Base cell size (px) for the expanded overlay board before user zoom. */
const BINGO_OVERLAY_CELL_PX = 43;
const BINGO_ZOOM_MIN = 0.4;
const BINGO_ZOOM_MAX = 4;

function renderBingoBoardGrid(board, stampedPairs, stampedCells, lines, options = {}) {
  const n = board.length;
  const pairSet = new Set(normalizeBingoPairList(stampedPairs));
  const cellSet = new Set(
    (stampedCells || [])
      .filter((cell) => Array.isArray(cell) && cell.length >= 2)
      .map((cell) => `${Number(cell[0])},${Number(cell[1])}`)
  );
  const lineMap = lines && typeof lines === "object" ? lines : {};
  const pickMode = Boolean(options.pickMode);
  const boardKey = String(options.boardKey || "");
  const onPick = typeof options.onPick === "function" ? options.onPick : null;
  const stopStampBubble = Boolean(options.stopStampBubble);

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
      if (pickMode && pair && !stamped && !lineDone && onPick) {
        cell.classList.add("stampable");
        cell.setAttribute("role", "button");
        cell.tabIndex = 0;
        cell.title = t("bingo.stampCell", { pair });
        const pick = (event) => {
          if (stopStampBubble && event) event.stopPropagation();
          onPick(boardKey, row, col, pair);
        };
        cell.addEventListener("click", pick);
        cell.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            pick(event);
          }
        });
      }
      grid.appendChild(cell);
    }
  }
  return { grid, n, lines: lineMap };
}

function bingoSidebarAvailWidth() {
  const host = el.bingoBoards;
  if (!host) return 280;
  const width = host.clientWidth;
  if (width > 40) return width;
  // Fallback before first layout: side column minus card padding.
  return 330 - 24;
}

function sizeBingoGrid(grid, n, cellPx) {
  const size = Math.max(1, n) * cellPx;
  grid.style.width = `${size}px`;
  grid.style.setProperty("--bingo-cell", `${cellPx}px`);
  grid.style.gridTemplateColumns = `repeat(${Math.max(n, 1)}, minmax(0, 1fr))`;
}

function applyBingoSidebarFit(viewport, grid, n, boardKey) {
  const avail = bingoSidebarAvailWidth();
  const readableWidth = Math.max(n, 1) * BINGO_MIN_SIDE_CELL_PX;
  if (readableWidth <= avail + 0.5) {
    const width = Math.min(avail, Math.max(BINGO_SIDE_PREF_MAX_PX, readableWidth));
    sizeBingoGrid(grid, n, width / Math.max(n, 1));
    viewport.appendChild(grid);
    return;
  }

  // Board wider than the side panel: keep a readable natural size, scale to fit.
  sizeBingoGrid(grid, n, BINGO_MIN_SIDE_CELL_PX);
  const natural = readableWidth;
  const scale = avail / natural;
  const scaler = document.createElement("div");
  scaler.className = "bingo-preview-scale";
  scaler.style.width = `${natural}px`;
  scaler.style.transform = `scale(${scale})`;
  scaler.appendChild(grid);

  viewport.classList.add("is-compact");
  viewport.style.height = `${natural * scale}px`;
  viewport.title = t("bingo.expandHint");
  viewport.setAttribute("role", "button");
  viewport.tabIndex = 0;
  viewport.setAttribute("aria-label", t("bingo.expandHint"));

  const badge = document.createElement("span");
  badge.className = "bingo-preview-badge";
  badge.textContent = t("bingo.expand");

  const open = (event) => {
    if (event?.target?.closest?.(".bingo-cell.stampable")) return;
    openBingoOverlay(boardKey);
  };
  viewport.addEventListener("click", open);
  viewport.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open(event);
    }
  });

  viewport.appendChild(scaler);
  viewport.appendChild(badge);
}

function applyBingoOverlayTransform() {
  const overlay = state.bingoOverlay;
  if (!overlay || !el.bingoOverlayWorld) return;
  const { zoom, panX, panY } = overlay;
  el.bingoOverlayWorld.style.transform =
    `translate(calc(-50% + ${panX}px), calc(-50% + ${panY}px)) scale(${zoom})`;
  if (el.bingoZoomReset) {
    el.bingoZoomReset.textContent = `${Math.round(zoom * 100)}%`;
  }
}

function setBingoOverlayZoom(nextZoom, originX = null, originY = null) {
  const overlay = state.bingoOverlay;
  if (!overlay || !el.bingoOverlayStage) return;
  const prev = overlay.zoom;
  const zoom = Math.max(BINGO_ZOOM_MIN, Math.min(BINGO_ZOOM_MAX, nextZoom));
  if (originX != null && originY != null && prev > 0) {
    const rect = el.bingoOverlayStage.getBoundingClientRect();
    const cx = originX - rect.left - rect.width / 2;
    const cy = originY - rect.top - rect.height / 2;
    const ratio = zoom / prev;
    overlay.panX = cx - (cx - overlay.panX) * ratio;
    overlay.panY = cy - (cy - overlay.panY) * ratio;
  }
  overlay.zoom = zoom;
  applyBingoOverlayTransform();
}

function closeBingoOverlay() {
  state.bingoOverlay = null;
  state.bingoOverlayDrag = null;
  if (el.bingoOverlayWorld) el.bingoOverlayWorld.innerHTML = "";
  if (el.bingoOverlay) el.bingoOverlay.classList.add("hidden");
  if (el.bingoOverlayStage) el.bingoOverlayStage.classList.remove("is-panning");
}

function refreshBingoOverlayContent() {
  const overlay = state.bingoOverlay;
  if (!overlay || !el.bingoOverlay || !el.bingoOverlayWorld) return;
  const status = state.status || {};
  if (!status.bingo_letterpairs) {
    closeBingoOverlay();
    return;
  }
  const boards = bingoBoardsFromStatus(status);
  const boardIndex = Math.max(0, Number(overlay.boardKey) - 1);
  const board = boards[boardIndex];
  if (!board || !board.length) {
    closeBingoOverlay();
    return;
  }
  const unlockedRaw = Number(status.bingo_unlocked_boards);
  const unlocked = Number.isFinite(unlockedRaw)
    ? Math.max(0, Math.min(boards.length, unlockedRaw))
    : boards.length;
  if (boardIndex >= unlocked) {
    closeBingoOverlay();
    return;
  }

  const boardKey = String(overlay.boardKey);
  const stampedMap = normalizeBingoStampedPairs(status.bingo_stamped_pairs);
  const cellsMap = normalizeBingoStampedCells(status.bingo_stamped_cells);
  const linesMap = normalizeBingoLinesChecked(status.bingo_lines_checked);
  const { remaining: stampRemaining } = bingoStampCharges(status);
  const pickMode = Boolean(state.bingoStampPickMode && stampRemaining > 0);

  const { grid, n } = renderBingoBoardGrid(
    board,
    stampedMap[boardKey] || [],
    cellsMap[boardKey] || [],
    linesMap[boardKey] || {},
    {
      boardKey,
      pickMode,
      onPick: useBingoStampOnCell,
      stopStampBubble: true,
    }
  );
  sizeBingoGrid(grid, n, BINGO_OVERLAY_CELL_PX);
  el.bingoOverlayWorld.replaceChildren(grid);
  if (el.bingoOverlayTitle) {
    const complete = isBingoBoardFullyComplete(linesMap[boardKey] || {});
    el.bingoOverlayTitle.textContent = complete
      ? t("bingo.boardComplete", { n: boardKey })
      : t("bingo.board", { n: boardKey });
  }
  applyBingoOverlayTransform();
  el.bingoOverlay.classList.remove("hidden");
}

function openBingoOverlay(boardKey) {
  const key = String(boardKey || "").trim();
  if (!key) return;
  const prev = state.bingoOverlay;
  state.bingoOverlay = {
    boardKey: key,
    zoom: prev && prev.boardKey === key ? prev.zoom : 1,
    panX: prev && prev.boardKey === key ? prev.panX : 0,
    panY: prev && prev.boardKey === key ? prev.panY : 0,
  };
  refreshBingoOverlayContent();
}

function bindBingoOverlayUi() {
  if (!el.bingoOverlay) return;
  const close = () => closeBingoOverlay();
  el.bingoOverlayClose?.addEventListener("click", close);
  el.bingoOverlayBackdrop?.addEventListener("click", close);
  el.bingoZoomIn?.addEventListener("click", () => setBingoOverlayZoom((state.bingoOverlay?.zoom || 1) * 1.2));
  el.bingoZoomOut?.addEventListener("click", () => setBingoOverlayZoom((state.bingoOverlay?.zoom || 1) / 1.2));
  el.bingoZoomReset?.addEventListener("click", () => {
    if (!state.bingoOverlay) return;
    state.bingoOverlay.zoom = 1;
    state.bingoOverlay.panX = 0;
    state.bingoOverlay.panY = 0;
    applyBingoOverlayTransform();
  });

  el.bingoOverlayStage?.addEventListener("wheel", (event) => {
    if (!state.bingoOverlay) return;
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    setBingoOverlayZoom((state.bingoOverlay.zoom || 1) * factor, event.clientX, event.clientY);
  }, { passive: false });

  el.bingoOverlayStage?.addEventListener("pointerdown", (event) => {
    if (!state.bingoOverlay) return;
    if (event.target.closest(".bingo-cell.stampable")) return;
    if (event.button != null && event.button !== 0) return;
    state.bingoOverlayDrag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originPanX: state.bingoOverlay.panX,
      originPanY: state.bingoOverlay.panY,
    };
    el.bingoOverlayStage.classList.add("is-panning");
    try { el.bingoOverlayStage.setPointerCapture(event.pointerId); } catch (_) { /* ignore */ }
  });
  el.bingoOverlayStage?.addEventListener("pointermove", (event) => {
    const drag = state.bingoOverlayDrag;
    if (!drag || drag.pointerId !== event.pointerId || !state.bingoOverlay) return;
    state.bingoOverlay.panX = drag.originPanX + (event.clientX - drag.startX);
    state.bingoOverlay.panY = drag.originPanY + (event.clientY - drag.startY);
    applyBingoOverlayTransform();
  });
  const endDrag = (event) => {
    const drag = state.bingoOverlayDrag;
    if (!drag || (event && drag.pointerId !== event.pointerId)) return;
    state.bingoOverlayDrag = null;
    el.bingoOverlayStage?.classList.remove("is-panning");
  };
  el.bingoOverlayStage?.addEventListener("pointerup", endDrag);
  el.bingoOverlayStage?.addEventListener("pointercancel", endDrag);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.bingoOverlay) {
      event.preventDefault();
      closeBingoOverlay();
    }
  });
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

function bingoStampCharges(status) {
  const max = Math.max(0, Number(status?.bingo_stamps_max) || 0);
  const remaining = Math.max(0, Number(status?.bingo_stamps_remaining) || 0);
  return { max, remaining };
}

function setBingoStampPickMode(enabled) {
  state.bingoStampPickMode = Boolean(enabled);
  renderBingoHud(state.status || {});
}

async function useBingoStampOnCell(boardKey, row, col, pair) {
  if (state.bingoStampBusy) return;
  if (!state.sessionId || !isPlayable()) {
    toast(t("toast.connectToPlay"), "warn");
    return;
  }
  if (!state.status?.bingo_storage_ready) {
    toast(t("toast.stampNotReady"), "warn");
    return;
  }
  state.bingoStampBusy = true;
  try {
    const result = await api(`/api/session/${state.sessionId}/bingo-stamp`, "POST", {
      board: boardKey,
      row,
      col,
    });
    if (result.status) updateHUD(result.status);
    state.bingoStampPickMode = false;
    const stampedPair = String(result.pair || pair || "").toUpperCase();
    toast(t("bingo.stampOk", { pair: stampedPair || "?" }), "ok");
    toastBingoCompletions(result.bingo_completed);
  } catch (err) {
    const message = String(err?.message || err || "");
    if (/no stamp charges/i.test(message)) toast(t("toast.stampNoCharges"), "warn");
    else if (/storage not ready/i.test(message)) toast(t("toast.stampNotReady"), "warn");
    else if (/already stamped|board locked|cell/i.test(message)) toast(t("toast.stampFailed"), "warn");
    else toast(t("toast.stampFailed"), "warn");
  } finally {
    state.bingoStampBusy = false;
    renderBingoHud(state.status || {});
  }
}

function renderBingoHud(status) {
  if (!el.bingoCard || !el.bingoBoards) return;
  const enabled = Boolean(status?.bingo_letterpairs);
  el.bingoCard.classList.toggle("hidden", !enabled);
  if (!enabled) {
    el.bingoBoards.innerHTML = "";
    if (el.bingoMeta) el.bingoMeta.textContent = "";
    if (el.bingoStampControls) el.bingoStampControls.classList.add("hidden");
    if (el.bingoStampHint) el.bingoStampHint.classList.add("hidden");
    state.bingoUi = null;
    state.bingoStampPickMode = false;
    closeBingoOverlay();
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
  const { max: stampMax, remaining: stampRemaining } = bingoStampCharges(status);
  if (stampRemaining <= 0) state.bingoStampPickMode = false;
  const pickMode = Boolean(state.bingoStampPickMode && stampRemaining > 0 && unlocked > 0);

  if (el.bingoStampControls) {
    const showStampUi = stampMax > 0;
    el.bingoStampControls.classList.toggle("hidden", !showStampUi);
    if (showStampUi) {
      if (el.bingoStampMeta) {
        el.bingoStampMeta.textContent = t("bingo.stamps", {
          remaining: stampRemaining,
          max: stampMax,
        });
      }
      if (el.bingoStampBtn) {
        el.bingoStampBtn.disabled = stampRemaining <= 0 || !unlocked || !status.bingo_storage_ready;
        el.bingoStampBtn.textContent = pickMode ? t("bingo.cancelStamp") : t("bingo.useStamp");
        el.bingoStampBtn.onclick = () => {
          if (pickMode) setBingoStampPickMode(false);
          else if (stampRemaining <= 0) toast(t("toast.stampNoCharges"), "warn");
          else if (!status.bingo_storage_ready) toast(t("toast.stampNotReady"), "warn");
          else setBingoStampPickMode(true);
        };
      }
    }
  }
  if (el.bingoStampHint) {
    el.bingoStampHint.classList.toggle("hidden", !pickMode);
    if (pickMode) el.bingoStampHint.textContent = t("bingo.pickHint");
  }

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

    const title = document.createElement("div");
    title.className = "bingo-board-title";

    const label = document.createElement("p");
    label.className = "bingo-board-label";
    label.textContent = complete
      ? t("bingo.boardComplete", { n: boardKey })
      : t("bingo.board", { n: boardKey });
    title.appendChild(label);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn-quiet bingo-board-toggle";
    toggle.textContent = collapsed ? t("bingo.show") : t("bingo.hide");
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.addEventListener("click", () => {
      setBingoBoardCollapsed(status, boardKey, !collapsed);
      renderBingoHud(state.status || status);
    });
    title.appendChild(toggle);
    header.appendChild(title);
    block.appendChild(header);

    const { grid, n, lines: lineMap } = renderBingoBoardGrid(
      board,
      stampedMap[boardKey] || [],
      cellsMap[boardKey] || [],
      lines,
      {
        boardKey,
        pickMode: pickMode && !collapsed,
        onPick: useBingoStampOnCell,
        stopStampBubble: true,
      }
    );
    const viewport = document.createElement("div");
    viewport.className = "bingo-board-viewport";
    block.appendChild(viewport);
    el.bingoBoards.appendChild(block);
    if (!collapsed) applyBingoSidebarFit(viewport, grid, n, boardKey);
    else viewport.appendChild(grid);

    anySize = Math.max(anySize, n);
    const lineKeys = Object.keys(lineMap);
    totalChecked += lineKeys.filter((key) => Boolean(lineMap[key])).length;
    totalLines += lineKeys.length || (n > 0 ? (2 * n + 3) : 0);
  }

  if (el.bingoMeta) {
    if (!unlocked) {
      el.bingoMeta.textContent = t("bingo.noBoards");
    } else if (unlocked === 1 && anySize) {
      el.bingoMeta.textContent = t("bingo.metaGrid", {
        n: anySize, checked: totalChecked, total: totalLines,
      });
    } else if (unlocked > 1) {
      el.bingoMeta.textContent = t("bingo.metaBoards", {
        boards: unlocked, checked: totalChecked, total: totalLines,
      });
    } else {
      el.bingoMeta.textContent = "";
    }
  }

  if (state.bingoOverlay) refreshBingoOverlayContent();
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
    if (!state.status?.ctrl_f_unlocked) toast(t("toast.ctrlFLocked"), "warn");
    else toast(t("toast.searchLocked"), "warn");
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
  const prevUnlocked = Array.isArray(state.status?.unlocked_branch_ids)
    ? state.status.unlocked_branch_ids.map((id) => Number(id))
    : [];
  noteResumeIdentityFromStatus(status);
  state.status = status;
  const remoteClicks = Number(status.clicks_used);
  if (status.practice) {
    state.clicksUsed = Number.isFinite(remoteClicks) ? remoteClicks : state.clicksUsed;
  } else {
    const saved = loadSavedClicks();
    const remote = Number.isFinite(remoteClicks) ? remoteClicks : 0;
    state.clicksUsed = Math.max(Number(state.clicksUsed) || 0, saved, remote);
  }
  syncRoundVisitTracking(status);
  if (status.practice) {
    el.connBadge.textContent = t("badge.practice");
    el.connBadge.className = "badge practice";
  } else if (status.connected_to_ap) {
    el.connBadge.textContent = t("badge.connected");
    el.connBadge.className = "badge online";
  } else {
    el.connBadge.textContent = t("badge.offline");
    el.connBadge.className = "badge offline";
  }
  updateConnectionPanel(status);

  if (wasConnected && !status.connected_to_ap && !status.practice) {
    toastSticky(t("toast.disconnectedBrowse"), "warn");
    state.bingoStampSyncKey = "";
    state.bingoRemoteStampCount = 0;
    state.bingoUi = null;
    state.articleLang = "";
  }
  if (wasPractice && !status.practice && !status.connected_to_ap) {
    clearStickyConnectionError();
  }
  if (!wasConnected && status.connected_to_ap) {
    clearStickyConnectionError();
    toast(t("toast.connected"), "ok", 4500);
    // /connect returns before AP handshake finishes; restore once we are actually online.
    void restoreArticleView(true);
  }
  if (status.boss_completed) {
    el.targetText.textContent = t("hud.goalComplete");
    setTargetSummaryTitle("");
  } else {
    el.targetText.textContent = status.current_target || "...";
    setTargetSummaryTitle(status.current_target || "");
  }
  updateRerollTargetControls(status);
  renderRoundsTrack(status);
  renderFragmentsTrack(status);
  renderBranchTargets(status);
  renderCrossroadBadge(status);
  if (el.journeyBtn) {
    el.journeyBtn.classList.toggle("hidden", !(status.connected_to_ap || status.practice));
  }

  el.compassHint.textContent = status.compass_unlocked
    ? (I18n?.localizeCompassHint
      ? I18n.localizeCompassHint(status.warmer_colder || "Calibrating")
      : (status.warmer_colder || t("hud.calibrating")))
    : t("hud.locked");
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

  if (!status.boss_completed) {
    state.announcedGoalComplete = false;
    if (state.victoryOpen) closeVictoryOverlay();
  } else if (!wasComplete && !state.announcedGoalComplete) {
    state.announcedGoalComplete = true;
    openVictoryOverlay(status);
  }
  const nextUnlocked = Array.isArray(status.unlocked_branch_ids)
    ? status.unlocked_branch_ids.map((id) => Number(id))
    : [];
  for (const id of nextUnlocked) {
    if (prevUnlocked.includes(id)) continue;
    const path = (Array.isArray(status.paths) ? status.paths : []).find(
      (item) => item && item.id === `branch:${id}`
    );
    toast(t("toast.branchUnlocked", { n: forkNumber(path) || Number(id) + 1 }), "ok", 7000);
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
    return `${t(lock.i18nKey)}: ${unlocked ? t("lens.on") : t("lens.off")}`;
  }).filter(Boolean);
  el.lensesItem.textContent = parts.length ? parts.join(" · ") : t("lens.native");
}

function isDebugMenuAllowed(info) {
  if (info && typeof info.debug_menu === "boolean") return info.debug_menu;
  const embedded = readEmbeddedBuildInfo();
  return Boolean(embedded?.debug_menu);
}

function applyDebugMenuAvailability(info) {
  const allowed = isDebugMenuAllowed(info);
  const wrap = document.getElementById("debugUnlockWrap");
  if (wrap) wrap.classList.toggle("hidden", !allowed);
  if (!allowed && (debugDisplayEnabled || debugPanelReady)) {
    disableDebugDisplayMenu();
  }
}

function setDebugQueryParam(enabled) {
  const url = new URL(window.location.href);
  if (enabled) url.searchParams.set("debug", "");
  else url.searchParams.delete("debug");
  // Keep hash (current article) while toggling debug mode.
  const next = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(window.history.state, "", next);
}

function setStuckPanelOpen(open) {
  if (!el.stuckPanel || !el.stuckToggleBtn) return;
  el.stuckPanel.classList.toggle("hidden", !open);
  el.stuckToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
}

function setDebugConsentOpen(open) {
  if (!el.debugConsentPanel) return;
  el.debugConsentPanel.classList.toggle("hidden", !open);
}

function enableDebugDisplayMenu() {
  if (!isDebugMenuAllowed()) return;
  debugDisplayEnabled = true;
  setDebugQueryParam(true);
  if (el.enableDebugMenuChk) el.enableDebugMenuChk.checked = true;
  setDebugConsentOpen(true);
  initDebugDisplayPanel();
}

function disableDebugDisplayMenu() {
  debugDisplayEnabled = false;
  debugPanelReady = false;
  setDebugQueryParam(false);
  document.getElementById("debugMenuCard")?.remove();
  if (el.enableDebugMenuChk) el.enableDebugMenuChk.checked = false;
  setDebugConsentOpen(false);
}

async function runDebugAction(action, payload = {}) {
  if (!isDebugMenuAllowed()) return null;
  if (!state.sessionId) await ensureSession();
  if (!isApConnected()) {
    toast(t("toast.debugNeedAp"), "warn");
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

  const progress = debugSection("Progress");
  progress.appendChild(debugRow([
    debugBtn("Complete round", () => runDebugAction("complete_round")),
    debugBtn("Fill fragments", () => runDebugAction("fill_fragments")),
  ]));
  progress.appendChild(debugRow([
    debugBtn("Unlock all rounds", () => runDebugAction("unlock_all_rounds")),
    debugBtn("Unlock all branches", () => runDebugAction("unlock_all_branches")),
    debugBtn("Finish Grand Goal", () => runDebugAction("finish_boss")),
  ]));
  progress.appendChild(debugRow([
    debugBtn("Reset rerolls", () => runDebugAction("reset_rerolls")),
    debugBtn("Reset backs", () => runDebugAction("reset_backs")),
  ]));
  const roundInput = document.createElement("input");
  roundInput.type = "number";
  roundInput.min = "1";
  roundInput.className = "debug-input";
  roundInput.placeholder = "Round #";
  progress.appendChild(debugRow([
    roundInput,
    debugBtn("Set round", () => {
      const round = Number(roundInput.value) || 1;
      runDebugAction("set_round", { round });
    }),
  ]));
  card.appendChild(progress);

  const items = debugSection("Unlock items");
  items.appendChild(debugRow([
    debugBtn("Back", () => runDebugAction("grant_item", { item: "Progressive Back" })),
    debugBtn("Reroll", () => runDebugAction("grant_item", { item: "Progressive Reroll" })),
    debugBtn("Bingo Card", () => runDebugAction("grant_item", { item: "Progressive Bingo Card" })),
    debugBtn("Bingo Stamp", () => runDebugAction("grant_item", { item: "Progressive Bingo Stamp" })),
    debugBtn("Branch Key", () => runDebugAction("grant_item", { item: "Branch Key" })),
    debugBtn("Compass", () => runDebugAction("grant_item", { item: "Wiki Compass" })),
    debugBtn("Ctrl+F", () => runDebugAction("grant_item", { item: "Ctrl+F Lens" })),
    debugBtn("All tools", () => runDebugAction("grant_tools")),
    debugBtn("All lenses", () => runDebugAction("grant_lenses")),
    debugBtn("Letters A–Z", () => runDebugAction("grant_letters")),
    debugBtn("Max scroll", () => runDebugAction("grant_scroll")),
  ]));
  const itemSelect = document.createElement("select");
  itemSelect.className = "debug-input";
  for (const name of [
    "Progressive Back", "Progressive Reroll", "Progressive Bingo Card", "Progressive Bingo Stamp",
    "Branch Key",
    "Wiki Compass", "Ctrl+F Lens", "Progressive Scroll Speed",
    "Table Lens", "Picture Lens", "Lead Lens", "Infobox Lens",
    "Contents Lens", "Navbox Lens", "Hatnote Lens", "Reference Lens",
    "Knowledge Fragment", "Round Access", "Footnote",
    "Foggy Links", "Missing Links", "Wrong Wiki",
    ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => `Search Letter ${letter}`),
  ]) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    itemSelect.appendChild(opt);
  }
  items.appendChild(debugRow([
    itemSelect,
    debugBtn("Grant +1", () => runDebugAction("grant_item", { item: itemSelect.value })),
  ]));
  card.appendChild(items);

  const travel = debugSection("Travel");
  travel.appendChild(debugRow([
    debugBtn("Target", async () => {
      const title = state.status?.current_target;
      state.articleLang = "";
      if (title) await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
    debugBtn("Grand Goal", async () => {
      const title = state.status?.goal_article;
      state.articleLang = "";
      if (title) await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
    debugBtn("Journey", () => {
      void openJourneyOverlay({ credits: Boolean(state.status?.boss_completed) });
    }),
    debugBtn("Victory", () => {
      if (state.status?.boss_completed) openVictoryOverlay(state.status);
      else toast("Finish Grand Goal first", "warn", 3000);
    }),
  ]));
  const pageInput = document.createElement("input");
  pageInput.type = "text";
  pageInput.className = "debug-input debug-input-wide";
  pageInput.placeholder = "Teleport to page title…";
  travel.appendChild(debugRow([
    pageInput,
    debugBtn("Go", async () => {
      const title = pageInput.value.trim();
      if (!title) {
        toast(t("toast.enterTitle"), "warn", 3000);
        return;
      }
      state.articleLang = "";
      await openArticle(title, { countAsClick: false, submitCheck: false, replaceHistory: true });
    }),
  ]));
  card.appendChild(travel);

  const challenge = debugSection("Challenges");
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
    debugBtn("Clear visits", () => {
      resetRoundVisits(state.currentTitle || "");
      toast(t("toast.visitsCleared"), "ok", 3000);
    }),
    debugBtn("Receive death", () => runDebugAction("receive_death", { cause: "Debug death" })),
    debugBtn("Send DeathLink", () => runDebugAction("send_death_link", { cause: "Debug DeathLink" })),
  ]));
  challenge.appendChild(debugRow([
    debugBtn("Trigger Foggy", () => runDebugAction("queue_trap", { trap: "Foggy Links" })),
    debugBtn("Trigger Missing", () => runDebugAction("queue_trap", { trap: "Missing Links" })),
    debugBtn("Trigger Wrong Wiki", () => runDebugAction("queue_trap", { trap: "Wrong Wiki" })),
  ]));
  card.appendChild(challenge);

  card.setAttribute("data-panel", "debug");
  const debugHead = document.createElement("div");
  debugHead.className = "card-head";
  const debugTitle = card.querySelector("h2");
  if (debugTitle) debugHead.appendChild(debugTitle);
  const debugToggle = document.createElement("button");
  debugToggle.type = "button";
  debugToggle.className = "card-toggle btn-quiet";
  debugToggle.setAttribute("data-panel-toggle", "");
  debugToggle.setAttribute("aria-expanded", "true");
  debugHead.appendChild(debugToggle);
  const debugBody = document.createElement("div");
  debugBody.className = "card-body";
  while (card.firstChild) debugBody.appendChild(card.firstChild);
  card.appendChild(debugHead);
  card.appendChild(debugBody);
  document.querySelector(".side-panel")?.appendChild(card);
  bindSidePanel(card);
  syncDebugOptionToggles(card);
}

const SIDE_PANEL_STORAGE_KEY = "wikipelago_side_panels";

function loadCollapsedPanels() {
  try {
    const raw = JSON.parse(localStorage.getItem(SIDE_PANEL_STORAGE_KEY) || "{}");
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  } catch {
    return {};
  }
}

function saveCollapsedPanels(map) {
  try {
    localStorage.setItem(SIDE_PANEL_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota */
  }
}

function isPanelCollapsed(id) {
  return Boolean(loadCollapsedPanels()[id]);
}

function setPanelCollapsed(id, collapsed) {
  const map = loadCollapsedPanels();
  if (collapsed) map[id] = true;
  else delete map[id];
  saveCollapsedPanels(map);
}

function syncPanelToggle(panel) {
  const id = panel?.getAttribute("data-panel");
  if (!id) return;
  const collapsed = isPanelCollapsed(id);
  panel.classList.toggle("is-collapsed", collapsed);
  const btn = panel.querySelector("[data-panel-toggle]");
  if (!btn) return;
  const label = collapsed ? t("panel.show") : t("panel.hide");
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  btn.setAttribute("aria-label", label);
  btn.title = label;
}

function bindSidePanel(panel) {
  if (!panel || panel.dataset.panelBound === "1") return;
  const id = panel.getAttribute("data-panel");
  const btn = panel.querySelector("[data-panel-toggle]");
  if (!id || !btn) return;
  panel.dataset.panelBound = "1";
  btn.addEventListener("click", () => {
    setPanelCollapsed(id, !isPanelCollapsed(id));
    syncPanelToggle(panel);
  });
  syncPanelToggle(panel);
}

function initSidePanelToggles() {
  document.querySelectorAll("[data-panel]").forEach(bindSidePanel);
}

function refreshSidePanelToggles() {
  document.querySelectorAll("[data-panel]").forEach(syncPanelToggle);
}

function bindStuckHelper() {
  if (el.stuckToggleBtn && el.stuckPanel) {
    el.stuckToggleBtn.addEventListener("click", () => {
      const open = el.stuckPanel.classList.contains("hidden");
      setStuckPanelOpen(open);
    });
    el.stuckToggleBtn.setAttribute("aria-expanded", "false");
  }
  if (el.enableDebugMenuChk) {
    el.enableDebugMenuChk.addEventListener("change", () => {
      if (!isDebugMenuAllowed()) {
        el.enableDebugMenuChk.checked = false;
        return;
      }
      if (el.enableDebugMenuChk.checked) {
        setDebugConsentOpen(true);
      } else {
        disableDebugDisplayMenu();
        toast(t("toast.debugDisabled"), "warn", 3500);
      }
    });
  }
  if (el.showDebugMenuBtn) {
    el.showDebugMenuBtn.addEventListener("click", () => {
      if (!isDebugMenuAllowed()) return;
      if (!el.enableDebugMenuChk?.checked) {
        if (el.enableDebugMenuChk) el.enableDebugMenuChk.checked = true;
        setDebugConsentOpen(true);
      }
      enableDebugDisplayMenu();
      toast(t("toast.debugEnabled"), "ok", 4000);
    });
  }
  applyDebugMenuAvailability();
  if (isDebugMenuAllowed() && new URLSearchParams(window.location.search).has("debug")) {
    setStuckPanelOpen(true);
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
    el.connBadge.textContent = t("badge.offline");
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
    // Strip localized [edit] / [modifier] / … chrome if editsection markup remains.
    .replace(/\[[^\]]{0,48}\]/g, (chunk) => (
      /edit|modifier|bearbeiten|editar|modifica|bewerken|redigera|edytuj|código|code|quelle|quellen/i.test(chunk)
        ? ""
        : chunk
    ))
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
  const { foggy = false, missing = false, applyLocks = true } = options;
  sanitizeHtml(root);
  markLeadSection(root);
  for (const [className, names] of Object.entries(WIKI_SECTION_HEADINGS)) {
    markNamedSections(root, names, className);
  }
  wrapTables(root);
  refreshArticleScrollHosts(root);
  processArticleLinks(root, { foggy, missing });
  // Locks toggle classes on the live article body — skip for detached pre-prepare roots.
  if (applyLocks) applyDisplayLocks();
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

function isNestedWikiTable(table) {
  return Boolean(table?.parentElement?.closest("table"));
}

function wrapTables(root) {
  root.querySelectorAll("table").forEach((table) => {
    const nested = isNestedWikiTable(table);
    // Nested layout tables keep intrinsic sizing; only top-level wraps scroll.
    if (!nested) {
      table.removeAttribute("width");
      if (table.style) {
        table.style.removeProperty("width");
        table.style.removeProperty("min-width");
        table.style.removeProperty("max-width");
      }
    }
    neutralizeTableChromeColors(table);
    table
      .querySelectorAll("caption, colgroup, col, thead, tbody, tfoot, tr, th, td")
      .forEach(neutralizeTableChromeColors);
    if (nested) return;
    if (table.parentElement?.classList.contains("table-scroll")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    table.replaceWith(wrap);
    wrap.appendChild(table);
  });
}

function refreshArticleScrollHosts(root = el.articleBody) {
  if (!root) return;
  // Avoid overflow:auto scrollports unless the table is actually wider than the article.
  root.querySelectorAll(".table-scroll").forEach((wrap) => {
    wrap.classList.remove("is-scrollable-x");
    wrap.classList.toggle("is-scrollable-x", wrap.scrollWidth > wrap.clientWidth + 1);
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
  toast(t("toast.pageTypeBlocked"), "warn");
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
      a.textContent = t("trap.foggyLink");
      a.title = "";
    }
    if (playable) playable.push(a);
  });

  if (playable) applyMissingToLinks(playable);
}

function wikiHtmlCacheKey(title, lang = articleLanguage()) {
  return `${lang}::${normalizeTitle(title)}`;
}

function clearWikiHtmlCache() {
  state.wikiHtmlCache.clear();
  state.wikiHtmlInflight.clear();
  state.wikiPreparedCache.clear();
  state.wikiPrepareInflight.clear();
  state.wikiPrefetchQueue = [];
  state.wikiPrefetchActive = 0;
  state.wikiPrefetchHoverTitle = "";
  state.wikiPrepareHoverTitle = "";
  if (state.wikiPrefetchHoverTimer) {
    clearTimeout(state.wikiPrefetchHoverTimer);
    state.wikiPrefetchHoverTimer = null;
  }
  if (state.wikiPrepareHoverTimer) {
    clearTimeout(state.wikiPrepareHoverTimer);
    state.wikiPrepareHoverTimer = null;
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

function storeWikiHtmlCache(title, html, lang = articleLanguage()) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title, lang);
  if (state.wikiHtmlCache.has(key)) state.wikiHtmlCache.delete(key);
  state.wikiHtmlCache.set(key, { html: String(html || "") });
  while (state.wikiHtmlCache.size > WIKI_PREFETCH_MAX_CACHE) {
    const oldest = state.wikiHtmlCache.keys().next().value;
    state.wikiHtmlCache.delete(oldest);
  }
}

function takeWikiHtmlCache(title, lang = articleLanguage()) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title, lang);
  const hit = state.wikiHtmlCache.get(key);
  if (!hit) return null;
  // Refresh LRU order.
  state.wikiHtmlCache.delete(key);
  state.wikiHtmlCache.set(key, hit);
  return hit.html;
}

async function fetchWikiHtmlUncached(title, lang = articleLanguage()) {
  const params = new URLSearchParams({
    action: "parse",
    page: title,
    prop: "text",
    formatversion: "2",
    format: "json",
    origin: "*",
    redirects: "true",
  });
  const url = `${wikipediaOrigin(lang)}/w/api.php?${params}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Wikipedia HTTP ${res.status} (${lang})`);
  const data = await res.json();
  if (data?.error) {
    const info = data.error.info || data.error.code || "Article unavailable";
    throw new Error(`${info} [${lang}]`);
  }
  if (!data.parse || !data.parse.text) throw new Error(`Article unavailable [${lang}]`);
  return data.parse.text;
}

async function fetchWikiHtml(title, lang = articleLanguage()) {
  ensureWikiHtmlCacheLanguage();
  const cached = takeWikiHtmlCache(title, lang);
  if (cached != null) return cached;

  const key = wikiHtmlCacheKey(title, lang);
  let inflight = state.wikiHtmlInflight.get(key);
  if (!inflight) {
    inflight = (async () => {
      try {
        const html = await fetchWikiHtmlUncached(title, lang);
        storeWikiHtmlCache(title, html, lang);
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

function storeWikiPreparedCache(title, root) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title);
  if (state.wikiPreparedCache.has(key)) state.wikiPreparedCache.delete(key);
  state.wikiPreparedCache.set(key, root);
  while (state.wikiPreparedCache.size > WIKI_PREFETCH_MAX_CACHE) {
    const oldest = state.wikiPreparedCache.keys().next().value;
    state.wikiPreparedCache.delete(oldest);
  }
}

function takeWikiPreparedCache(title) {
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(title);
  const hit = state.wikiPreparedCache.get(key);
  if (!hit) return null;
  state.wikiPreparedCache.delete(key);
  return hit;
}

function idleYield(timeoutMs = 2000) {
  return new Promise((resolve) => {
    if (typeof requestIdleCallback === "function") {
      requestIdleCallback(() => resolve(), { timeout: timeoutMs });
    } else {
      setTimeout(resolve, 0);
    }
  });
}

async function prepareWikiHtml(title) {
  const clean = String(title || "").trim();
  if (!clean || isBlockedWikiTitle(clean)) return;
  if (normalizeTitle(clean) === normalizeTitle(state.currentTitle)) return;
  ensureWikiHtmlCacheLanguage();
  const key = wikiHtmlCacheKey(clean);
  if (state.wikiPreparedCache.has(key) || state.wikiPrepareInflight.has(key)) return;

  const inflight = (async () => {
    try {
      const html = await fetchWikiHtml(clean);
      await idleYield();
      // Hover target may have changed; still finish prepare for LRU usefulness.
      const root = document.createElement("div");
      root.innerHTML = html;
      prepareArticleHtml(root, { foggy: false, missing: false, applyLocks: false });
      storeWikiPreparedCache(clean, root);
    } catch {
      /* ignore prepare failures — open will fall back to normal path */
    } finally {
      state.wikiPrepareInflight.delete(key);
    }
  })();
  state.wikiPrepareInflight.set(key, inflight);
  await inflight;
}

function scheduleWikiPrepareFromHover(title) {
  const clean = String(title || "").trim();
  if (!clean) return;
  if (state.wikiPrepareHoverTitle === clean && state.wikiPrepareHoverTimer) return;
  state.wikiPrepareHoverTitle = clean;
  if (state.wikiPrepareHoverTimer) clearTimeout(state.wikiPrepareHoverTimer);
  state.wikiPrepareHoverTimer = setTimeout(() => {
    state.wikiPrepareHoverTimer = null;
    void prepareWikiHtml(clean);
  }, WIKI_PREPARE_HOVER_MS);
}

function setArticleLoadingVisible(visible, label = null) {
  if (label == null) label = t("search.loading");
  if (!el.articleLoading) return;
  el.articleLoading.classList.toggle("hidden", !visible);
  el.articleLoading.setAttribute("aria-busy", visible ? "true" : "false");
  if (el.articleStage) el.articleStage.classList.toggle("is-loading", visible);
  if (el.articleLoadingText && visible) el.articleLoadingText.textContent = label;
}

function beginArticleLoading(label = null) {
  if (label == null) label = t("search.loading");
  const token = ++state.articleLoadingToken;
  // Avoid a flash when hover-prefetch already filled the cache.
  const timer = setTimeout(() => {
    if (token === state.articleLoadingToken) setArticleLoadingVisible(true, label);
  }, 90);
  return () => {
    clearTimeout(timer);
    if (token === state.articleLoadingToken) setArticleLoadingVisible(false);
  };
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
    travelKind = "",
  } = options;
  if (requireConnection && !requirePlayable()) return;
  if (isBlockedWikiTitle(title)) {
    toastBlockedWikiPage();
    return;
  }

  const endLoading = beginArticleLoading();

  try {
    const { displayLang, displayTitle, checkTitle, appliedWrongWiki } = await resolveArticleNavigation(title, { countAsClick });
    const prepareKey = wikiHtmlCacheKey(displayTitle, displayLang);
    const prepareWait = state.wikiPrepareInflight.get(prepareKey);
    if (prepareWait) {
      try { await prepareWait; } catch { /* fall through */ }
    }

    state.currentTitle = displayTitle;
    const seedLang = wikipediaLanguage();
    el.articleTitle.textContent = displayLang !== seedLang
      ? `${displayTitle} · ${displayLang}`
      : displayTitle;
    el.articleBody.scrollTop = 0;
    consumeTrapQueueForPage(checkTitle, state.status, { skip: appliedWrongWiki });

    const prepared = takeWikiPreparedCache(displayTitle);
    if (prepared) {
      el.articleBody.replaceChildren(...prepared.childNodes);
      // Re-apply current fog/missing on the live tree (pre-prepare used neutral flags).
      processArticleLinks(el.articleBody, {
        foggy: state.activeFoggy,
        missing: state.activeMissing,
      });
      applyDisplayLocks();
      refreshArticleScrollHosts(el.articleBody);
    } else {
      let html;
      try {
        html = await fetchWikiHtml(displayTitle, displayLang);
      } catch (err) {
        endLoading();
        const detail = err?.message ? ` (${err.message})` : "";
        toast(t("toast.openFailed", { title: displayTitle, detail }), "warn");
        return;
      }
      el.articleBody.innerHTML = html;
      prepareArticleHtml(el.articleBody, {
        foggy: state.activeFoggy,
        missing: state.activeMissing,
      });
    }
    armBombsOnPage(el.articleBody, state.status);
    if (countAsClick || !state.roundVisitSet.size) {
      state.roundVisitSet.add(normalizeTitle(displayTitle));
    } else if (!submitCheck) {
      state.roundVisitSet.add(normalizeTitle(displayTitle));
    }
    // Drop prior page snapshot; a new one is cloned lazily if Ctrl+F is used.
    state.baseArticleClone = null;
    if (state.searchOpen && el.pageSearchInput.value) {
      const sanitized = sanitizeSearchInput(el.pageSearchInput.value);
      if (sanitized !== el.pageSearchInput.value) el.pageSearchInput.value = sanitized;
      applySearchHighlights(sanitized);
    }

    if (countAsClick) state.clicksUsed += 1;
    saveLocalProgress();

    if (replaceHistory) {
      history.replaceState({ title: checkTitle }, "", `#${encodeURIComponent(checkTitle)}`);
    } else {
      history.pushState({ title: checkTitle }, "", `#${encodeURIComponent(checkTitle)}`);
    }

    // Show the page as soon as DOM work is done; bridge check can finish after.
    endLoading();

    // Always visit/stamp when playable. Only intentional wiki clicks score rounds.
    if (!isPlayable()) {
      if (countAsClick && submitCheck) toast(t("toast.disconnectedChecks"), "warn");
      return;
    }

    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/check`, "POST", {
      page_title: checkTitle,
      clicks_used: state.clicksUsed,
      submit_check: Boolean(submitCheck),
      travel_kind: travelKind || (submitCheck ? "nav" : "restore"),
    });

    if (submitCheck) {
      if (result.matched && (result.status?.practice || result.practice_rolled)) {
        // Unlimited practice: new target only — stay on this page (AP-style chaining).
        if (result.status) updateHUD(result.status);
        resetRoundVisits(displayTitle);
        const nextClicks = Number(result.status?.clicks_used);
        if (Number.isFinite(nextClicks)) {
          state.clicksUsed = Math.max(state.clicksUsed || 0, nextClicks);
        }
        saveLocalProgress();
        return;
      }
      if (result.matched) {
        const hits = Array.isArray(result.hits) ? result.hits : [];
        const parts = hits.length
          ? hits.map((hit) => {
            const title = hit.target || result.target;
            const base = hit.kind === "branch"
              ? t("toast.branchHit", {
                n: forkNumber(hit),
                title,
              })
              : t("toast.targetHit", { title });
            return hit.sent_text ? `${base} — ${hit.sent_text}` : base;
          })
          : [t("toast.targetHit", { title: result.target })];
        if (result.sent_text && !hits.some((hit) => hit.sent_text)) {
          parts[0] += ` — ${result.sent_text}`;
        }
        const bingoParts = formatBingoCompletionParts(result.bingo_completed);
        if (bingoParts.length) parts.push(bingoParts.join(" · "));
        toast(parts.join(" · "), "ok", 8000);
      } else {
        toastBingoCompletions(result.bingo_completed);
      }
      if (result.locked) toast(t("toast.roundLocked"), "warn", 6500);
      if (result.not_connected) toast(t("toast.disconnectedChecks"), "warn", 6500);
    } else {
      toastBingoCompletions(result.bingo_completed);
    }
    if (result.status) updateHUD(result.status);
  } catch (err) {
    endLoading();
    // Page is already visible; do not pretend the Wikipedia fetch failed.
    toast(err?.message || t("toast.syncFailed"), "warn");
  }
}

async function restoreArticleView(force = false) {
  if (!state.status || !isPlayable()) return;
  if (state.handlingDeath) return;
  state.articleLang = "";
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
  const dest = a.dataset.title || "";
  scheduleWikiPrefetchFromHover(dest);
  scheduleWikiPrepareFromHover(dest);
});

el.articleBody.addEventListener("load", (e) => {
  const tag = String(e.target?.tagName || "");
  if (tag === "IMG" || tag === "VIDEO") refreshArticleScrollHosts();
}, true);

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

  // Bomb hit (only on forward wiki clicks).
  if (linkBombsEnabled() && state.bombTitles.has(destNorm) && !isProtectedNavTitle(dest, state.status)) {
    await notifyDeathLink(`${state.status?.slot_name || "Player"} hit a link bomb`);
    await applyDeathEffect(t("toast.bombDeath"));
    return;
  }

  // Loop-death: forward revisit of a page already visited this round.
  if (
    deathsEnabled()
    && state.roundVisitSet.has(destNorm)
    && !isProtectedNavTitle(dest, state.status)
  ) {
    await notifyDeathLink(`${state.status?.slot_name || "Player"} looped on Wikipedia`);
    await applyDeathEffect(t("toast.loopDeath"));
    return;
  }

  openArticle(dest, { countAsClick: true });
});

function isEventInSidePanel(target) {
  return Boolean(target?.closest?.(".side-panel"));
}

function applyArticleWheel(deltaY) {
  if (!el.articleBody) return;
  const factor = state.status?.scrollsanity ? scrollFactor() : 1;
  el.articleBody.scrollTop += deltaY * factor;
}

// One scroll path: always drive #articleBody ourselves (except side panel / bingo overlay).
// Native scrolling over nested overflow:auto hosts was latching the wheel at mid-page.
window.addEventListener("wheel", (e) => {
  if (isEventInSidePanel(e.target)) return;
  if (e.target?.closest?.("#bingoOverlay")) return;
  if (!el.articleBody) return;

  const nest = e.target?.closest?.(".table-scroll.is-scrollable-x");
  if (
    nest
    && el.articleBody.contains(nest)
    && (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY))
  ) {
    e.preventDefault();
    nest.scrollLeft += e.shiftKey ? e.deltaY : e.deltaX;
    return;
  }

  e.preventDefault();
  applyArticleWheel(e.deltaY);
}, { passive: false });

window.addEventListener("resize", () => {
  refreshArticleScrollHosts();
}, { passive: true });

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
    toast(t("toast.connecting"), "ok", 4500);
    const online = await waitForApConnection();
    if (!online) {
      toastSticky(state.status?.last_error || t("toast.connectFailed"), "warn");
      return;
    }
    const nextIdentity = progressIdentity();
    if (prevIdentity && prevIdentity !== nextIdentity) {
      clearStickyArticleResume();
    }
    state.resumeIdentity = nextIdentity;
    await restoreArticleView(true);
  } catch (err) {
    toastSticky(err.message || t("toast.connectFailedShort"), "warn");
  }
});

el.practiceBtn?.addEventListener("click", async () => {
  try {
    clearStickyConnectionError();
    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/practice`, "POST", {
      wikipedia_language: uiLanguage(),
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
    toastSticky(err.message || t("toast.practiceFailed"), "warn");
  }
});

el.disconnectBtn?.addEventListener("click", async () => {
  try {
    const leavingPractice = isPracticeMode();
    await ensureSession();
    const result = await api(`/api/session/${state.sessionId}/disconnect`, "POST", {});
    if (result.status) updateHUD(result.status);
    else await pollStatus();
    toast(leavingPractice ? t("toast.leftPractice") : t("toast.disconnected"), "warn", 4500);
  } catch (err) {
    toastSticky(err.message || t("toast.disconnectFailed"), "warn");
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
    el.searchStatus.textContent = t("search.matchCount", { n: hits });
  }
});

function backBlockedToast() {
  const max = Number(state.status?.back_depth_max) || 0;
  if (max <= 0) toast(t("toast.backLocked"), "warn");
  else toast(t("toast.noBacks"), "warn");
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
  if (e.key === "Escape" && state.journeyOpen) {
    e.preventDefault();
    closeJourneyOverlay();
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
      toast(t("toast.backFailed", { error: err.message || err }), "warn");
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

function showMigrateBannerIfNeeded() {
  const banner = document.getElementById("migrateBanner");
  if (!banner) return;
  if (window.location.hostname.endsWith("onrender.com")) {
    banner.classList.remove("hidden");
  }
}

ensureToolIcons();
bindTargetTooltip();
bindUiLanguageControls();
bindBingoOverlayUi();
bindJourneyOverlayUi();
bindVictoryOverlayUi();
bindStuckHelper();
initSidePanelToggles();
showMigrateBannerIfNeeded();
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
  if (el.journeyPath) {
    let journeyResizeTimer = 0;
    const journeyResizeObserver = new ResizeObserver(() => {
      if (!state.journeyOpen || !state.journeyPayload) return;
      window.clearTimeout(journeyResizeTimer);
      journeyResizeTimer = window.setTimeout(() => {
        drawJourneyPath(state.journeyPayload);
      }, 50);
    });
    journeyResizeObserver.observe(el.journeyPath);
  }
}
setInterval(pollStatus, 1500);

(async () => {
  await loadBuildBadge();
  await ensureSession();
  await pollStatus();
  if (isPlayable()) await restoreArticleView(true);
})();
