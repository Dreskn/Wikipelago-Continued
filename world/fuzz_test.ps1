<#
.SYNOPSIS
    Random-option fuzz for the Wikipelago world. Needs no Archipelago install.

.DESCRIPTION
    Rolls random Wikipelago YAMLs across the full range of every option declared in
    world/APWorldSource/wikipelago/Options.py (read from that file, so new options are
    fuzzed automatically) and checks every case two ways:

      1. A PowerShell model of the world's rules (in this file): the item math of
         create_items() and the error conditions of generate_early() and the bingo setup.
      2. The world's own code, when Python 3.10+ is available: __init__.py is imported with
         small stand-ins for Archipelago's BaseClasses / Options / worlds modules, and
         generate_early, create_regions, create_items, set_rules and fill_slot_data run for
         every case. Accepted cases are also checked for one pool item per empty location,
         known item and location ids, and that every location and the goal are reachable
         once every pool item is collected.

    Each case is reported as accepted or rejected (with the world's reason). The run FAILS
    when:
      - the model and the world disagree (accept vs reject, a different first error, or a
        different item pool),
      - the world crashes (any error other than its own "Wikipelago ..." messages) or
        breaks one of the checks above,
      - a fixed expectation case gets the wrong verdict. These always run: the
        yaml/Wikipelago.yaml template, the Options.py defaults, a Realm Master seed and a
        minimal seed must be accepted; known-invalid configs must be rejected with the
        right error.

    Article-pool limits (too few articles in the enabled categories, Topic Realms without
    enough spare articles, bingo letter-pair weights) depend on the shipped data, so the
    model does not predict them. Those rejections are reported as "pool-limited" and only
    fail when the model expected an earlier error.

    Not checked here: Archipelago's own generator (YAML parsing, item placement and fill,
    accessibility, progression balancing, output). real_fuzz_test.ps1 runs that and needs
    an Archipelago source checkout or install. Without Python only the model runs, so
    drift between the model and the world code cannot be detected.

.PARAMETER Root
    The world/ folder. Defaults to the folder of this script.

.PARAMETER Runs
    Number of random cases. The fixed expectation cases always run as well.

