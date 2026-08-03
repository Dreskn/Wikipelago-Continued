param(
    [string]$Root = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

# APContainer packaging scheme version for Archipelago 0.6.7 (worlds/Files.py container_version).
$ContainerVersion = 7

$src = Join-Path $Root "APWorldSource"
$outDir = Join-Path $Root "APWorld"
$apPath = Join-Path $outDir "Wikipelago.apworld"
$worldDir = Join-Path $src "Wikipelago"
$manifestPath = Join-Path $src "archipelago.json"
$supportedLangs = @("en", "fr", "de", "es", "it", "pt", "nl", "sv", "pl")
$weightsPaths = @(
    foreach ($lang in $supportedLangs) {
        Join-Path $worldDir "letter_pair_weights_$lang.json"
    }
)
$stagingDir = Join-Path $Root "_apworld_build"

if (!(Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

foreach ($weightsPath in $weightsPaths) {
    if (!(Test-Path $weightsPath)) {
        throw "Missing required $weightsPath — run: python world/build_letter_pair_weights.py --lang all"
    }
}

if (!(Test-Path $manifestPath)) {
    throw "Missing required $manifestPath"
}

# Keep packaging clean: never ship bytecode caches.
Get-ChildItem -Path $worldDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $stagingDir | Out-Null

# Source manifest stays free of packaging fields; inject them only into the built apworld.
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
    [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip,
        $packagedManifestPath,
        "archipelago.json",
        [System.IO.Compression.CompressionLevel]::Optimal
    )

    Get-ChildItem -Path $worldDir -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($worldDir.Length).TrimStart("\", "/")
        if ($rel -match '(^|[\\/])__pycache__([\\/]|$)') { return }
        $entryName = ("Wikipelago/" + ($rel -replace "\\", "/"))
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

# Verify required entries and packaging fields.
$zip = [System.IO.Compression.ZipFile]::OpenRead($apPath)
try {
    $names = @($zip.Entries | ForEach-Object { ($_.FullName -replace "\\", "/").TrimStart("/") })
    $required = @(
        "archipelago.json",
        "Wikipelago/__init__.py",
        "Wikipelago/article_pool.py",
        "Wikipelago/data/pool_en.json",
        "Wikipelago/letter_pairs.py"
    ) + @(
        foreach ($lang in $supportedLangs) {
            "Wikipelago/letter_pair_weights_$lang.json"
        }
    )
    foreach ($need in $required) {
        if ($names -notcontains $need) {
            throw "Built apworld is missing required entry: $need (found: $($names -join ', '))"
        }
    }

    $manifestEntry = $zip.GetEntry("archipelago.json")
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open())
    try {
        $packaged = $reader.ReadToEnd() | ConvertFrom-Json
    }
    finally {
        $reader.Close()
    }

    foreach ($key in @("game", "world_version", "version", "compatible_version")) {
        if (-not $packaged.PSObject.Properties[$key]) {
            throw "Packaged archipelago.json missing required field: $key"
        }
    }
    if ([int]$packaged.version -ne $ContainerVersion -or [int]$packaged.compatible_version -ne $ContainerVersion) {
        throw "Unexpected container version in packaged manifest: version=$($packaged.version) compatible_version=$($packaged.compatible_version)"
    }
    Write-Host "Packaged world_version=$($packaged.world_version) container=$($packaged.version)"
}
finally {
    $zip.Dispose()
}

Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Built: $apPath"
