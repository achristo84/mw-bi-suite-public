# Scraper Onboarding Guide

This document describes how to add a new distributor scraper to the system.

## Overview

Each distributor scraper is a static Python module that:
1. Logs into the distributor portal using stored credentials
2. Exports or scrapes the product catalog
3. Parses items into a structured format
4. Feeds into the item mapping and price comparison pipeline

Scrapers run on a schedule (typically weekly) and cost essentially nothing to operate since they're just compute, no API calls.

## Prerequisites

- Portal credentials stored in GCP Secret Manager
- Distributor record created in database with `scraper_module` field set
- Access to Claude + Puppeteer MCP for website analysis

## Step 1: Website Analysis

Use Claude with the Puppeteer MCP to explore the distributor portal.

### What to Document

1. **Login Flow**
   - URL of login page
   - Form field selectors (username, password, submit button)
   - Any CAPTCHA or 2FA requirements
   - Post-login redirect URL

2. **Catalog Location**
   - How to navigate to the product catalog
   - Is there a "Download CSV" or "Export" option? (preferred)
   - If no export, document the catalog page structure

3. **Page Structure** (if scraping)
   - Product list container selector
   - Individual product selectors
   - Pagination mechanism (next button, infinite scroll, page numbers)

4. **Data Fields**
   - Where to find: SKU, product name, description, price, pack size/unit
   - Any inconsistencies in formatting

5. **Anti-Bot Measures**
   - Rate limiting observed
   - Any bot detection (Cloudflare, reCAPTCHA)
   - Session timeout behavior

### Example Analysis Prompt

```
Use the Puppeteer MCP to:
1. Navigate to [portal URL]
2. Document the login form structure
3. After login, find the product catalog
4. Check if there's a CSV/Excel export option
5. If no export, document the HTML structure of product listings
6. Note any pagination
7. Capture screenshots of key pages

Return a structured report with selectors and recommended scraping approach.
```

## Step 2: Generate Scraper Code

Based on the analysis, generate a scraper class. Use Claude (Sonnet) for code generation.

### Scraper Template

```python
"""
Scraper for [Distributor Name]
Portal: [portal URL]
Last updated: [date]
"""

import asyncio
import random
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper, ScrapedItem, CatalogScrape


class [Distributor]Scraper(BaseScraper):
    """Scraper for [Distributor] portal."""

    PORTAL_URL = "[login URL]"
    CATALOG_URL = "[catalog URL]"

    async def login(self, page) -> bool:
        """Login to [Distributor] portal."""
        await page.goto(self.PORTAL_URL)

        # Fill login form
        await page.fill('[selector for username]', self.credentials['username'])
        await page.fill('[selector for password]', self.credentials['password'])

        # Submit
        await page.click('[selector for submit button]')

        # Wait for successful login indicator
        await page.wait_for_selector('[selector indicating logged in]', timeout=10000)

        return True

    async def get_catalog(self, page) -> list[dict]:
        """Scrape product catalog."""
        await page.goto(self.CATALOG_URL)

        items = []

        # Option A: Download CSV export
        # async with page.expect_download() as download_info:
        #     await page.click('[export button selector]')
        # download = await download_info.value
        # return self.parse_csv(await download.path())

        # Option B: Scrape HTML pages
        while True:
            # Wait for products to load
            await page.wait_for_selector('[product container selector]')

            # Extract products from current page
            products = await page.query_selector_all('[product item selector]')

            for product in products:
                # Add random delay to mimic human behavior
                await asyncio.sleep(random.uniform(0.1, 0.3))

                item = {
                    'sku': await self._get_text(product, '[sku selector]'),
                    'name': await self._get_text(product, '[name selector]'),
                    'price': await self._get_text(product, '[price selector]'),
                    'unit': await self._get_text(product, '[unit selector]'),
                }
                items.append(item)

            # Check for next page
            next_button = await page.query_selector('[next page selector]')
            if next_button and await next_button.is_enabled():
                await next_button.click()
                await asyncio.sleep(random.uniform(2, 4))  # Rate limiting
            else:
                break

        return items

    async def _get_text(self, element, selector: str) -> str:
        """Safely extract text from element."""
        try:
            el = await element.query_selector(selector)
            if el:
                return (await el.text_content()).strip()
        except Exception:
            pass
        return ''

    def parse_item(self, raw: dict) -> ScrapedItem:
        """Parse raw scraped data into ScrapedItem."""
        return ScrapedItem(
            distributor_id=self.distributor_id,
            raw_sku=raw.get('sku', ''),
            raw_name=raw.get('name', ''),
            raw_price_text=raw.get('price', ''),
            raw_unit_text=raw.get('unit', ''),
            # Parsing logic for price and pack size
            parsed_price_cents=self._parse_price(raw.get('price', '')),
            parsed_pack_size=self._parse_pack_size(raw.get('unit', '')),
            parsed_pack_unit=self._parse_pack_unit(raw.get('unit', '')),
        )

    def _parse_price(self, price_text: str) -> int | None:
        """Parse price string to cents."""
        # Remove $ and convert to cents
        # Handle formats like "$142.56", "142.56", "$1,234.56"
        import re
        match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
        if match:
            return int(float(match.group()) * 100)
        return None

    def _parse_pack_size(self, unit_text: str) -> float | None:
        """Extract pack size from unit text."""
        # Handle formats like "36 lb case", "4/1 gal", "15 dz"
        import re
        # Pattern: number followed by unit
        match = re.search(r'(\d+\.?\d*)\s*(lb|oz|kg|gal|qt|dz|each|ct)', unit_text.lower())
        if match:
            return float(match.group(1))
        return None

    def _parse_pack_unit(self, unit_text: str) -> str | None:
        """Extract pack unit from unit text."""
        import re
        match = re.search(r'\d+\.?\d*\s*(lb|oz|kg|gal|qt|dz|each|ct)', unit_text.lower())
        if match:
            return match.group(1)
        return None
```

