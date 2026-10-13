<#
.SYNOPSIS
    Real Archipelago generation for random Wikipelago YAMLs.

.DESCRIPTION
    Builds world/APWorld/wikipelago.apworld (unless -SkipBuild), installs THAT file into
    the Archipelago under test, then runs Archipelago's generator once per case. The cases
    and their expected verdicts come from fuzz_test.ps1 (its fixed expectation cases plus
    -Runs random ones): a case the world accepts must produce a seed .zip, a case it
    rejects must fail with the same "Wikipelago ..." error. Every run is reported as PASS
    or FAIL, and the script exits non-zero when any run fails.

    Each run gets its own folder holding only its YAML (passed as --player_files_path) and
    its own output folder, like world/ci_generate.py does in CI.

    Archipelago under test, first match wins: -ArchipelagoRoot, the ARCHIPELAGO_ROOT
    environment variable, then an "Archipelago" folder next to this repo or inside it,
    C:\ProgramData\Archipelago, %LOCALAPPDATA%\Programs\Archipelago, C:\Archipelago and
    C:\Games\Archipelago (~/Archipelago on Linux/macOS).
      - Source checkout (Generate.py + worlds/): Generate.py runs with -PythonCommand, else
        a .venv / venv inside the checkout, else py -3.12/-3.11/-3.13, python, python3
        (Archipelago 0.6.7 needs Python 3.11-3.13). Install Archipelago's requirements once
        first: python ModuleUpdate.py --yes (inside the checkout). The CI pins 0.6.7.
      - Installed Archipelago (Windows, ArchipelagoGenerate.exe): runs that executable.

    The apworld is copied to <Archipelago>/custom_worlds/wikipelago.apworld, the folder
    Archipelago loads user worlds from. Any existing *wikipelago*.apworld in custom_worlds
    (and, for a source checkout, in worlds/) is first renamed to *.real_fuzz_backup and put
    back when the run ends, even after an error or Ctrl+C. If the script is killed hard,
    rename the .real_fuzz_backup file back yourself; the script refuses to start while one
    exists. A loose worlds/wikipelago folder would shadow the apworld, so the script stops
    if it finds one.

.PARAMETER Runs
    Number of random cases (fuzz_test.ps1 adds its fixed expectation cases).

.PARAMETER ArchipelagoRoot
    Archipelago source checkout or install folder.

.PARAMETER PythonCommand
    Python executable for a source checkout.

.PARAMETER KeepFiles
    Keep the generated seed zips (logs and YAMLs are always kept).

.PARAMETER NoPause
    Do not wait for Enter before closing.

.PARAMETER SkipBuild
    Use the existing world/APWorld/wikipelago.apworld instead of rebuilding it.

.PARAMETER Seed
    Seed for the random settings (see fuzz_test.ps1).

.PARAMETER OutputDir
    Output folder, default world/fuzz_output (wiped at the start).

.PARAMETER GenerateTimeoutSeconds
    Time limit for one Archipelago generation.

.EXAMPLE
    ./world/real_fuzz_test.ps1 -Runs 25 -ArchipelagoRoot C:\src\Archipelago -NoPause
#>
param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [int]$Runs = 25,
    [string]$ArchipelagoRoot = "",
    [string]$PythonCommand = "",
    [switch]$KeepFiles,
    [switch]$NoPause,
    [switch]$SkipBuild,
    [int]$Seed = -1,
    [string]$OutputDir = "",
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

function Pause-OnExit {
    if ($NoPause) { return }
    try {
        if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
            Read-Host "Press Enter to close" | Out-Null
        }
    } catch { }
}

function ConvertTo-PsLiteral([string]$Text) {
    return "'" + $Text.Replace("'", "''") + "'"
}

function ConvertTo-CommandLineArgument([string]$Arg) {
    if ($Arg.Length -gt 0 -and $Arg -notmatch '[\s"]') { return $Arg }
    return '"' + ($Arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

# Runs a program with stdin closed and returns its exit code and output.
function Invoke-Captured([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory, [hashtable]$Environment = @{}, [int]$TimeoutSeconds = 600) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = (@($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " ")
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }
    foreach ($key in $Environment.Keys) { $psi.EnvironmentVariables[$key] = [string]$Environment[$key] }
    $process = [System.Diagnostics.Process]::Start($psi)
    try {
        $process.StandardInput.Close()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            throw "$FilePath timed out after $TimeoutSeconds s"
        }
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Output = ($stdoutTask.Result + $stderrTask.Result) }
    } finally {
        $process.Dispose()
    }
}

