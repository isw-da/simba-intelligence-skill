# GUI-Only Installation Path

This guide is for users who are not comfortable with the command line. It
covers installing Simba Intelligence using graphical interfaces wherever
possible. A small number of terminal commands are still required (marked
clearly), but they are copy-paste only — no editing needed.

---

## What you need before starting

1. **A computer** running Windows 10/11 or macOS 12+
2. **An internet connection** to download software and container images
3. **An LLM provider account** (Google Cloud, Azure, AWS, or OpenAI) — you
   will configure this after SI is running

---

## Part 1: Install Docker Desktop (GUI)

Docker Desktop is the application that runs SI on your computer.

### Download

Go to https://www.docker.com/products/docker-desktop/ and download the
installer for your operating system.

### Install

- **Windows:** Double-click the installer, accept all defaults, restart
  your computer when prompted
- **macOS:** Open the downloaded file, drag Docker to Applications, open it,
  and grant permissions when asked

### Wait for Docker to start

Open Docker Desktop. In the bottom-left corner, wait until you see:
- **"Engine running"** in green

This may take 1-2 minutes on first launch.

---

## Part 2: Enable Kubernetes (GUI)

Kubernetes is what orchestrates the SI application. Docker Desktop includes
it — you just need to turn it on.

1. In Docker Desktop, click the **gear icon** (Settings) in the top-right
2. Click **"Kubernetes"** in the left sidebar
3. Check the box **"Enable Kubernetes"**
4. Click **"Apply & Restart"**
5. Wait — this takes several minutes the first time (it downloads components)
6. In the bottom-left, wait until you see **"Kubernetes running"** in green

---

## Part 3: Install Helm (one terminal command)

Helm is the tool that installs SI. This is the one thing that must be done
in a terminal, but it is a single copy-paste command.

### Windows

Open **PowerShell** (search for it in the Start menu), then paste:
```
winget install Helm.Helm
```

Close and reopen PowerShell after it finishes.

### macOS

Open **Terminal** (search for it in Spotlight), then paste:
```
brew install helm
```

If `brew` is not found, install Homebrew first by pasting this:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then retry `brew install helm`.

---

## Part 4: Run the installer script (one terminal command)

We provide a script that does everything else automatically — it installs
SI, waits for it to be ready, sets up the local access, and opens your
browser.

### Find your chart version

Go to https://hub.docker.com/r/insightsoftware/simba-intelligence-chart/tags
and note the latest version number (e.g. `25.4.0`). You will be asked for
this when the script runs.

### Windows

Download `install-si.ps1` and save it to your Downloads folder. Open
PowerShell and paste:
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd ~\Downloads
.\install-si.ps1
```

### macOS

Download `install-si.sh` and save it to your Downloads folder. Open
Terminal and paste:
```
chmod +x ~/Downloads/install-si.sh
~/Downloads/install-si.sh
```

The script will:
1. Check that Docker, Kubernetes, and Helm are ready
2. Ask for the chart version
3. Check that no other applications are using the required ports
4. Install Simba Intelligence
5. Wait for all components to start (5-10 minutes)
6. Set up the local access proxy
7. Open SI in your browser

---

## Part 5: Configure SI (all in the browser)

Once the browser opens to http://localhost:8080, everything from here is
done in the SI web interface.

### Step 1: Log in

Use the default admin credentials shown in the terminal output after
installation.

### Step 2: Configure your LLM provider

1. Click on your user menu or navigate to http://localhost:8080/llm-configuration
2. Select your provider tab:
   - **Google Vertex AI** — paste your service account JSON
   - **Azure OpenAI** — enter your API key, endpoint, and deployment names
   - **AWS Bedrock** — enter your access key, secret key, and region
   - **OpenAI** — enter your API key
3. Enable **Chat** and **Embeddings** (both are required)
4. Click **Test** to verify the connection
5. Click **Save**

### Step 3: Create a data connection

1. Navigate to **Data Connections**
2. Click **Create Connection**
3. Select your database type (Snowflake, PostgreSQL, SQL Server, BigQuery, etc.)
4. Enter your database credentials and connection details
5. Click **Test Connection** to verify
6. Click **Save**

### Step 4: Create a data source

1. Navigate to http://localhost:8080/data-source-agent
2. Select your connection from the dropdown
3. Describe what data you want to analyse in plain English, or upload a
   screenshot of the dashboard you want to build
4. The AI agent will create a data source for you
5. Review and approve

### Step 5: Start querying

1. Navigate to http://localhost:8080/playground
2. Select your data source
3. Ask questions in plain English

---

## Stopping SI

### Quickly (close everything)

Close all PowerShell / Terminal windows. SI will stop when the port-forwards
and Caddy stop.

### Properly

In PowerShell or Terminal, paste:
```
helm uninstall si -n simba-intel
kubectl delete namespace simba-intel
```

### Restart after computer restart

After restarting your computer:
1. Open Docker Desktop, wait for "Kubernetes running"
2. Re-run the installer script — it will detect SI is already installed
   and just set up the access proxy

---

## Troubleshooting

### "Docker is not running"

Open Docker Desktop and wait for "Engine running" in the bottom-left.

### "Kubernetes is not ready"

Open Docker Desktop → Settings → Kubernetes → check "Enable Kubernetes" →
Apply & Restart. Wait for "Kubernetes running" in green.

### Browser shows "can't reach this page"

The port-forward terminals may have closed. Re-run the installer script —
it will reconnect without reinstalling.

### "No LLM Configuration Found" in the SI interface

You need to set up an AI provider. Go to /llm-configuration and add your
credentials. See Step 2 in Part 5 above.

### Something else

Describe the problem to Claude with the Simba Intelligence skill installed.
It can diagnose and fix most issues interactively.