.PARAMETER GenerateCommand
    Optional PowerShell command run once per case, e.g. a real generator. Placeholders:
    {{yaml}} (the case's YAML file), {{players_dir}} (a folder holding only that YAML),
    {{output_dir}} (an empty folder for the output), {{seed}} and {{name}}. It runs in a
    child PowerShell with stdin closed. Exit code 0 counts as "generated" (and, when
    {{output_dir}} is used, a .zip must appear there); a non-zero exit must come with the
    expected "Wikipelago ..." error in the output. real_fuzz_test.ps1 uses this.

.PARAMETER OutputDir
    Where YAMLs, logs, results.json and summary.txt go. Defaults to world/fuzz_output
    (wiped at the start of each run).

.PARAMETER KeepFiles
    Keep generator output (seed zips) from -GenerateCommand runs. YAMLs and logs are
    always kept.

.PARAMETER Seed
    Seed for the random settings, to reproduce a run. Random when omitted.

.PARAMETER PythonCommand
    Python used for the world-code check. Defaults to py -3, python or python3.

.PARAMETER NoWorldCheck
    Skip the world-code check and only run the PowerShell model.

.PARAMETER GenerateTimeoutSeconds
    Time limit for one -GenerateCommand run.

.EXAMPLE
    ./world/fuzz_test.ps1 -Runs 25

.EXAMPLE
    ./world/fuzz_test.ps1 -Runs 200 -Seed 1234
#>
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [int]$Runs = 100,
    [string]$GenerateCommand = "",
    [string]$OutputDir = "",
    [switch]$KeepFiles,
    [int]$Seed = -1,
    [string]$PythonCommand = "",
    [switch]$NoWorldCheck,
    [int]$GenerateTimeoutSeconds = 900
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

function Write-Warn($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Utf8File([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

# ---------------------------------------------------------------------------
# World errors, in the order the world checks them (Pos). Data = depends on the
# shipped article pools / bingo weights, so the model cannot predict it.
# ---------------------------------------------------------------------------
$ReasonTable = @(
    @{ Key = "no_category"; Pos = 1; Data = $false; Pattern = "requires at least one enabled category" },
    @{ Key = "realm_master_no_branch"; Pos = 2; Data = $false; Pattern = "realm_master needs at least one branch" },
    @{ Key = "branch_needs_two_rounds"; Pos = 3; Data = $false; Pattern = "check_count must be at least 2" },
    @{ Key = "branch_exceeds_crossroads"; Pos = 4; Data = $false; Pattern = "main-road crossroads" },
    @{ Key = "pool_too_small"; Pos = 5; Data = $true; Pattern = "unique usable articles" },
    @{ Key = "realm_topics"; Pos = 6; Data = $true; Pattern = "cannot generate Topic Realms" },
    @{ Key = "branch_leftover"; Pos = 6; Data = $true; Pattern = "not enough leftover articles for branch" },
    @{ Key = "bingo_no_boards"; Pos = 7; Data = $false; Pattern = "bingo is enabled but no boards are available" },
    @{ Key = "bingo_too_many_boards"; Pos = 7; Data = $false; Pattern = "board count exceeds datapackage limit" },
    @{ Key = "bingo_weights"; Pos = 8; Data = $true; Pattern = "cannot sample a board" },
    @{ Key = "item_math"; Pos = 9; Data = $false; Pattern = "item math invalid" }
)

function Get-ReasonInfo([string]$Key) {
    foreach ($reason in $ReasonTable) {
        if ($reason.Key -eq $Key) { return $reason }
    }
    return $null
}

function Find-ReasonInText([string]$Text) {
    if (-not $Text) { return $null }
    foreach ($reason in $ReasonTable) {
        if ($Text.IndexOf($reason.Pattern, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $reason
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Options.py / world constants
# ---------------------------------------------------------------------------
function Get-OptionSpec([string]$OptionsPath) {
    $text = [System.IO.File]::ReadAllText($OptionsPath)
    $classes = @{}
    $classPattern = '(?ms)^class\s+(\w+)\((\w+)\):[^\n]*\n(.*?)(?=^class\s|^@dataclass|\z)'
    foreach ($match in [regex]::Matches($text, $classPattern)) {
        $classes[$match.Groups[1].Value] = @{ Base = $match.Groups[2].Value; Body = $match.Groups[3].Value }
    }
    $dataclass = [regex]::Match($text, '(?ms)^class\s+WikipelagoOptions\(PerGameCommonOptions\):[^\n]*\n(.*?)(?=^\S|\z)')
    if (-not $dataclass.Success) {
        throw "Could not find 'class WikipelagoOptions(PerGameCommonOptions)' in $OptionsPath"
    }

    $spec = [ordered]@{}
    foreach ($field in [regex]::Matches($dataclass.Groups[1].Value, '(?m)^\s+(\w+)\s*:\s*(\w+)\s*$')) {
        $name = $field.Groups[1].Value
        $className = $field.Groups[2].Value
        $cls = $classes[$className]
        if (-not $cls) {
            throw "Option class $className (field $name) not found in $OptionsPath"
        }
        $body = $cls.Body
        $defaultMatch = [regex]::Match($body, '(?m)^\s+default\s*=\s*(-?\d+)\s*$')
        $default = $null
        if ($defaultMatch.Success) { $default = [int]$defaultMatch.Groups[1].Value }
        $opt = @{ Name = $name; Class = $className }
        switch ($cls.Base) {
            "Range" {
                $start = [regex]::Match($body, '(?m)^\s+range_start\s*=\s*(-?\d+)\s*$')
                $end = [regex]::Match($body, '(?m)^\s+range_end\s*=\s*(-?\d+)\s*$')
                if (-not $start.Success -or -not $end.Success) {
                    throw "Range option $className has no literal range_start / range_end"
                }
                $opt.Kind = "Range"
                $opt.Min = [int]$start.Groups[1].Value
                $opt.Max = [int]$end.Groups[1].Value
                if ($null -eq $default) { $default = $opt.Min }
                $opt.Default = $default
            }
            { $_ -eq "Toggle" -or $_ -eq "DefaultOnToggle" } {
                $opt.Kind = "Toggle"
                if ($null -eq $default) {
                    $default = 0
                    if ($cls.Base -eq "DefaultOnToggle") { $default = 1 }
                }
                $opt.Default = $default
            }
            "Choice" {
                $choices = @(
                    [regex]::Matches($body, '(?m)^\s+option_(\w+)\s*=\s*(\d+)\s*$') |
                        Sort-Object { [int]$_.Groups[2].Value } |
                        ForEach-Object { @{ Name = $_.Groups[1].Value; Value = [int]$_.Groups[2].Value } }
                )
                if ($choices.Count -eq 0) { throw "Choice option $className has no option_* values" }
                $opt.Kind = "Choice"
                $opt.Choices = @($choices | ForEach-Object { $_.Name })
                if ($null -eq $default) { $default = 0 }
                $opt.Default = $default
                $opt.DefaultName = ($choices | Where-Object { $_.Value -eq $default } | Select-Object -First 1).Name
                if (-not $opt.DefaultName) { throw "Choice option $className default $default matches no option_*" }
            }
            default {
                throw "Option $name uses base class $($cls.Base), which fuzz_test.ps1 does not know how to fuzz yet"
            }
        }
        $spec[$name] = $opt
    }
    if ($spec.Count -eq 0) { throw "No options found in WikipelagoOptions ($OptionsPath)" }
    return $spec
}

function Get-PyIntConstant([string]$Path, [string]$Name) {
    $match = [regex]::Match([System.IO.File]::ReadAllText($Path), "(?m)^$Name\s*=\s*(\d+)\s*$")
    if (-not $match.Success) { throw "Could not read $Name from $Path" }
    return [int]$match.Groups[1].Value
}

function Get-CategoryKeys($Settings) {
    # include_sensitive_pages is a filter, not a category (and has no Realm Portal).
    return @(@($Settings.Keys) | Where-Object { $_ -like "include_*" -and $_ -ne "include_sensitive_pages" })
}

function Get-DefaultValue($Opt) {
    switch ($Opt.Kind) {
        "Range" { return [int]$Opt.Default }
        "Toggle" { return [bool]$Opt.Default }
        "Choice" { return [string]$Opt.DefaultName }
    }
}

function Get-RandomOptionValue($Opt) {
    switch ($Opt.Kind) {
        "Range" { return [int](Get-Random -Minimum $Opt.Min -Maximum ($Opt.Max + 1)) }
        "Toggle" { return [bool](Get-Random -Minimum 0 -Maximum 2) }
        "Choice" { return [string](Get-Random -InputObject $Opt.Choices) }
    }
}

function Copy-Settings($Base, $Overrides) {
    $copy = [ordered]@{}
    foreach ($key in $Base.Keys) { $copy[$key] = $Base[$key] }
    if ($Overrides) {
        foreach ($key in $Overrides.Keys) { $copy[$key] = $Overrides[$key] }
    }
    return $copy
}

function Get-DefaultSettings($Spec) {
    $settings = [ordered]@{ progression_balancing = 50 }
    foreach ($name in $Spec.Keys) { $settings[$name] = Get-DefaultValue $Spec[$name] }
    return $settings
}

function Get-OnlyCategories($Spec, [string[]]$Enabled) {
    $overrides = @{}
    foreach ($key in (Get-CategoryKeys $Spec)) { $overrides[$key] = ($Enabled -contains $key) }
    return $overrides
}

function New-RandomSettings($Spec, [string]$Style) {
    $settings = [ordered]@{ progression_balancing = [int](Get-Random -Minimum 0 -Maximum 100) }
    foreach ($name in $Spec.Keys) {
        $opt = $Spec[$name]
        $keepDefault = $Style -ne "uniform" -and (Get-Random -Minimum 0 -Maximum 100) -lt 75
        if ($keepDefault) {
            $settings[$name] = Get-DefaultValue $opt
        } else {
            $settings[$name] = Get-RandomOptionValue $opt
        }
    }
    if ($Style -eq "few-categories") {
        $categories = Get-CategoryKeys $settings
        $keep = @(Get-Random -InputObject $categories -Count (Get-Random -Minimum 1 -Maximum 4))
        foreach ($category in $categories) { $settings[$category] = ($keep -contains $category) }
    }
    return $settings
}

function Read-TemplateSettings([string]$Path, $Spec) {
    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)
    $settings = [ordered]@{}
    $problems = New-Object System.Collections.Generic.List[string]
    $inBlock = $false
    foreach ($line in $lines) {
        if ($line -match '^Wikipelago:\s*$') { $inBlock = $true; continue }
        if (-not $inBlock) { continue }
        if ($line -match '^\S') { break }
        if ($line -match '^\s*(#|$)') { continue }
        if ($line -notmatch '^\s+(\w+):\s*(.*?)\s*$') { $problems.Add("unreadable template line: $line"); continue }
        $key = $Matches[1]
        $raw = ($Matches[2] -replace '\s+#.*$', '').Trim()
        if ($raw -eq "" -or $raw.StartsWith("{")) { $problems.Add("template value for $key is not a plain value"); continue }
        if ($raw -match '^(true|false)$') { $value = ($raw -eq "true") }
        elseif ($raw -match '^-?\d+$') { $value = [int]$raw }
        else { $value = $raw }
        if (-not $Spec.Contains($key) -and $key -ne "progression_balancing" -and $key -ne "accessibility") {
            $problems.Add("template sets unknown option $key")
        }
        $settings[$key] = $value
    }
    if ($settings.Count -eq 0) { $problems.Add("no Wikipelago: block found in $Path") }
    return @{ Settings = $settings; Problems = $problems }
}

function Format-YamlValue($Value) {
    if ($Value -is [bool]) {
        if ($Value) { return "true" }
        return "false"
    }
    return [string]$Value
}

function ConvertTo-WikipelagoYaml($Settings, [string]$PlayerName, [string]$Description) {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("name: $PlayerName")
    $lines.Add("game: Wikipelago")
    $lines.Add("description: $Description")
    $lines.Add("")
    $lines.Add("Wikipelago:")
    foreach ($key in $Settings.Keys) {
        $lines.Add("  ${key}: $(Format-YamlValue $Settings[$key])")
    }
    return ($lines -join "`n") + "`n"
}

function Format-CaseBrief($S) {
    $parts = New-Object System.Collections.Generic.List[string]
    $parts.Add([string]$S.wikipedia_language)
    $parts.Add("rounds=$($S.check_count)")
    $parts.Add([string]$S.goal)
    if ($S.toggle_bingo_letterpairs) {
        $parts.Add("bingo=$($S.bingo_letterpairs_grid)x$($S.bingo_letterpairs_grid)*$([int]$S.bingo_cards_start + [int]$S.bingo_card_unlocks)")
    } else {
        $parts.Add("bingo=off")
    }
    if ([int]$S.branch_count -gt 0) {
        $kind = "branches"
        if ($S.topic_portals) { $kind = "realms" }
        $parts.Add("$kind=$($S.branch_count)x$($S.branch_length)")
    }
    $parts.Add("categories=$(@(Get-CategoryKeys $S | Where-Object { $S[$_] }).Count)")
    if ([int]$S.trap_count -gt 0) { $parts.Add("traps=$($S.trap_count)") }
    return ($parts -join " ")
}

# ---------------------------------------------------------------------------
# PowerShell model of the world's rules (mirrors __init__.py generate_early,
# _bingo_board_count and create_items). Keep in sync; the world check fails
# the run when they drift apart.
# ---------------------------------------------------------------------------
$SearchStartingLetterCount = @{ none = 0; all_vowels = 5; etaoi = 5; raise = 5 }
$TrapItemByType = @{ only_foggy_links = "Foggy Links"; only_missing_links = "Missing Links"; only_wrong_wiki = "Wrong Wiki" }
$DisplayToggleKeys = @(
    "randomize_tables", "randomize_pictures", "randomize_incipit", "randomize_infoboxes",
    "randomize_toc", "randomize_navboxes", "randomize_hatnotes", "randomize_references"
)

function Get-ModelPrediction($S) {
    $violations = New-Object System.Collections.Generic.List[object]
    $notes = New-Object System.Collections.Generic.List[string]
    $categories = @(Get-CategoryKeys $S | Where-Object { $S[$_] })
    $checkCount = [int]$S.check_count
    $isGrandGoal = ([string]$S.goal) -ne "realm_master"
    $branchCount = [Math]::Max(0, [Math]::Min([int]$S.branch_count, $MaxBranches))
    $branchLength = [Math]::Max(1, [Math]::Min([int]$S.branch_length, $MaxBranchLength))
    $topicPortals = [bool]$S.topic_portals -and $branchCount -gt 0
    $bingo = [bool]$S.toggle_bingo_letterpairs
    $boards = 0
    if ($bingo) { $boards = [Math]::Max(0, [int]$S.bingo_cards_start) + [Math]::Max(0, [int]$S.bingo_card_unlocks) }

    # generate_early, in order.
    if ($categories.Count -eq 0) { $violations.Add((Get-ReasonInfo "no_category")) }
    if (-not $isGrandGoal -and $branchCount -le 0) { $violations.Add((Get-ReasonInfo "realm_master_no_branch")) }
    if ($branchCount -gt 0 -and $checkCount -lt 2) { $violations.Add((Get-ReasonInfo "branch_needs_two_rounds")) }
    if ($branchCount -gt [Math]::Max(0, $checkCount - 1)) { $violations.Add((Get-ReasonInfo "branch_exceeds_crossroads")) }
    # (article pool size: data-dependent, not modelled)
    # Each Realm needs its own enabled category (and branch_length spare articles in it: not modelled).
    if ($topicPortals -and $categories.Count -lt $branchCount) { $violations.Add((Get-ReasonInfo "realm_topics")) }
    if ($bingo -and $boards -le 0) { $violations.Add((Get-ReasonInfo "bingo_no_boards")) }
    elseif ($bingo -and $boards -gt $MaxBingoBoards) { $violations.Add((Get-ReasonInfo "bingo_too_many_boards")) }

    # create_items item math.
    $grid = 0
    if ($bingo) { $grid = [int]$S.bingo_letterpairs_grid }
    $bingoLocations = (2 * $grid + 3) * $boards
    if (-not $bingo) { $bingoLocations = 0 }
    $branchLocations = $branchCount * $branchLength
    $free = $checkCount + $bingoLocations + $branchLocations

    $fragments = 0
    if ($isGrandGoal) {
        $fragments = [Math]::Min([int]$S.required_fragments, $checkCount) + [Math]::Max(0, [int]$S.additional_fragments_in_pool)
    }
    $startUnlocked = [Math]::Min([int]$S.start_rounds_unlocked, $checkCount)
    $perUnlock = [Math]::Max(1, [int]$S.rounds_per_unlock)
    $roundAccess = [Math]::Max(0, [int][Math]::Floor(($checkCount - $startUnlocked + $perUnlock - 1) / $perUnlock))
    $searchLetters = 0
    if ($S.searchsanity) {
        $mode = [string]$S.search_starting_letters
        if (-not $SearchStartingLetterCount.ContainsKey($mode)) {
            $notes.Add("model does not know search_starting_letters=$mode")
        } else {
            $searchLetters = 26 - $SearchStartingLetterCount[$mode]
        }
    }
    $scroll = 0
    if ($S.scrollsanity) { $scroll = $ScrollSpeedUpgrades }
    $display = @($DisplayToggleKeys | Where-Object { $S[$_] }).Count
    $back = [Math]::Max(0, [int]$S.back_depth_unlocks)
    $reroll = [Math]::Max(0, [int]$S.target_reroll_unlocks)
    $cardUnlocks = 0
    $stamps = 0
    if ($bingo) {
        $cardUnlocks = [Math]::Max(0, [int]$S.bingo_card_unlocks)
        $stamps = [Math]::Max(0, [int]$S.bingo_stamp_unlocks)
    }
    $branchKeys = 0
    if ($branchCount -gt 0 -and -not $topicPortals) { $branchKeys = $branchCount + [Math]::Max(0, [int]$S.additional_branch_keys) }
    $portals = 0
    if ($topicPortals) { $portals = $branchCount }
    $traps = [int]$S.trap_count

    $mandatory = $fragments + 2 + $back + $reroll + $cardUnlocks + $stamps + $roundAccess + $branchKeys + $portals + $searchLetters + $scroll + $display + $traps
    if ($mandatory -gt $free) { $violations.Add((Get-ReasonInfo "item_math")) }

    $counts = [ordered]@{
        "Knowledge Fragment" = $fragments
        "Progressive Back" = $back
        "Wiki Compass" = 1
        "Ctrl+F Lens" = 1
        "Progressive Reroll" = $reroll
        "Progressive Bingo Card" = $cardUnlocks
        "Progressive Bingo Stamp" = $stamps
        "Progressive Scroll Speed" = $scroll
        "Search Letter" = $searchLetters
        "Lens" = $display
        "Round Access" = $roundAccess
        "Branch Key" = $branchKeys
        "Portal" = $portals
        "Footnote" = [Math]::Max(0, $free - $mandatory)
    }
    $trapType = [string]$S.trap_type
    if ($trapType -eq "all" -or $trapType -eq "both") {
        $counts["Trap"] = $traps
    } elseif ($TrapItemByType.ContainsKey($trapType)) {
        $counts[$TrapItemByType[$trapType]] = $traps
    } else {
        $notes.Add("model does not know trap_type=$trapType")
    }

    return @{
        Violations = $violations
        ItemCounts = $counts
        FreeLocations = $free
        GrandGoal = $isGrandGoal
        Notes = $notes
    }
}

function Format-Prediction($Prediction) {
    if ($Prediction.Violations.Count -eq 0) { return "accept" }
    return "reject $($Prediction.Violations[0].Key)"
}

function Format-Outcome($Outcome) {
    switch ($Outcome.Status) {
        "accept" { return "accept" }
        "reject" {
            if ($Outcome.Reason) { return "reject $($Outcome.Reason)" }
            return "reject (unrecognised error)"
        }
        default { return "$($Outcome.Status)" }
    }
}

# Returns $null when the model is consistent with an outcome, else a description.
function Compare-ModelToOutcome($Prediction, $Outcome, [string]$Label) {
    $violations = $Prediction.Violations
    if ($Outcome.Status -eq "accept") {
        if ($violations.Count -gt 0) { return "model expects rejection ($($violations[0].Key)) but $Label accepted" }
        return $null
    }
    if ($Outcome.Status -ne "reject") {
        return "$Label crashed: $($Outcome.Message)"
    }
    $reason = Get-ReasonInfo $Outcome.Reason
    if (-not $reason) {
        return "$Label raised an error fuzz_test.ps1 does not know (add it to the model): $($Outcome.Message)"
    }
    if ($reason.Data) {
        $earlier = @($violations | Where-Object { $_.Pos -lt $reason.Pos })
        if ($earlier.Count -gt 0) {
            return "model expects $($earlier[0].Key) before $Label's $($reason.Key)"
        }
        return $null
    }
    if ($violations.Count -eq 0) { return "model expects acceptance but $Label rejected with $($reason.Key)" }
    if ($violations[0].Key -ne $reason.Key) {
        return "model expects $($violations[0].Key) but $Label rejected with $($reason.Key)"
    }
    return $null
}

function Group-ItemCounts($ItemCounts, [string]$TrapType) {
    $grouped = @{}
    foreach ($prop in $ItemCounts.PSObject.Properties) {
        $name = $prop.Name
        $count = [int]$prop.Value
        $group = $name
        if ($name -like "Search Letter *") { $group = "Search Letter" }
        elseif ($name -like "* Portal") { $group = "Portal" }
        elseif ($name -like "* Lens" -and $name -ne "Ctrl+F Lens") { $group = "Lens" }
        elseif (($TrapItemByType.Values -contains $name) -and ($TrapType -eq "all" -or $TrapType -eq "both")) { $group = "Trap" }
        if ($grouped.ContainsKey($group)) { $grouped[$group] += $count } else { $grouped[$group] = $count }
    }
    return $grouped
}

function Compare-ItemPool($Prediction, $WorldResult, $Settings) {
    $diffs = New-Object System.Collections.Generic.List[string]
    $actual = Group-ItemCounts $WorldResult.item_counts ([string]$Settings.trap_type)
    $names = @(@($Prediction.ItemCounts.Keys) + @($actual.Keys) | Sort-Object -Unique)
    foreach ($name in $names) {
        $expected = 0
        if ($Prediction.ItemCounts.Contains($name)) { $expected = [int]$Prediction.ItemCounts[$name] }
        $got = 0
        if ($actual.ContainsKey($name)) { $got = [int]$actual[$name] }
        if ($expected -ne $got) { $diffs.Add("$name model=$expected world=$got") }
    }
    $expectedLocations = $Prediction.FreeLocations
    if ($Prediction.GrandGoal) { $expectedLocations += 1 }
    if ([int]$WorldResult.locations_addressed -ne $expectedLocations) {
        $diffs.Add("locations model=$expectedLocations world=$($WorldResult.locations_addressed)")
    }
    if ($diffs.Count -eq 0) { return $null }
    return ($diffs -join ", ")
}

# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------
function ConvertTo-CommandLineArgument([string]$Arg) {
    if ($Arg.Length -gt 0 -and $Arg -notmatch '[\s"]') { return $Arg }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    $backslashes = 0
    foreach ($ch in $Arg.ToCharArray()) {
        if ($ch -eq [char]'\') { $backslashes++; continue }
        if ($ch -eq [char]'"') {
            [void]$sb.Append([string]::new([char]'\', $backslashes * 2 + 1))
            [void]$sb.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) { [void]$sb.Append([string]::new([char]'\', $backslashes)); $backslashes = 0 }
        [void]$sb.Append($ch)
    }
    [void]$sb.Append([string]::new([char]'\', $backslashes * 2))
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Stop-ProcessTree($Process) {
    try {
        if ($env:OS -eq "Windows_NT") {
            & taskkill.exe /PID $Process.Id /T /F 2>&1 | Out-Null
        } else {
            $Process.Kill($true)
        }
    } catch {
        try { $Process.Kill() } catch { }
    }
}

# Runs a program with stdin closed (so prompts such as Generate.py's "Press enter to close"
# cannot hang) and returns its exit code and output.
function Invoke-CapturedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = "",
        [hashtable]$Environment = @{},
        [int]$TimeoutSeconds = 0
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = (@($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " ")
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = $Utf8NoBom
    $psi.StandardErrorEncoding = $Utf8NoBom
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }
    foreach ($key in $Environment.Keys) { $psi.EnvironmentVariables[$key] = [string]$Environment[$key] }

    $process = [System.Diagnostics.Process]::Start($psi)
    try {
        $process.StandardInput.Close()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timedOut = $false
        if ($TimeoutSeconds -gt 0) {
            if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
                $timedOut = $true
                Stop-ProcessTree $process
            }
        }
        $process.WaitForExit()
        [void]$stdoutTask.Wait(30000)
        [void]$stderrTask.Wait(30000)
        $stdout = ""
        $stderr = ""
        if ($stdoutTask.IsCompleted) { $stdout = $stdoutTask.Result }
        if ($stderrTask.IsCompleted) { $stderr = $stderrTask.Result }
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut = $stdout
            StdErr = $stderr
            TimedOut = $timedOut
        }
    } finally {
        $process.Dispose()
    }
}

function Resolve-Python([string]$Requested) {
    $candidates = New-Object System.Collections.Generic.List[object]
    if ($Requested) {
        $candidates.Add(@($Requested))
    } else {
        $candidates.Add(@("py", "-3"))
        $candidates.Add(@("python"))
        $candidates.Add(@("python3"))
    }
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $prefix = @($candidate | Select-Object -Skip 1)
        try {
            $probe = Invoke-CapturedProcess -FilePath $command.Source -Arguments ($prefix + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")) -TimeoutSeconds 60
        } catch {
            continue
        }
        $version = ($probe.StdOut + "").Trim()
        if ($probe.ExitCode -eq 0 -and $version -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 10) {
            return @{ Exe = $command.Source; Prefix = $prefix; Version = $version; Display = (@($candidate) -join " ") }
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# World-code check (Python, standard library only)
# ---------------------------------------------------------------------------
$WorldCheckPy = @'
"""Run the Wikipelago world's own generation steps with small Archipelago stand-ins.

Written and run by world/fuzz_test.ps1 (not part of the APWorld). Standard library only.
Reads a JSON list of cases ({"name", "seed", "settings"}) and writes, for each case, the
outcome of generate_early / create_regions / create_items / set_rules / fill_slot_data plus
consistency checks, and a description of the world's options.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import enum
import importlib
import json
import random
import sys
import traceback
import types
import typing

AP_COMMON_OPTIONS = {"progression_balancing", "accessibility"}


class StandInError(Exception):
    pass


def install_archipelago_stand_ins():
    base = types.ModuleType("BaseClasses")

    class ItemClassification(enum.IntFlag):
        filler = 0
        progression = 1
        useful = 2
        trap = 4
        skip_balancing = 8
        progression_skip_balancing = 9

    class Item:
        game = "Generic"

        def __init__(self, name, classification, code, player):
            self.name = name
            self.classification = classification
            self.code = code
            self.player = player
            self.location = None

    class Location:
        game = "Generic"

        def __init__(self, player, name="", address=None, parent=None):
            self.player = player
            self.name = name
            self.address = address
            self.parent_region = parent
            self.item = None
            self.locked = False
            self.access_rule = lambda state: True

        def place_locked_item(self, item):
            if self.item is not None:
                raise StandInError(f"location {self.name!r} already holds {self.item.name!r}")
            self.item = item
            item.location = self
            self.locked = True

    class Entrance:
        def __init__(self, player, name, parent):
            self.player = player
            self.name = name
            self.parent_region = parent
            self.connected_region = None
            self.access_rule = lambda state: True

    class Region:
        def __init__(self, name, player, multiworld, hint=None):
            self.name = name
            self.player = player
            self.multiworld = multiworld
            self.locations = []
            self.exits = []
            self.entrances = []

        def add_locations(self, locations, location_type=None):
            location_type = location_type or Location
            for name, address in locations.items():
                self.locations.append(location_type(self.player, name, address, self))

        def connect(self, connecting_region, name=None, rule=None):
            entrance = Entrance(self.player, name or f"{self.name} -> {connecting_region.name}", self)
            if rule is not None:
                entrance.access_rule = rule
            entrance.connected_region = connecting_region
            connecting_region.entrances.append(entrance)
            self.exits.append(entrance)
            return entrance

    base.ItemClassification = ItemClassification
    base.Item = Item
    base.Location = Location
    base.Entrance = Entrance
    base.Region = Region

    options = types.ModuleType("Options")

    class Option:
        default = 0

        def __init__(self, value):
            self.value = value

        @classmethod
        def from_any(cls, data):
            raise NotImplementedError(cls.__name__)

    class Toggle(Option):
        @classmethod
        def from_any(cls, data):
            if isinstance(data, bool):
                return cls(int(data))
            if isinstance(data, int) and data in (0, 1):
                return cls(data)
            if isinstance(data, str) and data.strip().lower() in ("true", "false", "on", "off"):
                return cls(int(data.strip().lower() in ("true", "on")))
            raise ValueError(f"{cls.__name__}: {data!r} is not a toggle value")

    class DefaultOnToggle(Toggle):
        default = 1

    class Range(Option):
        range_start = 0
        range_end = 1

        @classmethod
        def from_any(cls, data):
            if isinstance(data, str) and data.strip().lstrip("-").isdigit():
                data = int(data.strip())
            if isinstance(data, bool) or not isinstance(data, int):
                raise ValueError(f"{cls.__name__}: {data!r} is not a number")
            if not cls.range_start <= data <= cls.range_end:
                raise ValueError(f"{cls.__name__}: {data} is outside {cls.range_start}..{cls.range_end}")
            return cls(data)

    class Choice(Option):
        @classmethod
        def _prefixed(cls, prefix):
            return {
                name[len(prefix):]: getattr(cls, name)
                for name in dir(cls)
                if name.startswith(prefix) and isinstance(getattr(cls, name), int)
            }

        @classmethod
        def values_by_name(cls):
            return cls._prefixed("option_")

        @classmethod
        def aliases_by_name(cls):
            return cls._prefixed("alias_")

        @classmethod
        def from_any(cls, data):
            values = cls.values_by_name()
            if isinstance(data, str):
                key = data.strip().lower()
                if key in values:
                    return cls(values[key])
                aliases = cls.aliases_by_name()
                if key in aliases:
                    return cls(aliases[key])
            elif isinstance(data, int) and not isinstance(data, bool) and data in values.values():
                return cls(data)
            raise ValueError(f"{cls.__name__}: {data!r} is not one of {sorted(values)}")

    @dataclasses.dataclass
    class PerGameCommonOptions:
        def as_dict(self, *option_names):
            return {name: getattr(self, name).value for name in option_names}

    options.Option = Option
    options.Toggle = Toggle
    options.DefaultOnToggle = DefaultOnToggle
    options.Range = Range
    options.Choice = Choice
    options.PerGameCommonOptions = PerGameCommonOptions

    worlds = types.ModuleType("worlds")
    worlds.__path__ = []
    auto_world = types.ModuleType("worlds.AutoWorld")

    class WebWorld:
        theme = "grass"

    class World:
        game = "Generic"

        def __init__(self, multiworld, player):
            self.multiworld = multiworld
            self.player = player
            self.random = random.Random()

    auto_world.WebWorld = WebWorld
    auto_world.World = World

    generic = types.ModuleType("worlds.generic")
    generic.__path__ = []
    rules = types.ModuleType("worlds.generic.Rules")

    def set_rule(spot, rule):
        spot.access_rule = rule

    def add_rule(spot, rule, combine="and"):
        old = spot.access_rule
        if combine == "or":
            spot.access_rule = lambda state: old(state) or rule(state)
        else:
            spot.access_rule = lambda state: old(state) and rule(state)

    rules.set_rule = set_rule
    rules.add_rule = add_rule
    worlds.AutoWorld = auto_world
    worlds.generic = generic
    generic.Rules = rules
    sys.modules.update({
        "BaseClasses": base,
        "Options": options,
        "worlds": worlds,
        "worlds.AutoWorld": auto_world,
        "worlds.generic": generic,
        "worlds.generic.Rules": rules,
    })
    return options


class FakeMultiWorld:
    def __init__(self):
        self.regions = []
        self.itempool = []
        self.completion_condition = {}
        self._index_key = None
        self._locations = {}
        self._entrances = {}
        self._regions = {}

    def _index(self):
        key = (len(self.regions), sum(len(r.locations) + len(r.exits) for r in self.regions))
        if key == self._index_key:
            return
        self._locations, self._entrances, self._regions = {}, {}, {}
        for region in self.regions:
            self._regions.setdefault((region.name, region.player), region)
            for location in region.locations:
                self._locations.setdefault((location.name, location.player), location)
            for entrance in region.exits:
                self._entrances.setdefault((entrance.name, entrance.player), entrance)
        self._index_key = key

    def get_location(self, name, player):
        self._index()
        if (name, player) not in self._locations:
            raise KeyError(f"no location {name!r}")
        return self._locations[(name, player)]

    def get_entrance(self, name, player):
        self._index()
        if (name, player) not in self._entrances:
            raise KeyError(f"no entrance {name!r}")
        return self._entrances[(name, player)]

    def get_region(self, name, player):
        self._index()
        if (name, player) not in self._regions:
            raise KeyError(f"no region {name!r}")
        return self._regions[(name, player)]


class FullInventoryState:
    def __init__(self, counts):
        self.counts = dict(counts)
        self.reachable_regions = set()

    def has(self, item, player, count=1):
        return self.counts.get(item, 0) >= count

    def has_all(self, items, player):
        return all(self.counts.get(item, 0) > 0 for item in items)

    def has_any(self, items, player):
        return any(self.counts.get(item, 0) > 0 for item in items)

    def count(self, item, player):
        return self.counts.get(item, 0)

    def can_reach_region(self, name, player):
        return name in self.reachable_regions


def build_options(options_cls, settings):
    hints = typing.get_type_hints(options_cls)
    fields = [field.name for field in dataclasses.fields(options_cls)]
    unknown = sorted(set(settings) - set(fields) - AP_COMMON_OPTIONS)
    if unknown:
        raise ValueError(f"unknown option(s): {', '.join(unknown)}")
    values = {}
    for name in fields:
        option_cls = hints[name]
        values[name] = option_cls.from_any(settings[name]) if name in settings else option_cls(option_cls.default)
    return options_cls(**values)


def describe_options(options_cls, ap_options):
    hints = typing.get_type_hints(options_cls)
    described = {}
    for field in dataclasses.fields(options_cls):
        cls = hints[field.name]
        if issubclass(cls, ap_options.Range):
            described[field.name] = {"kind": "Range", "min": cls.range_start, "max": cls.range_end, "default": cls.default}
        elif issubclass(cls, ap_options.Toggle):
            described[field.name] = {"kind": "Toggle", "default": int(cls.default)}
        elif issubclass(cls, ap_options.Choice):
            ordered = sorted(cls.values_by_name().items(), key=lambda kv: kv[1])
            described[field.name] = {"kind": "Choice", "default": cls.default, "choices": [name for name, _ in ordered]}
        else:
            described[field.name] = {"kind": cls.__name__}
    return described


def check_world(world, multiworld, item_table, location_table):
    problems = []
    player = world.player
    locations = [location for region in multiworld.regions for location in region.locations]
    name_counts = collections.Counter(location.name for location in locations)
    duplicates = sorted(name for name, count in name_counts.items() if count > 1)
    if duplicates:
        problems.append(f"duplicate locations {duplicates[:3]}")
    for location in locations:
        if location.address is None:
            continue
        data = location_table.get(location.name)
        if data is None:
            problems.append(f"location {location.name!r} is not in location_table")
        elif data.code != location.address:
            problems.append(f"location {location.name!r} has id {location.address}, table says {data.code}")
    empty = [location for location in locations if location.item is None]
    if len(multiworld.itempool) != len(empty):
        problems.append(f"item pool holds {len(multiworld.itempool)} items for {len(empty)} empty locations")
    for item in multiworld.itempool:
        data = item_table.get(item.name)
        if data is None:
            problems.append(f"item {item.name!r} is not in item_table")
        elif data.code != item.code:
            problems.append(f"item {item.name!r} has id {item.code}, table says {data.code}")
        if item.name == "Victory":
            problems.append("Victory is in the shuffled item pool")

    counts = collections.Counter(item.name for item in multiworld.itempool)
    state = FullInventoryState(counts)
    regions = {region.name: region for region in multiworld.regions}
    if "Menu" not in regions:
        problems.append("no Menu region")
    frontier = ["Menu"] if "Menu" in regions else []
    while frontier:
        name = frontier.pop()
        if name in state.reachable_regions:
            continue
        state.reachable_regions.add(name)
        for entrance in regions[name].exits:
            target = entrance.connected_region
            if target is not None and target.name not in state.reachable_regions and entrance.access_rule(state):
                frontier.append(target.name)
    unreachable = [
        location.name for location in locations
        if location.parent_region.name not in state.reachable_regions or not location.access_rule(state)
    ]
    if unreachable:
        problems.append(f"{len(unreachable)} location(s) unreachable with every pool item, e.g. {unreachable[:3]}")
    unreachable_set = set(unreachable)
    for location in locations:
        if location.item is not None and location.name not in unreachable_set:
            state.counts[location.item.name] = state.counts.get(location.item.name, 0) + 1
    condition = multiworld.completion_condition.get(player)
    if condition is None:
        problems.append("no completion condition set")
    elif not condition(state):
        problems.append("goal not reachable with every pool item collected")
    stats = {
        "item_counts": dict(sorted(counts.items())),
        "locations_addressed": sum(1 for location in locations if location.address is not None),
        "empty_locations": len(empty),
    }
    return problems, stats


def run_case(world_cls, options_cls, case, item_table, location_table):
    result = {"name": case["name"]}
    try:
        options = build_options(options_cls, case.get("settings") or {})
    except Exception as exc:
        result.update(status="crash", stage="options", message=f"invalid options: {exc}")
        return result
    multiworld = FakeMultiWorld()
    world = world_cls(multiworld, 1)
    world.options = options
    world.random = random.Random(int(case.get("seed") or 0))
    stage = "generate_early"
    try:
        world.generate_early()
        stage = "create_regions"
        world.create_regions()
        stage = "create_items"
        world.create_items()
        stage = "set_rules"
        world.set_rules()
        stage = "fill_slot_data"
        json.dumps(world.fill_slot_data())
    except Exception as exc:
        deliberate = type(exc) is Exception and str(exc).startswith("Wikipelago")
        if deliberate:
            result.update(status="reject", stage=stage, message=str(exc))
        else:
            result.update(status="crash", stage=stage, message=f"{type(exc).__name__}: {exc}",
                          traceback=traceback.format_exc())
        return result
    problems, stats = check_world(world, multiworld, item_table, location_table)
    result.update(stats)
    if problems:
        result.update(status="crash", stage="checks", message="; ".join(problems))
    else:
        result["status"] = "accept"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--world-src", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    output = {"harness_error": None, "python": sys.version.split()[0], "options": None, "results": []}
    try:
        ap_options = install_archipelago_stand_ins()
        sys.path.insert(0, args.world_src)
        package = importlib.import_module("wikipelago")
        options_cls = importlib.import_module("wikipelago.Options").WikipelagoOptions
        item_table = importlib.import_module("wikipelago.Items").item_table
        location_table = importlib.import_module("wikipelago.Locations").location_table
        world_cls = package.WikipelagoWorld
        output["options"] = describe_options(options_cls, ap_options)
    except Exception:
        output["harness_error"] = (
            "Could not import the world with the stand-in Archipelago modules "
            "(world error, or a new Archipelago API the stand-ins in fuzz_test.ps1 lack):\n"
            + traceback.format_exc()
        )
    else:
        with open(args.cases, encoding="utf-8-sig") as handle:
            cases = json.load(handle)
        for case in cases:
            output["results"].append(run_case(world_cls, options_cls, case, item_table, location_table))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@

function Compare-OptionSpec($Spec, $Described) {
    $diffs = New-Object System.Collections.Generic.List[string]
    $names = @($Described.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($name in $names) {
        if (-not $Spec.Contains($name)) { $diffs.Add("$name missing from the Options.py parse"); continue }
        $want = $Described.$name
        $have = $Spec[$name]
        if ($want.kind -ne $have.Kind) { $diffs.Add("$name kind $($have.Kind) vs $($want.kind)"); continue }
        if ([int]$want.default -ne [int]$have.Default) { $diffs.Add("$name default $($have.Default) vs $($want.default)") }
        if ($want.kind -eq "Range" -and ([int]$want.min -ne $have.Min -or [int]$want.max -ne $have.Max)) {
            $diffs.Add("$name range $($have.Min)..$($have.Max) vs $($want.min)..$($want.max)")
        }
        if ($want.kind -eq "Choice" -and ((@($want.choices) -join ",") -ne (@($have.Choices) -join ","))) {
            $diffs.Add("$name choices differ")
        }
    }
    foreach ($name in $Spec.Keys) {
        if ($names -notcontains $name) { $diffs.Add("$name parsed but not a WikipelagoOptions field") }
    }
    return $diffs
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
$worldSrc = Join-Path $Root "APWorldSource"
$worldDir = Join-Path $worldSrc "wikipelago"
$optionsPath = Join-Path $worldDir "Options.py"
$repoRoot = Split-Path -Parent $Root
$templatePath = [System.IO.Path]::Combine($repoRoot, "yaml", "Wikipelago.yaml")

$spec = Get-OptionSpec $optionsPath
$MaxBranches = Get-PyIntConstant (Join-Path $worldDir "Locations.py") "MAX_BRANCHES"
$MaxBranchLength = Get-PyIntConstant (Join-Path $worldDir "Locations.py") "MAX_BRANCH_LENGTH"
$MaxBingoBoards = Get-PyIntConstant (Join-Path $worldDir "Locations.py") "MAX_BINGO_BOARDS"
$ScrollSpeedUpgrades = Get-PyIntConstant (Join-Path $worldDir "__init__.py") "SCROLL_SPEED_UPGRADES"

if ($Seed -lt 0) { $Seed = Get-Random -Minimum 1 -Maximum 2147483647 }
$null = Get-Random -SetSeed $Seed

if (-not $OutputDir) {
    $OutputDir = Join-Path $Root "fuzz_output"
}
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null
$OutputDir = (Resolve-Path $OutputDir).Path
$yamlRoot = Join-Path $OutputDir "yamls"
$logDir = Join-Path $OutputDir "logs"
$generatorOutRoot = Join-Path $OutputDir "output"
New-Item -ItemType Directory -Path $yamlRoot | Out-Null
New-Item -ItemType Directory -Path $logDir | Out-Null

# --- Cases: fixed expectations first, then random ones.
$defaults = Get-DefaultSettings $spec
$cases = New-Object System.Collections.Generic.List[object]
$expectNumber = 0
function Add-ExpectCase([string]$Id, $Settings, [string]$Expect, $Problems) {
    $script:expectNumber += 1
    $cases.Add(@{
        Id = $Id
        Player = "WikiExpect{0:D2}" -f $script:expectNumber
        Style = "expect"
        Settings = $Settings
        Expect = $Expect
        Problems = $Problems
        Seed = 1000 + $script:expectNumber
    })
}

$template = Read-TemplateSettings $templatePath $spec
Add-ExpectCase "expect-template" (Copy-Settings $defaults $template.Settings) "accept" $template.Problems
Add-ExpectCase "expect-defaults" (Copy-Settings $defaults @{}) "accept" $null
Add-ExpectCase "expect-realm-master" (Copy-Settings $defaults @{
    goal = "realm_master"; branch_count = 3; branch_length = 3; topic_portals = $true; wikipedia_language = "fr"
}) "accept" $null
Add-ExpectCase "expect-minimal" (Copy-Settings $defaults @{
    check_count = 10; required_fragments = 1; additional_fragments_in_pool = 0; toggle_bingo_letterpairs = $false
    branch_count = 0; back_depth_unlocks = 0; target_reroll_unlocks = 0; trap_count = 0
}) "accept" $null
Add-ExpectCase "reject-no-category" (Copy-Settings $defaults (Get-OnlyCategories $spec @())) "no_category" $null
Add-ExpectCase "reject-realm-master-no-branch" (Copy-Settings $defaults @{ goal = "realm_master"; branch_count = 0 }) "realm_master_no_branch" $null
Add-ExpectCase "reject-bingo-no-boards" (Copy-Settings $defaults @{
    toggle_bingo_letterpairs = $true; bingo_cards_start = 0; bingo_card_unlocks = 0
}) "bingo_no_boards" $null
Add-ExpectCase "reject-item-math" (Copy-Settings $defaults @{
    check_count = 10; toggle_bingo_letterpairs = $false; branch_count = 0; trap_count = 99
}) "item_math" $null
$realmTopics = Copy-Settings $defaults (Get-OnlyCategories $spec @("include_history", "include_music"))
$realmTopics.topic_portals = $true
$realmTopics.branch_count = 3
Add-ExpectCase "reject-realm-topics" $realmTopics "realm_topics" $null
$poolTooSmall = Copy-Settings $defaults (Get-OnlyCategories $spec @("include_animals"))
$poolTooSmall.check_count = 100
Add-ExpectCase "reject-pool-too-small" $poolTooSmall "pool_too_small" $null

for ($i = 1; $i -le $Runs; $i++) {
    $roll = Get-Random -Minimum 0 -Maximum 100
    $style = "uniform"
    if ($roll -lt 40) { $style = "default-ish" } elseif ($roll -ge 85) { $style = "few-categories" }
    $cases.Add(@{
        Id = "fuzz-{0:D3}" -f $i
        Player = "WikiFuzz{0:D3}" -f $i
        Style = $style
        Settings = New-RandomSettings $spec $style
        Expect = $null
        Problems = $null
        Seed = Get-Random -Minimum 1 -Maximum 999999999
    })
}

foreach ($case in $cases) {
    $playersDir = Join-Path $yamlRoot $case.Id
    New-Item -ItemType Directory -Path $playersDir | Out-Null
    $case.PlayersDir = $playersDir
    $case.YamlPath = Join-Path $playersDir "$($case.Id).yaml"
    $description = "fuzz_test.ps1 $($case.Style) case $($case.Id) (seed $Seed)"
    Write-Utf8File $case.YamlPath (ConvertTo-WikipelagoYaml $case.Settings $case.Player $description)
    $case.Prediction = Get-ModelPrediction $case.Settings
}

# --- World-code check.
$failures = 0
$worldResults = @{}
$worldCheck = "model only"
$python = $null
if ($NoWorldCheck) {
    Write-Warn "-NoWorldCheck: only the PowerShell model runs; the world's own code is not exercised."
} else {
    $python = Resolve-Python $PythonCommand
    if (-not $python) {
        $tried = "py -3, python, python3"
        if ($PythonCommand) { $tried = $PythonCommand }
        Write-Warn "Python 3.10+ not found (tried $tried). Only the PowerShell model runs, so model/world drift cannot be detected. Install Python or pass -PythonCommand."
    }
}
if ($python) {
    $harnessPath = Join-Path $OutputDir "world_check.py"
    $casesJsonPath = Join-Path $OutputDir "world_check_cases.json"
    $worldJsonPath = Join-Path $OutputDir "world_check_results.json"
    Write-Utf8File $harnessPath $WorldCheckPy
    $caseList = @($cases | ForEach-Object { [ordered]@{ name = $_.Id; seed = $_.Seed; settings = $_.Settings } })
    Write-Utf8File $casesJsonPath (ConvertTo-Json -InputObject $caseList -Depth 6)
    Write-Info "Running the world's own code for $($cases.Count) cases with $($python.Display) (Python $($python.Version))"
    $run = Invoke-CapturedProcess -FilePath $python.Exe -Arguments ($python.Prefix + @("-B", "-I", $harnessPath, "--world-src", $worldSrc, "--cases", $casesJsonPath, "--out", $worldJsonPath)) -WorkingDirectory $OutputDir
    if ($run.ExitCode -ne 0 -or -not (Test-Path $worldJsonPath)) {
        Write-Fail "World check harness failed (exit $($run.ExitCode)):`n$($run.StdOut)$($run.StdErr)"
        exit 1
    }
    $worldData = [System.IO.File]::ReadAllText($worldJsonPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($worldData.harness_error) {
        Write-Fail $worldData.harness_error
        exit 1
    }
    foreach ($result in @($worldData.results)) { $worldResults[$result.name] = $result }
    $worldCheck = "world code via $($python.Display) (Python $($worldData.python)) + PowerShell model"
    $specDiffs = Compare-OptionSpec $spec $worldData.options
    if ($specDiffs.Count -gt 0) {
        $failures += 1
        Write-Fail "fuzz_test.ps1 read Options.py differently from Python: $($specDiffs -join '; ')"
    }
}

# --- Generator command setup.
$psExe = (Get-Process -Id $PID).Path
$usesOutputDir = $GenerateCommand -like "*{{output_dir}}*"
$generatorPasses = 0
$generatorFailures = 0
Write-Info "Seed ${Seed}: $($cases.Count) cases ($expectNumber expectation + $Runs random), checked with $worldCheck"
if ($GenerateCommand) {
    Write-Info "Generator command: $GenerateCommand"
}

$summary = New-Object System.Collections.Generic.List[string]
$jsonResults = New-Object System.Collections.Generic.List[object]
$accepted = 0
$crashed = 0
$rejectedByReason = [ordered]@{}

foreach ($case in $cases) {
    $prediction = $case.Prediction
    $problems = New-Object System.Collections.Generic.List[string]
    $notes = New-Object System.Collections.Generic.List[string]
    foreach ($note in $prediction.Notes) { $problems.Add($note) }
    if ($case.Problems) { foreach ($problem in $case.Problems) { $problems.Add($problem) } }

    $worldOutcome = $null
    $world = $worldResults[$case.Id]
    if ($python) {
        if (-not $world) {
            $problems.Add("no world-check result")
        } else {
            $reason = $null
            if ($world.status -eq "reject") {
                $info = Find-ReasonInText $world.message
                if ($info) { $reason = $info.Key }
            }
            $worldOutcome = @{ Status = [string]$world.status; Reason = $reason; Message = [string]$world.message }
            $diff = Compare-ModelToOutcome $prediction $worldOutcome "the world"
            if ($diff) {
                $problems.Add($diff)
            } elseif ($worldOutcome.Status -eq "accept") {
                $poolDiff = Compare-ItemPool $prediction $world $case.Settings
                if ($poolDiff) { $problems.Add("item pool differs: $poolDiff") }
            }
        }
    }

    $expectedOutcome = $null
    if ($case.Expect) {
        if ($case.Expect -eq "accept") {
            $expectedOutcome = @{ Status = "accept"; Reason = $null; Message = "" }
        } else {
            $expectedOutcome = @{ Status = "reject"; Reason = $case.Expect; Message = $case.Expect }
        }
        $diff = Compare-ModelToOutcome $prediction $expectedOutcome "the expectation"
        if ($diff) { $problems.Add("model vs expectation: $diff") }
        if ($worldOutcome -and ((Format-Outcome $worldOutcome) -ne (Format-Outcome $expectedOutcome))) {
            $problems.Add("expected $(Format-Outcome $expectedOutcome), the world gave $(Format-Outcome $worldOutcome): $($worldOutcome.Message)")
        }
    }

    # Verdict shown for the case: the world's when available, else the model's.
    $verdict = Format-Prediction $prediction
    if ($worldOutcome) {
        $verdict = Format-Outcome $worldOutcome
        $info = Get-ReasonInfo $worldOutcome.Reason
        if ($info -and $info.Data -and @($prediction.Violations | Where-Object { $_.Key -eq $info.Key }).Count -eq 0) {
            $verdict += " (pool-limited)"
        }
    } elseif ($prediction.Violations.Count -eq 0) {
        $verdict = "accept (model; article pool not checked)"
    }
    $verdictKey = "accept"
    if ($worldOutcome) {
        if ($worldOutcome.Status -eq "reject") { $verdictKey = [string]$worldOutcome.Reason }
        elseif ($worldOutcome.Status -ne "accept") { $verdictKey = "crash" }
    } elseif ($prediction.Violations.Count -gt 0) {
        $verdictKey = $prediction.Violations[0].Key
    }
    if ($verdictKey -eq "accept") { $accepted += 1 }
    elseif ($verdictKey -eq "crash") { $crashed += 1 }
    else {
        if (-not $verdictKey) { $verdictKey = "unrecognised" }
        if ($rejectedByReason.Contains($verdictKey)) { $rejectedByReason[$verdictKey] += 1 } else { $rejectedByReason[$verdictKey] = 1 }
    }

    # --- Optional generator run.
    $generator = $null
    if ($GenerateCommand) {
        $caseOut = Join-Path $generatorOutRoot $case.Id
        New-Item -ItemType Directory -Path $caseOut -Force | Out-Null
        $logPath = Join-Path $logDir "$($case.Id).log"
        $command = $GenerateCommand.Replace("{{yaml}}", $case.YamlPath).Replace("{{players_dir}}", $case.PlayersDir).Replace("{{output_dir}}", $caseOut).Replace("{{seed}}", [string]$case.Seed).Replace("{{name}}", $case.Id)
        $wrapped = "`$ErrorActionPreference = 'Continue'`n$command`nif (`$null -ne `$LASTEXITCODE) { exit `$LASTEXITCODE }`n"
        $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($wrapped))
        $started = Get-Date
        try {
            $run = Invoke-CapturedProcess -FilePath $psExe -Arguments @("-NoProfile", "-NonInteractive", "-EncodedCommand", $encoded) -WorkingDirectory $Root -TimeoutSeconds $GenerateTimeoutSeconds
            $log = "> $command`n`n$($run.StdOut)"
            if ($run.StdErr) { $log += "`n--- stderr ---`n$($run.StdErr)" }
            Write-Utf8File $logPath $log
            $text = "$($run.StdOut)`n$($run.StdErr)"
            if ($run.TimedOut) {
                $generator = @{ Status = "crash"; Reason = $null; Message = "timed out after $GenerateTimeoutSeconds s" }
            } elseif ($text -match '(?i)(Could not load world|Did not load)[^\r\n]*wikipelago') {
                $generator = @{ Status = "crash"; Reason = $null; Message = "Archipelago did not load the wikipelago.apworld under test: $($Matches[0])" }
            } elseif ($run.ExitCode -eq 0) {
                $zips = @()
                if ($usesOutputDir) { $zips = @(Get-ChildItem -Path $caseOut -Filter *.zip -File -ErrorAction SilentlyContinue) }
                if ($usesOutputDir -and $zips.Count -eq 0) {
                    $generator = @{ Status = "crash"; Reason = $null; Message = "exit 0 but no .zip in $caseOut" }
                } else {
                    $generator = @{ Status = "accept"; Reason = $null; Message = "" }
                }
            } else {
                $info = Find-ReasonInText $text
                if ($info) {
                    $generator = @{ Status = "reject"; Reason = $info.Key; Message = $info.Pattern }
                } else {
                    $tail = (@(($text -split "`r?`n") | Where-Object { $_.Trim() }) | Select-Object -Last 3) -join " | "
                    $generator = @{ Status = "crash"; Reason = $null; Message = "exit $($run.ExitCode) without a Wikipelago rejection: $tail" }
                }
            }
        } catch {
            Write-Utf8File $logPath $_.Exception.ToString()
            $generator = @{ Status = "crash"; Reason = $null; Message = $_.Exception.Message }
        }
        $generator.Seconds = [int]((Get-Date) - $started).TotalSeconds
        $generator.Log = $logPath

        $genProblems = New-Object System.Collections.Generic.List[string]
        $diff = Compare-ModelToOutcome $prediction $generator "the generator"
        if ($diff) { $genProblems.Add($diff) }
        if (-not $diff -and $worldOutcome -and $worldOutcome.Status -ne "crash" -and ((Format-Outcome $worldOutcome) -ne (Format-Outcome $generator))) {
            $worldInfo = Get-ReasonInfo $worldOutcome.Reason
            $genInfo = Get-ReasonInfo $generator.Reason
            if (($worldInfo -and $worldInfo.Data) -or ($genInfo -and $genInfo.Data)) {
                $notes.Add("generator gave $(Format-Outcome $generator), local check $(Format-Outcome $worldOutcome): article-pool result depends on the random seed")
            } else {
                $genProblems.Add("the world check gave $(Format-Outcome $worldOutcome) but the generator gave $(Format-Outcome $generator)")
            }
        }
        if ($expectedOutcome -and ((Format-Outcome $generator) -ne (Format-Outcome $expectedOutcome))) {
            $genProblems.Add("expected $(Format-Outcome $expectedOutcome), the generator gave $(Format-Outcome $generator)")
        }
        if ($genProblems.Count -eq 0) { $generatorPasses += 1 } else { $generatorFailures += 1 }
        foreach ($problem in $genProblems) { $problems.Add("generator: $problem (log: $logPath)") }
        if (-not $KeepFiles -and (Test-Path $caseOut)) {
            Get-ChildItem -Path $caseOut -Filter *.zip -File -ErrorAction SilentlyContinue | Remove-Item -Force
        }
    }

    $label = "{0,-30} {1,-40} {2}" -f $case.Id, $verdict, (Format-CaseBrief $case.Settings)
    if ($generator) {
        $label += "  | generator: $(Format-Outcome $generator) in $($generator.Seconds)s"
    }
    if ($problems.Count -eq 0) {
        Write-Pass $label
        foreach ($note in $notes) { Write-Info "  $note" }
        $summary.Add("PASS $label")
    } else {
        $failures += 1
        Write-Fail $label
        foreach ($problem in $problems) { Write-Host "       - $problem" -ForegroundColor Red }
        $summary.Add("FAIL $label")
        foreach ($problem in $problems) { $summary.Add("     - $problem") }
    }
    foreach ($note in $notes) { $summary.Add("     note: $note") }

    $entry = [ordered]@{
        id = $case.Id
        style = $case.Style
        yaml = $case.YamlPath
        expect = $case.Expect
        model = Format-Prediction $prediction
        world = $null
        generator = $null
        passed = ($problems.Count -eq 0)
        problems = @($problems)
        notes = @($notes)
    }
    if ($worldOutcome) { $entry.world = [ordered]@{ verdict = Format-Outcome $worldOutcome; message = $worldOutcome.Message } }
    if ($generator) { $entry.generator = [ordered]@{ verdict = Format-Outcome $generator; message = $generator.Message; log = $generator.Log; seconds = $generator.Seconds } }
    $jsonResults.Add($entry)
}

$summaryPath = Join-Path $OutputDir "summary.txt"
$header = @(
    "fuzz_test.ps1 seed $Seed ($expectNumber expectation + $Runs random cases)",
    "check: $worldCheck",
    ""
)
Write-Utf8File $summaryPath ((@($header) + @($summary)) -join [Environment]::NewLine)
Write-Utf8File (Join-Path $OutputDir "results.json") (ConvertTo-Json -InputObject $jsonResults.ToArray() -Depth 6)

$rejectedTotal = 0
foreach ($value in $rejectedByReason.Values) { $rejectedTotal += $value }
$reasonText = (@($rejectedByReason.Keys | ForEach-Object { "$_ $($rejectedByReason[$_])" }) -join ", ")

Write-Host ""
Write-Host "Fuzz summary" -ForegroundColor White
Write-Host "  Output folder : $OutputDir"
Write-Host "  Seed          : $Seed (re-run with -Seed $Seed)"
Write-Host "  Checked with  : $worldCheck"
Write-Host "  Cases         : $($cases.Count) ($expectNumber expectation + $Runs random)"
Write-Host "  Accepted      : $accepted"
Write-Host "  Rejected      : $rejectedTotal$(if ($reasonText) { " ($reasonText)" })"
if ($crashed -gt 0) {
    Write-Host "  World crashed : $crashed"
}
if ($GenerateCommand) {
    Write-Host "  Generator     : $generatorPasses passed, $generatorFailures failed"
}
Write-Host "  Failures      : $failures"
Write-Host "  Summary file  : $summaryPath"
if (-not $GenerateCommand) {
    Write-Host "  Not covered   : Archipelago's own generator (fill, accessibility, output). Run real_fuzz_test.ps1 for that."
}

if ($failures -gt 0) {
    exit 1
}
exit 0