function Get-ArchipelagoKind([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Container)) { return $null }
    if ((Test-Path -LiteralPath (Join-Path $Path "Generate.py")) -and
        (Test-Path -LiteralPath ([System.IO.Path]::Combine($Path, "worlds", "__init__.py")))) {
        return "source"
    }
    if (Test-Path -LiteralPath (Join-Path $Path "ArchipelagoGenerate.exe")) { return "installed" }
    return $null
}

function Find-Archipelago {
    $explicit = @()
    if ($ArchipelagoRoot) { $explicit += @{ Path = $ArchipelagoRoot; From = "-ArchipelagoRoot" } }
    elseif ($env:ARCHIPELAGO_ROOT) { $explicit += @{ Path = $env:ARCHIPELAGO_ROOT; From = "ARCHIPELAGO_ROOT" } }
    foreach ($entry in $explicit) {
        $full = [System.IO.Path]::GetFullPath($entry.Path)
        $kind = Get-ArchipelagoKind $full
        if (-not $kind) {
            throw "$($entry.From) points to '$full', which is neither an Archipelago source checkout (Generate.py + worlds\) nor an install (ArchipelagoGenerate.exe)."
        }
        return @{ Root = $full; Kind = $kind; From = $entry.From }
    }

    $repoRoot = Split-Path -Parent $Root
    $candidates = New-Object System.Collections.Generic.List[string]
    $candidates.Add((Join-Path (Split-Path -Parent $repoRoot) "Archipelago"))
    $candidates.Add((Join-Path $repoRoot "Archipelago"))
    if ($env:OS -eq "Windows_NT") {
        $candidates.Add("C:\ProgramData\Archipelago")
        if ($env:LOCALAPPDATA) { $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Archipelago")) }
        $candidates.Add("C:\Archipelago")
        $candidates.Add("C:\Games\Archipelago")
    } elseif ($HOME) {
        $candidates.Add((Join-Path $HOME "Archipelago"))
    }
    foreach ($candidate in $candidates) {
        $kind = Get-ArchipelagoKind $candidate
        if ($kind) { return @{ Root = [System.IO.Path]::GetFullPath($candidate); Kind = $kind; From = "auto-detected" } }
    }
    throw ("Could not find Archipelago. Looked in:`n  " + ($candidates -join "`n  ") +
        "`nPass -ArchipelagoRoot <folder> or set ARCHIPELAGO_ROOT. Use an Archipelago 0.6.7+ source checkout " +
        "(for example git clone --branch 0.6.7 https://github.com/ArchipelagoMW/Archipelago, then python ModuleUpdate.py --yes) " +
        "or an installed Archipelago.")
}

function Resolve-ApPython([string]$ApRoot) {
    $candidates = New-Object System.Collections.Generic.List[object]
    if ($PythonCommand) {
        $candidates.Add(@($PythonCommand))
    } else {
        foreach ($relative in @(".venv\Scripts\python.exe", "venv\Scripts\python.exe", ".venv/bin/python", "venv/bin/python")) {
            $path = Join-Path $ApRoot $relative
            if (Test-Path -LiteralPath $path -PathType Leaf) { $candidates.Add(@($path)) }
        }
        $candidates.Add(@("py", "-3.12"))
        $candidates.Add(@("py", "-3.11"))
        $candidates.Add(@("py", "-3.13"))
        $candidates.Add(@("python"))
        $candidates.Add(@("python3"))
    }
    $seen = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { continue }
        $prefix = @($candidate | Select-Object -Skip 1)
        try {
            $probe = Invoke-Captured $command.Source ($prefix + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")) "" @{} 60
        } catch {
            continue
        }
        $version = $probe.Output.Trim()
        $seen.Add("$(@($candidate) -join ' ') -> $version")
        if ($probe.ExitCode -eq 0 -and $version -match '^3\.(11|12|13)$') {
            return @{ Exe = $command.Source; Prefix = $prefix; Version = $version; Display = (@($candidate) -join " ") }
        }
    }
    $detail = "none found"
    if ($seen.Count -gt 0) { $detail = $seen -join "; " }
    throw "No Python 3.11-3.13 for the Archipelago source checkout ($detail). Pass -PythonCommand <path to python.exe>."
}

$apworldBuilt = Join-Path $Root "APWorld\wikipelago.apworld"
$moved = New-Object System.Collections.Generic.List[object]
$installedTarget = $null
$exitCode = 1

try {
    $ap = Find-Archipelago
    $apRoot = $ap.Root
    $apVersion = ""
    $utilsPy = Join-Path $apRoot "Utils.py"
    if (Test-Path -LiteralPath $utilsPy) {
        $versionMatch = [regex]::Match([System.IO.File]::ReadAllText($utilsPy), '(?m)^__version__\s*=\s*"([^"]+)"')
        if ($versionMatch.Success) { $apVersion = " $($versionMatch.Groups[1].Value)" }
    }
    Write-Info "Archipelago$apVersion under test: $apRoot ($($ap.Kind), $($ap.From))"

    if ($OutputDir) { $OutputDir = [System.IO.Path]::GetFullPath($OutputDir) } else { $OutputDir = Join-Path $Root "fuzz_output" }
    if ($OutputDir.Contains("'")) { throw "OutputDir must not contain a single quote: $OutputDir" }

    # The generator command fuzz_test.ps1 runs for each case (in a child PowerShell, stdin closed).
    $python = $null
    if ($ap.Kind -eq "source") {
        $python = Resolve-ApPython $apRoot
        Write-Info "Python for Generate.py: $($python.Display) (Python $($python.Version))"
        $check = Invoke-Captured $python.Exe ($python.Prefix + @("ModuleUpdate.py")) $apRoot @{ PYTHONIOENCODING = "utf-8" } 600
        if ($check.ExitCode -ne 0) {
            $tail = (@(($check.Output -split "`r?`n") | Where-Object { $_.Trim() }) | Select-Object -Last 5) -join "`n  "
            throw "Archipelago's Python requirements are not installed for $($python.Display). Install them once with:`n  cd $(ConvertTo-PsLiteral $apRoot); & $(ConvertTo-PsLiteral $python.Exe) $($python.Prefix -join ' ') ModuleUpdate.py --yes`nModuleUpdate.py said:`n  $tail"
        }
        $pythonArgs = (@($python.Prefix) | ForEach-Object { ConvertTo-PsLiteral $_ }) -join " "
        $generateCommand = "Set-Location -LiteralPath $(ConvertTo-PsLiteral $apRoot); " +
            "`$env:SKIP_REQUIREMENTS_UPDATE = '1'; `$env:PYTHONIOENCODING = 'utf-8'; " +
            "& $(ConvertTo-PsLiteral $python.Exe) $pythonArgs $(ConvertTo-PsLiteral (Join-Path $apRoot 'Generate.py')) " +
            "--player_files_path '{{players_dir}}' --outputpath '{{output_dir}}' --seed {{seed}}"
    } else {
        $generateCommand = "Set-Location -LiteralPath $(ConvertTo-PsLiteral $apRoot); `$env:PYTHONIOENCODING = 'utf-8'; " +
            "& $(ConvertTo-PsLiteral (Join-Path $apRoot 'ArchipelagoGenerate.exe')) " +
            "--player_files_path '{{players_dir}}' --outputpath '{{output_dir}}' --seed {{seed}}"
    }

    if ($SkipBuild) {
        if (-not (Test-Path -LiteralPath $apworldBuilt)) {
            throw "Missing $apworldBuilt. Run ./world/build_apworld.ps1 or drop -SkipBuild."
        }
        Write-Info "Using the existing build (-SkipBuild): $apworldBuilt ($((Get-Item -LiteralPath $apworldBuilt).LastWriteTime))"
    } else {
        Write-Info "Building wikipelago.apworld"
        & (Join-Path $Root "build_apworld.ps1") -Root $Root
        if (-not (Test-Path -LiteralPath $apworldBuilt)) { throw "build_apworld.ps1 did not produce $apworldBuilt" }
    }

    # Make the Archipelago under test load exactly this apworld.
    $probe = Join-Path $apRoot ".real_fuzz_write_test"
    try {
        [System.IO.File]::WriteAllText($probe, "")
        Remove-Item -LiteralPath $probe -Force
    } catch {
        throw "$apRoot is not writable. Archipelago then loads user worlds from your home folder instead of custom_worlds, which this script does not handle. Use a writable install or a source checkout."
    }
    $customWorlds = Join-Path $apRoot "custom_worlds"
    $looseWorld = [System.IO.Path]::Combine($apRoot, "worlds", "wikipelago")
    if (Test-Path -LiteralPath $looseWorld -PathType Container) {
        throw "$looseWorld exists. Archipelago loads loose world folders before apworlds, so it would shadow the build under test. Move it away first."
    }
    $frozenWorlds = [System.IO.Path]::Combine($apRoot, "lib", "worlds")
    if (Test-Path -LiteralPath $frozenWorlds) {
        $bundled = @(Get-ChildItem -LiteralPath $frozenWorlds -Filter "wikipelago*" -ErrorAction SilentlyContinue)
        if ($bundled.Count -gt 0) { throw "This Archipelago bundles a Wikipelago world in $frozenWorlds; it would shadow the build under test." }
    }
    $searchDirs = @($customWorlds)
    if ($ap.Kind -eq "source") { $searchDirs += (Join-Path $apRoot "worlds") }
    $existing = @()
    foreach ($dir in $searchDirs) {
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        $leftover = @(Get-ChildItem -LiteralPath $dir -File -Filter "*.real_fuzz_backup" -ErrorAction SilentlyContinue)
        if ($leftover.Count -gt 0) {
            throw "Found $($leftover[0].FullName) from an interrupted real_fuzz_test run. Rename it back to .apworld (or delete it if you do not need it), then re-run."
        }
        $existing += @(Get-ChildItem -LiteralPath $dir -File -Filter "*.apworld" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*wikipelago*" })
    }
    foreach ($file in $existing) {
        $backup = "$($file.FullName).real_fuzz_backup"
        Move-Item -LiteralPath $file.FullName -Destination $backup
        $moved.Add(@{ Original = $file.FullName; Backup = $backup })
        Write-Info "Moved your $($file.FullName) aside to $backup; it is restored when this run ends."
    }
    if (-not (Test-Path -LiteralPath $customWorlds)) { New-Item -ItemType Directory -Path $customWorlds | Out-Null }
    $installedTarget = Join-Path $customWorlds "wikipelago.apworld"
    Copy-Item -LiteralPath $apworldBuilt -Destination $installedTarget
    $wantHash = (Get-FileHash -LiteralPath $apworldBuilt -Algorithm SHA256).Hash
    $haveHash = (Get-FileHash -LiteralPath $installedTarget -Algorithm SHA256).Hash
    if ($wantHash -ne $haveHash) { throw "Copy check failed for $installedTarget" }
    Write-Info "Installed $apworldBuilt -> $installedTarget (sha256 $($wantHash.Substring(0, 12))); removed again when this run ends."

    $params = @{
        Root = $Root
        Runs = $Runs
        GenerateCommand = $generateCommand
        OutputDir = $OutputDir
        GenerateTimeoutSeconds = $GenerateTimeoutSeconds
    }
    if ($Seed -ge 0) { $params.Seed = $Seed }
    if ($KeepFiles) { $params.KeepFiles = $true }
    if ($python -and $python.Prefix.Count -eq 0) { $params.PythonCommand = $python.Exe }
    & (Join-Path $Root "fuzz_test.ps1") @params
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 1 }
    if ($exitCode -eq 0) {
        Write-Pass "real_fuzz_test: every Archipelago run matched the expected verdict."
    } else {
        Write-Fail "real_fuzz_test: at least one run failed (see the [FAIL] lines above and the logs in $(Join-Path $OutputDir 'logs'))."
    }
}
catch {
    Write-Fail $_.Exception.Message
    $exitCode = 1
}
finally {
    if ($installedTarget -and (Test-Path -LiteralPath $installedTarget)) {
        Remove-Item -LiteralPath $installedTarget -Force
        Write-Info "Removed the test copy $installedTarget"
    }
    for ($i = $moved.Count - 1; $i -ge 0; $i--) {
        $entry = $moved[$i]
        if (Test-Path -LiteralPath $entry.Backup) {
            Move-Item -LiteralPath $entry.Backup -Destination $entry.Original -Force
            Write-Info "Restored $($entry.Original)"
        }
    }
}

Pause-OnExit
exit $exitCode
