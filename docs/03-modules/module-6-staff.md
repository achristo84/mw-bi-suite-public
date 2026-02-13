# Module 6: Staff & Hiring

**Priority**: LOW — Build when core modules stable  
**Dependencies**: None (standalone)  
**Estimated Timeline**: Future Phase

## Overview

The Staff & Hiring module addresses workforce management needs:
- Applicant tracking from Indeed
- Interview scheduling automation
- Schedule optimization
- Shift coverage management

This module is lower priority because:
1. Team is small and stable currently
2. Manual processes are manageable at current scale
3. Toast has scheduling features that may suffice short-term

## Components

### 6.1 Applicant Tracker

**Purpose**: Centralize applicant information and track hiring pipeline.

#### Current Process Pain Points

1. Applicants come through Indeed
2. Resumes reviewed manually
3. Interview times coordinated via text/email
4. No central record of applicant status
5. Easy to lose track of candidates

#### Proposed Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   NEW       │───▶│  SCREENING  │───▶│ INTERVIEW   │───▶│   OFFER     │
│             │    │             │    │  SCHEDULED  │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  REJECTED   │    │  REJECTED   │    │  REJECTED   │    │   HIRED     │
│  (auto/     │    │  (not fit)  │    │  (after     │    │             │
│   spam)     │    │             │    │   interview)│    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

#### Applicant Data Model

```sql
CREATE TABLE applicants (
    id UUID PRIMARY KEY,
    source VARCHAR(50),           -- 'indeed', 'referral', 'walk-in'
    source_id VARCHAR(100),       -- Indeed application ID
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    position_applied VARCHAR(50), -- 'FOH', 'BOH', 'Either'
    resume_path VARCHAR(500),     -- Cloud Storage path
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE applicant_events (
    id UUID PRIMARY KEY,
    applicant_id UUID REFERENCES applicants(id),
    event_type VARCHAR(30),       -- 'status_change', 'note', 'email', 'interview'
    event_data JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Applicant List View

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  APPLICANTS                                                   [+ Add Manually]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Filter: [All Statuses ▼]  Position: [All ▼]  Source: [All ▼]                  │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  NAME              POSITION   SOURCE   APPLIED    STATUS        ACTION          │
│  ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                  │
│  Sarah Johnson     FOH        Indeed   Nov 28     🟡 Screening  [View] [📅]    │
│  Mike Chen         BOH        Indeed   Nov 27     🟢 Interview  [View]          │
│                                                   Scheduled 11/30               │
│  Alex Rivera       Either     Referral Nov 25     🟡 Screening  [View] [📅]    │
│  Jordan Smith      FOH        Indeed   Nov 24     🔴 Rejected   [View]          │
│                                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  Showing 4 of 12 applicants                                    [Load More]      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Interview Scheduler

**Purpose**: Simplify interview coordination.

#### Scheduling Flow

1. **Define availability** - Set times you're available to interview
2. **Send invite link** - Applicant picks from available slots
3. **Confirmation** - Both parties get calendar invite
4. **Reminders** - Automated reminder before interview

#### Availability Management

```
┌─────────────────────────────────────────────────────────────────────┐
│  INTERVIEW AVAILABILITY                              [Save Changes] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Default weekly availability:                                        │
│                                                                      │
│  Monday    [OFF - Closed]                                           │
│  Tuesday   [1:00 PM] - [3:00 PM]  (after lunch prep)               │
│  Wednesday [1:00 PM] - [3:00 PM]                                    │
│  Thursday  [1:00 PM] - [3:00 PM]                                    │
│  Friday    [OFF - Too busy]                                         │
│  Saturday  [OFF - Too busy]                                         │
│  Sunday    [OFF - Too busy]                                         │
│                                                                      │
│  Interview duration: [30 minutes ▼]                                 │
│  Buffer between interviews: [15 minutes ▼]                          │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Block specific dates:                                               │
│  • Nov 28-29 (Thanksgiving)                                         │
│  • Dec 24-25 (Christmas)                                            │
│  [+ Add blocked date]                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Booking Page

Applicants receive a link to self-schedule:

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│         🏔️ MILL & WHISTLE                                          │
│         Interview Scheduling                                         │
│                                                                      │
│  Hi Sarah! Please select a time for your interview:                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │       November/December 2024                                 │   │
│  │                                                              │   │
│  │  Tuesday, Dec 3                                              │   │
│  │    [1:00 PM]  [1:30 PM]  [2:00 PM]  [2:30 PM]               │   │
│  │                                                              │   │
│  │  Wednesday, Dec 4                                            │   │
│  │    [1:00 PM]  [1:30 PM]  [2:00 PM]  [2:30 PM]               │   │
│  │                                                              │   │
│  │  Thursday, Dec 5                                             │   │
│  │    [1:00 PM]  [1:30 PM]                                     │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Location: Mill & Whistle, 123 Main St, Wilmington VT               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Calendar Integration

Use Google Calendar API to:
- Check existing events for conflicts
- Create interview events
- Send invites to both parties
- Trigger reminder emails

---

### 6.3 Schedule Optimizer (Future)

**Purpose**: Generate optimal staff schedules based on demand and constraints.

#### Constraints

- **Labor laws**: No overtime without approval, required breaks
- **Availability**: Staff submitted availability windows
- **Skills**: BOH vs FOH certification
- **Demand**: Predicted busy periods from sales data
- **Fairness**: Equitable distribution of good/bad shifts

