# Infrastructure & Deployment Guide

How to set up and deploy your own instance of the Mill & Whistle BI Suite on Google Cloud Platform.

## GCP Services Used

| Service | Purpose | Why This Service |
|---------|---------|-----------------|
| **Cloud SQL** | PostgreSQL database | Managed Postgres with automatic backups, private networking, scales with Cloud Run |
| **Cloud Run** | API server hosting | Serverless, scales to zero when idle, auto-scales under load, ~$5-10/mo |
| **Cloud Storage** | Invoice PDFs, exports | Durable object storage, integrates with Cloud Run service account |
| **Secret Manager** | API keys, DB password, OAuth tokens | Secure credential storage, accessed at runtime via service account |
| **Artifact Registry** | Docker images | Private container registry, used by CI/CD pipeline |
| **Cloud Build** | CI/CD builds | Triggered by GitHub Actions, builds Docker images |

## Architecture Overview

```
GitHub Actions (CI/CD)
    |
    v
Artifact Registry (Docker images)
    |
    v
Cloud Run (API server) ----> Cloud SQL (PostgreSQL)
    |                              |
    v                              v
Cloud Storage (PDFs)      Secret Manager (credentials)
```

## Initial Setup

### 1. Create GCP Project

```bash
# Create project
gcloud projects create YOUR_GCP_PROJECT --name="Your Project Name"
gcloud config set project YOUR_GCP_PROJECT

# Enable billing (required for Cloud SQL, Cloud Run)
# Do this in the GCP Console: https://console.cloud.google.com/billing

# Enable required APIs
gcloud services enable \
  sqladmin.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  gmail.googleapis.com \
  sheets.googleapis.com
```

### 2. Set Up Cloud SQL

```bash
# Create PostgreSQL instance
gcloud sql instances create YOUR_DB_INSTANCE \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=YOUR_REGION \
  --storage-size=10GB \
  --storage-type=SSD

# Create database
gcloud sql databases create mw_bi_suite --instance=YOUR_DB_INSTANCE

# Create app user
gcloud sql users create mw_app \
  --instance=YOUR_DB_INSTANCE \
  --password=YOUR_DB_PASSWORD

# Store password in Secret Manager
echo -n "YOUR_DB_PASSWORD" | gcloud secrets create db-password \
  --data-file=- --project=YOUR_GCP_PROJECT
```

### 3. Set Up Cloud Storage

```bash
# Create bucket for invoice PDFs
gcloud storage buckets create gs://YOUR_BUCKET_NAME \
  --location=YOUR_REGION \
  --uniform-bucket-level-access
```

### 4. Set Up Artifact Registry

```bash
# Create Docker repository
gcloud artifacts repositories create YOUR_REPO_NAME \
  --repository-format=docker \
  --location=YOUR_REGION
```

### 5. Store Secrets

```bash
# Anthropic API key (for Claude Haiku invoice parsing)
echo -n "your_anthropic_key" | gcloud secrets create anthropic-api-key \
  --data-file=- --project=YOUR_GCP_PROJECT

# Gmail OAuth credentials (for email ingestion)
echo -n "your_client_id" | gcloud secrets create gmail-client-id \
  --data-file=- --project=YOUR_GCP_PROJECT

echo -n "your_client_secret" | gcloud secrets create gmail-client-secret \
  --data-file=- --project=YOUR_GCP_PROJECT

echo -n "your_refresh_token" | gcloud secrets create gmail-refresh-token \
  --data-file=- --project=YOUR_GCP_PROJECT
```

### 6. Create Service Accounts

```bash
# Cloud Run service account
gcloud iam service-accounts create mw-bi-suite \
  --display-name="MW BI Suite Cloud Run"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT \
  --member="serviceAccount:mw-bi-suite@YOUR_GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT \
  --member="serviceAccount:mw-bi-suite@YOUR_GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# CI/CD service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT \
  --member="serviceAccount:github-actions@YOUR_GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT \
  --member="serviceAccount:github-actions@YOUR_GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT \
  --member="serviceAccount:github-actions@YOUR_GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 7. Set Up Workload Identity Federation (for GitHub Actions)

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create github-pool \
  --location="global"

# Create provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"

# Allow GitHub repo to impersonate service account
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@YOUR_GCP_PROJECT.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_GITHUB_ORG/YOUR_REPO_NAME"
```

### 8. Configure GitHub Secrets

Add these secrets in your GitHub repository settings:

