<div align="center">

<img src="https://img.shields.io/badge/Platform-Multi--Cloud_AIOps-0ea5e9?style=for-the-badge&logo=icloud&logoColor=white" />
<img src="https://img.shields.io/badge/Stack-FastAPI_+_React_+_PostgreSQL-a855f7?style=for-the-badge" />
<img src="https://img.shields.io/badge/Cloud-AWS_%7C_GCP_%7C_Azure-f59e0b?style=for-the-badge" />
<img src="https://img.shields.io/badge/Status-Deployment--Grade-10b981?style=for-the-badge" />

# ☁️ CloudHeal — Autonomous Multi-Cloud AIOps Platform

**Enterprise-grade autonomous infrastructure management platform with real-time drift detection, AI-powered healing, and multi-cloud observability.**

[🚀 Live Demo Flow](#demo-walkthrough) • [🏗️ Architecture](#architecture) • [⚡ Quick Start](#quick-start) • [🔐 Cloud Setup](#cloud-credentials)

</div>

---

## What This Is

CloudHeal is a **production-hardened AIOps platform** that monitors AWS, GCP, and Azure infrastructure in real time, detects configuration drift, predicts failures before they happen, and autonomously applies healing actions — all with human-in-the-loop approval.

This is not a demo toy. It runs on real cloud APIs, real WebSockets, real ML models, and a real async event pipeline.

---

## Feature Map

| Area | Capability |
|------|-----------|
| **Multi-Cloud Discovery** | AWS, GCP, Azure resource scanning with full pagination — EC2, RDS, Lambda, ECS, SQS, SNS, ELBv2, GCE, GCS, Cloud SQL, Cloud Run, Cloud Functions, Pub/Sub, Azure VMs, App Services, SQL |
| **Realtime Dashboard** | WebSocket-driven live metrics (CPU, memory, health score), provider distribution, resource inventory table |
| **Drift Detection** | Snapshot any resource as desired-state baseline; poll every 60s; alert on field-level drift with risk scoring |
| **AI Auto-Healing** | 5 action types (restart, scale-up, reroute, isolate, failover); pending-approval workflow; RCA attribution |
| **FinOps Intelligence** | IsolationForest ML cost anomaly detection; 30-day baseline; spending spike alerts |
| **Security Posture** | Security group exposure detection; finding severity scoring; compliance tagging |
| **Root Cause Analysis** | Graph-traversal RCA engine with AI-generated remediation suggestions |
| **War Room** | Live terminal log stream; AI decision feed; pending approvals; real-time metric sparklines |
| **Aura AI** | Gemini-powered chat assistant with full platform context |
| **Event Timeline** | Immutable chronological audit log with severity filtering and date grouping |
| **Propagation Simulator** | Cascade failure blast-radius analysis with interactive graph visualization |
| **Demo Scenarios** | 5 controlled, reversible scenarios for live portfolio walkthroughs |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React)                          │
│  Dashboard │ WarRoom │ Drift │ Healing │ FinOps │ Security       │
│  WebSocket client (Zustand store, visibility reconnect)         │
└───────────────────┬─────────────────────────────────────────────┘
                    │ HTTPS / WSS (nginx reverse proxy)
┌───────────────────▼─────────────────────────────────────────────┐
│                   FastAPI Backend (Python 3.12)                 │
│                                                                 │
│  REST API ─────────────── 16 routers                           │
│  WebSocket ─────────────── Redis pub/sub fan-out               │
│  Background Scheduler ──── asyncio task supervision            │
│  Monitoring Loop ──────── 60s cloud scan + metric broadcast    │
│  ML Engine ─────────────── IsolationForest (cost anomalies)    │
│  Anomaly Detection ─────── Security + FinOps heuristics        │
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
   PostgreSQL           Redis             Kafka
   (async SQLAlchemy)  (pub/sub, cache)  (event pipeline)
       │
┌──────▼──────────────────────────────────────────────────────────┐
│              Cloud Provider APIs                                │
│   AWS (boto3 + paginators) │ GCP (google-api-python-client)    │
│   Azure (azure-sdk-for-python + tenacity retry)                │
└─────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Single Redis pub/sub listener fan-out to all WebSocket clients (O(1) broadcast, not O(N))
- Full pagination on all AWS and GCP list APIs — no silent data truncation
- ML model persisted to Docker named volume (survives restarts, shared across replicas)
- `asynccontextmanager` lifespan handler (no deprecated `@app.on_event`)
- JWT TTL: 30 minutes (not 24h)
- All credentials AES-Fernet encrypted at rest

---

## Quick Start

### Prerequisites
- Docker Desktop 4.x+
- Python 3.12 (for local dev only)
- Node 18+ (for local frontend dev only)

### 1. Clone & configure

```bash
git clone <repo-url>
cd cloud-healing-system
cp .env.example .env   # Then fill in your values
```

### 2. Generate secrets

