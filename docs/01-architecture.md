# System Architecture

## Overview

The Mill & Whistle BI Suite is structured as a layered system with clear separation between data ingestion, storage, processing, and output.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                    │
├──────────────┬──────────────┬─────────────┬─────────────┬──────────────────────┤
│  Distributors │    Toast     │   Indeed    │   Mercury   │  Gmail/Calendar      │
│  (Email/PDF)  │   (Export)   │   (Manual)  │   (Manual)  │    (API)             │
└──────┬───────┴──────┬───────┴──────┬──────┴──────┬──────┴──────────┬───────────┘
       │              │              │             │                 │
       ▼              ▼              ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            INGESTION LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Email listener (invoices, confirmations)                                      │
│  • PDF parser (LLM-assisted: Haiku)                                             │
│  • CSV/Excel importers (Toast exports, price lists)                             │
│  • Manual entry forms (new distributors, recipes)                               │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CORE DATABASE                                         │
│                         (PostgreSQL on GCP)                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         │
│  │ Distributors│   │ Ingredients │   │   Recipes   │   │   Orders    │         │
│  │             │   │             │   │             │   │             │         │
│  │ • contacts  │   │ • canonical │   │ • batches   │   │ • planned   │         │
│  │ • minimums  │   │   items     │   │ • yields    │   │ • submitted │         │
│  │ • schedules │   │ • variants  │   │ • portions  │   │ • received  │         │
│  │ • terms     │   │   (by dist) │   │ • costs     │   │ • invoiced  │         │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘         │
│                                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         │
│  │   Invoices  │   │    Sales    │   │  Inventory  │   │    Staff    │         │
│  │             │   │             │   │             │   │             │         │
│  │ • line items│   │ • by item   │   │ • on-hand   │   │ • schedule  │         │
│  │ • disputes  │   │ • by period │   │ • par levels│   │ • roles     │         │
│  │ • payments  │   │ • forecasts │   │ • waste log │   │ • applicants│         │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘         │
│                                                                                  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PROCESSING LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Price normalization engine (convert all units → grams/ml/each)               │
│  • Cost roll-up calculator (ingredient → recipe → menu item)                    │
│  • Order optimizer (delivery windows + minimums + par levels)                   │
│  • Anomaly detector (price spikes, invoice mismatches)                          │
│  • Forecast engine (sales velocity → ingredient demand)                         │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUT LAYER                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Daily digest email (alerts, action items, metrics)                           │
│  • Draft order emails (to distributor reps)                                     │
│  • Invoice payment queue (for Mercury)                                          │
│  • Dashboard (wall display + executive web view)                                │
│  • Recipe/menu cost reports                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Database** | PostgreSQL (Cloud SQL) | Reliable, excellent for relational data, good GCP integration |
| **Backend** | Python (FastAPI) | Founder familiarity, great for data processing, excellent LLM libraries |
| **PDF Parsing** | Claude Haiku API | Cost-effective, handles messy invoice formats well |
| **Email** | Gmail API or Mailgun | Gmail if using existing workspace, Mailgun for dedicated inbox |
| **Frontend** | React (simple) or HTMX | HTMX if minimal JS preferred; React if building toward larger app |
| **Hosting** | Cloud Run | Serverless, scales to zero, easy CI/CD |
| **File Storage** | Cloud Storage | For invoice PDFs, exports |
| **Notifications** | SendGrid or Gmail SMTP | Daily digest emails |
| **CI/CD** | GitHub Actions | Team preference |

## GCP Services Used

```
┌─────────────────────────────────────────────────────────────┐
│                     GCP PROJECT                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │   Cloud Run     │    │   Cloud SQL     │                │
│  │   (API Server)  │───▶│  (PostgreSQL)   │                │
│  └────────┬────────┘    └─────────────────┘                │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Cloud Storage   │    │ Cloud Scheduler │                │
│  │ (PDFs, exports) │    │ (Daily digest)  │                │
│  └─────────────────┘    └─────────────────┘                │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Secret Manager  │    │  Cloud Build    │                │
│  │ (API keys)      │    │  (CI/CD)        │                │
│  └─────────────────┘    └─────────────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## External API Integrations

### Phase 1 (MVP)
- **Anthropic API (Haiku)**: Invoice PDF parsing
- **Gmail API**: Email ingestion and sending
- **SendGrid** (optional): Transactional emails

### Phase 2 (Growth)
- **Toast API**: Sales data, menu sync
- **Mercury API** (if available): Payment automation

### Phase 3 (Ecommerce)
- **Shopify API**: Order sync, inventory
- **Klaviyo API**: Marketing automation

## Security Considerations

1. **API Keys**: Store in GCP Secret Manager, never in code
2. **Database**: Private IP only, accessed via Cloud Run
3. **Authentication**: Start simple (shared password), evolve to OAuth
4. **Invoice PDFs**: Store with restricted access, retain for 7 years
5. **PII**: Minimize storage of customer data (Toast handles this)

## Cost Estimates

| Service | Specification | Monthly Cost |
|---------|---------------|--------------|
| Cloud SQL | db-f1-micro, 10GB | $10-15 |
| Cloud Run | 256MB, scales to 0 | $5-10 |
| Cloud Storage | <1GB | <$1 |
| Claude Haiku | ~100 invoices/mo | $5-20 |
| SendGrid | Free tier | $0 |
| **Total** | | **~$25-50** |

## Scalability Notes

The current architecture is designed for a single-location operation. If expanding to multiple locations, consider:

1. Adding `location_id` to relevant tables
2. Multi-tenant isolation patterns
3. Increased Cloud SQL tier
4. Regional Cloud Run deployments
