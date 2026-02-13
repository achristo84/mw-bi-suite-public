# Distributor Clients Implementation

**Created:** 2026-01-28
**Status:** Complete
**Goal:** Build API clients for all captured distributors to enable Order Hub functionality

---

## Overview

Build Python client classes for each distributor that provide:
- Authentication (login, session management)
- Product search
- Cart operations (add, remove, view)
- Delivery date selection
- (Future) Order submission

All clients inherit from a base class and implement a common interface for the SearchAggregator.

---

## Distributor Summary

| # | Distributor | Platform | Auth Type | Difficulty | Status |
|---|-------------|----------|-----------|------------|--------|
| 1 | Valley Foods | Azure B2C | OAuth2 Bearer (browser) | Medium | Working |
| 2 | Mountain Produce | Azure B2C | OAuth2 Bearer (shared) | Medium | Working (uses ValleyFoodsClient) |
| 3 | Metro Wholesale | Custom | Cookie + JSON | Easy | Working |
| 4 | Farm Direct | NetSuite | Cookie + Heartbeat | Easy | Working |
| 5 | Green Market | Rails | Cookie + CSRF | Easy | Working |
| 6 | Restaurant Supply Co | Custom | reCAPTCHA + Cloudflare | Hard | Deferred |
| 7 | Online Marketplace | - | - | Hard | Deferred |

**Priority:** 1-5 (food service) first, then 6-7 (general merchandise) if time permits.

---

## Architecture

### Base Class

Location: `app/services/distributor_client.py`

```python
class DistributorApiClient:
    """Base class for all distributor API clients."""

    async def login(self) -> bool
    async def search(self, query: str) -> List[SearchResult]
    async def get_cart(self) -> Cart
    async def add_to_cart(self, sku: str, quantity: int) -> bool
    async def remove_from_cart(self, line_id: str) -> bool
    async def set_delivery_date(self, date: str) -> bool
    async def get_delivery_dates(self) -> List[date]
```

### Client Files

```
app/services/clients/
├── __init__.py
├── valleyfoods_client.py      # Valley Foods + Mountain Produce (shared platform)
├── metro_wholesale_client.py
├── farm_direct_client.py
├── green_market_client.py
└── (future) restaurant_supply_client.py
```

### Browser Automation (for anti-bot sites)

For distributors with anti-bot protection or complex OAuth flows, we use **SeleniumBase UC + Playwright CDP**:

1. **SeleniumBase UC** launches Chrome with anti-bot evasion
2. **Playwright CDP** connects via Chrome DevTools Protocol for automation
3. Tokens/cookies are extracted from sessionStorage or network responses

### Shared Types

Location: `app/services/distributor_client.py`

```python
@dataclass
class SearchResult:
    sku: str
    description: str
    price_cents: Optional[int]
    pack_size: Optional[str]
    pack_unit: Optional[str]
    in_stock: Optional[bool]
    image_url: Optional[str]
    category: Optional[str]
    product_id: Optional[str]
```

---

## Implementation Details

### 1. Valley Foods + Mountain Produce (Shared OAuth2 Platform)

**File:** `app/services/clients/valleyfoods_client.py`

**Key Details:**
- OAuth2 via Azure B2C
- Single login for both distributors
- Switch via `CustomerId` parameter (stored in `api_config`)
- Token lifetime ~1 hour, implement refresh

**Auth Flow:**
```
Initial: Browser auto-login → User logs in → tokens saved
Runtime: Client loads tokens → Uses access token → Refresh when expired
```

**Key Finding:** ROPC (password grant) is NOT enabled on the B2C tenant, so browser-based PKCE flow is required for initial authentication. Refresh token can be used for ongoing access.

---

### 2. Metro Wholesale

**File:** `app/services/clients/metro_wholesale_client.py`

**Key Details:**
- Cookie-based auth (JSON POST to `/login/`)
- Organization ID and Business Unit from `api_config`
- Product codes in `JDE_{sku}-{businessUnitId}` format
- Prices as strings ("$45.14") - need parsing
- Visit login page first (for session cookies), then JSON POST

---

### 3. Farm Direct (NetSuite SuiteCommerce)

**File:** `app/services/clients/farm_direct_client.py`

**Key Details:**
- Simplest login of all distributors (one JSON POST)
- Cookie-based auth (`JSESSIONID`)
- SHORT session timeout (~5 min) - needs heartbeat
- Company ID and Price Level from `api_config`
- No separate price API - prices in search results
- Offset-based pagination (infinite scroll)

**Critical:** Heartbeat is essential. Implemented `_ensure_session_fresh()` with 2-minute heartbeat interval.

---

### 4. Green Market (Rails / LocalFoodHQ)

**File:** `app/services/clients/green_market_client.py`

**Key Details:**
- Cookie + CSRF for form POSTs, cookie-only for JSON APIs
- Buyer ID and Seller ID from `api_config`
- **Order-first workflow** - must create PO before adding items
- Integer product unit IDs

**Unique workflow:** Create PO with date → then add items. CSRF only needed for form POSTs, not JSON APIs.

---

## Testing Strategy

### Unit Tests

Each client should have unit tests with mocked HTTP responses.

### Integration Tests

Manual testing against real APIs:
1. Login successfully
2. Search returns expected results
3. Add item to cart
4. View cart shows item
5. Remove item from cart
6. Cart is empty

---

## Credentials Management

Credentials stored in GCP Secret Manager. Each distributor has a secret with JSON `{"email": "...", "password": "..."}`. The `secret_name` is stored in the distributor's `api_config` JSONB column.

---

## Browser Automation Strategy

### When to Use Browser Automation

| Distributor | Method | Notes |
|-------------|--------|-------|
| Valley Foods / Mountain Produce | **Browser auto-login** | Azure B2C OAuth2 requires browser |
| Metro Wholesale | Cookie auth | Simple JSON POST works |
| Farm Direct | Cookie auth | Simple JSON POST works |
| Green Market | Cookie + CSRF | Simple form POST works |
| Restaurant Supply Co | **Browser auto-login** | reCAPTCHA requires stealth browser |

### Token Refresh Flow

```
1. App needs to make API call
2. Check: Is access_token valid? → Use it
3. Check: Is refresh_token valid? → Exchange for new access_token (no browser)
4. Neither valid → Run browser auto-login to get fresh tokens
5. Store tokens in Secret Manager or distributor_sessions table
```

### Server Deployment

- **Linux:** Use Xvfb (virtual display) for invisible browser operation
- **Headless mode:** Works for some sites, not others
- **Fallback:** If headless fails, queue for manual re-auth

---

## Open Questions

1. **Delivery date handling:** Should we cache available dates or fetch fresh each time?
2. **Session persistence:** Store sessions in DB or memory-only?
3. **Error handling:** Standard retry logic? Circuit breaker pattern?

---

## References

- Base client: `app/services/distributor_client.py`
- Search aggregator: `app/services/search_aggregator.py`
