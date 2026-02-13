# Implementation Phases

## Overview

This document outlines the phased approach to building the Mill & Whistle BI Suite. Each phase builds on the previous, with clear deliverables and success criteria.

**Total Timeline Estimate**: 10-12 weeks for core functionality (Phases 0-5)

---

## Phase 0: Foundation
**Timeline**: Week 1  
**Goal**: Establish technical infrastructure and core data structures

### Tasks

#### Infrastructure Setup
- [ ] Create GCP project (`mw-bi-suite`)
- [ ] Set up Cloud SQL PostgreSQL instance (db-f1-micro)
- [ ] Configure Cloud Storage bucket for files
- [ ] Set up Secret Manager for API keys
- [ ] Create GitHub repository
- [ ] Configure GitHub Actions for CI/CD
- [ ] Set up Cloud Run service (initially empty)

#### Database Foundation
- [ ] Create initial migration system (Alembic recommended)
- [ ] Create `distributors` table
- [ ] Create `ingredients` table (canonical)
- [ ] Create `dist_ingredients` table (variants)
- [ ] Create `price_history` table

#### Basic Admin Interface
- [ ] Set up FastAPI project structure
- [ ] Create distributor CRUD endpoints
- [ ] Build simple web form for adding/editing distributors
- [ ] Test deployment to Cloud Run

#### Data Migration
- [ ] Export distributor data from existing Google Sheet
- [ ] Write migration script
- [ ] Import all current distributors with contacts, minimums, schedules

### Deliverables
1. Running Cloud Run service with basic API
2. PostgreSQL database with distributor data migrated
3. Simple web interface to manage distributors
4. CI/CD pipeline deploying on push to main

### Success Criteria
- [ ] Can add/edit distributor via web form
- [ ] Data persists in Cloud SQL
- [ ] Deployment takes <5 minutes from push

---

## Phase 1: Invoice Intelligence
**Timeline**: Weeks 2-3  
**Goal**: Automated invoice capture and parsing

### Tasks

#### Email Ingestion (Week 2)
- [ ] Decide: Dedicated inbox vs. forwarding rule
- [ ] Set up Gmail API credentials (or Mailgun)
- [ ] Build email listener service
- [ ] Extract PDF attachments
- [ ] Store PDFs in Cloud Storage
- [ ] Create `invoices` table
- [ ] Log received invoices to database

#### PDF Parsing (Week 2-3)
- [ ] Set up Anthropic API credentials
- [ ] Design Haiku parsing prompt
- [ ] Build PDF text extraction (PyPDF2 or similar)
- [ ] Implement parsing pipeline
- [ ] Create `invoice_lines` table
- [ ] Store parsed data with confidence scores

#### Review Interface (Week 3)
- [ ] Build invoice review queue
- [ ] Show parsed data for human verification
- [ ] Allow corrections before approval
- [ ] Mark invoices as reviewed/approved

#### Payment Tracking (Week 3)
- [ ] Add payment fields to invoice model
- [ ] Build payment queue view
- [ ] Mark as paid functionality
- [ ] Export payment list (for Mercury)

#### Price Capture (Week 3)
- [ ] Auto-create price_history entries from approved invoices
- [ ] Link invoice lines to dist_ingredients where possible
- [ ] Flag unmatched items for review

### Deliverables
1. Invoices automatically captured from email
2. PDF parsing with >80% accuracy
3. Human review interface
4. Payment tracking dashboard
5. Price history building automatically

### Success Criteria
- [ ] Invoice arrives via email → appears in system within 5 minutes
- [ ] 80%+ of line items parsed correctly
- [ ] Review and approval takes <2 minutes per invoice
- [ ] Can see all unpaid invoices and totals

---

## Phase 2: Ingredient & Price Foundation
**Timeline**: Weeks 3-4 (overlaps with Phase 1)  
**Goal**: Normalized ingredient database with price comparison

### Tasks

#### Canonical Ingredients (Week 3)
- [ ] Build ingredient CRUD interface
- [ ] Define categories (dairy, produce, protein, dry goods, etc.)
- [ ] Add key ingredients used in current recipes
- [ ] Set base units (g, ml, each) for each

#### Unit Conversion Engine (Week 3)
- [ ] Implement weight conversions (lb, oz, kg → g)
- [ ] Implement volume conversions (gal, qt, cup → ml)
- [ ] Handle count units (dozen → each)
- [ ] Build pack size parser for common formats

#### Variant Mapping (Week 4)
- [ ] Build mapping interface
- [ ] LLM-assisted mapping suggestions
- [ ] Queue for unmapped invoice items
- [ ] Bulk mapping tools

#### Price Comparison (Week 4)
- [ ] Create `v_current_prices` view
- [ ] Create `v_ingredient_price_comparison` view
- [ ] Build price comparison matrix UI
- [ ] Price per base unit calculations

