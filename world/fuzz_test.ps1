param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [int]$Runs = 100,
    [string]$GenerateCommand = "",
    [string]$OutputDir = "",
    [switch]$KeepFiles
)

$ErrorActionPreference = "Stop"

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Cyan
}

function Write-Pass($message) {
    Write-Host "[PASS] $message" -ForegroundColor Green
}

function Write-Fail($message) {
    Write-Host "[FAIL] $message" -ForegroundColor Red
}

function Get-RandomBool {
    return [bool](Get-Random -Minimum 0 -Maximum 2)
}

function Get-GoalPreset {
    $values = @(
        "minecraft",
        "the_legend_of_zelda",
        "dark_souls",
        "elden_ring",
        "super_mario_bros",
        "pokemon_red_and_blue",
        "chess",
        "catan",
        "the_dark_knight",
        "star_wars_film",
        "lord_of_the_rings_fellowship",
        "the_matrix",
        "avatar_the_last_airbender",
        "breaking_bad",
        "stranger_things",
        "game_of_thrones",
        "the_simpsons",
        "spongebob_squarepants",
        "super_smash_bros_ultimate",
        "halo_combat_evolved"
    )
    return Get-Random -InputObject $values
}

function Test-LocalSettings([hashtable]$Settings) {
    $checkCount = [int]$Settings.check_count
    $required = [int]$Settings.required_fragments
    $startUnlocked = [int]$Settings.start_rounds_unlocked
    $perUnlock = [Math]::Max(1, [int]$Settings.rounds_per_unlock)
    $startingLetters = switch ($Settings.search_starting_letters) {
        "all_vowels" { 5 }
        "etaoi" { 5 }
        "raise" { 5 }
        default { 0 }
    }
    $searchLettersNeeded = if ($Settings.searchsanity) { 26 - $startingLetters } else { 0 }
    $scrollUpgradesNeeded = if ($Settings.scrollsanity) { 5 } else { 0 }
    $displayUnlockKeys = @(
        "randomize_tables",
        "randomize_pictures",
        "randomize_incipit",
        "randomize_infoboxes",
        "randomize_toc",
        "randomize_navboxes",
        "randomize_hatnotes",
        "randomize_references"
    )
    $displayUnlocksNeeded = @($displayUnlockKeys | Where-Object { $Settings[$_] }).Count

    if ($required -gt $checkCount) {
        return "required_fragments exceeds check_count"
    }
    if ($startUnlocked -gt $checkCount) {
        return "start_rounds_unlocked exceeds check_count"
    }

    $roundAccessCount = [Math]::Max(0, [int][Math]::Ceiling(($checkCount - $startUnlocked) / [double]$perUnlock))
    $branchCount = 0
    if ($null -ne $Settings.branch_count) {
        $branchCount = [Math]::Max(0, [int]$Settings.branch_count)
    }
    $branchLength = 3
    if ($null -ne $Settings.branch_length) {
        $branchLength = [Math]::Max(1, [int]$Settings.branch_length)
    }
    $additionalBranchKeys = 0
    if ($null -ne $Settings.additional_branch_keys) {
        $additionalBranchKeys = [Math]::Max(0, [int]$Settings.additional_branch_keys)
    }
    if ($branchCount -gt 0 -and $checkCount -lt 2) {
        return "branch_count requires check_count of at least 2"
    }
    if ($branchCount -gt [Math]::Max(0, $checkCount - 1)) {
        return "branch_count exceeds eligible main-road crossroads"
    }
    $branchKeys = if ($branchCount -gt 0) { $branchCount + $additionalBranchKeys } else { 0 }
    $freeLocations = $checkCount + ($branchCount * $branchLength)
    $mandatoryItems = $required + 3 + $roundAccessCount + $searchLettersNeeded + $scrollUpgradesNeeded + $displayUnlocksNeeded + $branchKeys
    if ($mandatoryItems -gt $freeLocations) {
        return "mandatory progression items exceed available checks"
    }

    return $null
}

