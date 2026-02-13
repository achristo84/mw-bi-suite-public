# Module 1: Distributor Management System (DMS)

**Priority**: HIGH — Build First  
**Dependencies**: None  
**Estimated Timeline**: Weeks 1-3

## Overview

The Distributor Management System is the foundation of the entire suite. It handles:
- Centralized distributor registry with contacts, terms, and schedules
- Invoice ingestion via email with LLM-powered PDF parsing
- Invoice-to-order reconciliation with discrepancy detection
- Dispute tracking and resolution workflow
- Payment queue generation for Mercury

## Components

### 1.1 Distributor Registry

**Purpose**: Single source of truth for all distributor information.

**Features**:
- Store contact info (rep name, email, phone)
- Portal credentials (encrypted)
- Order minimums and delivery schedules
- Order deadlines ("Wednesday 10am for Friday delivery")
- Payment terms
- Vendor categorization

**Interface**: Simple web form for adding/editing distributors

**Data Migration**: Import from existing Google Sheet (see `05-distributors.md`)

**Schema**: See `distributors` table in `02-data-model.md`

---

### 1.2 Invoice Ingestion

**Purpose**: Automatically capture invoices from email and parse them into structured data.

#### Email Listener Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Distributor    │     │   Gmail API     │     │   Ingestion     │
│  sends invoice  │────▶│   or Forwarding │────▶│   Service       │
│  via email      │     │   Rule          │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Cloud Storage  │
                                               │  (PDF archive)  │
                                               └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Claude Haiku   │
                                               │  PDF Parser     │
                                               └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Review Queue   │
                                               │  (Human check)  │
                                               └────────┬────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │   Database      │
                                               │   (invoices,    │
                                               │   invoice_lines)│
                                               └─────────────────┘
```

#### Email Setup Options

**Option A: Dedicated Inbox** (Recommended)
- Create `invoices@yourdomain.com`
- Use Gmail API to poll for new messages
- Pros: Clean separation, easy filtering
- Cons: Need to update distributor contacts

**Option B: Forwarding Rule**
- Filter existing inbox for invoices
- Auto-forward to processing endpoint
- Pros: No distributor contact updates needed
- Cons: Requires careful filtering rules

#### PDF Parsing with Claude Haiku

**Prompt Template**:
```
You are parsing a distributor invoice PDF. Extract the following information in JSON format:

{
  "distributor_name": "string",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD or null",
  "subtotal_cents": integer,
  "tax_cents": integer,
  "total_cents": integer,
  "line_items": [
    {
      "sku": "string or null",
      "description": "string",
      "quantity": number,
      "unit_price_cents": integer,
      "extended_price_cents": integer
    }
  ],
  "confidence": 0.0-1.0
}

Important:
- All prices should be in cents (multiply dollars by 100)
- If a field is unclear, set confidence lower
- Include ALL line items, even if some fields are unclear

Invoice content:
[PDF text extracted here]
```

**Confidence Thresholds**:
- ≥0.9: Auto-approve, no human review needed
- 0.7-0.9: Flag for quick review
- <0.7: Require full human review

**Cost Estimate**: ~$0.01-0.05 per invoice (Haiku is very cheap)

---

### 1.3 Invoice Reconciliation

**Purpose**: Match invoices to orders and flag discrepancies.

#### Matching Logic

```python
def reconcile_invoice(invoice, orders):
    """
    Match invoice lines to order lines.
    Returns list of matches and discrepancies.
    """
    # Find candidate orders (same distributor, recent, not yet invoiced)
    candidate_orders = find_candidate_orders(
        distributor_id=invoice.distributor_id,
        date_range=(invoice.invoice_date - 14 days, invoice.invoice_date)
    )
    
    for invoice_line in invoice.lines:
        best_match = None
        
        for order in candidate_orders:
            for order_line in order.lines:
                if matches_sku(invoice_line, order_line):
                    # Check for discrepancies
                    discrepancies = []
                    
                    if invoice_line.quantity != order_line.quantity:
                        discrepancies.append({
                            'type': 'quantity_mismatch',
                            'expected': order_line.quantity,
                            'actual': invoice_line.quantity
                        })
                    
                    if invoice_line.unit_price != order_line.expected_price:
                        discrepancies.append({
                            'type': 'price_mismatch',
                            'expected': order_line.expected_price,
                            'actual': invoice_line.unit_price
                        })
                    
                    best_match = (order_line, discrepancies)
                    break
        
        if best_match:
            invoice_line.matched_order_line = best_match[0]
            invoice_line.match_status = 'matched' if not best_match[1] else 'discrepancy'
        else:
            invoice_line.match_status = 'unmatched'
