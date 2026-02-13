# Distributor API Capture Workflow

This document describes the process for capturing and analyzing distributor ordering APIs for Order Hub integration.

## Overview

We use Playwright to launch a browser that records all network traffic while you interact with a distributor's website. After capture, we analyze the data to document API endpoints, extract auth tokens, and test APIs directly with curl.

**Advantages over mitmproxy:**
- No certificate installation required
- Works with any site (no SSL interception issues)
- Simpler setup

## Prerequisites

```bash
# Install Playwright (one-time)
python3 -m pip install playwright
python3 -m playwright install firefox
```

## Step 1: Run the Capture

### Start the Capture Browser

```bash
cd mw-bi-suite

# Basic usage - opens browser at specified URL
python3 scripts/capture_browser.py --url "https://example-distributor.com" --name distributor-name

# Examples:
python3 scripts/capture_browser.py --url "https://distributor-portal-url.example.com" --name distributor-api-capture
python3 scripts/capture_browser.py --url "https://another-distributor-portal.example.com" --name distributor2-capture
```

The browser opens and you interact with it normally.

### What to Capture

For each distributor, capture these workflows:

1. **Login** - Enter credentials and log in
2. **Search** - Search for products ("eggs", "whole milk" are good test queries)
3. **Add to cart** - Add a few items to cart
4. **View order** - Look at order/cart details
5. **Create new order** - If the site supports multiple orders
6. **View delivery dates** - Check available delivery schedule

### Stop the Capture

When done, create the stop signal file:
```bash
touch captures/{session-name}/.stop
```

Or press Ctrl+C in the terminal.

## Step 2: Understand the Captured Files

Captures are saved to `captures/{session-name}/`:

| File | Description | Primary Use |
|------|-------------|-------------|
| `requests.jsonl` | All HTTP requests | Find API endpoints, extract tokens |
| `responses.jsonl` | All HTTP responses | Response bodies (may be empty for cross-origin) |
| `cookies.jsonl` | Cookie snapshots | Session management |
| `console.jsonl` | Browser console | Debug info |
| `metadata.json` | Capture summary | Quick stats |

## Step 3: Analyze the Capture

### 3.1 Quick Overview

```bash
cd captures/{session-name}

# Check capture stats
cat metadata.json | python3 -m json.tool
```

Example output:
```json
{
  "capture_start": "2026-01-27T17:18:15.018820",
  "duration_seconds": 245.08,
  "total_requests": 294,
  "total_responses": 140
}
```

### 3.2 Find API Endpoints

List all API-like requests (filter out static assets):

```bash
cat requests.jsonl | python3 -c "
import json, sys

for line in sys.stdin:
    req = json.loads(line)
    url = req['url']
    method = req['method']

    # Filter for API calls
    if '/api/' in url.lower() or method == 'POST':
        # Skip analytics
        if any(x in url.lower() for x in ['analytics', 'tracking', 'google', 'facebook']):
            continue

        has_body = '[POST]' if req.get('post_data') else ''
        print(f\"{method:6} {url[:100]} {has_body}\")
"
```

### 3.3 Group by Endpoint

See unique API endpoints:

```bash
cat requests.jsonl | python3 -c "
import json, sys
from collections import Counter

endpoints = Counter()
for line in sys.stdin:
    r = json.loads(line)
    url = r['url']
    if '/api/' in url.lower():
        # Extract path without query params
        path = url.split('?')[0]
        # Normalize to base path
        endpoints[f\"{r['method']} {path}\"] += 1

for ep, count in endpoints.most_common(30):
    print(f'{count:3}x  {ep}')
"
```

### 3.4 Extract Full Request Details

For a specific API, get complete request info:

```bash
cat requests.jsonl | python3 -c "
import json, sys

API_NAME = 'SearchProduct'  # Adjust this

for line in sys.stdin:
    req = json.loads(line)
    if API_NAME in req['url']:
        print('='*60)
        print(f\"URL: {req['url']}\")
        print(f\"Method: {req['method']}\")
        print()
        print('Headers:')
        for k, v in sorted(req['headers'].items()):
            # Only show relevant headers
            if k.lower() in ['authorization', 'content-type', 'accept', 'origin', 'referer']:
                val = v[:80] + '...' if len(v) > 80 else v
                print(f'  {k}: {val}')
        if req.get('post_data'):
            print()
            print('Request Body:')
            try:
                body = json.loads(req['post_data'])
                print(json.dumps(body, indent=2))
            except:
                print(req['post_data'][:500])
        print()
        break  # First match
"
```

### 3.5 Extract Auth Token

Most APIs use Bearer tokens. Extract for testing:

```bash
cat requests.jsonl | python3 -c "
import json, sys

for line in sys.stdin:
    req = json.loads(line)
    auth = req['headers'].get('authorization', '')
    if auth.startswith('Bearer '):
        print(auth[7:])  # Token only
        break
" > /tmp/api_token.txt

echo "Token saved to /tmp/api_token.txt"
echo "Token length: $(wc -c < /tmp/api_token.txt) bytes"
```

### 3.6 Find Customer/Account IDs

Look for customer identifiers in request bodies:

```bash
cat requests.jsonl | python3 -c "
import json, sys, re

for line in sys.stdin:
    req = json.loads(line)
    if req.get('post_data'):
        # Look for customer ID patterns
        data = req['post_data']
        if 'customer' in data.lower():
            try:
                body = json.loads(data)
                print(f\"URL: {req['url'].split('/')[-1]}\")
                print(json.dumps(body, indent=2)[:500])
                print()
            except:
                pass
" | head -50
```