## Step 3: Test Scraper

### Local Testing

```bash
# Run scraper locally with test credentials
python -m scrapers.run --distributor [distributor_id] --dry-run

# Verify output
# - Check number of items scraped
# - Verify price parsing accuracy
# - Check for any errors or missing fields
```

### Validation Checklist

- [ ] Login succeeds without errors
- [ ] All catalog pages are scraped (check pagination)
- [ ] SKUs are extracted correctly
- [ ] Prices are parsed to cents accurately
- [ ] Pack sizes and units are parsed correctly
- [ ] No rate limiting errors encountered
- [ ] Session doesn't time out mid-scrape

## Step 4: Commit and Configure

### File Placement

```
scrapers/
├── __init__.py
├── base.py
├── valleyfoods.py   # Valley Foods/Mountain Produce
├── farmdirect.py    # Farm Direct
├── greenmarket.py   # Green Market
└── [new_scraper].py # Your new scraper
```

### Database Configuration

Update the distributor record:

```sql
UPDATE distributors
SET scraper_module = 'scrapers.[module_name]',
    scrape_frequency = 'weekly',
    portal_password_encrypted = '[reference to Secret Manager]'
WHERE id = '[distributor_id]';
```

### Schedule Configuration

Add to Cloud Scheduler or cron:

```yaml
# cloud-scheduler.yaml
- name: scrape-[distributor]
  schedule: "0 9 * * 1"  # Every Monday at 9am
  target: /api/scrape/[distributor_id]
  retry_count: 2
```

## Step 5: Initial Mapping

After the first successful scrape:

1. Review unmapped items in the admin UI
2. Use LLM-assisted suggestions to map items to canonical ingredients
3. Human-verify high-value items
4. Set quality tier annotations where relevant

## Maintenance

### When Scrapers Break

Website changes will break scrapers. When this happens:

1. **Alert received** - Scrape job fails, sends notification
2. **Diagnose** - Use Claude + Puppeteer MCP to analyze what changed
3. **Update** - Claude generates updated selectors/logic
4. **Test** - Verify fix locally
5. **Deploy** - Commit and redeploy

### Common Issues

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Login fails | Credentials expired | Update in Secret Manager |
| Empty catalog | Selector changed | Re-analyze page structure |
| Missing prices | Price element moved | Update price selector |
| Rate limited | Too aggressive | Increase delays |
| Session timeout | Long scrape | Add session refresh logic |

## Anti-Detection Best Practices

1. **Rate Limiting**
   - Random delays between requests (2-5 seconds)
   - Longer delays between pages (3-8 seconds)

2. **Session Management**
   - Login once per scrape
   - Reuse session for entire catalog
   - Don't make parallel requests

3. **Timing**
   - Scrape during business hours (9am-5pm)
   - Weekly frequency, not daily
   - Randomize exact scrape time within window

4. **User Agent**
   - Use realistic browser user agent
   - Match browser being used (Chromium)

5. **Behavior**
   - Don't scrape every single page
   - Skip low-value categories if possible
   - Act like a human browsing

## Fallback: Manual CSV Import

If scraping becomes impossible (heavy anti-bot, legal concerns), support manual CSV import:

1. Staff logs into portal manually
2. Exports price list as CSV/Excel
3. Uploads to system via admin UI
4. System processes like a scrape

This is more labor but always works.
