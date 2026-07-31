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
$worldRoot = Join-Path $srcRoot "Wikipelago"
$repoRoot = Split-Path -Parent $Root
$bridgePath = [System.IO.Path]::Combine($repoRoot, "bridge", "bridge.py")
$webAppPath = [System.IO.Path]::Combine($repoRoot, "web", "app.js")
$webIndexPath = [System.IO.Path]::Combine($repoRoot, "web", "index.html")
$webManifestPath = [System.IO.Path]::Combine($repoRoot, "web", "manifest.webmanifest")
$webServiceWorkerPath = [System.IO.Path]::Combine($repoRoot, "web", "service-worker.js")
$yamlPath = [System.IO.Path]::Combine($repoRoot, "yaml", "Wikipelago.yaml")
$apworldPath = [System.IO.Path]::Combine($Root, "APWorld", "Wikipelago.apworld")

if ($BuildApworld) {
    & (Join-Path $Root "build_apworld.ps1") -Root $Root
}

$failures = New-Object System.Collections.Generic.List[string]

try {
    if (-not (Test-Path $worldRoot)) { throw "Missing APWorldSource\Wikipelago folder" }
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
    Assert-HasPattern $yamlToCheck 'trap_count:\s*\d+' 'YAML template is missing trap_count'
    Assert-HasPattern $yamlToCheck 'trap_type:\s*(both|only_foggy_links|only_missing_links)' 'YAML template is missing trap_type'
    Assert-HasPattern $yamlToCheck 'trap_link:\s*(true|false)' 'YAML template is missing trap_link'
    Assert-HasPattern $yamlToCheck 'toggle_bingo_letterpairs:\s*(true|false)' 'YAML template is missing toggle_bingo_letterpairs'
    Assert-HasPattern $yamlToCheck 'bingo_letterpairs_grid:\s*\d+' 'YAML template is missing bingo_letterpairs_grid'
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
    if (-not (Test-Path -LiteralPath $poolEnPath)) {
        throw "EN multi-tag pool data/pool_en.json missing [$poolEnPath]"
    }
    Assert-HasPattern $optionsPath 'class WikipediaLanguage' 'WikipediaLanguage option is missing'
    Assert-HasPattern $optionsPath 'class IncludeSensitivePages' 'IncludeSensitivePages option is missing'
    Assert-HasPattern $optionsPath 'class IncludeFamousPeople' 'IncludeFamousPeople option is missing'
    Assert-HasPattern $initPath 'first_start = picks\[0\]' 'Random first-round start selection is missing'
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
    Assert-HasPattern $optionsPath 'class TrapCount' 'TrapCount option is missing'
    Assert-HasPattern $optionsPath 'class TrapType' 'TrapType option is missing'
    Assert-HasPattern $optionsPath 'class TrapLink' 'TrapLink option is missing'
    Assert-HasPattern $optionsPath 'class ToggleBingoLetterpairs' 'ToggleBingoLetterpairs option is missing'
    Assert-HasPattern $optionsPath 'class BingoLetterpairsGrid' 'BingoLetterpairsGrid option is missing'
    Assert-HasPattern $optionsPath 'class BingoCardsStart' 'BingoCardsStart option is missing'
    Assert-HasPattern $optionsPath 'How many letter-pair bingo boards are unlocked from the start \(0 =' 'BingoCardsStart docstring should allow 0'
    Assert-HasPattern $itemsPath '"Foggy Links"' 'Foggy Links trap item is missing'
    Assert-HasPattern $itemsPath '"Missing Links"' 'Missing Links trap item is missing'
    Assert-HasPattern $initPath '_trap_item_names' 'Trap item name helper is missing'
    Assert-HasPattern $bridgePath 'MAX_AP_CONNECT_ATTEMPTS' 'Bridge reconnect attempt limit is missing'
    Assert-HasPattern $bridgePath 'send_death_link' 'Bridge DeathLink send helper is missing'
    Assert-HasPattern $bridgePath 'send_trap_link' 'Bridge TrapLink send helper is missing'
    Assert-HasPattern $webAppPath 'submitCheck' 'Web submitCheck gating is missing'
    Assert-HasPattern $webAppPath 'submit_check: Boolean\(submitCheck\)' 'Web always-visit check payload is missing'
    Assert-HasPattern $webAppPath 'function renderBingoHud' 'Web bingo HUD renderer is missing'
    Assert-HasPattern $webAppPath 'applyBingoAutoHide' 'Web bingo auto-hide helper is missing'
    Assert-NoPattern $webIndexPath 'id="bingoSectionToggleBtn"' 'Web must not keep section-level bingo toggle'
    Assert-HasPattern $webAppPath 'function toastBingoCompletions' 'Web bingo toast helper is missing'
    Assert-HasPattern $webAppPath 'bingo_letterpairs_boards' 'Web multi-board bingo status handling is missing'
    Assert-HasPattern $webAppPath 'use-back' 'Web Progressive Back use-back call is missing'
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
    Assert-HasPattern $webIndexPath 'id="connectionSummary"' 'Web connection summary markup is missing'
    Assert-HasPattern $webIndexPath 'id="disconnectBtn"' 'Web disconnect button markup is missing'
    Assert-HasPattern $webAppPath 'syncBingoStampsToBridge' 'Web bingo stamp sync helper is missing'
    Assert-HasPattern $webAppPath 'bingoStampStorageKey' 'Web bingo stamp storage key helper is missing'
    Assert-HasPattern $webIndexPath 'id="bingoCard"' 'Web bingo card markup is missing'
    Assert-HasPattern $webAppPath 'toastSticky' 'Web sticky toast helper is missing'
    Assert-HasPattern $webAppPath 'applyDeathEffect' 'Web death effect helper is missing'
    Assert-HasPattern $webAppPath 'resetRoundVisits\(""\)' 'Web death path must clear visit tracking immediately'
    Assert-HasPattern $webAppPath 'if \(state\.handlingDeath\) return;' 'Web must ignore input while a death is handling'
    Assert-HasPattern $webAppPath 'armBombsOnPage' 'Web bomb arming helper is missing'
    Assert-HasPattern $webAppPath 'rerollCurrentTarget' 'Web target reroll helper is missing'
    Assert-HasPattern $bridgePath 'reroll-target' 'Bridge target reroll route is missing'
    Assert-HasPattern $bridgePath 'def target_rerolls_max' 'Bridge dynamic target_rerolls_max is missing'
    Assert-HasPattern $bridgePath 'use-back' 'Bridge use-back route is missing'
    Assert-HasPattern $bridgePath 'Progressive Back' 'Bridge Progressive Back item is missing'
    Assert-HasPattern $bridgePath 'Progressive Reroll' 'Bridge Progressive Reroll item is missing'
    Assert-HasPattern $bridgePath 'Progressive Bingo Card' 'Bridge Progressive Bingo Card item is missing'
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
    Assert-HasPattern $bridgePath 'if self\.round_index >= self\.check_count:' 'Bridge must allow reroll on the final normal round'
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
    Assert-HasPattern $initPath 'free_locations = round_count \+ bingo_count' 'Bingo free_locations padding math is missing'
    Assert-HasPattern $initPath 'Progressive Back' 'World Progressive Back item pool wiring is missing'
    Assert-HasPattern $initPath 'Progressive Reroll' 'World Progressive Reroll item pool wiring is missing'
    Assert-HasPattern $initPath 'Progressive Bingo Card' 'World Progressive Bingo Card item pool wiring is missing'
    Assert-NoPattern $initPath '"Back Button"' 'World must not still pool the old Back Button item'
    Assert-HasPattern $itemsPath '"Progressive Back"' 'Items table Progressive Back is missing'
    Assert-HasPattern $itemsPath '"Progressive Reroll"' 'Items table Progressive Reroll is missing'
    Assert-HasPattern $itemsPath '"Progressive Bingo Card"' 'Items table Progressive Bingo Card is missing'
    Assert-NoPattern $itemsPath '"Back Button"' 'Items table must not keep Back Button'
    Assert-HasPattern (Join-Path $worldRoot "Locations.py") 'Board \{board\} Full Card' 'Bingo Full Card location must be board-prefixed'
    Assert-HasPattern (Join-Path $worldRoot "letter_pairs.py") 'def letter_pair_from_title' 'letter_pair_from_title helper is missing'
    Assert-HasPattern (Join-Path $worldRoot "letter_pair_weights.json") '"TH"' 'Shipped letter_pair_weights.json is missing TH'
    Assert-HasPattern $yamlPath 'bingo_cards_start:' 'YAML bingo_cards_start is missing'
    Assert-HasPattern $yamlPath 'back_depth_start:' 'YAML back_depth_start is missing'
    Assert-HasPattern $yamlPath 'target_rerolls_start:' 'YAML target_rerolls_start is missing'
    Assert-HasPattern $bridgePath '"trap_count"' 'Bridge status trap_count is missing'
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
            $packagedPy = Get-ChildItem -Path (Join-Path $temp "Wikipelago") -Filter *.py -File
            foreach ($file in $packagedPy) {
                if (-not (Test-StrictUtf8File $file.FullName)) {
                    throw "Packaged APWorld file is not strict UTF-8: $($file.Name)"
                }
            }
            $packagedWeights = Join-Path $temp "Wikipelago\letter_pair_weights.json"
            if (-not (Test-Path $packagedWeights)) {
                throw "Packaged APWorld is missing letter_pair_weights.json"
            }
            Assert-HasPattern $packagedWeights '"TH"' 'Packaged letter_pair_weights.json is missing TH'
            $packagedInit = Join-Path $temp "Wikipelago\__init__.py"
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
