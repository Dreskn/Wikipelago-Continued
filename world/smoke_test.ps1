param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [switch]$BuildApworld
)

$ErrorActionPreference = "Stop"

function Write-Pass($message) {
    Write-Host "[PASS] $message" -ForegroundColor Green
}

function Write-Fail($message) {
    Write-Host "[FAIL] $message" -ForegroundColor Red
}

function Test-StrictUtf8File([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $utf8 = [System.Text.UTF8Encoding]::new($false, $true)
    try {
        [void]$utf8.GetString($bytes)
        return $true
    } catch {
        return $false
    }
}

function Assert-NoPattern([string]$Path, [string]$Pattern, [string]$Message) {
    if (Select-String -Path $Path -Pattern $Pattern -Quiet) {
        throw "$Message [$Path]"
    }
}

function Assert-HasPattern([string]$Path, [string]$Pattern, [string]$Message) {
    if (-not (Select-String -Path $Path -Pattern $Pattern -Quiet)) {
        throw "$Message [$Path]"
    }
}

$srcRoot = Join-Path $Root "APWorldSource"
$worldRoot = Join-Path $srcRoot "wikipelago"
$repoRoot = Split-Path -Parent $Root
$bridgePath = [System.IO.Path]::Combine($repoRoot, "bridge", "bridge.py")
$webAppPath = [System.IO.Path]::Combine($repoRoot, "web", "app.js")
$webIndexPath = [System.IO.Path]::Combine($repoRoot, "web", "index.html")
$webCssPath = [System.IO.Path]::Combine($repoRoot, "web", "style.css")
$webI18nPath = [System.IO.Path]::Combine($repoRoot, "web", "i18n.js")
$webManifestPath = [System.IO.Path]::Combine($repoRoot, "web", "manifest.webmanifest")
$webServiceWorkerPath = [System.IO.Path]::Combine($repoRoot, "web", "service-worker.js")
$yamlPath = [System.IO.Path]::Combine($repoRoot, "yaml", "Wikipelago.yaml")
$apworldPath = [System.IO.Path]::Combine($Root, "APWorld", "wikipelago.apworld")

if ($BuildApworld) {
    & (Join-Path $Root "build_apworld.ps1") -Root $Root
}

$failures = New-Object System.Collections.Generic.List[string]

try {
    if (-not (Test-Path $worldRoot)) { throw "Missing APWorldSource\wikipelago folder" }
    Write-Pass "Found world source folder"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    $filesToCheck = Get-ChildItem -Path $worldRoot -Filter *.py -File
    foreach ($file in $filesToCheck) {
        if (-not (Test-StrictUtf8File $file.FullName)) {
            throw "File is not strict UTF-8: $($file.FullName)"
        }
    }
    Write-Pass "All APWorld source .py files are strict UTF-8"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    if (Test-Path $bridgePath) {
        if (-not (Test-StrictUtf8File $bridgePath)) {
            throw "Bridge file is not strict UTF-8: $bridgePath"
        }
        Write-Pass "Bridge file is strict UTF-8"
    } else {
        throw "Missing bridge.py at $bridgePath"
    }
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    if (-not (Test-Path $yamlPath)) {
        throw "Missing YAML template at $yamlPath"
    }
    $yamlToCheck = $yamlPath
    if (-not (Test-StrictUtf8File $yamlToCheck)) {
        throw "YAML template is not strict UTF-8: $yamlToCheck"
    }
    Assert-NoPattern $yamlToCheck 'goal_article_preset:\s*pokemon\s*$' 'Invalid YAML preset alias found'
    Assert-HasPattern $yamlToCheck 'Deprecated and ignored' 'YAML template must mark goal_article_preset as deprecated'
    Assert-HasPattern $yamlToCheck 'searchsanity:\s*(true|false)' 'YAML template is missing searchsanity'
    Assert-HasPattern $yamlToCheck 'scrollsanity:\s*(true|false)' 'YAML template is missing scrollsanity'
    Assert-HasPattern $yamlToCheck 'search_starting_letters:\s*(none|all_vowels|etaoi|raise)' 'YAML template is missing search_starting_letters'
    Assert-HasPattern $yamlToCheck 'randomize_tables:\s*(true|false)' 'YAML template is missing randomize_tables'
    Assert-HasPattern $yamlToCheck 'randomize_pictures:\s*(true|false)' 'YAML template is missing randomize_pictures'
    Assert-HasPattern $yamlToCheck 'randomize_incipit:\s*(true|false)' 'YAML template is missing randomize_incipit'
    Assert-HasPattern $yamlToCheck 'randomize_infoboxes:\s*(true|false)' 'YAML template is missing randomize_infoboxes'
    Assert-HasPattern $yamlToCheck 'randomize_toc:\s*(true|false)' 'YAML template is missing randomize_toc'
    Assert-HasPattern $yamlToCheck 'randomize_navboxes:\s*(true|false)' 'YAML template is missing randomize_navboxes'
    Assert-HasPattern $yamlToCheck 'randomize_hatnotes:\s*(true|false)' 'YAML template is missing randomize_hatnotes'
    Assert-HasPattern $yamlToCheck 'randomize_references:\s*(true|false)' 'YAML template is missing randomize_references'
    Assert-HasPattern $yamlToCheck 'include_music:\s*(true|false)' 'YAML template is missing include_music'
    Assert-HasPattern $yamlToCheck 'deaths:\s*(true|false)' 'YAML template is missing deaths'
    Assert-HasPattern $yamlToCheck 'death_link:\s*(true|false)' 'YAML template is missing death_link'
    Assert-HasPattern $yamlToCheck 'link_bombs:\s*(true|false)' 'YAML template is missing link_bombs'
    Assert-HasPattern $yamlToCheck 'link_bomb_density:\s*(few|more|insane)' 'YAML template is missing link_bomb_density'
    Assert-HasPattern $yamlToCheck '^requires:\s*$' 'YAML template is missing requires block'
    Assert-HasPattern $yamlToCheck '^\s*version:\s*0\.6\.7\s*$' 'YAML template is missing requires.version 0.6.7'
    $ciPath = Join-Path $repoRoot ".github\workflows\ci.yml"
    Assert-HasPattern $ciPath 'ArchipelagoMW/Archipelago' 'CI must check out Archipelago to run Generate'
    Assert-HasPattern $ciPath 'AP_REF: "0\.6\.7"' 'CI Generate must pin Archipelago 0.6.7'
    Assert-HasPattern $ciPath 'world/ci_generate.py' 'CI must run world/ci_generate.py'
    Assert-HasPattern ([System.IO.Path]::Combine($Root, "ci_generate.py")) 'wikipelago.apworld' 'world/ci_generate.py must install the built apworld'
    Assert-HasPattern $yamlToCheck '^\s*Wikipelago:\s*1\.0\.0\s*$' 'YAML template is missing requires.game.Wikipelago 1.0.0'
    Assert-HasPattern $bridgePath 'CLIENT_VERSION = "1.0-beta1"' 'Bridge client version must be 1.0-beta1'
    Assert-HasPattern ([System.IO.Path]::Combine($repoRoot, "bridge", "start_bridge.bat")) 'py -3' 'Bridge start script must use the Windows py launcher'
    Assert-HasPattern ([System.IO.Path]::Combine($worldRoot, "archipelago.json")) '"full_version": "1.0-beta1"' 'World full_version must be 1.0-beta1'
    Assert-HasPattern $yamlToCheck 'required_fragments:\s*\d+' 'YAML template is missing required_fragments'
    Assert-HasPattern $yamlToCheck 'additional_fragments_in_pool:\s*\d+' 'YAML template is missing additional_fragments_in_pool'
    Assert-HasPattern $yamlToCheck 'trap_count:\s*\d+' 'YAML template is missing trap_count'
    Assert-HasPattern $yamlToCheck 'trap_type:\s*(all|both|only_foggy_links|only_missing_links|only_wrong_wiki)' 'YAML template is missing trap_type'
    Assert-HasPattern $yamlToCheck 'trap_link:\s*(true|false)' 'YAML template is missing trap_link'
    Assert-HasPattern $yamlToCheck 'toggle_bingo_letterpairs:\s*(true|false)' 'YAML template is missing toggle_bingo_letterpairs'
    Assert-HasPattern $yamlToCheck 'bingo_letterpairs_grid:\s*\d+' 'YAML template is missing bingo_letterpairs_grid'
    Assert-HasPattern $yamlToCheck 'branch_count:\s*\d+' 'YAML template is missing branch_count'
    Assert-HasPattern $yamlToCheck 'branch_length:\s*\d+' 'YAML template is missing branch_length'
    Assert-HasPattern $yamlToCheck 'additional_branch_keys:\s*\d+' 'YAML template is missing additional_branch_keys'
    Write-Pass "YAML template encoding and preset values look sane"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    $initPath = Join-Path $worldRoot "__init__.py"
    $optionsPath = Join-Path $worldRoot "Options.py"
    $itemsPath = Join-Path $worldRoot "Items.py"
    $articlePoolPath = Join-Path $worldRoot "article_pool.py"
    $poolEnPath = Join-Path $worldRoot "data\pool_en.json"

    Assert-NoPattern $initPath '`r`n' 'Literal backtick newline text regression found in __init__.py'
    Assert-NoPattern $initPath 'goal_article_preset:\s*pokemon\s*$' 'Invalid YAML preset text leaked into __init__.py'
    Assert-NoPattern $optionsPath 'include_board_games' 'board_games category should be removed in 0.6'
    Assert-HasPattern $articlePoolPath 'def load_article_pool' 'article_pool.load_article_pool missing'
    Assert-HasPattern $articlePoolPath 'def is_blocked_wiki_title' 'article_pool.is_blocked_wiki_title missing'
    Assert-HasPattern $articlePoolPath 'plik' 'article_pool blocked namespaces must include Polish Plik'
    Assert-HasPattern $articlePoolPath 'fichier' 'article_pool blocked namespaces must include French Fichier'
    Assert-HasPattern $articlePoolPath 'vorlage' 'article_pool blocked namespaces must include German Vorlage'
    Assert-HasPattern $articlePoolPath 'sjabloon' 'article_pool blocked namespaces must include Dutch Sjabloon'
    Assert-HasPattern $articlePoolPath 'szablon' 'article_pool blocked namespaces must include Polish Szablon'
    Assert-HasPattern $articlePoolPath 'portail' 'article_pool blocked namespaces must include French Portail'
    Assert-HasPattern $initPath 'is_blocked_wiki_title' 'Generate must skip blocked wiki namespaces'
    if (-not (Test-Path -LiteralPath $poolEnPath)) {
        throw "EN multi-tag pool data/pool_en.json missing [$poolEnPath]"
    }
    Assert-NoPattern $poolEnPath 'Template:Pornography' 'EN pool must not ship Template:Pornography'
    Assert-HasPattern $optionsPath 'class WikipediaLanguage' 'WikipediaLanguage option is missing'
    Assert-HasPattern $optionsPath 'class IncludeSensitivePages' 'IncludeSensitivePages option is missing'
    Assert-HasPattern $optionsPath 'class IncludeFamousPeople' 'IncludeFamousPeople option is missing'
    Assert-HasPattern $initPath 'pick_grand_goal_card' 'World must pick Grand Goal from the goal pool'
    Assert-NoPattern $initPath '_preset_goal_name' 'Deprecated goal presets must not be used at generate time'
    Assert-HasPattern $initPath '"goal_question"' 'World slot data must include goal_question'
    $grandGoalPath = Join-Path $worldRoot "grand_goal.py"
    Assert-HasPattern $grandGoalPath 'def pick_grand_goal_card' 'grand_goal.pick_grand_goal_card missing'
    Assert-HasPattern $grandGoalPath 'include_sensitive' 'Grand Goal pick must honor include_sensitive_pages'
    Assert-HasPattern $initPath 'sensitive_titles' 'World must pass pool-flagged sensitive titles into Grand Goal pick'
    $bankDir = Join-Path $repoRoot "docs\grand-goal\bank"
    foreach ($lang in @("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")) {
        $bankFile = Join-Path $bankDir "$lang.json"
        if (-not (Test-Path -LiteralPath $bankFile)) {
            throw "Missing Grand Goal question bank [$bankFile]"
        }
        Assert-NoPattern $bankFile '"status":' "Grand Goal pool must not use a draft/review status field [$lang]"
    }
    Assert-HasPattern $initPath '_entry_matches' 'Multi-tag pool filter helper is missing'
    Assert-HasPattern $optionsPath 'class Searchsanity' 'Searchsanity option is missing'
    Assert-HasPattern $optionsPath 'class Scrollsanity' 'Scrollsanity option is missing'
    Assert-HasPattern $optionsPath 'class SearchStartingLetters' 'Search Starting Letters option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeTables' 'Randomize Tables option is missing'
    Assert-HasPattern $optionsPath 'class RandomizePictures' 'Randomize Pictures option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeIncipit' 'Randomize Incipit option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeInfoboxes' 'Randomize Infoboxes option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeToc' 'Randomize TOC option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeNavboxes' 'Randomize Navboxes option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeHatnotes' 'Randomize Hatnotes option is missing'
    Assert-HasPattern $optionsPath 'class RandomizeReferences' 'Randomize References option is missing'
    Assert-HasPattern $itemsPath '"Progressive Scroll Speed"' 'Progressive Scroll Speed item is missing'
    Assert-HasPattern $itemsPath '"Table Lens"' 'Table Lens item is missing'
    Assert-HasPattern $itemsPath '"Picture Lens"' 'Picture Lens item is missing'
    Assert-HasPattern $itemsPath '"Lead Lens"' 'Lead Lens item is missing'
    Assert-HasPattern $itemsPath '"Infobox Lens"' 'Infobox Lens item is missing'
    Assert-HasPattern $itemsPath '"Contents Lens"' 'Contents Lens item is missing'
    Assert-HasPattern $itemsPath '"Navbox Lens"' 'Navbox Lens item is missing'
    Assert-HasPattern $itemsPath '"Hatnote Lens"' 'Hatnote Lens item is missing'
    Assert-HasPattern $itemsPath '"Reference Lens"' 'Reference Lens item is missing'
    Assert-HasPattern $optionsPath 'class IncludeMusic' 'IncludeMusic option is missing'
    Assert-HasPattern $initPath 'include_music' 'Music category selection is missing'
    Assert-HasPattern $optionsPath 'class Deaths' 'Deaths option is missing'
    Assert-HasPattern $optionsPath 'class DeathLink' 'DeathLink option is missing'
    Assert-HasPattern $optionsPath 'class LinkBombs' 'LinkBombs option is missing'
    Assert-HasPattern $optionsPath 'class RequiredFragments' 'RequiredFragments option is missing'
    Assert-HasPattern $optionsPath 'class AdditionalFragmentsInPool' 'AdditionalFragmentsInPool option is missing'
    Assert-HasPattern $optionsPath 'class TrapCount' 'TrapCount option is missing'
    Assert-HasPattern $optionsPath 'class TrapType' 'TrapType option is missing'
    Assert-HasPattern $optionsPath 'option_all = 0' 'TrapType must include all'
    Assert-HasPattern $optionsPath 'alias_both = 0' 'Deprecated trap_type both must remain a valid alias'
    Assert-HasPattern $yamlPath 'both is deprecated' 'YAML must note that trap_type both is deprecated'
    Assert-HasPattern $optionsPath 'class TrapLink' 'TrapLink option is missing'
    Assert-HasPattern $optionsPath 'class ToggleBingoLetterpairs' 'ToggleBingoLetterpairs option is missing'
    Assert-HasPattern $optionsPath 'class BingoLetterpairsGrid' 'BingoLetterpairsGrid option is missing'
    Assert-HasPattern $optionsPath 'class BingoCardsStart' 'BingoCardsStart option is missing'
    Assert-HasPattern $optionsPath 'How many letter-pair bingo boards are unlocked from the start \(0 =' 'BingoCardsStart docstring should allow 0'
    Assert-HasPattern $itemsPath '"Foggy Links"' 'Foggy Links trap item is missing'
    Assert-HasPattern $itemsPath '"Missing Links"' 'Missing Links trap item is missing'
    Assert-HasPattern $itemsPath '"Wrong Wiki"' 'Wrong Wiki trap item is missing'
    Assert-HasPattern $initPath '_trap_item_names' 'Trap item name helper is missing'
    Assert-HasPattern $bridgePath 'MAX_AP_CONNECT_ATTEMPTS' 'Bridge reconnect attempt limit is missing'
    Assert-HasPattern $bridgePath 'send_death_link' 'Bridge DeathLink send helper is missing'
    Assert-HasPattern $bridgePath 'send_trap_link' 'Bridge TrapLink send helper is missing'
    Assert-HasPattern $webAppPath 'submitCheck' 'Web submitCheck gating is missing'
    Assert-HasPattern $webAppPath 'submit_check: Boolean\(submitCheck\)' 'Web always-visit check payload is missing'
    Assert-HasPattern $webAppPath 'function renderBingoHud' 'Web bingo HUD renderer is missing'
    Assert-HasPattern $webAppPath 'bingo-board-title' 'Web per-board hide must sit beside the Board N label'
    Assert-HasPattern $webAppPath 'applyBingoAutoHide' 'Web bingo auto-hide helper is missing'
    Assert-NoPattern $webIndexPath 'id="bingoSectionToggleBtn"' 'Web must not keep section-level bingo toggle'
    Assert-HasPattern $webAppPath 'function toastBingoCompletions' 'Web bingo toast helper is missing'
    Assert-HasPattern $webAppPath 'bingo_letterpairs_boards' 'Web multi-board bingo status handling is missing'
    Assert-HasPattern $webAppPath 'use-back' 'Web Progressive Back use-back call is missing'
    Assert-HasPattern $webAppPath 'portail' 'Web blocked namespaces must include French Portail'
    Assert-HasPattern $webAppPath 'state.trapQueue\[0\]' 'Traps must apply one at a time from the front of the queue'
    Assert-HasPattern $webAppPath 'diff.trapType.all' 'HUD trap type label must include all'
    Assert-HasPattern $webI18nPath 'diff.trapType.all' 'i18n trap type all is missing'
    Assert-HasPattern $webAppPath 'liens externes' 'Web section headings must include French Liens externes'
    Assert-HasPattern $webAppPath 'WIKI_SECTION_HEADINGS' 'Web multilingual section heading map is missing'
    Assert-HasPattern $webAppPath 'can_go_back' 'Web can_go_back gating is missing'
    Assert-HasPattern $webAppPath 'data-tool="reroll"' 'Web Progressive Reroll tool icon is missing'
    Assert-HasPattern $webAppPath 'line-complete' 'Web bingo completed-line styling hook is missing'
    Assert-HasPattern $bridgePath 'bingo_completed' 'Bridge bingo_completed response field is missing'
    Assert-HasPattern $bridgePath '_bingo_line_label' 'Bridge bingo line label helper is missing'
    Assert-HasPattern $bridgePath 'merge_bingo_stamps' 'Bridge bingo stamp merge helper is missing'
    Assert-HasPattern $bridgePath 'bingo-stamps' 'Bridge bingo-stamps route is missing'
    Assert-HasPattern $bridgePath '_request_bingo_stamps_from_storage' 'Bridge bingo DataStorage Get helper is missing'
    Assert-HasPattern $bridgePath '_persist_bingo_stamps' 'Bridge bingo DataStorage Set helper is missing'
    Assert-HasPattern $bridgePath '"cmd": "Get"' 'Bridge DataStorage Get packet is missing'
    Assert-HasPattern $bridgePath '"cmd": "Set"' 'Bridge DataStorage Set packet is missing'
    Assert-HasPattern $bridgePath '"cmd": "SetNotify"' 'Bridge DataStorage SetNotify packet is missing'
    Assert-HasPattern $bridgePath '_resolve_set_reply' 'Bridge DataStorage SetReply handler is missing'
    Assert-HasPattern $bridgePath 'bingo_storage_ready' 'Bridge bingo_storage_ready status is missing'
    Assert-HasPattern $bridgePath 'bingo_stamps_updated' 'Bridge bingo_stamps_updated event is missing'
    Assert-HasPattern $bridgePath '_persist_bingo_stamps\(force=True\)' 'Bridge must force-persist after DataStorage Retrieved'
    Assert-HasPattern $bridgePath 'if not force and not self\.state\.bingo_storage_ready' 'Bridge must gate DataStorage writes until Retrieved'
    Assert-HasPattern $webAppPath 'bingo_storage_ready' 'Web bingo_storage_ready sync gate is missing'
    Assert-HasPattern $webAppPath 'bingo_stamps_updated' 'Web bingo_stamps_updated event handler is missing'
    Assert-HasPattern $webAppPath 'Before DataStorage Retrieved, never push' 'Web must not push stamps before storage ready'
    Assert-HasPattern $bridgePath 'disconnect_session' 'Bridge disconnect_session handler is missing'
    Assert-HasPattern $bridgePath '/disconnect' 'Bridge disconnect route is missing'
    Assert-HasPattern $webAppPath 'updateConnectionPanel' 'Web connection panel collapse helper is missing'
    Assert-HasPattern $webAppPath 'disconnectBtn' 'Web disconnect button wiring is missing'
    Assert-HasPattern $webAppPath 'isPracticeMode' 'Web practice mode helper is missing'
    Assert-HasPattern $webAppPath 'isPlayable' 'Web isPlayable helper is missing'
    Assert-HasPattern $webAppPath '/practice' 'Web practice API call is missing'
    Assert-HasPattern $webIndexPath 'id="connectionSummary"' 'Web connection summary markup is missing'
    Assert-HasPattern $webIndexPath 'id="connectedSlotText"' 'Web connection panel must show the slot name'
    Assert-HasPattern $webIndexPath 'connection-head' 'Web connection panel must keep Disconnect on the header row'
    Assert-HasPattern $webIndexPath 'id="disconnectBtn"' 'Web disconnect button markup is missing'
    Assert-HasPattern $webIndexPath 'id="practiceBtn"' 'Web practice button markup is missing'
    Assert-HasPattern $webAppPath 'syncBingoStampsToBridge' 'Web bingo stamp sync helper is missing'
    Assert-HasPattern $webAppPath 'bingoStampStorageKey' 'Web bingo stamp storage key helper is missing'
    Assert-HasPattern $webIndexPath 'id="bingoCard"' 'Web bingo card markup is missing'
    Assert-HasPattern $webAppPath 'toastSticky' 'Web sticky toast helper is missing'
    Assert-HasPattern $webAppPath 'applyDeathEffect' 'Web death effect helper is missing'
    Assert-HasPattern $webAppPath 't\("toast.bombDeath"\)' 'Link-bomb death toast must be translated'
    Assert-HasPattern $webAppPath 't\("toast.loopDeath"\)' 'Loop-death toast must be translated'
    Assert-HasPattern $webI18nPath '"journey.kind.nav"' 'Journey kind labels must exist in i18n'
    Assert-HasPattern $webI18nPath '"trap.foggy"' 'Trap display names must exist in i18n'
    Assert-HasPattern $webAppPath 'resetRoundVisits\(""\)' 'Web death path must clear visit tracking immediately'
    Assert-HasPattern $webAppPath 'if \(state\.handlingDeath\) return;' 'Web must ignore input while a death is handling'
    Assert-HasPattern $webAppPath 'armBombsOnPage' 'Web bomb arming helper is missing'
    Assert-HasPattern $webAppPath 'rerollCurrentTarget' 'Web target reroll helper is missing'
    Assert-HasPattern $bridgePath 'rerollable_target_slots' 'Bridge must reroll every live target in one use'
    Assert-HasPattern $bridgePath 'def target_rerolls_max' 'Bridge dynamic target_rerolls_max is missing'
    Assert-HasPattern $bridgePath 'use-back' 'Bridge use-back route is missing'
    Assert-HasPattern $bridgePath 'Progressive Back' 'Bridge Progressive Back item is missing'
    Assert-HasPattern $bridgePath 'Progressive Reroll' 'Bridge Progressive Reroll item is missing'
    Assert-HasPattern $bridgePath 'Progressive Bingo Card' 'Bridge Progressive Bingo Card item is missing'
    Assert-HasPattern $bridgePath 'Progressive Bingo Stamp' 'Bridge Progressive Bingo Stamp item is missing'
    Assert-HasPattern $bridgePath 'bingo-stamp' 'Bridge bingo-stamp route is missing'
    Assert-HasPattern $bridgePath 'use_bingo_stamp' 'Bridge use_bingo_stamp handler is missing'
    Assert-HasPattern $bridgePath 'bingo_letterpairs_boards' 'Bridge multi-board bingo status is missing'
    Assert-HasPattern $bridgePath 'unlocked_bingo_boards' 'Bridge unlocked_bingo_boards helper is missing'
    Assert-HasPattern $bridgePath 'async def ensure_goal_status_if_complete' 'Bridge ensure_goal_status_if_complete is missing'
    Assert-HasPattern $bridgePath 'if self\.state\.boss_completed:' 'Bridge goal status must honor boss_completed'
    Assert-HasPattern $bridgePath 'location_grand_goal in self\.state\.checked_locations' 'Bridge goal status must require Grand Goal checked'
    Assert-NoPattern $bridgePath 'all\(loc in self\.state\.checked_locations for loc in self\.state\.location_round_ids\)' 'Bridge must not declare goal when only all rounds are checked'
    Assert-HasPattern $initPath 'needed_from_remaining = round_count \+ 1' 'World must sample opening start plus N non-goal targets'
    Assert-NoPattern $initPath 'targets = non_final_targets \+ \[self\.goal_article\]' 'World must not append goal_article as the final round target'
    Assert-HasPattern $initPath 'used_titles = \{first_start, \*targets, self\.goal_article\}' 'World must keep Grand Goal out of round targets'
    Assert-HasPattern $bridgePath 'goal_article_title' 'Bridge must store slot_data goal_article separately'
    Assert-HasPattern $bridgePath '"rounds_completed"' 'Bridge status rounds_completed is missing'
    Assert-HasPattern $bridgePath 'round_index < len\(self\.round_pairs\)' 'Bridge must allow reroll on the final normal round'
    Assert-NoPattern $bridgePath 'cannot reroll the Grand Goal round' 'Bridge must not treat the final round as an unrerollable Goal round'
    Assert-NoPattern $bridgePath 'round_pairs\[-1\]\["target"\] = goal_title' 'Bridge must not overwrite final round target with Grand Goal'
    Assert-NoPattern $webAppPath 'Goal round' 'Web must not label the final round as Goal round'
    Assert-HasPattern $webAppPath 'rounds_completed' 'Web rounds track must use rounds_completed'
    Assert-HasPattern $initPath '"reroll_pool"' 'World slot_data reroll_pool is missing'
    Assert-HasPattern $initPath '"trap_count"' 'World slot_data trap_count is missing'
    Assert-HasPattern $initPath '"bingo_letterpairs"' 'World slot_data bingo_letterpairs is missing'
    Assert-HasPattern $initPath '"bingo_letterpairs_boards"' 'World slot_data bingo_letterpairs_boards is missing'
    Assert-HasPattern $initPath '"bingo_cards_start"' 'World slot_data bingo_cards_start is missing'
    Assert-HasPattern $initPath 'bingo is enabled but no boards are available' 'World bingo zero-boards failsafe is missing'
    Assert-HasPattern $initPath 'return max\(0, int\(self\.options\.bingo_cards_start\.value\)\)' 'World must allow bingo_cards_start 0'
    Assert-HasPattern $initPath '"back_depth_start"' 'World slot_data back_depth_start is missing'
    Assert-HasPattern $initPath '"target_rerolls_start"' 'World slot_data target_rerolls_start is missing'
    Assert-HasPattern $initPath 'build_letter_pair_bingo_board' 'Letter-pair bingo board builder wiring is missing'
    Assert-HasPattern $initPath 'free_locations = round_count \+ bingo_count \+ branch_loc_count' 'Bingo/branch free_locations padding math is missing'
    Assert-HasPattern $initPath 'additional_fragments_in_pool' 'World additional fragments pool wiring is missing'
    Assert-HasPattern $initPath 'fragment_pool_count' 'World fragment_pool_count wiring is missing'
    Assert-HasPattern $initPath 'Progressive Back' 'World Progressive Back item pool wiring is missing'
    Assert-HasPattern $initPath 'Progressive Reroll' 'World Progressive Reroll item pool wiring is missing'
    Assert-HasPattern $initPath 'Progressive Bingo Card' 'World Progressive Bingo Card item pool wiring is missing'
    Assert-HasPattern $initPath 'Progressive Bingo Stamp' 'World Progressive Bingo Stamp item pool wiring is missing'
    Assert-HasPattern $initPath '"bingo_stamp_unlocks"' 'World slot_data bingo_stamp_unlocks is missing'
    Assert-NoPattern $initPath '"Back Button"' 'World must not still pool the old Back Button item'
    Assert-HasPattern $itemsPath '"Progressive Back"' 'Items table Progressive Back is missing'
    Assert-HasPattern $itemsPath '"Progressive Reroll"' 'Items table Progressive Reroll is missing'
    Assert-HasPattern $itemsPath '"Progressive Bingo Card"' 'Items table Progressive Bingo Card is missing'
    Assert-HasPattern $itemsPath '"Progressive Bingo Stamp"' 'Items table Progressive Bingo Stamp is missing'
    Assert-HasPattern (Join-Path $worldRoot "letter_pairs.py") 'row_\{index\}"' 'Bingo slot location ids must use row_N keys'
    Assert-HasPattern $webAppPath 'bingo-stamp' 'Web bingo stamp API client is missing'
    Assert-NoPattern $itemsPath '"Back Button"' 'Items table must not keep Back Button'
    Assert-HasPattern (Join-Path $worldRoot "Locations.py") 'Board \{board\} Full Card' 'Bingo Full Card location must be board-prefixed'
    Assert-HasPattern (Join-Path $worldRoot "letter_pairs.py") 'def letter_pair_from_title' 'letter_pair_from_title helper is missing'
    Assert-HasPattern (Join-Path $worldRoot "letter_pairs.py") 'SCRABBLE_LETTERS' 'Scrabble alphabet table is missing'
    Assert-HasPattern (Join-Path $worldRoot "letter_pairs.py") 'MAX_BINGO_GRID_SIZE = 20' 'Bingo grid max must be 20'
    Assert-HasPattern (Join-Path $worldRoot "Locations.py") 'MAX_BINGO_GRID = 20' 'Locations MAX_BINGO_GRID must be 20'
    Assert-HasPattern (Join-Path $worldRoot "Options.py") 'Scrabble letter-pair frequencies \(3-20\)' 'BingoLetterpairsGrid docstring must mention Scrabble 3-20'
    Assert-HasPattern (Join-Path $worldRoot "letter_pair_weights_en.json") '"TH"' 'Shipped letter_pair_weights_en.json is missing TH'
    foreach ($lang in @("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")) {
        $weightsFile = Join-Path $worldRoot "letter_pair_weights_$lang.json"
        if (-not (Test-Path $weightsFile)) {
            throw "Missing shipped letter-pair weights for language '$lang': $weightsFile"
        }
    }
    & python (Join-Path $Root "test_letter_pairs.py")
    if ($LASTEXITCODE -ne 0) {
        throw "test_letter_pairs.py failed"
    }
    Write-Pass "Scrabble letter-pair extraction cases pass"
    & python (Join-Path $Root "test_blocked_namespaces.py")
    if ($LASTEXITCODE -ne 0) {
        throw "test_blocked_namespaces.py failed"
    }
    Write-Pass "Blocked wiki-namespace helpers match the client; pools are clean"
    Assert-HasPattern $yamlPath 'bingo_cards_start:' 'YAML bingo_cards_start is missing'
    Assert-HasPattern $yamlPath 'back_depth_start:' 'YAML back_depth_start is missing'
    Assert-HasPattern $yamlPath 'target_rerolls_start:' 'YAML target_rerolls_start is missing'
    Assert-HasPattern $yamlPath 'branch_count:' 'YAML branch_count is missing'
    Assert-HasPattern $yamlPath 'branch_length:' 'YAML branch_length is missing'
    Assert-HasPattern $yamlPath 'additional_branch_keys:' 'YAML additional_branch_keys is missing'
    Assert-HasPattern $itemsPath '"Branch Key"' 'Items table Branch Key is missing'
    Assert-HasPattern $initPath '"crossroads"' 'World slot_data crossroads is missing'
    Assert-HasPattern $initPath '"branches"' 'World slot_data branches is missing'
    Assert-HasPattern $initPath 'location_ids\["branches"\]' 'World slot_data branch location ids are missing'
    Assert-HasPattern $initPath 'state.has\("Branch Key", self.player, need_keys\)' 'Branch N logic must require N Branch Keys'
    Assert-HasPattern $initPath 'need_ra <= 0 or state.has\("Round Access", self.player, need_ra\)' 'Branch logic must also require the matching crossroad Round Access'
    Assert-NoPattern $initPath 'state.has\("Branch Key", self.player, 1\)' 'Branch locations must not all open with a single Branch Key'
    Assert-HasPattern (Join-Path $worldRoot "Regions.py") 'To Branch \{branch\}' 'Each side branch must be its own region'
    Assert-HasPattern $bridgePath 'wikipelago_clicks_' 'Bridge clicks DataStorage key is missing'
    Assert-HasPattern $bridgePath 'wikipelago_travel_' 'Bridge travel DataStorage key is missing'
    Assert-HasPattern $bridgePath '_request_clicks_from_storage' 'Bridge clicks DataStorage Get helper is missing'
    Assert-HasPattern $bridgePath '_persist_clicks' 'Bridge clicks DataStorage Set helper is missing'
    Assert-HasPattern $bridgePath '_request_travel_from_storage' 'Bridge travel DataStorage Get helper is missing'
    Assert-HasPattern $bridgePath '_persist_travel' 'Bridge travel DataStorage Set helper is missing'
    Assert-HasPattern $bridgePath 'if not force and not self\.state\.clicks_storage_ready' 'Bridge must gate clicks DataStorage writes until Retrieved'
    Assert-HasPattern $bridgePath 'if not force and not self\.state\.travel_storage_ready' 'Bridge must gate travel DataStorage writes until Retrieved'
    Assert-HasPattern $bridgePath 'merge_clicks' 'Bridge clicks max-merge helper is missing'
    Assert-HasPattern $bridgePath 'live_branch_targets' 'Bridge live_branch_targets status is missing'
    Assert-HasPattern $bridgePath 'branch_keys_available' 'Bridge branch_keys_available status is missing'
    Assert-HasPattern $bridgePath 'unlocked_crossroad_rounds' 'Bridge unlocked_crossroad_rounds status is missing'
    Assert-HasPattern $bridgePath '/journey' 'Bridge journey route is missing'
    Assert-HasPattern $bridgePath 'unlocked_branch_ids' 'Bridge unlocked_branch_ids helper is missing'
    Assert-HasPattern $webAppPath 'Math.max\(Number\(state.clicksUsed\) \|\| 0, saved, remote\)' 'Web must max-merge clicks and never assign a lower remote value'
    Assert-HasPattern $webAppPath 'function renderForkSpur' 'Web fork spur attached to crossroad hooks is missing'
    Assert-HasPattern $webAppPath 'function journeyPageNodes' 'Web journey page-node helper is missing'
    Assert-HasPattern $webAppPath 'function drawJourneyPath' 'Web journey path renderer is missing'
    Assert-HasPattern $webAppPath 'if \(milestoneLabel % 2 === 1\) label.classList.add\("above"\)' 'Web journey labels must alternate above and below'
    Assert-HasPattern $webAppPath 'onRight \? -1 : 1' 'Web Journey vertical wraps must bulge like parentheses by side'
    Assert-HasPattern $webIndexPath 'id="journeyPath"' 'Web Journey path markup is missing'
    Assert-NoPattern $webIndexPath 'id="journeyTimeline"' 'Web Journey must not keep a timestamp timeline'
    Assert-NoPattern $webIndexPath 'id="journeyHeatmap"' 'Web Journey must not keep a revisits heatmap'
    Assert-NoPattern $webAppPath 'toLocaleTimeString' 'Web Journey must not show visit timestamps'
    Assert-HasPattern $webAppPath 'live_branch_targets' 'Web live branch target HUD is missing'
    Assert-HasPattern $webAppPath 'status.branch_keys_available' 'Web Branch Key badge must show remaining keys'
    Assert-HasPattern $webAppPath 'hud.forkTarget' 'Web fork target label is missing'
    Assert-HasPattern $webAppPath 'dataset.fork' 'Web crossroad fork numbers on the track hook are missing'
    Assert-HasPattern $webIndexPath 'hud.targets' 'Web Targets heading is missing'
    Assert-HasPattern $webIndexPath 'target-list' 'Web target rows must sit under a Targets divider'
    Assert-HasPattern $webCssPath 'border-bottom: 1px solid #314557' 'Web target list must have a matching line below the rows'
    Assert-HasPattern $webI18nPath '"hud.rounds": "Progression"' 'Web Rounds heading must be renamed Progression'
    Assert-HasPattern $webI18nPath '"hud.forkTarget": "Branch {n}"' 'Web target labels must say Branch N'
    Assert-HasPattern $webAppPath '/journey' 'Web journey API client is missing'
    Assert-HasPattern $webAppPath 'openJourneyOverlay' 'Web Journey overlay helper is missing'
    Assert-HasPattern $webIndexPath 'id="branchTracks"' 'Web branch track markup is missing'
    Assert-HasPattern $webIndexPath 'id="branchTargets"' 'Web branch target markup is missing'
    Assert-NoPattern $webIndexPath 'id="pathSwitcher"' 'Web must not keep a manual path switcher'
    Assert-NoPattern $bridgePath 'switch-path' 'Bridge must not keep a switch-path route'
    Assert-NoPattern $webAppPath 'switch-path' 'Web must not call switch-path'
    Assert-HasPattern $bridgePath '"goal_question"' 'Bridge status must include goal_question'
    Assert-HasPattern $webIndexPath 'id="victoryOverlay"' 'Web Grand Goal victory overlay markup is missing'
    Assert-HasPattern $webIndexPath 'id="supportDock"' 'Web support buttons are missing'
    Assert-HasPattern $webAppPath 'openVictoryOverlay' 'Web must open a victory overlay on Grand Goal'
    Assert-HasPattern $webAppPath 'Wrong Wiki' 'Web must handle the Wrong Wiki trap'
    Assert-HasPattern $bridgePath 'unlock_all_branches' 'Bridge debug must unlock all branches'
    Assert-HasPattern $bridgePath 'WIKIPELAGO_DEBUG_MENU' 'Bridge must gate the debug menu behind WIKIPELAGO_DEBUG_MENU'
    Assert-HasPattern $webIndexPath 'id="debugUnlockWrap"' 'Web debug console wrap is missing'
    Assert-HasPattern $webIndexPath 'wiki.spaceface.dev' 'Web must keep the wiki path solver'
    Assert-HasPattern $webAppPath 'function isDebugMenuAllowed' 'Web must hide the debug console unless the server enables it'
    Assert-NoPattern $webIndexPath 'id="journeyFilter"' 'Web Journey must not keep a main/fork path filter'
    Assert-HasPattern $webAppPath 'TRACK_OVERFLOW_MIN = 5' 'Web track overflow must require at least 5 like-segments'
    Assert-HasPattern $webAppPath 'TRACK_FORK_OVERFLOW_MIN = 3' 'Web fork overflow must require at least 3 like-segments'
    Assert-HasPattern $bridgePath '"bingo_cell"' 'Bridge must log bingo cell stamps on the journey'
    Assert-HasPattern $bridgePath '"grand_goal",' 'Bridge must log Grand Goal completion on the journey'
    Assert-NoPattern $webAppPath 'roughTitleBingoPair' 'Journey must not color every page that shares a stamped letter pair'
    Assert-HasPattern $webAppPath '#b57bff' 'Journey bingo bubbles must be purple'
    Assert-HasPattern $webIndexPath 'rounds-label-row' 'Web Journey button must sit on the Progression heading row'
    Assert-NoPattern $webIndexPath 'id="clicksText"' 'Web side panel must not show a click counter'
    Assert-NoPattern $webIndexPath 'clicks-row' 'Web side panel must not keep a Clicks row'
    Assert-HasPattern $webCssPath 'bottom: calc\(100% \+ 2px\)' 'Web fork index must sit above the crossroad T'
    Assert-HasPattern $webCssPath '--hook-thick: 24px' 'Web T stem must match the 24px branch chip width'
    Assert-HasPattern $webCssPath '--track-crossroad-w: 48px' 'Web crossroad chips must be 48px wide'
    Assert-HasPattern $webAppPath 'TRACK_CROSSROAD_PX = 48' 'Web crossroad layout width must be 48px'
    Assert-HasPattern $webIndexPath 'id="goalHover"' 'Web Grand Goal must use the target hover tooltip'
    Assert-HasPattern $webAppPath 'setHoverWikiTitle' 'Web branch and goal titles must share the target tooltip'
    Assert-HasPattern $webAppPath 'TRACK_EMPHASIS_MIN_PX = 24' 'Web current and +N chips must be 24px wide'
    Assert-HasPattern $webAppPath 'TRACK_SEG_MAX_PX = 16' 'Web idle track bars must cap at 16px'
    Assert-HasPattern $webCssPath '--track-seg-max: 16px' 'Web idle track bars must cap at 16px in CSS'
    Assert-HasPattern $webCssPath 'justify-content: center; /\* leftover space after the 16px idle-bar cap \*/' 'Web round track must be centered when idle bars do not fill the panel'
    Assert-HasPattern $webCssPath 'max-width: var\(--track-seg-max\);' 'Web idle-bar max-width must apply to rounds only'
    Assert-HasPattern $webCssPath 'font-size: 14px' 'Web track labels must be 14px'
    Assert-HasPattern $webCssPath 'font-size: 19px' 'Web bingo cell type must be a whole 19px'
    Assert-HasPattern $webAppPath 'BINGO_SIDE_PREF_MAX_PX = 202' 'Web sidebar bingo board must be 20% larger'
    Assert-HasPattern $bridgePath '"trap_count"' 'Bridge status trap_count is missing'
    Assert-HasPattern $bridgePath 'start_practice' 'Bridge practice mode start helper is missing'
    Assert-HasPattern $bridgePath '/api/session/\{sid\}/practice' 'Bridge practice route is missing'
    Assert-HasPattern $bridgePath 'load_practice_titles' 'Bridge practice pool loader is missing'
    Assert-HasPattern $bridgePath 'letter_pair_from_title' 'Bridge letter_pair_from_title helper is missing'
    Assert-HasPattern $bridgePath 'apply_bingo_visit' 'Bridge bingo visit helper is missing'
    Assert-HasPattern $bridgePath 'bingo_letterpairs_boards' 'Bridge multi-board bingo status is missing'
    Assert-HasPattern $bridgePath 'bingo_stamped_cells' 'Bridge bingo stamped cells status is missing'
    Assert-HasPattern $itemsPath 'for index, letter in enumerate\("ABCDEFGHIJKLMNOPQRSTUVWXYZ"' 'Search Letter item loop is missing'
    Assert-HasPattern $initPath '_display_unlock_items' 'Display unlock helper is missing'
    Assert-HasPattern $initPath 'def create_event' 'World create_event helper is missing'
    Assert-HasPattern $initPath 'place_locked_item\(self\.create_item\("Victory"\)\)' 'Grand Goal must lock a real Victory item id for hosting'
    Assert-NoPattern $initPath 'place_locked_item\(self\.create_event\("Victory"\)\)' 'Grand Goal must not lock a None-id Victory event'
    Assert-HasPattern $itemsPath '"Victory"' 'Victory must exist as a datapackage item (locked on Grand Goal only)'
    Write-Pass "Known bad title regressions are absent from source pools"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    Assert-HasPattern $bridgePath 'TITLE_CANONICALS' 'Bridge canonical title map is missing'
    Assert-HasPattern $bridgePath '_canonicalize_title_sync' 'Bridge title canonicalization helper is missing'
    Assert-HasPattern $bridgePath '_fetch_resolved_title' 'Bridge resolved-title lookup is missing'
    Assert-HasPattern $bridgePath '_titles_match' 'Bridge title matcher is missing'
    Assert-HasPattern $bridgePath 'current_start' 'Bridge current start status helper is missing'
    Assert-HasPattern $bridgePath 'searchsanity' 'Bridge searchsanity state is missing'
    Assert-HasPattern $bridgePath 'scrollsanity' 'Bridge scrollsanity state is missing'
    Assert-HasPattern $bridgePath 'scroll_speed_level' 'Bridge scroll speed status is missing'
    Assert-HasPattern $bridgePath 'search_starting_letters' 'Bridge search_starting_letters state is missing'
    Assert-HasPattern $bridgePath 'randomize_tables' 'Bridge randomize_tables state is missing'
    Assert-HasPattern $bridgePath 'tables_unlocked' 'Bridge tables_unlocked status is missing'
    Assert-HasPattern $bridgePath 'pictures_unlocked' 'Bridge pictures_unlocked status is missing'
    Assert-HasPattern $bridgePath 'incipit_unlocked' 'Bridge incipit_unlocked status is missing'
    Assert-HasPattern $bridgePath '"round_access_count": self\.round_access_count\(\)' 'Bridge round access count status is missing'
    Assert-HasPattern $bridgePath '"unlocked_rounds": self\.unlocked_rounds\(\)' 'Bridge unlocked rounds status is missing'
    Assert-HasPattern $bridgePath '"/manifest\.webmanifest"' 'Bridge PWA manifest route is missing'
    Assert-HasPattern $bridgePath '"/service-worker\.js"' 'Bridge service worker route is missing'
    Assert-HasPattern $bridgePath '"/icons/"' 'Bridge PWA icon route is missing'
    Write-Pass "Bridge title-matching safeguards are present"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    Assert-HasPattern $webAppPath 'preferredResumeTitle' 'Web resume helper is missing'
    Assert-HasPattern $webAppPath 'restoreArticleView' 'Web restore-article flow is missing'
    Assert-HasPattern $webAppPath 'current_start' 'Web client is not using current_start resume data'
    Assert-HasPattern $webAppPath 'openSearchOverlay' 'Web search overlay helper is missing'
    Assert-HasPattern $webAppPath 'SCROLL_SPEED_FACTORS' 'Web scroll speed table is missing'
    Assert-HasPattern $webAppPath 'scrollFactor' 'Web scroll factor helper is missing'
    Assert-HasPattern $webAppPath 'sanitizeSearchInput' 'Web search letter gating helper is missing'
    Assert-HasPattern $webAppPath 'status\.unlocked_rounds' 'Web unlocked rounds progress is missing'
    Assert-HasPattern $webAppPath 'renderRoundsTrack' 'Web rounds track renderer is missing'
    Assert-HasPattern $webAppPath 'renderDifficultyIcons' 'Web difficulty icons renderer is missing'
    Assert-HasPattern $webIndexPath 'id="roundsTrack"' 'Web rounds track element is missing'
    Assert-HasPattern $webIndexPath 'id="difficultyCard"' 'Web difficulty card element is missing'
    Assert-HasPattern $webIndexPath 'id="sanityCard"' 'Web sanity unlocks card element is missing'
    Assert-HasPattern $webIndexPath 'data-panel-toggle' 'Web side panels must have hide/show toggles'
    Assert-HasPattern $webIndexPath 'data-panel="progression"' 'Web Progression card must collapse as one panel'
    Assert-NoPattern $webIndexPath 'data-panel="connection"' 'Web Connection card must not have a hide toggle'
    Assert-NoPattern $webIndexPath 'data-panel="targets"' 'Web Targets must collapse with Progression, not alone'
    Assert-NoPattern $webIndexPath 'data-panel="fragments"' 'Web Fragments must collapse with Progression, not alone'
    Assert-HasPattern $webAppPath 'function initSidePanelToggles' 'Web side panel collapse helper is missing'
    Assert-HasPattern $webAppPath 'wikipelago_side_panels' 'Web side panel collapse state must persist'
    Assert-HasPattern $webI18nPath '"panel.hide"' 'Web hide-panel string is missing'
    Assert-HasPattern $webI18nPath '"panel.show"' 'Web show-panel string is missing'
    Assert-HasPattern $webAppPath 'serviceWorker\.register\("/service-worker\.js"\)' 'Web service worker registration is missing'
    Assert-HasPattern $webIndexPath 'rel="manifest"' 'Web manifest link is missing'
    Assert-HasPattern $webManifestPath '"display": "standalone"' 'PWA standalone display mode is missing'
    Assert-HasPattern $webManifestPath '"sizes": "192x192"' 'PWA 192px icon declaration is missing'
    Assert-HasPattern $webManifestPath '"sizes": "512x512"' 'PWA 512px icon declaration is missing'
    Assert-HasPattern $webServiceWorkerPath 'url\.pathname\.startsWith\("/api/"\)' 'Service worker API bypass is missing'
    Write-Pass "Web reconnect/resume safeguards are present"
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

try {
    if (Test-Path $apworldPath) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $temp = Join-Path ([System.IO.Path]::GetTempPath()) ("wikipelago_smoke_" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $temp | Out-Null
        try {
            [System.IO.Compression.ZipFile]::ExtractToDirectory($apworldPath, $temp)
            $packagedPy = Get-ChildItem -Path (Join-Path $temp "wikipelago") -Filter *.py -File
            foreach ($file in $packagedPy) {
                if (-not (Test-StrictUtf8File $file.FullName)) {
                    throw "Packaged APWorld file is not strict UTF-8: $($file.Name)"
                }
            }
            foreach ($lang in @("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")) {
                $packagedWeights = Join-Path $temp "wikipelago\letter_pair_weights_$lang.json"
                if (-not (Test-Path $packagedWeights)) {
                    throw "Packaged APWorld is missing letter_pair_weights_$lang.json"
                }
            }
            Assert-HasPattern (Join-Path $temp "wikipelago\letter_pair_weights_en.json") '"TH"' 'Packaged letter_pair_weights_en.json is missing TH'
            $packagedInit = Join-Path $temp "wikipelago\__init__.py"
            $packagedManifest = Join-Path $temp "wikipelago\archipelago.json"
            if (-not (Test-Path $packagedManifest)) {
                throw "Packaged apworld missing wikipelago/archipelago.json"
            }
            Assert-HasPattern $packagedManifest '"world_version":\s*"1\.0\.0"' 'Packaged world_version should be 1.0.0'

            Assert-NoPattern $packagedInit '`r`n' 'Literal backtick newline text regression found in packaged __init__.py'
            Write-Pass "Built .apworld package passed UTF-8 and syntax-regression checks"
        } finally {
            if (Test-Path $temp) { Remove-Item -Recurse -Force $temp }
        }
    } else {
        Write-Host "[INFO] No built APWorld found at $apworldPath, so package checks were skipped." -ForegroundColor Yellow
    }
} catch {
    $failures.Add($_.Exception.Message)
    Write-Fail $_.Exception.Message
}

Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "Smoke test passed." -ForegroundColor Green
    exit 0
}

Write-Host "Smoke test failed:" -ForegroundColor Red
foreach ($failure in $failures) {
    Write-Host " - $failure" -ForegroundColor Red
}
exit 1
