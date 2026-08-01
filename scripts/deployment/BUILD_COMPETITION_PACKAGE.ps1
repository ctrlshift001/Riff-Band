[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist/ai4ms-competition",
    [string]$EnvironmentFile = "deployment/competition/.env.competition",
    [string]$ImageTag = "ai4ms-workbench:competition",
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$deploymentSource = Join-Path $repoRoot "deployment/competition"
$startScript = Join-Path $deploymentSource "START_AI4MS.ps1"
$designDocument = Join-Path $repoRoot "docs/competition/AI4MS_AGENT_APPLICATION_DESIGN.html"
$environmentPath = Join-Path $repoRoot $EnvironmentFile
$outputPath = Join-Path $repoRoot $OutputDirectory

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "Competition environment file not found: $environmentPath"
}

& $startScript -EnvironmentFile $environmentPath -ValidateOnly
if ($LASTEXITCODE -ne 0) {
    throw "Competition environment validation failed."
}

$requiredAssets = @(
    "docker-compose.yml",
    "START_AI4MS.ps1",
    "START_AI4MS.bat",
    "START_AI4MS.sh"
)
foreach ($asset in $requiredAssets) {
    $assetPath = Join-Path $deploymentSource $asset
    if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
        throw "Required deployment asset is missing: $assetPath"
    }
}
if (-not (Test-Path -LiteralPath $designDocument -PathType Leaf)) {
    throw "Competition design document is missing: $designDocument"
}

if ($ValidateOnly) {
    Write-Host "Competition package inputs are valid. No package was written."
    exit 0
}

$worktreeChanges = @(& git -C $repoRoot status --porcelain --untracked-files=normal)
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect the Git worktree before packaging."
}
if ($worktreeChanges.Count -gt 0) {
    throw "Git worktree is not clean. Commit the exact delivery source before packaging."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to build the competition package."
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is installed but the Docker daemon is unavailable."
}
if (Test-Path -LiteralPath $outputPath) {
    throw "Output already exists: $outputPath. Move or remove it explicitly before rebuilding."
}

Write-Host "Building $ImageTag..."
& docker build --tag $ImageTag $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Docker image build failed."
}

New-Item -ItemType Directory -Path $outputPath | Out-Null
$imageArchive = Join-Path $outputPath "ai4ms-workbench.tar"
& docker save --output $imageArchive $ImageTag
if ($LASTEXITCODE -ne 0) {
    throw "Docker image export failed."
}

foreach ($asset in $requiredAssets) {
    Copy-Item -LiteralPath (Join-Path $deploymentSource $asset) -Destination $outputPath
}
Copy-Item -LiteralPath $environmentPath -Destination (Join-Path $outputPath ".env.competition")
Copy-Item -LiteralPath (Join-Path $repoRoot "docs/DEPLOYMENT.md") `
    -Destination (Join-Path $outputPath "DEPLOYMENT.md")
Copy-Item -LiteralPath $designDocument `
    -Destination (Join-Path $outputPath "AI4MS_AGENT_APPLICATION_DESIGN.html")

$imageHash = (Get-FileHash -LiteralPath $imageArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$commit = (& git -C $repoRoot rev-parse --short HEAD).Trim()
"$imageHash  ai4ms-workbench.tar" |
    Set-Content -LiteralPath (Join-Path $outputPath "SHA256SUMS.txt") -Encoding utf8
@(
    "source_commit=$commit",
    "image=$ImageTag"
) | Set-Content -LiteralPath (Join-Path $outputPath "BUILD_INFO.txt") -Encoding utf8

$expectedPackageFiles = @(
    ".env.competition",
    "AI4MS_AGENT_APPLICATION_DESIGN.html",
    "ai4ms-workbench.tar",
    "BUILD_INFO.txt",
    "DEPLOYMENT.md",
    "docker-compose.yml",
    "SHA256SUMS.txt",
    "START_AI4MS.bat",
    "START_AI4MS.ps1",
    "START_AI4MS.sh"
) | Sort-Object
$actualPackageFiles = @(
    Get-ChildItem -LiteralPath $outputPath -File |
        ForEach-Object { $_.Name } |
        Sort-Object
)
$unexpectedFiles = @(
    Compare-Object $expectedPackageFiles $actualPackageFiles |
        ForEach-Object { $_.InputObject }
)
if ($unexpectedFiles.Count -gt 0) {
    throw "Competition package whitelist mismatch: $($unexpectedFiles -join ', ')"
}

$secretValues = @()
foreach ($line in Get-Content -LiteralPath $environmentPath) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
    }
    $separator = $trimmed.IndexOf("=")
    if ($separator -le 0) {
        continue
    }
    $name = $trimmed.Substring(0, $separator).Trim()
    $value = $trimmed.Substring($separator + 1).Trim().Trim('"').Trim("'")
    if ($name -match "(KEY|TOKEN)$" -and $value.Length -ge 8) {
        $secretValues += $value
    }
}
$readablePackageFiles = $expectedPackageFiles | Where-Object {
    $_ -ne ".env.competition" -and $_ -ne "ai4ms-workbench.tar"
}
foreach ($fileName in $readablePackageFiles) {
    $content = Get-Content -LiteralPath (Join-Path $outputPath $fileName) -Raw
    foreach ($secret in $secretValues) {
        if ($content.Contains($secret)) {
            throw "A competition secret leaked into public package file: $fileName"
        }
    }
}

Write-Host "Competition package created at $outputPath"
Write-Host "The package contains a readable competition-only API key. Deliver it privately and revoke it after judging."
