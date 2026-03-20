# =============================================================================
# Simba Intelligence Installer — Windows PowerShell
# =============================================================================
# This script automates the full local deployment of Simba Intelligence.
# It checks prerequisites, creates config files, installs SI, waits for
# pods, sets up port-forwards + Caddy, and opens the browser.
#
# Usage:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install-si.ps1
#
# Options (environment variables):
#   $env:CHART_VERSION  — override chart version
#   $env:NAMESPACE      — override namespace (default: simba-intel)
#   $env:RELEASE_NAME   — override Helm release name (default: si)
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Configuration ---
$Namespace   = if ($env:NAMESPACE)    { $env:NAMESPACE }    else { "simba-intel" }
$ReleaseName = if ($env:RELEASE_NAME) { $env:RELEASE_NAME } else { "si" }
$ChartRepo   = "oci://docker.io/insightsoftware/simba-intelligence-chart"
$ValuesFile  = "C:\temp\simba-values.yaml"
$CaddyFile   = "C:\temp\Caddyfile"

function Write-Info  { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[!!] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[XX] $msg" -ForegroundColor Red; exit 1 }

# --- Step 1: Check prerequisites ---
Write-Host ""
Write-Host "============================================="
Write-Host "  Simba Intelligence Installer"
Write-Host "============================================="
Write-Host ""
Write-Host "Checking prerequisites..."

# Docker
try { $null = Get-Command docker -ErrorAction Stop } catch {
    Write-Err "Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
}
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker is not running. Start Docker Desktop and wait for the engine to be ready."
}
Write-Info "Docker is running"

# kubectl
try { $null = Get-Command kubectl -ErrorAction Stop } catch {
    Write-Err "kubectl is not installed. It should come with Docker Desktop."
}
$nodes = kubectl get nodes 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "No Kubernetes cluster available. Enable Kubernetes in Docker Desktop Settings."
}
$context = kubectl config current-context
Write-Info "Kubernetes cluster is ready (context: $context)"

# Helm
try { $null = Get-Command helm -ErrorAction Stop } catch {
    Write-Err "Helm is not installed. Install with: winget install Helm.Helm"
}
Write-Info "Helm is installed"

# --- Step 2: Get chart version ---
$ChartVersion = $env:CHART_VERSION
if (-not $ChartVersion) {
    Write-Host ""
    $ChartVersion = Read-Host "Enter the chart version to install (e.g. 25.4.0)"
}
if (-not $ChartVersion) {
    Write-Err "Chart version is required. Find versions at https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags"
}
Write-Info "Using chart version: $ChartVersion"

# --- Step 3: Check for port collisions ---
Write-Host ""
Write-Host "Checking for port collisions..."
$blocked = $false
foreach ($port in @(8080, 8081, 8082)) {
    $listeners = netstat -ano | findstr ":$port" | findstr "LISTENING"
    if ($listeners) {
        Write-Warn "Port $port is in use:"
        Write-Host $listeners
        $blocked = $true
    }
}
if ($blocked) {
    Write-Host ""
    $proceed = Read-Host "Ports are in use. Stop the processes above, then press Enter (or Ctrl+C to abort)"
}
Write-Info "Ports 8080, 8081, 8082 are available"

# --- Step 4: Create config files ---
Write-Host ""
Write-Host "Creating configuration files..."
New-Item -ItemType Directory -Force -Path C:\temp | Out-Null

@"
ingress:
  enabled: false
"@ | Out-File -Encoding utf8 $ValuesFile
Write-Info "Values file: $ValuesFile"

