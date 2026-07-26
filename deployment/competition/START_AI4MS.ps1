[CmdletBinding()]
param(
    [string]$EnvironmentFile = "",
    [switch]$ValidateOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$deploymentRoot = $PSScriptRoot
$environmentFile = if ([string]::IsNullOrWhiteSpace($EnvironmentFile)) {
    Join-Path $deploymentRoot ".env.competition"
}
elseif ([IO.Path]::IsPathRooted($EnvironmentFile)) {
    $EnvironmentFile
}
else {
    Join-Path $deploymentRoot $EnvironmentFile
}
$composeFile = Join-Path $deploymentRoot "docker-compose.yml"
$imageArchive = Join-Path $deploymentRoot "ai4ms-workbench.tar"
$checksumFile = Join-Path $deploymentRoot "SHA256SUMS.txt"
$imageTag = "ai4ms-workbench:competition"
$workbenchUrl = "http://127.0.0.1:8000"

function Get-DotEnvValues {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
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
        $values[$name] = $value
    }
    return $values
}

function Test-UsableSecret {
    param([AllowEmptyString()][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }
    return $Value -notmatch "^(your_|replace-|changeme|sk-xxx)"
}

if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
    throw "Missing .env.competition beside START_AI4MS.ps1."
}
if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
    throw "Missing docker-compose.yml beside START_AI4MS.ps1."
}

$configuration = Get-DotEnvValues -Path $environmentFile
$keyNames = @(
    "AUTOENV_OPENAI_API_KEY",
    "AUTOENV_DEEPSEEK_V4_PRO_API_KEY",
    "AUTOENV_DEEPSEEK_V4_FLASH_API_KEY"
)
$hasUsableKey = $false
foreach ($keyName in $keyNames) {
    if ($configuration.ContainsKey($keyName) -and (Test-UsableSecret $configuration[$keyName])) {
        $hasUsableKey = $true
        break
    }
}
if (-not $hasUsableKey) {
    throw "No usable competition LLM API key is configured."
}

Write-Host "AI4MS competition configuration is valid. Secrets were not printed."
if ($ValidateOnly) {
    exit 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop or Docker Engine is not installed."
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is installed but the Docker daemon is unavailable."
}

& docker image inspect $imageTag *> $null
$imagePresent = $LASTEXITCODE -eq 0
if (-not $imagePresent -and (Test-Path -LiteralPath $imageArchive -PathType Leaf)) {
    if (Test-Path -LiteralPath $checksumFile -PathType Leaf) {
        $checksumLine = Get-Content -LiteralPath $checksumFile | Select-Object -First 1
        $expectedHash = ($checksumLine -split "\s+", 2)[0].Trim().ToLowerInvariant()
        $actualHash = (Get-FileHash -LiteralPath $imageArchive -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expectedHash -notmatch "^[0-9a-f]{64}$" -or $actualHash -ne $expectedHash) {
            throw "The SHA-256 checksum for ai4ms-workbench.tar is invalid."
        }
        Write-Host "Competition image checksum is valid."
    }
    Write-Host "Loading the AI4MS competition image..."
    & docker load --input $imageArchive
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to load ai4ms-workbench.tar."
    }
}
elseif (-not $imagePresent) {
    throw "Neither ai4ms-workbench.tar nor the $imageTag image is available."
}

Write-Host "Starting AI4MS..."
& docker compose --env-file $environmentFile -f $composeFile up --detach --no-build
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start AI4MS."
}

$healthDeadline = [DateTime]::UtcNow.AddSeconds(120)
$healthy = $false
while ([DateTime]::UtcNow -lt $healthDeadline) {
    try {
        $health = Invoke-RestMethod -Uri "$workbenchUrl/healthz" -TimeoutSec 5
        if ($health.status -eq "ok") {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $healthy) {
    throw "AI4MS did not become healthy within 120 seconds. Run docker compose logs for details."
}

Write-Host "Checking live LLM connectivity..."
$probe = Invoke-RestMethod `
    -Method Post `
    -Uri "$workbenchUrl/api/v1/meta/inference/probe" `
    -ContentType "application/json" `
    -Body "{}" `
    -TimeoutSec 210
if ($probe.status -ne "ok") {
    throw "The AI4MS service started, but the live LLM probe failed."
}

Write-Host "AI4MS is ready. Model: $($probe.model)"
Write-Host "Open $workbenchUrl"
if (-not $NoBrowser) {
    Start-Process $workbenchUrl
}