```

#### Discrepancy Types

| Type | Description | Auto-Action |
|------|-------------|-------------|
| `price_mismatch` | Invoiced price ≠ expected price | Flag for review if >5% difference |
| `quantity_mismatch` | Received qty ≠ ordered qty | Flag for review |
| `unmatched_item` | Item on invoice not on order | Flag for review |
| `missing_item` | Item on order not on invoice | Flag - may be backordered |

---

### 1.4 Dispute Tracker

**Purpose**: Log issues, track resolution, calculate outstanding credits.

#### Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    OPEN     │───▶│  CONTACTED  │───▶│  RESOLVED   │    │ WRITTEN OFF │
│             │    │             │    │             │    │             │
│ Issue       │    │ Email sent  │    │ Credit      │    │ No credit   │
│ identified  │    │ to rep      │    │ received    │    │ expected    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

#### Dispute Entry

**Required Fields**:
- Invoice reference
- Line item (if applicable)
- Type: `wrong_item`, `bad_quality`, `missing`, `price_discrepancy`, `short_quantity`
- Description (free text)
- Amount disputed

**Optional Fields**:
- Photo upload (for quality issues)
- Expected resolution

#### Draft Dispute Email

System generates draft email for review:

```
Subject: Invoice #{invoice_number} - {dispute_type} Issue

Hi {rep_name},

We received invoice #{invoice_number} dated {invoice_date} and found the following issue:

Issue Type: {dispute_type}
Item: {item_description}
Details: {description}

Expected: {expected}
Received: {actual}
Amount in dispute: ${amount}

Please advise on how to proceed with a credit or replacement.

Thanks,
{sender_name}
Mill & Whistle
```

---

### 1.5 Payment Queue

**Purpose**: Generate list of invoices to pay via Mercury.

#### Features

- Show all unpaid invoices sorted by due date
- Calculate running total
- Mark as paid with reference number
- Export to CSV if needed

#### Dashboard View

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PAYMENTS DUE                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  OVERDUE                                                            │
│  ├─ Mountain Produce #4521  $347.82    Due: Nov 20    [Mark Paid]   │
│                                                                      │
│  THIS WEEK                                                          │
│  ├─ Valley Foods #89234    $892.15    Due: Nov 28    [Mark Paid]   │
│  ├─ Farm Direct #1847      $301.44    Due: Nov 29    [Mark Paid]   │
│                                                                      │
│  NEXT WEEK                                                          │
│  ├─ Green Market #6234     $445.20    Due: Dec 3     [Mark Paid]   │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  Total Outstanding: $1,986.61                                       │
│  Total This Week:   $1,193.59                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 1.6 Price History

**Purpose**: Track price changes over time for analysis and alerts.

#### Data Capture

Prices are captured from multiple sources:
1. **Invoices** (most authoritative) - captured during parsing
2. **Catalog/Website** (manual entry) - for comparison shopping
3. **Quotes** (manual entry) - from rep conversations

#### Price Change Detection

```python
def check_price_change(dist_ingredient_id, new_price, source):
    """Check if price has changed significantly."""
    previous = get_latest_price(dist_ingredient_id)
    
    if previous is None:
        return {'is_new': True}
    
    change_pct = (new_price - previous.price) / previous.price * 100
    
    return {
        'is_new': False,
        'previous_price': previous.price,
        'new_price': new_price,
        'change_pct': change_pct,
        'is_significant': abs(change_pct) > 5  # 5% threshold
    }