#### Price Alerts (Week 4)
- [ ] Implement price change detection
- [ ] Define alert thresholds (5%, 10%)
- [ ] Add to daily digest

#### Catalog Scraping Foundation (Week 4)
- [ ] Create `catalog_scrapes` and `scraped_items` tables
- [ ] Build base scraper class with anti-detection measures (rate limiting, session reuse)
- [ ] Implement manual CSV import fallback for when scraping fails
- [ ] Set up GCP Secret Manager for portal credentials

#### First Distributor Scraper (Week 4+)
- [ ] Use Claude + Puppeteer MCP to analyze Valley Foods/Mountain Produce portal
- [ ] Generate static Python scraper using Playwright
- [ ] Test scraper and commit to repo
- [ ] Implement LLM-assisted item mapping for scraped items
- [ ] Schedule weekly scrape job

### Deliverables
1. Canonical ingredient database populated
2. All current distributor items mapped
3. Price comparison across distributors
4. Automated price change alerts
5. Working Valley Foods/Mountain Produce catalog scraper
6. Manual CSV import as fallback

### Success Criteria
- [ ] Can see "butter costs $X.XX/g from Valley Foods, $Y.YY/g from Mountain Produce"
- [ ] New invoice items suggest mappings automatically
- [ ] Price changes >10% trigger alerts
- [ ] Valley Foods catalog scraped weekly with prices updated
- [ ] Can compare prices BEFORE ordering, not just after invoices

---

## Phase 3: Recipe Costing
**Timeline**: Weeks 5-6  
**Goal**: Recipe database with live cost calculations

### Tasks

#### Recipe Database (Week 5)
- [ ] Create `recipes` table
- [ ] Create `recipe_ingredients` table
- [ ] Create `menu_items` table
- [ ] Build recipe CRUD interface

#### Recipe Import (Week 5)
- [ ] Define standard input format
- [ ] Build Google Sheets parser
- [ ] Handle ingredient matching
- [ ] Queue unmatched ingredients for mapping

#### Cost Calculator (Week 5-6)
- [ ] Implement cost roll-up algorithm
- [ ] Support "cheapest" pricing strategy
- [ ] Apply yield/waste factors
- [ ] Calculate cost per portion

#### Menu Analysis (Week 6)
- [ ] Build margin analyzer report
- [ ] Calculate food cost percentages
- [ ] Flag items above target food cost
- [ ] Optimization recommendations

#### What-If Simulator (Week 6)
- [ ] Ingredient price change simulation
- [ ] Menu price change simulation
- [ ] Recipe modification simulation
- [ ] Impact analysis output

### Deliverables
1. All current recipes imported
2. Live cost calculations per recipe
3. Menu profitability report
4. Price/recipe change simulator

### Success Criteria
- [ ] "Breakfast sandwich costs $2.61 to make"
- [ ] "Food cost is 34.8% (above 30% target)"
- [ ] "If butter goes up 15%, sandwich cost increases $0.12"

---

## Phase 4: Order Planning
**Timeline**: Weeks 7-8  
**Goal**: Proactive ordering with optimization

### Tasks

#### Par Levels (Week 7)
- [ ] Add par_level to ingredients
- [ ] Build par level management UI
- [ ] Below-par alerting

#### Inventory Tracking (Week 7)
- [ ] Simple inventory count form
- [ ] Track on-hand quantities
- [ ] Auto-deduct from deliveries

#### Delivery Calendar (Week 7)
- [ ] Visual calendar of delivery days
- [ ] Order deadline highlighting
- [ ] Deadline notifications

#### Order Optimization (Week 8)
- [ ] Minimum order tracking
- [ ] Fill-item suggestions
- [ ] Multi-distributor optimization (basic)

#### Order Workflow (Week 8)
- [ ] Order draft generator
- [ ] Email formatting
- [ ] Order tracking (sent → received → invoiced)
- [ ] Receiving workflow with discrepancy flagging

#### Dispute Integration (Week 8)
- [ ] Connect receiving issues to disputes
- [ ] Dispute email drafts
- [ ] Track open disputes

### Deliverables
1. Par level monitoring with alerts
2. Delivery calendar with deadlines
3. Optimized order recommendations
4. Complete order lifecycle tracking
5. Integrated dispute workflow

### Success Criteria
- [ ] "Butter below par, order by Wednesday for Friday delivery"
- [ ] "Farm Direct order: $248, need $52 more for minimum"
- [ ] Order email drafts ready to send
- [ ] Receiving creates disputes when issues found

---

## Phase 5: Sales Integration
**Timeline**: Weeks 9-10  
**Goal**: Connect sales data for full analytics

### Tasks

#### Toast Import (Week 9)
- [ ] Toast item mapping interface
- [ ] CSV import parser
- [ ] Create `daily_sales` table
- [ ] Scheduled import job

#### Product Mix Analysis (Week 9)
- [ ] Daily/weekly sales reports
- [ ] Trend analysis
- [ ] Day-of-week patterns