#### Input Data

```python
# Staff availability
availability = {
    'sarah': {
        'monday': [(6, 14)],      # 6am-2pm
        'tuesday': [(6, 14)],
        'wednesday': [],          # Not available
        'thursday': [(6, 14)],
        'friday': [(6, 14)],
        'saturday': [(6, 12)],    # 6am-12pm only
        'sunday': []
    },
    # ... more staff
}

# Demand forecast (staff-hours needed by hour)
demand = {
    'monday': {6: 2, 7: 3, 8: 3, 9: 3, 10: 2, 11: 2},
    'saturday': {6: 3, 7: 4, 8: 4, 9: 4, 10: 3, 11: 3},
    # ...
}

# Constraints
max_hours_per_week = 40
min_hours_between_shifts = 8
require_manager_present = True
```

#### Schedule Output

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  GENERATED SCHEDULE                                    Week of Dec 2-8, 2024   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│         MON     TUE     WED     THU     FRI     SAT     SUN     TOTAL          │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  Sarah   6-12   6-12    OFF    6-12    6-12    6-10    OFF     34 hrs          │
│  Mike    OFF    6-12    6-12   6-12    6-12    8-12    OFF     34 hrs          │
│  Alex    6-10   OFF     6-10   OFF     6-10    6-12    6-12    32 hrs          │
│  Chef J  6-12   6-12    6-12   6-12    6-12    6-12    OFF     36 hrs          │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  Coverage Analysis:                                                              │
│  ✓ All shifts covered                                                           │
│  ✓ No overtime                                                                   │
│  ✓ Manager present all shifts                                                   │
│  ⚠️ Saturday 6-8am: Only 2 staff (recommend 3)                                  │
│                                                                                  │
│  [Approve & Publish]    [Modify]    [Regenerate]                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Why This Is Future/Optional

Toast has built-in scheduling features. Evaluate whether:
1. Toast scheduling meets your needs
2. The optimization is worth the development effort
3. Team size warrants automated scheduling

---

### 6.4 Shift Coverage Alerts

**Purpose**: Handle call-outs and find coverage quickly.

#### Call-Out Workflow

```
┌─────────────────┐
│  Staff Member   │
│  Calls Out      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Manager Logs   │────▶│  System Finds   │
│  Call-Out       │     │  Available Staff│
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Send Coverage  │
                        │  Requests       │
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  Text    │ │  Text    │ │  Text    │
              │  Sarah   │ │  Mike    │ │  Alex    │
              └────┬─────┘ └────┬─────┘ └────┬─────┘
                   │            │            │
                   ▼            ▼            ▼
              [Accept]     [Decline]    [Accept]
                   │                        │
                   └───────────┬────────────┘
                               ▼
                        ┌─────────────────┐
                        │  First Accept   │
                        │  Gets Shift     │
                        └─────────────────┘
```

#### Coverage Request Message

```
🚨 Shift Coverage Needed

Jordan called out for tomorrow's shift:
📅 Tuesday, Dec 3
⏰ 6:00 AM - 12:00 PM
📍 FOH

Reply YES to pick up this shift.
First to respond gets it!

(Reply STOP to opt out of coverage requests)
```

---

## Implementation Considerations

### Build vs Buy Analysis

| Feature | Build | Buy/Use Existing |
|---------|-------|------------------|
| Applicant Tracking | Simple CRUD app | Indeed has basic tracking |
| Interview Scheduling | Calendly integration | Calendly ($12/mo) |
| Schedule Optimization | Complex algorithm | Toast Scheduling, 7shifts, When I Work |
| Shift Coverage | Custom alerts | When I Work has this |

**Recommendation**: Start with minimal custom build (applicant tracker + Calendly integration), evaluate dedicated scheduling tools as team grows.

### Integration Points

- **Indeed API**: Pull new applications automatically
- **Google Calendar**: Interview scheduling
- **Toast**: Sync employee info, possibly scheduling
- **SMS (Twilio)**: Shift coverage alerts

---

## API Endpoints

### Applicants
- `GET /api/applicants` - List applicants
- `GET /api/applicants/{id}` - Get applicant details
- `POST /api/applicants` - Add applicant manually
- `PUT /api/applicants/{id}/status` - Update status
- `POST /api/applicants/{id}/notes` - Add note

### Interviews
- `GET /api/interviews/availability` - Get available slots
- `POST /api/interviews/schedule` - Book interview
- `DELETE /api/interviews/{id}` - Cancel interview

### Scheduling (Future)
- `GET /api/schedule/current` - Current schedule
- `POST /api/schedule/generate` - Generate new schedule
- `POST /api/schedule/callout` - Log call-out
- `POST /api/schedule/coverage-request` - Send coverage requests

---

## Implementation Checklist

### Phase 6a (Applicant Tracking) - If Built
- [ ] Create applicant database tables
- [ ] Build applicant list/detail views
- [ ] Implement status workflow
- [ ] Set up Indeed integration (or manual entry)

### Phase 6b (Interview Scheduling)
- [ ] Integrate Calendly OR build custom scheduler
- [ ] Connect to Google Calendar
- [ ] Create booking page
- [ ] Set up reminder emails

### Phase 6c (Scheduling) - Future/Optional
- [ ] Evaluate Toast scheduling vs custom
- [ ] If custom: build availability collection
- [ ] If custom: implement schedule optimizer
- [ ] Build shift coverage alerting