| Secret | Value |
|--------|-------|
| `WIF_PROVIDER` | `projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | `github-actions@YOUR_GCP_PROJECT.iam.gserviceaccount.com` |

### 9. Deploy Cloud Run Service

```bash
# Build and push image
gcloud builds submit --tag YOUR_REGION-docker.pkg.dev/YOUR_GCP_PROJECT/YOUR_REPO_NAME/mw-bi-suite

# Deploy
gcloud run deploy mw-bi-suite \
  --image=YOUR_REGION-docker.pkg.dev/YOUR_GCP_PROJECT/YOUR_REPO_NAME/mw-bi-suite \
  --region=YOUR_REGION \
  --service-account=mw-bi-suite@YOUR_GCP_PROJECT.iam.gserviceaccount.com \
  --add-cloudsql-instances=YOUR_GCP_PROJECT:YOUR_REGION:YOUR_DB_INSTANCE \
  --set-env-vars="INSTANCE_CONNECTION_NAME=YOUR_GCP_PROJECT:YOUR_REGION:YOUR_DB_INSTANCE" \
  --set-secrets="DB_PASSWORD=db-password:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=2
```

---

## Local Development

### Prerequisites

1. **Google Cloud SDK** (`gcloud`) - [Install guide](https://cloud.google.com/sdk/docs/install)
2. **Cloud SQL Proxy** - `brew install cloud-sql-proxy` (macOS) or [download](https://cloud.google.com/sql/docs/postgres/connect-instance-auth-proxy)
3. **Python 3.12+**
4. **Node.js 18+** (for frontend)

### Quick Start

```bash
# 1. Authenticate with GCP
gcloud auth login
gcloud auth application-default login

# 2. Start Cloud SQL Proxy (keep running in background)
cloud-sql-proxy YOUR_GCP_PROJECT:YOUR_REGION:YOUR_DB_INSTANCE --port=5434

# 3. Set environment variables
export DB_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=YOUR_GCP_PROJECT)
export DB_PORT=5434

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run migrations
python3 -m alembic upgrade head

# 6. Start backend
uvicorn app.main:app --reload
# API at http://localhost:8000, docs at http://localhost:8000/docs

# 7. Start frontend (separate terminal)
cd frontend && npm install && npm run dev
# Frontend at http://localhost:5173
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port (use `5434` for local dev with Cloud SQL Proxy) |
| `DB_NAME` | `mw_bi_suite` | Database name |
| `DB_USER` | `mw_app` | Database user |
| `DB_PASSWORD` | (required) | Database password |
| `INSTANCE_CONNECTION_NAME` | (Cloud Run only) | Cloud SQL connection name |
| `ANTHROPIC_API_KEY` | (optional) | Required for invoice/price parsing |

### Troubleshooting

**"Connection refused" on port 5434**

The Cloud SQL Proxy is not running. Start it:

```bash
cloud-sql-proxy YOUR_GCP_PROJECT:YOUR_REGION:YOUR_DB_INSTANCE --port=5434
```

Verify it's listening:

```bash
lsof -i :5434
```

**"no password supplied"**

The `DB_PASSWORD` environment variable is empty. Fetch it:

```bash
export DB_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=YOUR_GCP_PROJECT)
```

**Credential errors**

Re-authenticate with GCP:

```bash
gcloud auth login
gcloud auth application-default login
```

---

## Deployment Pipeline

```
Push to main --> GitHub Actions --> Authenticate via WIF
    --> Build Docker image --> Push to Artifact Registry
    --> Deploy to Cloud Run
```

The pipeline is defined in `.github/workflows/deploy.yml`. It uses Workload Identity Federation for keyless authentication (no service account keys stored in GitHub).

---

## Cost Estimates

| Service | Monthly Cost |
|---------|--------------|
| Cloud SQL (db-f1-micro) | ~$10-15 |
| Cloud Run (low traffic, scales to zero) | ~$5-10 |
| Artifact Registry | <$1 |
| Cloud Storage (<1GB) | <$1 |
| Secret Manager | <$1 |
| Claude Haiku API (~50 invoices) | <$1 |
| **Total** | **~$20-30** |

---

## Planned: Cloud Scheduler

| Job | Schedule | Purpose |
|-----|----------|---------|
| `invoice-check` | Every 15 min | Check for new invoice emails |
| `price-scrape` | Weekly | Run distributor price scrapers |
| `daily-digest` | 7am daily | Send daily summary email |
