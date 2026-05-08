# 🏆 CloudHeal: Master Deployment, Showcase & Presentation Playbook
> **Official Engineering Guide for Project Owners**
> 
> This document is the definitive source of truth for deploying, validating, and presenting the **CloudHeal AIOps Platform**. It is designed for reliability, professional impact, and seamless execution.

---

## 📑 Table of Contents
1.  [Project Overview & Architecture](#section-1--project-overview)
2.  [Complete AWS EC2 Deployment](#section-2--complete-aws-ec2-deployment)
3.  [Domain, HTTPS & Nginx Configuration](#section-3--domain--https--nginx)
4.  [Cloud Provider Credential Setup](#section-4--cloud-provider-credential-setup)
5.  [Deployment Validation Checklist](#section-5--deployment-validation-checklist)
6.  [Demo Scenario Execution Guide](#section-6--demo-scenario-execution-guide)
7.  [Screen Recording & Screenshot Strategy](#section-7--screen-recording--screenshots)
8.  [GitHub Portfolio Preparation](#section-8--github-portfolio-preparation)
9.  [Interview & MS Application Storytelling](#section-9--interview--ms-application-story)
10. [Post-Deployment Operations](#section-10--post-deployment-operations)

---

## SECTION 1 — PROJECT OVERVIEW

### What is CloudHeal?
CloudHeal is a **production-grade Autonomous AIOps Platform** designed for multi-cloud environments (AWS, GCP, Azure). It solves the complexity of managing fragmented infrastructure by providing a unified "Control Plane" that not only monitors but **autonomously heals** infrastructure issues using AI and event-driven patterns.

### Core Engineering Features
*   **Multi-Cloud Discovery Engine**: Deep-scans 30+ resource types across providers with full pagination support.
*   **Event-Driven Healing**: Uses Kafka to decouple detection from remediation, allowing for asynchronous, scalable healing actions.
*   **Real-time Observability**: WebSocket-based dashboard providing sub-second updates on system health and drift.
*   **Drift Detection & Risk Scoring**: Automatically detects unauthorized configuration changes and assigns a risk score based on blast radius.
*   **Aura AI (Gemini-Powered)**: A contextual assistant that explains root causes and suggests remediation steps.

### Architecture Summary
The platform follows a **microservices-inspired containerized architecture**:
1.  **Frontend (React/Vite)**: High-performance dashboard using Zustand for state and Framer Motion for micro-animations.
2.  **Backend (FastAPI/Python 3.12)**: Asynchronous API handling heavy cloud I/O and WebSocket fan-out.
3.  **Data Layer**: PostgreSQL (Persistent state), Redis (Pub/Sub & Caching), Kafka (Event stream).
4.  **Observability Stack**: Prometheus (Metrics), Grafana (Visualization), Loki (Logs), Jaeger (Tracing).

### Why This Architecture Matters
*   **Scalability**: Kafka allows the system to process thousands of telemetry events without blocking the API.
*   **Resilience**: Health-checked services in Docker ensure automatic recovery of the stack.
*   **Security**: Credentials are AES-encrypted at rest; communication is TLS-hardened.

---

## SECTION 2 — COMPLETE AWS EC2 DEPLOYMENT

### 1. Provisioning the Infrastructure
1.  **Login to AWS Console** and navigate to **EC2**.
2.  **Launch Instance**:
    *   **Name**: `CloudHeal-Production`
    *   **OS**: `Ubuntu 22.04 LTS` (64-bit x86)
    *   **Instance Type**: `t3.medium` (Minimum) | `t3.large` (Recommended for smoother Kafka/ML performance).
    *   **Key Pair**: Create a new `.pem` key or use an existing one.
3.  **Network Settings (Security Group)**:
    *   Add **Inbound Rules**:
        *   `Port 22` (SSH) — Restrict to My IP.
        *   `Port 80` (HTTP) — Anywhere.
        *   `Port 443` (HTTPS) — Anywhere.
        *   `Port 3001` (Grafana - Optional) — Restrict to My IP if you want direct access.
4.  **Storage**: 30GB gp3 SSD (Default 8GB is too small for Docker images + Kafka logs).

### 2. Initial Server Setup
Connect via SSH:
```bash
ssh -i "your-key.pem" ubuntu@your-ec2-ip
```

Update system and install dependencies:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl python3-pip
```

### 3. Install Docker & Compose
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker # Apply group changes without logout

# Install Docker Compose V2 (if not present)
sudo apt install -y docker-compose-v2
```

### 4. Deploying the Platform
```bash
# Clone the repository
git clone <your-repo-url>
cd cloud-healing-system

# Configure Environment
cp .env.example .env
nano .env # Fill in the mandatory values (see SECTION 4)

# Generate Secure Secrets
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Update .env with generated keys
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
sed -i "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENCRYPTION_KEY/" .env

# Start the stack
docker compose up -d --build
```

### 5. Verification
Check container status:
```bash
docker compose ps
```
**Expected Output**: All containers (`aiops_backend`, `aiops_frontend`, `aiops_db`, `aiops_kafka`, etc.) should be in `Up (healthy)` state.

---

## SECTION 3 — DOMAIN + HTTPS + NGINX

### 1. Domain Connection
1.  Go to your Domain Provider (Namecheap, GoDaddy, Route53).
2.  Add an **A Record**:
    *   `Host`: `@` (or `cloud`)
    *   `Value`: Your EC2 Public IP.
    *   `TTL`: 3600 (or Automatic).

### 2. Generate SSL Certificate
```bash
sudo apt install certbot -y
sudo certbot certonly --standalone -d your-domain.com
```
*   The certificates will be saved in `/etc/letsencrypt/live/your-domain.com/`.

### 3. Production Nginx Configuration
We must switch the frontend to use the production HTTPS configuration.
1.  **Edit `frontend/nginx.production.conf`**:
    *   Replace `YOUR_DOMAIN` with your actual domain (e.g., `cloudheal.app`).
2.  **Update `docker-compose.yml`**:
    *   Ensure the `frontend` service mounts the SSL certificates:
    ```yaml
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./frontend/nginx.production.conf:/etc/nginx/conf.d/default.conf:ro
    ```
3.  **Restart Services**:
    ```bash
    docker compose up -d frontend
    ```

### 4. Verification
Visit `https://your-domain.com`. You should see the padlock icon in the browser address bar.

---

## SECTION 4 — CLOUD PROVIDER CREDENTIAL SETUP

### 🛡️ AWS Setup (Least Privilege)
1.  **IAM User**: Create `cloudheal-service`.
2.  **Policy**: Attach an Inline Policy with `ReadOnlyAccess` + specific `ec2:Describe*` permissions.
3.  **Credentials**: Generate **Access Key** & **Secret Key**.
4.  **Dashboard**: In CloudHeal UI → Cloud Connect → AWS → Paste keys + default region (e.g., `us-east-1`).

### 🛡️ GCP Setup
1.  **IAM & Admin**: Create a Service Account.
2.  **Roles**: `Compute Viewer`, `Monitoring Viewer`.
3.  **Keys**: Add Key → Create New Key (JSON).
4.  **Dashboard**: In CloudHeal UI → Cloud Connect → GCP → Paste the entire JSON content.

### 🛡️ Azure Setup
1.  **App Registration**: Register `CloudHeal-App`.
2.  **Secret**: Create a Client Secret.
3.  **IAM**: Go to Subscription → Access Control (IAM) → Add Role Assignment → `Reader`.
4.  **Dashboard**: Provide `Tenant ID`, `Client ID`, `Client Secret`, and `Subscription ID`.

---

## SECTION 5 — DEPLOYMENT VALIDATION CHECKLIST

| Component | Step | Expected Behavior |
|-----------|------|-------------------|
| **API** | `curl https://domain.com/api/health` | `{"status":"healthy","database":"ok"}` |
| **Auth** | Register a new user | Receive OTP via email (or check logs if simulator enabled) |
| **Discovery** | Click "Sync Metrics" | Progress bar moves; table populates with real EC2/GCP instances |
| **WebSockets** | Watch "Live Stats" | CPU/Memory charts should wiggle every 60s without refresh |
| **Kafka** | `docker logs aiops_prediction_worker` | Logs show `Consumed message from telemetry` |
| **Drift** | Edit a tag on an AWS EC2 instance | Notification appears in "War Room" within 2 mins |

---

## SECTION 6 — DEMO SCENARIO EXECUTION GUIDE

### The "Perfect" 10-Minute Demo
1.  **The Intro (1 min)**: "This is CloudHeal. It's an autonomous AIOps platform that bridge the gap between monitoring and action."
2.  **Cloud Discovery (2 min)**: Show the Dashboard. Point to the multi-cloud distribution chart. Click "Sync" to show real-time resource fetching.
3.  **The Incident (3 min)**:
    *   Navigate to `/demo`.
    *   Trigger **Scenario: CPU Spike**.
    *   Switch to **War Room**.
    *   **What to say**: "Notice the live terminal. Our Kafka-driven telemetry just detected a spike. The risk engine is calculating the blast radius."
4.  **The Autonomous Healing (3 min)**:
    *   An **Approval Card** appears in the War Room.
    *   **Click "Approve"** for the "Auto-Scale" or "Restart" action.
    *   Show the "Event Timeline" showing the action being applied.
5.  **FinOps & Drift (1 min)**: Briefly show the Drift Detection report and the Cost Anomaly chart.

---

## SECTION 7 — SCREEN RECORDING & SCREENSHOTS

### Recording Specs (OBS Studio)
*   **Resolution**: 1920x1080 (1080p).
*   **Format**: `.mp4` (H.264).
*   **Audio**: Use a high-quality mic; avoid laptop internal mics.
*   **Sequence**: Landing Page → Dashboard → Cloud Connect → Demo Scenario → War Room → Aura AI Chat.

### Key Screenshots for Portfolio
1.  **The "Hero" Dashboard**: All stat cards filled, provider map visible.
2.  **The War Room**: Terminal logs streaming + 2-3 healing approval cards.
3.  **Drift Report**: Side-by-side JSON comparison of "Expected" vs "Actual" state.
4.  **Aura AI Chat**: A complex question like "Why is my RDS instance failing?" with the AI's detailed response.

---

## SECTION 8 — GITHUB PORTFOLIO PREPARATION

### README Excellence
Your README is your resume. Structure it as follows:
1.  **Header**: Project Name + Professional Logo + Deployment Badges.
2.  **The "Why"**: One paragraph on the problem solved.
3.  **High-Level Architecture**: Use the Mermaid diagram or a clean SVG.
4.  **Feature Showcase**: Use high-quality GIFs for the War Room and Dashboard.
5.  **Quick Start**: Clear Docker commands.
6.  **Engineering Deep Dive**: Explain how you handled Kafka concurrency or WebSocket scaling.

### Cleanup Tasks
*   **Delete `.env`**: Ensure no secrets are in Git history (use `git filter-repo` if necessary).
*   **Prune Branches**: Keep only `main` and a stable `dev` branch.
*   **Add License**: `MIT` or `Apache 2.0`.

---

## SECTION 9 — INTERVIEW & MS APPLICATION STORY

### 💡 The "Elevator Pitch"
"I built CloudHeal to solve the 'alert fatigue' problem in SRE. Instead of just showing dashboards, the system uses an event-driven architecture with Kafka and AI to suggest and apply autonomous healing actions across AWS and GCP."

### 💡 Technical Deep-Dive Questions
*   **"How did you handle WebSocket scaling?"**
    *   *Answer*: "I implemented a Redis Pub/Sub fan-out. The backend listens to a single Redis channel and broadcasts to all connected clients, keeping resource usage O(1) instead of O(N)."
*   **"Why Kafka instead of just a database queue?"**
    *   *Answer*: "Decoupling. Kafka allows us to replay telemetry events for ML training and ensures that if a healing worker fails, the event is not lost—it can be retried without affecting the API."

---

## SECTION 10 — POST-DEPLOYMENT OPERATIONS

### 🔄 Monitoring Health
*   **Check Logs**: `docker compose logs -f --tail 100`
*   **Disk Usage**: `docker system df` (Cleanup with `docker system prune -af` if needed).

### 🔐 Security Maintenance
*   **SSL Renewal**: Certbot handles this via a cronjob usually, but manually test with `certbot renew --dry-run`.
*   **Secrets Rotation**: Change `SECRET_KEY` in `.env` every 90 days.

### 🚀 Scaling Up
If CPU usage stays >80%:
1.  Increase EC2 instance to `t3.xlarge`.
2.  Scale workers: `docker compose up -d --scale healing_worker=3`.

---
**End of Playbook**
*Version 1.0.0 — Generated by Original Lead Engineer*
