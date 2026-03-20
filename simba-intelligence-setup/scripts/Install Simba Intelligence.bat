@echo off
REM =============================================================================
REM Simba Intelligence — Double-Click Installer for Windows
REM =============================================================================
REM Save as "Install Simba Intelligence.bat"
REM Double-click to run.
REM =============================================================================

title Simba Intelligence Installer
cls
echo =============================================
echo   Simba Intelligence Installer
echo   Windows — Local Development
echo =============================================
echo.

REM --- Check Docker ---
echo Checking prerequisites...
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] Docker is not running.
    echo     Start Docker Desktop and wait for "Engine running".
    echo.
    pause
    exit /b 1
)
echo [OK] Docker is running

REM --- Check Kubernetes ---
kubectl get nodes >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] Kubernetes is not running.
    echo     In Docker Desktop: Settings ^> Kubernetes ^> Enable Kubernetes
    echo.
    pause
    exit /b 1
)
echo [OK] Kubernetes is ready

REM --- Check Helm ---
helm version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] Helm is not installed.
    echo     Run: winget install Helm.Helm
    echo     Then close and reopen this window.
    echo.
    pause
    exit /b 1
)
echo [OK] Helm is installed

REM --- Chart version ---
echo.
echo Find versions at: https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags
echo.
set /p CHART_VERSION="Chart version to install (e.g. 25.4.0): "
if "%CHART_VERSION%"=="" (
    echo [X] Version is required.
    pause
    exit /b 1
)

REM --- Stop existing Caddy ---
echo.
echo Freeing ports...
for /f %%i in ('docker ps -q --filter ancestor^=caddy:2') do docker stop %%i >nul 2>&1
timeout /t 2 /nobreak >nul

REM --- Check existing install ---
helm list --namespace simba-intel 2>nul | findstr "si" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo.
    echo [!] SI is already installed.
    set /p REINSTALL="Uninstall and reinstall? (y/N): "
    if /i "%REINSTALL%"=="y" (
        echo Removing...
        helm uninstall si --namespace simba-intel >nul 2>&1
        kubectl delete namespace simba-intel --ignore-not-found=true >nul 2>&1
        timeout /t 10 /nobreak >nul
        echo [OK] Previous install removed
    )
)

REM --- Create values file ---
if not exist C:\temp mkdir C:\temp
(
echo ingress:
echo   enabled: false
) > C:\temp\simba-values.yaml

REM --- Create Caddyfile ---
(
echo :8080 {
echo   @discovery path /discovery/*
echo   reverse_proxy @discovery host.docker.internal:8081
echo.
echo   reverse_proxy host.docker.internal:8082
echo }
) > C:\temp\Caddyfile

REM --- Install ---
echo.
echo Installing Simba Intelligence %CHART_VERSION%...
echo (This takes 5-10 minutes on first install)
echo.

helm install si oci://docker.io/insightsoftware/simba-intelligence-chart --version %CHART_VERSION% -f C:\temp\simba-values.yaml --namespace simba-intel --create-namespace
if %ERRORLEVEL% neq 0 (
    echo [X] Helm install failed.
    pause
    exit /b 1
)
echo [OK] Helm install submitted

REM --- Wait for pods ---
echo.
echo Waiting for pods to become ready...
echo (Checking every 15 seconds)
echo.

:waitloop
set READY=0
set TOTAL=0
for /f %%i in ('kubectl -n simba-intel get pods --no-headers 2^>nul ^| find /c "Running"') do set READY=%%i
for /f %%i in ('kubectl -n simba-intel get pods --no-headers 2^>nul ^| find /c /v "Completed"') do set TOTAL=%%i
echo   Pods: %READY%/%TOTAL% running...
if %READY% geq 10 goto podsdone
timeout /t 15 /nobreak >nul
goto waitloop

:podsdone
echo [OK] All pods running

REM --- Start port-forwards ---
echo.
echo Setting up access...
start /b kubectl -n simba-intel port-forward svc/si-simba-intelligence-chart 8082:5050
start /b kubectl -n simba-intel port-forward svc/si-discovery-web 8081:9050
timeout /t 2 /nobreak >nul
start /b docker run --rm -p 8080:8080 -v C:\temp\Caddyfile:/etc/caddy/Caddyfile caddy:2
timeout /t 3 /nobreak >nul

REM --- Done ---
echo.
echo =============================================
echo   Simba Intelligence is ready!
echo =============================================
echo.
echo   Opening http://localhost:8080 ...
echo.
echo   Default login: admin / SimbaIntelligence123456!
echo.
echo   Next: Configure your LLM at /llm-configuration
echo.

start http://localhost:8080

echo Press any key to stop SI and close.
pause >nul

REM --- Cleanup ---
taskkill /f /im kubectl.exe >nul 2>&1
for /f %%i in ('docker ps -q --filter ancestor^=caddy:2') do docker stop %%i >nul 2>&1
echo Stopped.
