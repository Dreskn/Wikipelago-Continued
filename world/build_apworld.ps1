param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$src = Join-Path $Root "APWorldSource"
$outDir = Join-Path $Root "APWorld"
$zipPath = Join-Path $src "Wikipelago.zip"
$apPath = Join-Path $outDir "Wikipelago.apworld"
$worldDir = Join-Path $src "Wikipelago"
$weightsPath = Join-Path $worldDir "letter_pair_weights.json"

if (!(Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

if (!(Test-Path $weightsPath)) {
    throw "Missing required $weightsPath — run world/build_letter_pair_weights.py before packaging."
}

# Keep packaging clean: never ship bytecode caches.
Get-ChildItem -Path $worldDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if (Test-Path $apPath) { Remove-Item $apPath -Force }

Compress-Archive -Path (Join-Path $src "archipelago.json"), $worldDir -DestinationPath $zipPath
Rename-Item -Path $zipPath -NewName "Wikipelago.apworld"
Move-Item -Path (Join-Path $src "Wikipelago.apworld") -Destination $apPath -Force

# Verify data files landed in the zip.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($apPath)
try {
    $names = @($zip.Entries | ForEach-Object { ($_.FullName -replace '\\', '/').TrimStart('/') })
    foreach ($need in @(
        "Wikipelago/__init__.py",
        "Wikipelago/letter_pairs.py",
        "Wikipelago/letter_pair_weights.json",
        "archipelago.json"
    )) {
        if ($names -notcontains $need) {
            throw "Built apworld is missing required entry: $need (found: $($names -join ', '))"
        }
    }
}
finally {
    $zip.Dispose()
}

Write-Host "Built: $apPath"
