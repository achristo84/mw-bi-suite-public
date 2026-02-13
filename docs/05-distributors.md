# Current Distributors

## Overview

Mill & Whistle works with multiple distributors due to limited access in rural Vermont. Each has different strengths, minimums, delivery schedules, and challenges.

---

## Active Food Distributors

### Valley Foods
**Type**: National broadline distributor
**Minimum**: $300
**Delivery Days**: Monday - Friday
**Order Deadline**: Day before delivery

**Strengths**:
- Reliable delivery
- Wide product selection
- Daily delivery options

**Weaknesses**:
- Generally lower quality products
- Large pack sizes
- Corporate/impersonal service

**Best For**: Staples, high-volume items, emergency orders

---

### Mountain Produce (Valley Foods subsidiary)
**Type**: Regional specialty distributor
**Minimum**: $300
**Delivery Days**: Monday - Friday
**Order Deadline**: Day before delivery

**Strengths**:
- Higher quality than Valley Foods
- Local/regional products
- Same portal as Valley Foods

**Weaknesses**:
- Unreliable (frequent issues)
- Wrong items, missing items common
- Poor communication

**Best For**: Local products when Valley Foods doesn't carry, but verify orders carefully

**Note**: Document all issues for dispute tracking. This vendor requires extra oversight.

---

### Farm Direct
**Type**: Regional nonprofit distributor (Vermont based)
**Minimum**: $300
**Delivery Days**: Friday only
**Order Deadline**: Wednesday 10:00 AM

**Strengths**:
- Good to work with
- Local/seasonal produce
- Variety of retail products
- Mission-aligned (nonprofit)

**Weaknesses**:
- Friday only delivery
- Seasonal produce availability
- Variable pricing

**Best For**: Produce (seasonal), local dairy, retail items with story

---

### Green Market
**Type**: New England regional distributor (retail focus)
**Minimum**: $250
**Delivery Days**: Monday, Wednesday
**Order Deadline**: TBD

**Strengths**:
- Good retail selection
- Local New England products
- Dairy options

**Weaknesses**:
- Very expensive
- Limited delivery days
- High prices on basics

**Best For**: Specialty retail items, premium dairy when cost justifies

---

### Metro Wholesale
**Type**: Specialty foodservice
**Minimum**: $250
**Delivery Days**: Thursday (order by Monday)

**Strengths**:
- High quality specialty products
- Broad foodservice selection

**Weaknesses**:
- Higher minimums for specialty
- Once weekly delivery

**Best For**: Specialty ingredients, premium items

---

## Specialty Distributors

### Specialty Gourmet (online)
**Type**: Premium specialty ingredients
**Minimum**: None (shipping based)
**Delivery**: Shipped

**Products**: Specialty items, premium ingredients

**Notes**: Use for special menu items, events. Expensive but unique products.

---

### Online Wholesale Marketplace
**Type**: Online wholesale marketplace
**Minimum**: Varies by vendor
**Delivery**: Shipped

**Products**: Retail goods from independent makers

**Strengths**:
- Great retail selection
- Net 60 terms
- Discovery of new products

**Best For**: Non-perishable retail, gifts, home goods

---

## Distributor Gaps

Current gaps in distributor coverage:

1. **Reliable local produce** - Farm Direct is good but seasonal
2. **Specialty dairy** - Need mascarpone, high-quality yogurt sources
3. **Bread/bakery** - No dedicated bakery distributor
4. **Meat/protein** - Limited local options

**Planned additions**:
- Research local farms for direct relationships
- Evaluate additional regional distributors
- Consider wholesale club trips for bulk staples

---

## Data Migration Notes

When importing to the new system:

```
Distributor fields to capture:
- name
- rep_name
- rep_email
- rep_phone
- portal_url
- portal_username (encrypt)
- order_email
- minimum_order_cents
- delivery_days (array)
- order_deadline (text description)
- payment_terms_days (default 15)
- vendor_category
- notes
- is_active
```

Priority for initial migration:
1. Valley Foods (highest volume)
2. Farm Direct (regular orders)
3. Mountain Produce (despite issues, used often)
4. Green Market (periodic orders)
5. Others as needed