function New-WikipelagoSettings {
    $searchLetterModes = @("none", "all_vowels", "etaoi", "raise")
    while ($true) {
        $checkCount = Get-Random -Minimum 15 -Maximum 101
        $startUnlocked = Get-Random -Minimum 1 -Maximum ([Math]::Min($checkCount, 15) + 1)
        $roundsPerUnlock = Get-Random -Minimum 1 -Maximum 8
        $requiredFragments = Get-Random -Minimum 1 -Maximum ([Math]::Min($checkCount, 12) + 1)

        $settings = [ordered]@{
            progression_balancing = Get-Random -Minimum 0 -Maximum 100
            check_count = $checkCount
            required_fragments = $requiredFragments
            start_rounds_unlocked = $startUnlocked
            rounds_per_unlock = $roundsPerUnlock
            random_goal_article = Get-RandomBool
            goal_article_preset = Get-GoalPreset
            searchsanity = Get-RandomBool
            scrollsanity = Get-RandomBool
            search_starting_letters = Get-Random -InputObject $searchLetterModes
            randomize_tables = Get-RandomBool
            randomize_pictures = Get-RandomBool
            randomize_incipit = Get-RandomBool
            randomize_infoboxes = Get-RandomBool
            randomize_toc = Get-RandomBool
            randomize_navboxes = Get-RandomBool
            randomize_hatnotes = Get-RandomBool
            randomize_references = Get-RandomBool
            wikipedia_language = Get-Random -InputObject @("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")
            include_video_games = Get-RandomBool
            include_movies = Get-RandomBool
            include_tv_shows = Get-RandomBool
            include_anime_manga = Get-RandomBool
            include_sports = Get-RandomBool
            include_science_space = Get-RandomBool
            include_technology = Get-RandomBool
            include_history = Get-RandomBool
            include_geography = Get-RandomBool
            include_food_cuisine = Get-RandomBool
            include_art_literature = Get-RandomBool
            include_mythology_folklore = Get-RandomBool
            include_music = Get-RandomBool
            include_politics = Get-RandomBool
            include_famous_people = Get-RandomBool
            include_animals = Get-RandomBool
            include_biology_medicine = Get-RandomBool
            include_miscellaneous = Get-RandomBool
            include_sensitive_pages = Get-RandomBool
            branch_count = 0
            branch_length = 3
            additional_branch_keys = 0
        }

        if ((Get-Random -Minimum 0 -Maximum 100) -lt 35 -and $checkCount -ge 8) {
            $maxBranches = [Math]::Min(3, $checkCount - 1)
            $settings.branch_count = Get-Random -Minimum 1 -Maximum ($maxBranches + 1)
            $settings.branch_length = Get-Random -Minimum 1 -Maximum 5
            $settings.additional_branch_keys = Get-Random -Minimum 0 -Maximum 3
        }

        if (-not ($settings.GetEnumerator() | Where-Object { $_.Key -like 'include_*' -and $_.Value }).Count) {
            $settings.include_video_games = $true
        }

        if (-not (Test-LocalSettings -Settings $settings)) {
            return $settings
        }
    }
}

function ConvertTo-WikipelagoYaml([hashtable]$Settings, [string]$Name) {
@"
name: $Name
game: Wikipelago
description: Auto-generated fuzz case

Wikipelago:
  progression_balancing: $($Settings.progression_balancing)
  check_count: $($Settings.check_count)
  required_fragments: $($Settings.required_fragments)
  start_rounds_unlocked: $($Settings.start_rounds_unlocked)
  rounds_per_unlock: $($Settings.rounds_per_unlock)
  random_goal_article: $([string]$Settings.random_goal_article).ToLower()
  goal_article_preset: $($Settings.goal_article_preset)
  searchsanity: $([string]$Settings.searchsanity).ToLower()
  scrollsanity: $([string]$Settings.scrollsanity).ToLower()
  search_starting_letters: $($Settings.search_starting_letters)
  randomize_tables: $([string]$Settings.randomize_tables).ToLower()
  randomize_pictures: $([string]$Settings.randomize_pictures).ToLower()
  randomize_incipit: $([string]$Settings.randomize_incipit).ToLower()
  randomize_infoboxes: $([string]$Settings.randomize_infoboxes).ToLower()
  randomize_toc: $([string]$Settings.randomize_toc).ToLower()
  randomize_navboxes: $([string]$Settings.randomize_navboxes).ToLower()
  randomize_hatnotes: $([string]$Settings.randomize_hatnotes).ToLower()
  randomize_references: $([string]$Settings.randomize_references).ToLower()
  wikipedia_language: $($Settings.wikipedia_language)
  include_video_games: $([string]$Settings.include_video_games).ToLower()
  include_movies: $([string]$Settings.include_movies).ToLower()
  include_tv_shows: $([string]$Settings.include_tv_shows).ToLower()
  include_anime_manga: $([string]$Settings.include_anime_manga).ToLower()
  include_sports: $([string]$Settings.include_sports).ToLower()
  include_science_space: $([string]$Settings.include_science_space).ToLower()
  include_technology: $([string]$Settings.include_technology).ToLower()
  include_history: $([string]$Settings.include_history).ToLower()
  include_geography: $([string]$Settings.include_geography).ToLower()
  include_food_cuisine: $([string]$Settings.include_food_cuisine).ToLower()
  include_art_literature: $([string]$Settings.include_art_literature).ToLower()
  include_mythology_folklore: $([string]$Settings.include_mythology_folklore).ToLower()
  include_music: $([string]$Settings.include_music).ToLower()
  include_politics: $([string]$Settings.include_politics).ToLower()
  include_famous_people: $([string]$Settings.include_famous_people).ToLower()
  include_animals: $([string]$Settings.include_animals).ToLower()
  include_biology_medicine: $([string]$Settings.include_biology_medicine).ToLower()
  include_miscellaneous: $([string]$Settings.include_miscellaneous).ToLower()
  include_sensitive_pages: $([string]$Settings.include_sensitive_pages).ToLower()
  branch_count: $($Settings.branch_count)
  branch_length: $($Settings.branch_length)
  additional_branch_keys: $($Settings.additional_branch_keys)
"@
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $Root "fuzz_output"
}
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null
$yamlDir = Join-Path $OutputDir "yamls"
$logDir = Join-Path $OutputDir "logs"
New-Item -ItemType Directory -Path $yamlDir | Out-Null
New-Item -ItemType Directory -Path $logDir | Out-Null

