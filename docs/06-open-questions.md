# Open Questions

## Decisions Needed Before/During Implementation

This document tracks questions that need answers to proceed with development. Update as decisions are made.

---

## Infrastructure & Setup

### Q1: Invoice Email Strategy
**Question**: Create a dedicated inbox or filter existing business email?

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Dedicated inbox (invoices@yourdomain.com) | Clean separation, simple filtering | Need to update distributor contacts |
| B: Filter existing inbox | No distributor updates needed | More complex filtering rules, may miss invoices |

**Recommendation**: Option A - dedicated inbox is cleaner long-term

**Decision**: _Pending_

---

### Q2: System Name
**Question**: What should we call this system?

**Impact**: Repo name, documentation, internal references

**Suggestions**:
- `mw-bi-suite` (current working name)
- `your-gcp-project` (example project ID)
- `whistle` (short, memorable)
- `backstage` (operations happen backstage)

**Decision**: _Pending_

---

### Q3: Initial UI Priority
**Question**: Web dashboard from day one, or email-first with manual DB queries?

**Options**:
| Option | Pros | Cons |
|--------|------|------|
| A: Full web UI from start | Better user experience, easier for chef | More development time upfront |
| B: Daily email + basic admin pages | Faster to MVP, test what's useful | Requires DB access for ad-hoc queries |

**Recommendation**: Option B for Phase 1, add dashboard in Phase 5

**Decision**: _Pending_

---

### Q4: Multi-User Access
**Question**: Who needs login access?

**Users to consider**:
- [ ] Owner/admin (full access)
- [ ] Manager (admin)
- [ ] Chef (view + limited edit?)
- [ ] Other staff (view only?)

**Authentication approach**:
- Simple: Shared password initially
- Better: Google OAuth (since using Google Workspace)
- Future: Role-based access

**Decision**: _Pending_

---

## Data & Integration

### Q5: Recipe Format Standardization
**Question**: What should the standard recipe input format be?

**Need**: Example recipe from current Google Sheets to design importer

**Action**: Share 2-3 sample recipes in current format

**Current format documented?**: _No_

**Decision**: _Pending - need examples_

---

### Q6: Toast Data Export
**Question**: What reports can be exported from Toast, and in what format?

**Need to research**:
- [ ] Product Mix report format
- [ ] Sales Summary report format
- [ ] Export frequency limits
- [ ] API availability timeline

**Action**: Log into Toast and explore export options

**Decision**: _Pending research_

---

### Q7: Invoice Format Samples
**Question**: How different are invoice PDFs across distributors?

**Need**: Sample invoices from each major distributor to test parsing

**Samples needed from**:
- [ ] Valley Foods
- [ ] Mountain Produce
- [ ] Farm Direct
- [ ] Green Market

**Action**: Collect recent invoice PDFs

**Decision**: _Pending samples_

---

## Operations

### Q8: Par Level Methodology
**Question**: How should par levels be calculated initially?

**Options**:
| Option | Description |
|--------|-------------|
| A: Chef's intuition | Chef sets based on experience |
| B: Formula-based | Daily usage × lead time + buffer |
| C: Start high, refine | Conservative pars, adjust down |

**Recommendation**: Start with chef's input (A), add formula suggestions (B) over time

**Decision**: _Pending_

---

### Q9: Inventory Count Frequency
**Question**: How often should physical inventory counts happen?

**Options**:
- Daily (high effort, high accuracy)
- Weekly (balanced)
- Monthly (low effort, less accurate)
- Triggered (when variance detected)

**Recommendation**: Weekly for high-value items, monthly full count

**Decision**: _Pending_

---

### Q10: Notification Recipients
**Question**: Who should receive the daily digest email?

**Candidates**:
- [ ] Owner
- [ ] Manager
- [ ] Chef
- [ ] All of above

**Should roles get different digests?**: _TBD_

**Decision**: _Pending_

---

## Business Rules

### Q11: Price Alert Thresholds
**Question**: What price change percentages should trigger alerts?

**Proposed defaults**:
- HIGH alert: >10% increase
- MEDIUM alert: 5-10% increase
- INFO: Any decrease

**Are these thresholds appropriate?**: _Pending validation_

**Decision**: _Pending_

---

### Q12: Target Food Cost Percentage
**Question**: What is the target food cost percentage for menu items?

**Industry standard**: 28-32% for fast-casual

**Proposed**: 30% target, flag anything >35%

**Actual target**: _Pending_

**Decision**: _Pending_

---

### Q13: Invoice Payment Terms
**Question**: Standard payment timing?

**Current understanding**: Net 15, but happy to pay immediately

**Questions**:
- Pay on receipt or batch weekly?
- Any early-pay discounts to pursue?
- Should system auto-suggest payment timing?

**Decision**: _Pending_

---

## Technical

### Q14: Hosting Domain
**Question**: What domain/subdomain for the admin interface?

**Options**:
- `ops.yourdomain.com`
- `admin.yourdomain.com`
- `app.yourdomain.com`
- Keep internal (no public domain, just Cloud Run URL)

**Note**: Toast currently hosts main website

**Decision**: _Pending_

---

### Q15: PDF Parsing Model
**Question**: Which Claude model for invoice parsing?

**Options**:
| Model | Cost | Speed | Accuracy |
|-------|------|-------|----------|
| Haiku | ~$0.01/invoice | Fast | Good |
| Sonnet | ~$0.05/invoice | Medium | Better |

**Recommendation**: Start with Haiku, upgrade if accuracy issues

**Decision**: _Pending_

---

### Q16: Data Retention
**Question**: How long to keep historical data?

**Considerations**:
- Invoices: 7 years (tax purposes)
- Price history: Indefinite (useful for analysis)
- Sales data: Indefinite
- PDFs: 7 years

**Storage cost impact**: Minimal at current scale

**Decision**: _Pending_

---

## Future Considerations

### Q17: Multi-Location
**Question**: Any plans for additional locations?

**Impact**: Database schema design (location_id fields)

**Current answer**: _Unknown_

**Decision**: Design for single location, ensure schema extensible

---

### Q18: Ecommerce Timeline
**Question**: Confirmed 4-6 month timeline for Shopify launch?

**Integration needs**:
- Inventory sync
- Product catalog
- Order data

**Action**: Keep schema flexible for ecomm integration

**Decision**: _Pending confirmation_

---

### Q19: Toast API
**Question**: Worth pursuing Toast API access early?

**Effort**: Application process, integration development

**Value**: Real-time sales data, menu sync

**Alternative**: Manual CSV export works for MVP

**Decision**: _Pending - evaluate after Phase 5 MVP_

---

## Decision Log

Track decisions as they're made:

| Date | Question | Decision | Rationale |
|------|----------|----------|-----------|
| _TBD_ | Q1 | _TBD_ | _TBD_ |

---

## How to Update This Document

As questions are answered:
1. Update the **Decision** field
2. Add entry to **Decision Log**
3. Update relevant spec documents if needed
4. Commit with message: `docs: decided Q# - [brief description]`