```

#### Alert Thresholds

| Change | Alert Level | Action |
|--------|-------------|--------|
| >10% increase | HIGH | Include in daily digest, suggest alternatives |
| 5-10% increase | MEDIUM | Include in daily digest |
| <5% change | LOW | Log only |
| Any decrease | INFO | Include in digest as positive news |

---

## Daily Digest Email

**Sent**: Daily at 6:00 AM (before opening)  
**Recipients**: Executive team (configurable)

### Template

```
Subject: Mill & Whistle Daily Digest - {date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📥 INVOICES RECEIVED YESTERDAY
─────────────────────────────
• Valley Foods #89234 - $892.15 (12 items) ✓ Parsed successfully
• Mountain Produce #4588 - $234.56 (8 items) ⚠️ 2 discrepancies found

⚠️ DISCREPANCIES REQUIRING ATTENTION
────────────────────────────────────
1. Mountain Produce #4588: Butter charged at $4.20/lb, order showed $3.85/lb
   Difference: $14.00
   [View Details] [Draft Email to Rep]

2. Mountain Produce #4588: Ordered 2 cases eggs, invoiced for 3
   Difference: $32.00
   [View Details] [Draft Email to Rep]

💰 PAYMENTS DUE
───────────────
This Week: $1,193.59
• Valley Foods #89234 - $892.15 - Due Nov 28
• Farm Direct #1847 - $301.44 - Due Nov 29

Overdue: $347.82
• Mountain Produce #4521 - Due Nov 20 (8 days overdue)

📈 PRICE CHANGES
────────────────
↑ Heavy Cream (Valley Foods): $3.45 → $3.89/qt (+12.8%) ⚠️
↑ Butter (Mountain Produce): $3.85 → $4.20/lb (+9.1%)
↓ Eggs 15dz (Farm Direct): $34.00 → $32.00 (-5.9%) ✓

🎫 OPEN DISPUTES
────────────────
• 2 open disputes totaling $46.00
• Oldest: Mountain Produce wrong item (opened Nov 15)
[View All Disputes]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## API Endpoints

### Distributors
- `GET /api/distributors` - List all distributors
- `GET /api/distributors/{id}` - Get distributor details
- `POST /api/distributors` - Create distributor
- `PUT /api/distributors/{id}` - Update distributor
- `DELETE /api/distributors/{id}` - Soft delete

### Invoices
- `GET /api/invoices` - List invoices (with filters)
- `GET /api/invoices/{id}` - Get invoice with lines
- `POST /api/invoices/parse` - Upload PDF for parsing
- `PUT /api/invoices/{id}/approve` - Approve parsed invoice
- `PUT /api/invoices/{id}/paid` - Mark as paid

### Disputes
- `GET /api/disputes` - List disputes (filter by status)
- `POST /api/disputes` - Create dispute
- `PUT /api/disputes/{id}` - Update dispute status
- `GET /api/disputes/{id}/draft-email` - Generate draft email

### Reports
- `GET /api/reports/payment-queue` - Payments due
- `GET /api/reports/price-changes` - Recent price changes
- `GET /api/reports/daily-digest` - Generate digest content

---

## Implementation Checklist

### Phase 0 (Foundation)
- [ ] Set up GCP project and Cloud SQL
- [ ] Create `distributors` table
- [ ] Build basic web form for distributor CRUD
- [ ] Migrate existing distributor data

### Phase 1a (Invoice Ingestion)
- [ ] Set up invoice email inbox
- [ ] Configure Gmail API or forwarding
- [ ] Build PDF text extraction
- [ ] Implement Claude Haiku parsing prompt
- [ ] Create invoice review interface
- [ ] Store parsed invoices to database

### Phase 1b (Reconciliation & Tracking)
- [ ] Build invoice-to-order matching logic
- [ ] Create discrepancy detection
- [ ] Build dispute entry form
- [ ] Implement dispute email drafts
- [ ] Create payment queue view
- [ ] Build daily digest email

### Phase 1c (Price History)
- [ ] Capture prices from invoices automatically
- [ ] Build price change detection
- [ ] Add price alerts to daily digest