## Step 4: Test APIs with curl

Use the captured token to verify APIs work:

### Basic Test

```bash
TOKEN=$(cat /tmp/api_token.txt)

curl -s -X POST "https://api.example.com/api/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"query": "eggs", "limit": 5}' \
  | python3 -m json.tool
```

### Save Response Samples

```bash
mkdir -p samples

# Search response
curl -s -X POST "https://api.example.com/api/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "eggs", "limit": 2}' \
  | python3 -m json.tool > samples/search_response.json

# Pricing response
curl -s -X POST "https://api.example.com/api/prices" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_ids": ["abc", "def"]}' \
  | python3 -m json.tool > samples/price_response.json
```

## Step 5: Document the API

Create `API_SPEC.md` in the capture directory:

### Template

```markdown
# {Distributor} API Specification

**Captured:** {date}
**Platform:** {platform name}
**Base URL:** `https://...`

## Authentication

- **Type:** Bearer token (OAuth2 / Azure B2C / etc.)
- **Token Endpoint:** `POST /oauth/token`
- **Token Lifetime:** ~1 hour

## Customer Context

| Field | Value |
|-------|-------|
| Customer ID | `abc-123-...` |
| Account Number | `12345` |

## Core APIs

### 1. Product Search

**Endpoint:** `POST /api/search`

**Request:**
\`\`\`json
{
  "query": "eggs",
  "limit": 25
}
\`\`\`

**Response:**
\`\`\`json
{
  "products": [
    {
      "id": "...",
      "sku": "...",
      "name": "...",
      "price": 12.99,
      "pack_size": "12/1 Dz"
    }
  ]
}
\`\`\`

### 2. Get Prices
... (similar format)

## Data Normalization

| API Field | Our Field | Transform |
|-----------|-----------|-----------|
| `id` | `external_id` | Direct |
| `sku` | `sku` | Direct |
| `price` | `price_cents` | × 100 |
| `pack_size` | `pack_size` | Parse |

## Pack Size Examples

| Raw | Interpretation |
|-----|----------------|
| `12/1 Dz` | 12 dozen per case |
| `144/1 Oz` | 144 × 1oz pieces |
```

## Step 6: Organize Final Deliverables

Final directory structure:

```
captures/{distributor}-api-capture/
├── API_SPEC.md           # Complete documentation
├── samples/              # Verified response samples
│   ├── search_response.json
│   ├── price_response.json
│   ├── order_response.json
│   └── delivery_dates_response.json
├── requests.jsonl        # Raw capture (keep for reference)
├── responses.jsonl
├── cookies.jsonl
├── console.jsonl
└── metadata.json
```

## Common Analysis Patterns

### Find All POST Endpoints with Bodies

```bash
cat requests.jsonl | python3 -c "
import json, sys

for line in sys.stdin:
    r = json.loads(line)
    if r['method'] == 'POST' and r.get('post_data') and '/api/' in r['url']:
        print(f\"POST {r['url'].split('/api/')[-1].split('?')[0]}\")
        try:
            body = json.loads(r['post_data'])
            print(f\"  Keys: {list(body.keys())}\")
        except:
            pass
" | sort | uniq
```

### Check Response Status Codes

```bash
cat responses.jsonl | python3 -c "
import json, sys
from collections import Counter

codes = Counter()
for line in sys.stdin:
    r = json.loads(line)
    codes[r['status']] += 1

for code, count in sorted(codes.items()):
    print(f'{code}: {count}')
"
```

### Extract All Bearer Tokens (if multiple)

```bash
cat requests.jsonl | python3 -c "
import json, sys

tokens = set()
for line in sys.stdin:
    r = json.loads(line)
    auth = r['headers'].get('authorization', '')
    if auth.startswith('Bearer '):
        tokens.add(auth[7:50] + '...')

for t in tokens:
    print(t)
"
```

## Troubleshooting

### Token Expired

Tokens typically last 1 hour. If curl returns 401:
1. Re-run the capture to get a fresh token
2. Or document the token refresh endpoint

### Empty Response Bodies

Playwright may not capture cross-origin response bodies. Solutions:
1. Use curl with captured token to get real responses
2. Check browser DevTools Network tab directly
3. Export HAR file from browser

### Missing Requests

Some sites use:
- WebSocket connections (not captured)
- GraphQL (look for `/graphql` endpoint)
- Custom protocols

Check `console.jsonl` for clues.

## Distributor Onboarding Checklist

After capture and analysis:

- [ ] Capture completed (login, search, cart, order flows)
- [ ] Token extracted and tested with curl
- [ ] Search API documented with full request/response
- [ ] Pricing API documented (if separate from search)
- [ ] Add to cart API documented
- [ ] Create order API documented
- [ ] Customer/account IDs captured
- [ ] Delivery schedule API documented
- [ ] Pack size format examples collected
- [ ] Field mapping to our schema documented
- [ ] Sample responses saved to `samples/`
- [ ] `API_SPEC.md` complete and accurate
- [ ] Capture status updated in distributor record

## Security Notes

- Tokens in `/tmp/api_token.txt` expire after ~1 hour
- Never commit tokens to git
- Raw captures may contain sensitive data - add to `.gitignore`
- Store production credentials in GCP Secret Manager