@"
:8080 {
  @discovery path /discovery/*
  reverse_proxy @discovery host.docker.internal:8081

  reverse_proxy host.docker.internal:8082
}
"@ | Out-File -Encoding utf8 $CaddyFile
Write-Info "Caddyfile: $CaddyFile"

# --- Step 5: Check for existing installation ---
$existing = helm list --namespace $Namespace 2>$null | Select-String $ReleaseName
if ($existing) {
    Write-Warn "Existing installation found in namespace $Namespace"
    $reinstall = Read-Host "Uninstall existing release and reinstall? (y/N)"
    if ($reinstall -eq "y" -or $reinstall -eq "Y") {
        Write-Host "Uninstalling existing release..."
        helm uninstall $ReleaseName --namespace $Namespace
        kubectl delete namespace $Namespace --ignore-not-found=true
        Start-Sleep -Seconds 10
        Write-Info "Previous installation removed"
    } else {
        Write-Err "Aborted. Remove the existing installation first."
    }
}

# --- Step 6: Install ---
Write-Host ""
Write-Host "Installing Simba Intelligence $ChartVersion..."
Write-Host "This may take a few minutes on first install (downloading images)."
Write-Host ""

helm install $ReleaseName $ChartRepo `
    --version $ChartVersion `
    -f $ValuesFile `
    --namespace $Namespace `
    --create-namespace

if ($LASTEXITCODE -ne 0) { Write-Err "Helm install failed." }
Write-Info "Helm install submitted"

# --- Step 7: Wait for pods ---
Write-Host ""
Write-Host "Waiting for pods to become ready (timeout: 10 minutes)..."
Write-Host "This can take 5-10 minutes on first install."

$timeout = 600
$elapsed = 0
while ($elapsed -lt $timeout) {
    $allPods = kubectl -n $Namespace get pods --no-headers 2>$null
    $running = ($allPods | Select-String "Running" | Measure-Object).Count
    $completed = ($allPods | Select-String "Completed" | Measure-Object).Count
    $total = ($allPods | Measure-Object).Count
    $active = $total - $completed
    $notReady = $active - $running

    Write-Host -NoNewline "`r  Pods: $running/$active running, $notReady pending... (${elapsed}s elapsed)   "

    if ($notReady -eq 0 -and $running -gt 0) {
        Write-Host ""
        Write-Info "All pods are running"
        break
    }

    Start-Sleep -Seconds 15
    $elapsed += 15
}

if ($elapsed -ge $timeout) {
    Write-Warn "Timeout. Some pods may still be starting. Check: kubectl -n $Namespace get pods"
}

# --- Step 8: Start port-forwards ---
Write-Host ""
Write-Host "Starting port-forwards and reverse proxy..."

# Stop any existing Caddy
docker ps -q --filter ancestor=caddy:2 2>$null | ForEach-Object { docker stop $_ 2>$null } | Out-Null

Start-Sleep -Seconds 2

# Start port-forwards as background jobs
$pf1 = Start-Job -ScriptBlock {
    kubectl -n $using:Namespace port-forward "svc/$using:ReleaseName-simba-intelligence-chart" 8082:5050
}
Start-Sleep -Seconds 1

$pf2 = Start-Job -ScriptBlock {
    kubectl -n $using:Namespace port-forward "svc/$using:ReleaseName-discovery-web" 8081:9050
}
Start-Sleep -Seconds 1

# Start Caddy
docker run --rm -d -p 8080:8080 -v "${CaddyFile}:/etc/caddy/Caddyfile" caddy:2 | Out-Null
Start-Sleep -Seconds 3

# Verify
try {
    $mainCheck = curl.exe -s http://localhost:8080/ 2>$null
    if ($mainCheck -match "html") { Write-Info "Main app is accessible" }
    else { Write-Warn "Main app not responding yet" }
} catch { Write-Warn "Main app not responding yet" }

try {
    $discCheck = curl.exe -s http://localhost:8080/discovery/api/user 2>$null
    if ($discCheck -match "401|Unauthorized") { Write-Info "Discovery is accessible" }
    else { Write-Warn "Discovery not responding yet" }
} catch { Write-Warn "Discovery not responding yet" }

# --- Done ---
Write-Host ""
Write-Host "============================================="
Write-Host "  Simba Intelligence is ready!"
Write-Host "============================================="
Write-Host ""
Write-Host "  URL:  http://localhost:8080"
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Log in with the default admin credentials"
Write-Host "    2. Configure your LLM provider at /llm-configuration"
Write-Host "    3. Create a data connection"
Write-Host "    4. Create a data source with the Data Source Agent"
Write-Host "    5. Query your data in the Playground"
Write-Host ""
Write-Host "  To stop:"
Write-Host "    Stop-Job $($pf1.Id), $($pf2.Id); Remove-Job $($pf1.Id), $($pf2.Id)"
Write-Host "    docker stop (docker ps -q --filter ancestor=caddy:2)"
Write-Host ""
Write-Host "  To uninstall:"
Write-Host "    helm uninstall $ReleaseName -n $Namespace"
Write-Host "    kubectl delete namespace $Namespace"
Write-Host ""

# Open browser
Start-Process "http://localhost:8080"
