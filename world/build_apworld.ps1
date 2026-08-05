param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

# APContainer packaging scheme version for Archipelago 0.6.7 (worlds/Files.py).
$ContainerVersion = 7
$PackageName = "wikipelago"   # zip basename + inner folder (must match, lowercase)

$src = Join-Path $Root "APWorldSource"
$outDir = Join-Path $Root "APWorld"
$apPath = Join-Path $outDir "$PackageName.apworld"
$worldDir = Join-Path $src $PackageName
$manifestPath = Join-Path $worldDir "archipelago.json"
$weightsPath = Join-Path $worldDir "letter_pair_weights.json"
$stagingDir = Join-Path $Root "_apworld_build"

if (!(Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

if (!(Test-Path $worldDir)) {
    throw "Missing world folder: $worldDir"
}
if (!(Test-Path $manifestPath)) {
    throw "Missing required $manifestPath (should live inside $PackageName/)"
}
if (!(Test-Path $weightsPath)) {
    throw "Missing required $weightsPath — run world/build_letter_pair_weights.py before packaging."
}

# Never ship bytecode caches.
Get-ChildItem -Path $worldDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $stagingDir | Out-Null

# Source manifest stays free of packaging fields; inject only into the built copy.
$manifestObj = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
$manifestHash = [ordered]@{}
foreach ($prop in $manifestObj.PSObject.Properties) {
    $manifestHash[$prop.Name] = $prop.Value
}
$manifestHash["version"] = $ContainerVersion
$manifestHash["compatible_version"] = $ContainerVersion
$packagedManifestPath = Join-Path $stagingDir "archipelago.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText(
    $packagedManifestPath,
    ($manifestHash | ConvertTo-Json -Depth 8),
    $utf8NoBom
)

if (Test-Path $apPath) { Remove-Item $apPath -Force }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open(
    $apPath,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    # Manifest INSIDE the world folder (not zip root).
    [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip,
        $packagedManifestPath,
        "$PackageName/archipelago.json",
        [System.IO.Compression.CompressionLevel]::Optimal
    )

    Get-ChildItem -Path $worldDir -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($worldDir.Length).TrimStart("\", "/")
        if ($rel -match '(^|[\\/])__pycache__([\\/]|$)') { return }
        # Don't zip the source manifest twice; packaged copy already has version fields.
        if (($rel -replace "\\", "/") -eq "archipelago.json") { return }

        $entryName = ("$PackageName/" + ($rel -replace "\\", "/"))
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip,
            $_.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        )
    }
}
finally {
    $zip.Dispose()
}

# Verify.
$zip = [System.IO.Compression.ZipFile]::OpenRead($apPath)
try {
    $names = @($zip.Entries | ForEach-Object { ($_.FullName -replace "\\", "/").TrimStart("/") })
    foreach ($need in @(
        "$PackageName/archipelago.json",
        "$PackageName/__init__.py",
        "$PackageName/letter_pairs.py",
        "$PackageName/letter_pair_weights.json"
    )) {
        if ($names -notcontains $need) {
            throw "Built apworld is missing required entry: $need`nFound:`n$($names -join "`n")"
        }
    }
    if ($names -contains "archipelago.json") {
        throw "Manifest must not be at zip root; expected $PackageName/archipelago.json"
    }

    $manifestEntry = $zip.GetEntry("$PackageName/archipelago.json")
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open())
    try { $packaged = $reader.ReadToEnd() | ConvertFrom-Json }
    finally { $reader.Close() }

    foreach ($key in @("game", "world_version", "version", "compatible_version")) {
        if (-not $packaged.PSObject.Properties[$key]) {
            throw "Packaged archipelago.json missing required field: $key"
        }
    }
    if ([int]$packaged.version -ne $ContainerVersion -or [int]$packaged.compatible_version -ne $ContainerVersion) {
        throw "Unexpected container version: version=$($packaged.version) compatible_version=$($packaged.compatible_version)"
    }
    Write-Host "Packaged game=$($packaged.game) world_version=$($packaged.world_version) container=$($packaged.version)"
}
finally {
    $zip.Dispose()
}

Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Built: $apPath"