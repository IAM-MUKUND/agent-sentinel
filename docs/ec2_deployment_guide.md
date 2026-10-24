# Agent Sentinel — AWS EC2 Deployment Guide

> **Constraints**: Free Tier (t2.micro / t3.micro), $100 credit, no Git, 2+ days uptime.
> MongoDB stays on **Atlas** (free M0 tier) — you already have it. No local Mongo needed.

---

## Architecture Overview

```
Internet
   │
   ▼
EC2 Instance (t3.micro — Ubuntu 24.04 LTS)
   ├── Nginx (port 80/443)  ← reverse proxy
   │     ├── /          → serves built React static files
   │     └── /api/      → proxies to FastAPI (localhost:8000)
   ├── FastAPI (localhost:8000)  ← backend, managed by systemd
   └── Node.js (build-only, not running in prod)

MongoDB Atlas (M0 free tier)  ← stays remote, no change
Groq API                       ← stays remote, no change
```

**Why this layout**: The React app is compiled to static HTML/CSS/JS and served by Nginx directly. FastAPI runs as a persistent background service managed by `systemd` (survives reboots, auto-restarts on crash). No Docker required.

---

## Part 1 — Launch the EC2 Instance

### 1.1 Log in to AWS Console

1. Go to [https://console.aws.amazon.com](https://console.aws.amazon.com)
2. Navigate to **EC2** → **Instances** → **Launch Instances**

### 1.2 Configure the Instance

| Setting                 | Value                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------- |
| **Name**          | `agent-sentinel`                                                                                |
| **AMI**           | Ubuntu Server 24.04 LTS (Free tier eligible)                                                      |
| **Instance type** | `t3.micro` (Free tier: 750 hrs/month)                                                           |
| **Key pair**      | Create new → name it`agent-sentinel-key` → download `.pem` file → **save it safely** |
| **Storage**       | 20 GB gp3 (Free tier gives 30 GB)                                                                 |

### 1.3 Configure Security Group (Firewall)

Create a new security group named `agent-sentinel-sg` with these **Inbound Rules**:

| Type  | Protocol | Port | Source                  | Why                       |
| ----- | -------- | ---- | ----------------------- | ------------------------- |
| SSH   | TCP      | 22   | My IP (your current IP) | Admin access              |
| HTTP  | TCP      | 80   | 0.0.0.0/0               | Public web access         |
| HTTPS | TCP      | 443  | 0.0.0.0/0               | (Optional, for SSL later) |

> [!CAUTION]
> Do NOT open port 8000 to the public. FastAPI must only be reachable via Nginx internally.

### 1.4 Launch and Note the IP

Click **Launch Instance**. Once running, note:

- **Public IPv4 Address** (e.g., `54.123.45.67`) — used to SSH in and visit the site

---

## Part 2 — Connect to the Instance

### On your local machine (WSL/Linux terminal):

```bash
# 1. Fix the key file permissions (required by SSH)
chmod 400 ~/Downloads/agent-sentinel-key.pem

# 2. SSH into the instance
ssh -i ~/Downloads/agent-sentinel-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```

You should see a prompt like `ubuntu@ip-172-31-xx-xx:~$`. You are now inside the EC2 machine.

---

## Part 3 — Install System Dependencies (on EC2)

Run all of these inside the EC2 SSH session:

```bash
# Update package index
sudo apt update && sudo apt upgrade -y

# Install Python 3.11, pip, venv, Node.js 20, Nginx
sudo apt install -y python3.11 python3.11-venv python3-pip nginx curl

# Install Node.js 20 (LTS) via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify versions
python3.11 --version   # should print Python 3.11.x
node --version         # should print v20.x.x
npm --version          # should print 10.x.x
nginx -v               # should print nginx version
```

---

## Part 4 — Transfer the Codebase (No Git)

You will use `scp` (secure copy) to upload the project from your local machine to EC2. Run these **on your LOCAL machine** (in a new WSL terminal — keep the SSH session open in the other):

### 4.1 Create a deployment archive (exclude secrets and junk)

```bash
# On your LOCAL machine
cd /home/mukundvinayak/agent-sentinel

# Create a clean archive — excludes .venv, node_modules, .env, test_data, logs
tar --exclude='./.venv' \
    --exclude='./agentsentinel/node_modules' \
    --exclude='./agentsentinel/dist' \
    --exclude='./.git' \
    --exclude='./logs' \
    --exclude='./test_data' \
    --exclude='./backend/__pycache__' \
    --exclude='./backend/agents/__pycache__' \
    --exclude='./backend/middleware/__pycache__' \
    --exclude='./backend/middleware/waf/__pycache__' \
    -czf /tmp/agent-sentinel-deploy.tar.gz .

# Check the archive size (should be a few MB, not hundreds)
du -sh /tmp/agent-sentinel-deploy.tar.gz
```

### 4.2 Upload to EC2

```bash
# On your LOCAL machine
scp -i ~/Downloads/agent-sentinel-key.pem \
    /tmp/agent-sentinel-deploy.tar.gz \
    ubuntu@<YOUR_EC2_PUBLIC_IP>:/home/ubuntu/
```

### 4.3 Extract on EC2

```bash
# Back on EC2 SSH session
cd /home/ubuntu
tar -xzf agent-sentinel-deploy.tar.gz -C /home/ubuntu/agent-sentinel --strip-components=1
# If the target dir doesn't exist, create it first:
mkdir -p /home/ubuntu/agent-sentinel
tar -xzf agent-sentinel-deploy.tar.gz -C /home/ubuntu/agent-sentinel

ls /home/ubuntu/agent-sentinel   # should show: backend, agentsentinel, docs, etc.
```

---

## Part 5 — Configure Environment Variables on EC2

> [!IMPORTANT]
> Never upload your `.env` file via SCP — it risks exposure in transfer logs. Create it directly on the EC2 instance.

```bash
# On EC2
nano /home/ubuntu/agent-sentinel/backend/.env
```

Paste your **exact** local `.env` file contents into nano. Update `MONGO_URI` to ensure your Atlas cluster's IP allowlist includes the EC2 IP (see Part 5.1). Press `Ctrl+X`, then `Y`, then `Enter` to save.

### 5.1 Allow EC2 IP in MongoDB Atlas

1. In MongoDB Atlas → **Network Access** → **Add IP Address**
2. Add your EC2's **Public IPv4 address** (e.g., `54.123.45.67`)
3. Click **Confirm**

> [!NOTE]
> EC2 Free Tier IPs can change on reboot unless you use an Elastic IP. If you see DB connection errors after a reboot, update the Atlas allowlist with the new IP.

---

## Part 6 — Set Up the Python Backend

```bash
# On EC2
cd /home/ubuntu/agent-sentinel

# Create Python virtual environment using Python 3.11
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Install backend dependencies
cd backend
pip install --upgrade pip
pip install fastapi uvicorn pydantic python-dotenv pymongo pyyaml groq

# Also install the exact versions from requirements.txt if it's complete:
# pip install -r requirements.txt

# Quick smoke test — should print without error
python3 -c "from fastapi import FastAPI; print('FastAPI OK')"
python3 -c "from pymongo import MongoClient; print('PyMongo OK')"
python3 -c "from groq import Groq; print('Groq OK')"

# Deactivate venv for now
deactivate
```

---

## Part 7 — Build the React Frontend

```bash
# On EC2
cd /home/ubuntu/agent-sentinel/agentsentinel

# Install npm dependencies
npm install

# IMPORTANT: Update the API URL before building
# The frontend must point to the EC2 public IP, not localhost
# Search for localhost:8000 references in the source:
grep -r "localhost:8000" src/
```

You need to update any hardcoded `http://localhost:8000` references. The cleanest way:

```bash
# Replace all occurrences in the src directory
sed -i 's|http://localhost:8000|http://<YOUR_EC2_PUBLIC_IP>|g' src/components/SupportChat.jsx
sed -i 's|http://localhost:8000|http://<YOUR_EC2_PUBLIC_IP>|g' src/components/AdminDashboard.jsx
# Run the grep again to confirm nothing is left:
grep -r "localhost:8000" src/
```

> [!IMPORTANT]
> Replace `<YOUR_EC2_PUBLIC_IP>` with your actual EC2 IP (e.g., `54.123.45.67`). Do this for EVERY file that references localhost.

```bash
# Now build the production bundle
npm run build

# A 'dist' folder should appear with the static files
ls dist/
# Expected output: assets/  index.html
```

---

## Part 8 — Configure Nginx

Nginx will serve the frontend static files and proxy `/api/` to FastAPI.

```bash
# Create Nginx site configuration
sudo nano /etc/nginx/sites-available/agent-sentinel
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name <YOUR_EC2_PUBLIC_IP>;  # Replace with your actual EC2 IP

    # Serve React static files
    root /home/ubuntu/agent-sentinel/agentsentinel/dist;
    index index.html;

    # React Router — send all non-asset requests to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy all /api/* requests to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 120s;   # Important: LLM calls can take time
        proxy_connect_timeout 120s;
    }
}
```

```bash
# Enable the site (symlink to sites-enabled)
sudo ln -s /etc/nginx/sites-available/agent-sentinel /etc/nginx/sites-enabled/

# Remove the default site
sudo rm /etc/nginx/sites-enabled/default

# Test the config for syntax errors
sudo nginx -t
# Expected: nginx: configuration file /etc/nginx/nginx.conf syntax is ok

# Apply the configuration
sudo systemctl restart nginx
sudo systemctl enable nginx   # auto-start on reboot
```

---

## Part 9 — Run FastAPI as a systemd Service

This makes the backend survive reboots and auto-restart on crash.

```bash
sudo nano /etc/systemd/system/agent-sentinel.service
```

Paste this:

```ini
[Unit]
Description=Agent Sentinel FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/agent-sentinel/backend
Environment="PATH=/home/ubuntu/agent-sentinel/.venv/bin"
EnvironmentFile=/home/ubuntu/agent-sentinel/backend/.env
ExecStart=/home/ubuntu/agent-sentinel/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd to pick up the new service file
sudo systemctl daemon-reload

# Start the service
sudo systemctl start agent-sentinel

# Enable auto-start on reboot
sudo systemctl enable agent-sentinel

# Check it is running
sudo systemctl status agent-sentinel
```

You should see `Active: active (running)` in green.

---

## Part 10 — Verify the Deployment

### 10.1 Check FastAPI is responding

```bash
# On EC2
curl http://127.0.0.1:8000/api/status
# Expected: {"status":"ok","message":"Agent Sentinel Backend is running"}
```

### 10.2 Check Nginx is serving the frontend

From **your local browser**, navigate to:

```
http://<YOUR_EC2_PUBLIC_IP>
```

You should see the Agent Sentinel login page.

### 10.3 Check the full stack

From your browser:

```
http://<YOUR_EC2_PUBLIC_IP>/api/status
```

Expected: `{"status":"ok","message":"Agent Sentinel Backend is running"}`

If both work, the deployment is complete.

---

## Part 11 — Keep it Running (2+ Days)

### Prevent SSH timeout from killing processes

Your services are managed by `systemd`, so they run independently of your SSH session. You can safely close the terminal — the backend and Nginx will keep running.

### Monitor logs

```bash
# Live backend logs (like watching your terminal locally)
sudo journalctl -u agent-sentinel -f

# Backend errors only
sudo journalctl -u agent-sentinel -p err -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Check service status anytime

```bash
sudo systemctl status agent-sentinel
sudo systemctl status nginx
```

### Restart services if needed

```bash
sudo systemctl restart agent-sentinel
sudo systemctl restart nginx
```

---

## Part 12 — Cost Estimate (Free Tier + Credits)

| Resource                | Free Tier                                  | Monthly cost if exceeded |
| ----------------------- | ------------------------------------------ | ------------------------ |
| EC2 t3.micro            | 750 hrs/month (enough for 1 instance 24/7) | ~$8.50/month             |
| EBS Storage (20 GB gp3) | 30 GB/month free                           | <$1/month                |
| Data Transfer Out       | 15 GB/month free                           | $0.09/GB after           |
| MongoDB Atlas M0        | Free forever                               | $0                       |
| Groq API                | Free tier (limited)                        | Pay per token            |

**For 2 days**: ~$0.57 on EC2 compute (within free tier). Total cost is effectively **$0** for this duration if you are within your first 12 months of AWS.

> [!TIP]
> Set up an **AWS Budget Alert** at $10 so you get an email before any unexpected charges:
> AWS Console → Billing → Budgets → Create Budget → Monthly cost budget → $10 threshold.

---

## Part 13 — Updating the Application (No Git)

If you make code changes locally and need to redeploy without Git:

```bash
# 1. On LOCAL machine: re-create the archive
cd /home/mukundvinayak/agent-sentinel
tar --exclude='./.venv' --exclude='./agentsentinel/node_modules' \
    --exclude='./agentsentinel/dist' --exclude='./.git' \
    --exclude='./logs' --exclude='./backend/.env' \
    -czf /tmp/agent-sentinel-update.tar.gz .

# 2. Upload only changed files (faster option for small changes):
scp -i ~/Downloads/agent-sentinel-key.pem \
    backend/main.py \
    ubuntu@<YOUR_EC2_PUBLIC_IP>:/home/ubuntu/agent-sentinel/backend/

# 3. On EC2: restart the backend
sudo systemctl restart agent-sentinel

# 4. For frontend changes: rebuild and Nginx picks it up automatically
cd /home/ubuntu/agent-sentinel/agentsentinel && npm run build
# (No Nginx restart needed — static files are served directly)
```

---

## Troubleshooting

| Problem                       | Check                                    | Fix                                                                       |
| ----------------------------- | ---------------------------------------- | ------------------------------------------------------------------------- |
| Site not loading              | `sudo systemctl status nginx`          | `sudo systemctl restart nginx`                                          |
| API returning 502 Bad Gateway | `sudo systemctl status agent-sentinel` | `sudo journalctl -u agent-sentinel -n 50`                               |
| MongoDB connection error      | Atlas IP allowlist                       | Add EC2 IP in Atlas → Network Access                                     |
| `ModuleNotFoundError`       | Wrong Python used                        | Verify`EnvironmentFile` and `ExecStart` path in service file          |
| LLM calls timing out          | Nginx proxy timeout                      | Already set to 120s in the config above                                   |
| EC2 IP changed after reboot   | -                                        | Add Elastic IP in AWS Console (free while attached to a running instance) |