#### Usage Variance (Week 10)
- [ ] Theoretical usage calculator
- [ ] Actual usage tracker
- [ ] Variance report
- [ ] Investigation recommendations

#### Dashboard (Week 10)
- [ ] Wall display mode
- [ ] Executive dashboard
- [ ] Real-time (ish) updates

### Deliverables
1. Toast sales data imported daily
2. Product mix and trend reports
3. Theoretical vs actual usage analysis
4. Operations dashboard

### Success Criteria
- [ ] "Sold 52 breakfast sandwiches yesterday"
- [ ] "Butter variance: +73% over theoretical"
- [ ] Dashboard shows today's sales in near real-time

---

## Phase 6: Automation & Polish
**Timeline**: Ongoing  
**Goal**: Reduce manual intervention, improve reliability

### Tasks

#### Confidence Improvements
- [ ] Tune parsing prompts based on error patterns
- [ ] Increase auto-approval thresholds
- [ ] Reduce manual review needs

#### Additional Distributor Scrapers
- [ ] Analyze and build Farm Direct scraper
- [ ] Analyze and build Green Market scraper
- [ ] Add scraper health monitoring and automatic alerts on failure
- [ ] Build scraper maintenance workflow (Claude + Puppeteer MCP for fixes)

#### Price Decision Support
- [ ] Build quality tier annotation interface
- [ ] Create pre-order price check workflow
- [ ] Side-by-side comparison with quality context
- [ ] "Best value" recommendations

#### Toast API (When Ready)
- [ ] Apply for Toast API access
- [ ] Implement real-time order sync
- [ ] Menu item sync

#### Forecasting (Advanced)
- [ ] Demand forecasting from sales patterns
- [ ] Auto-suggested par levels
- [ ] Predictive ordering

#### Mobile Optimization
- [ ] Ensure all UIs work on mobile
- [ ] Quick-action shortcuts
- [ ] Camera integration for photos

#### Ecommerce Prep
- [ ] Design Shopify integration points
- [ ] Klaviyo data sync planning
- [ ] Unified inventory model

### Deliverables
1. Higher automation rates
2. Toast API integration (if approved)
3. Mobile-friendly interfaces
4. Ready for Shopify/Klaviyo integration
5. Full distributor scraping coverage (Valley Foods, Farm Direct, Green Market)
6. Quality-aware price comparison for informed purchasing decisions

---

## Daily Digest Evolution

The daily digest email evolves as modules come online:

### Phase 1 (DMS)
```
📥 Invoices received
💰 Payments due
🎫 Open disputes
```

### Phase 2 (IPI)
```
📥 Invoices received
💰 Payments due
📈 Price changes (from invoices + catalog scrapes)
🔄 Catalog scrape status
🎫 Open disputes
```

### Phase 3 (RMC)
```
📥 Invoices received
💰 Payments due
📈 Price changes
📊 Menu cost updates
🎫 Open disputes
```

### Phase 4 (OPA)
```
📥 Invoices received
💰 Payments due
📈 Price changes
📦 Order deadlines
⚠️ Items below par
📊 Menu cost updates
🎫 Open disputes
```

### Phase 5 (SOA)
```
📈 Yesterday's sales
📥 Invoices received
💰 Payments due
📈 Price changes
📦 Order deadlines
⚠️ Items below par
📊 Food cost %
🔍 Usage variance
🎫 Open disputes
```

---

## Resource Requirements

### Time Investment (Estimated)
- Phase 0: 10-15 hours
- Phase 1: 25-35 hours
- Phase 2: 15-20 hours
- Phase 3: 20-25 hours
- Phase 4: 25-30 hours
- Phase 5: 20-25 hours
- **Total: 115-150 hours**

### Monthly Costs (At Full Build)
| Service | Cost |
|---------|------|
| Cloud SQL | $12 |
| Cloud Run | $8 |
| Cloud Storage | $1 |
| Claude API | $15 |
| Domain (amortized) | $1 |
| **Total** | **~$37/month** |

### Skills Required
- Python (FastAPI)
- PostgreSQL
- HTML/CSS (basic)
- LLM prompting
- GCP familiarity

---

## Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| Invoice parsing accuracy | Start with human review; tune prompts over time |
| Toast API access | Design for CSV import first; API is enhancement |
| Distributor format changes | Flexible parsing; alert on low-confidence parses |

### Operational Risks

| Risk | Mitigation |
|------|------------|
| Adoption by chef | Involve early; make daily digest the key touchpoint |
| Data entry burden | Automate as much as possible; make forms mobile-friendly |
| System downtime | Cloud Run is reliable; add health checks and alerts |

### Business Risks

| Risk | Mitigation |
|------|------------|
| Scope creep | Stick to phase plan; defer nice-to-haves |
| Time away from operations | Build incrementally; each phase provides value |
| Distributor changes | Flexible data model; easy onboarding process |