```bash
# SECRET_KEY (paste into .env)
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (paste into .env)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Start the platform

```bash
docker compose up -d --build
```

**Service startup order** (automatic via healthchecks):
1. PostgreSQL → Redis → Kafka/Zookeeper
2. Backend (waits for all three healthy)
3. Frontend (nginx, serves built React app)

### 4. Open the platform

```
http://localhost:3000
```

Register an account → verify OTP → connect a cloud provider → watch resources stream in.

---

## Cloud Credentials

### AWS
Required IAM permissions (read-only):
```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:DescribeInstances", "ec2:DescribeRegions",
    "rds:DescribeDBInstances",
    "lambda:ListFunctions",
    "ecs:ListClusters", "ecs:DescribeClusters",
    "sqs:ListQueues",
    "sns:ListTopics",
    "elasticloadbalancing:DescribeLoadBalancers",
    "cloudwatch:GetMetricStatistics"
  ],
  "Resource": "*"
}
```
Generate an IAM access key and paste `aws_access_key_id` + `aws_secret_access_key` + `region` into Cloud Connect.

### GCP
1. Create a Service Account in IAM
2. Grant: `Viewer` + `Monitoring Viewer`
3. Download JSON key
4. Paste the JSON content into Cloud Connect

### Azure
1. Register an app in Azure AD (App Registrations)
2. Add `Reader` role on your subscription
3. Create a client secret
4. Provide: `tenant_id`, `client_id`, `client_secret`, `subscription_id`

---

## Demo Walkthrough

The platform has a built-in **Demo Control Panel** (`/demo`) for live walkthroughs.

### Recommended Screen Recording Flow (12 minutes)

| Segment | Duration | What to show |
|---------|----------|--------------|
| **Dashboard** | 2 min | Resource inventory, stat cards, provider distribution |
| **Activity Burst** | 1 min | Fire Demo → "Live Dashboard Activity" — chart animates live |
| **CPU Spike** | 2 min | Fire Demo → "CPU Spike" — drift alert fires in WarRoom |
| **War Room** | 2 min | Show terminal logs, metric sparklines, approval queue |
| **AI Healing** | 2 min | Fire Demo → "AI Healing Suggestion" — approve in WarRoom |
| **Drift Detection** | 1 min | Show drift reports, expand a report, show remediation tab |
| **Reset** | 30s | Click "Reset Demo Data" — clean state |

### Best Pages to Screenshot
1. **Dashboard** — stat cards + live area chart (after Activity Burst)
2. **War Room** — terminal + approval cards + metric tiles
3. **Drift Detection** — expanded report with risk score
4. **Topology Graph** — service dependency visualization
5. **FinOps** — cost anomaly after firing Cost Spike scenario

---

## Production Deployment (Single EC2)

### 1. Launch EC2
- Instance type: `t3.medium` minimum (`t3.large` recommended)
- OS: Ubuntu 22.04 LTS
- Security group: ports 80, 443 inbound; 22 for SSH

### 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
```

### 3. Get TLS certificate

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
```

### 4. Deploy

```bash
git clone <repo-url> && cd cloud-healing-system
# Fill in production .env values
cp frontend/nginx.production.conf frontend/nginx.conf  # Enable HTTPS
sed -i 's/YOUR_DOMAIN/your-domain.com/g' frontend/nginx.conf
docker compose up -d --build
```

### 5. Verify

```bash
curl https://your-domain.com/health
# Expected: {"status":"healthy","database":"ok","redis":"ok","kafka":"ok"}
```

---

## Environment Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | JWT signing key — 64 hex chars minimum |
| `ENCRYPTION_KEY` | ✅ | Fernet key for credential encryption |
| `DATABASE_URL` | ✅ | PostgreSQL async URL |
| `REDIS_URL` | ✅ | Redis connection URL |
| `REDIS_PASSWORD` | ✅ | Redis password |
| `KAFKA_BOOTSTRAP_SERVERS` | ✅ | Kafka broker address |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key (for Aura AI) |
| `SMTP_SERVER` | ✅ | SMTP host for OTP emails |
| `SMTP_USER` / `SMTP_PASSWORD` | ✅ | SMTP credentials |
| `MODEL_CACHE_DIR` | Optional | ML model volume path (default: `/app/data/models`) |
| `OTLP_ENDPOINT` | Optional | Jaeger/OTLP endpoint for tracing |

---

## Troubleshooting

### Backend won't start
```bash
docker logs aiops_backend --tail 50
# Check for: ValidationError → missing .env variable
# Check for: NameError → dependency import issue
```

### WebSocket not connecting
```bash
# Verify nginx proxy config
docker logs aiops_frontend --tail 20
# Verify backend WS endpoint
curl http://localhost:8000/health
```

### Cloud scan returns 0 resources
- Check IAM permissions (see Cloud Credentials section)
- Run `docker logs aiops_backend | grep "scan"` 
- Trigger manual scan from Dashboard → Sync Metrics

### Database connection refused
```bash
docker logs aiops_postgres --tail 20
# If failing, wait 30s for PostgreSQL to initialize fully
docker compose restart aiops_backend
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.115, Python 3.12, SQLAlchemy 2.0 async |
| Frontend | React 18, Vite, Zustand, Framer Motion, Recharts, Tailwind |
| Database | PostgreSQL 15 (asyncpg) |
| Cache / PubSub | Redis 7 (aioredis) |
| Event Pipeline | Apache Kafka 3.6 |
| ML | scikit-learn IsolationForest |
| Cloud SDKs | boto3, google-api-python-client, azure-sdk-for-python |
| AI | Google Gemini Flash (Aura assistant) |
| Observability | OpenTelemetry, Jaeger (optional) |
| Infrastructure | Docker Compose, Nginx |

---

<div align="center">

Built as a portfolio-grade engineering showcase demonstrating production SRE practices, distributed systems design, and multi-cloud platform engineering.

</div>