$summary = [System.Collections.Generic.List[string]]::new()
$localFailures = 0
$generatorFailures = 0
$generatorSuccesses = 0

Write-Info "Running $Runs fuzz cases"
if ($GenerateCommand) {
    Write-Info "Using generator command: $GenerateCommand"
} else {
    Write-Info "No generator command supplied; running local option fuzz only"
}

for ($i = 1; $i -le $Runs; $i++) {
    $name = "WikiFuzz$('{0:D3}' -f $i)"
    $settings = New-WikipelagoSettings
    $yaml = ConvertTo-WikipelagoYaml -Settings $settings -Name $name
    $yamlPath = Join-Path $yamlDir "$name.yaml"
    Set-Content -Path $yamlPath -Value $yaml -Encoding utf8

    $localError = Test-LocalSettings -Settings $settings
    if ($localError) {
        $localFailures += 1
        $summary.Add("Run $i LOCAL_FAIL $localError :: $yamlPath")
        continue
    }

    if (-not $GenerateCommand) {
        $summary.Add("Run $i LOCAL_PASS :: $yamlPath")
        continue
    }

    $logPath = Join-Path $logDir "$name.log"
    $commandToRun = $GenerateCommand.Replace("{{yaml}}", $yamlPath)

    try {
        $output = & powershell -NoProfile -Command $commandToRun 2>&1 | Out-String
        Set-Content -Path $logPath -Value $output -Encoding utf8
        if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
            $generatorSuccesses += 1
            $summary.Add("Run $i PASS :: $yamlPath")
        } else {
            $generatorFailures += 1
            $summary.Add("Run $i FAIL exit=$LASTEXITCODE :: $yamlPath :: $logPath")
        }
    } catch {
        $generatorFailures += 1
        Set-Content -Path $logPath -Value $_.Exception.ToString() -Encoding utf8
        $summary.Add("Run $i FAIL exception :: $yamlPath :: $logPath")
    }
}

$summaryPath = Join-Path $OutputDir "summary.txt"
Set-Content -Path $summaryPath -Value ($summary -join [Environment]::NewLine) -Encoding utf8

Write-Host ""
Write-Host "Fuzz summary" -ForegroundColor White
Write-Host "Output folder: $OutputDir"
Write-Host "Local option failures: $localFailures"
if ($GenerateCommand) {
    Write-Host "Generator passes: $generatorSuccesses"
    Write-Host "Generator failures: $generatorFailures"
} else {
    Write-Host "Local-only passes: $($Runs - $localFailures)"
}
Write-Host "Summary file: $summaryPath"

if (-not $KeepFiles -and -not $GenerateCommand) {
    Write-Info "Keeping YAMLs because they help inspect weird settings quickly."
}

if ($localFailures -gt 0 -or $generatorFailures -gt 0) {
    exit 1
}
exit 0
