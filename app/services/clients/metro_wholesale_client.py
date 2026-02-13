"""Metro Wholesale API client.

Cookie-based authentication with prices returned as formatted strings.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import httpx

from sqlalchemy.orm import Session

from app.services.distributor_client import (
    DistributorApiClient,
    SearchResult,
    CartItem,
    Cart,
)

logger = logging.getLogger(__name__)

# Defaults are read from distributor api_config; these are only fallbacks
_DEFAULT_ORGANIZATION_ID = ""
_DEFAULT_BUSINESS_UNIT = ""


class MetroWholesaleClient(DistributorApiClient):
    """Client for Metro Wholesale.

    Uses cookie-based authentication. Prices are returned as
    formatted strings (e.g., "$45.14") and need parsing.
    """

    def __init__(self, db: Session, distributor_id: UUID):
        super().__init__(db, distributor_id)
        self._cart_id: Optional[int] = None

    @property
    def base_url(self) -> str:
        return self.api_config.get("base_url", "")

    @property
    def organization_id(self) -> str:
        return self.api_config.get("organization_id", _DEFAULT_ORGANIZATION_ID)

    @property
    def business_unit(self) -> str:
        return self.api_config.get("business_unit", _DEFAULT_BUSINESS_UNIT)

    async def authenticate(self) -> bool:
        """Authenticate via JSON POST to login endpoint.

        Metro Wholesale requires:
        1. Visit login page first (to get session cookies)
        2. POST JSON with credentials

        Returns:
            True if authentication succeeded
        """
        credentials = self._get_credentials()
        if not credentials:
            logger.error("No credentials found for Metro Wholesale")
            return False

        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            logger.error("Missing email or password in Metro Wholesale credentials")
            return False

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # Step 1: GET login page to establish session cookies
                await client.get(
                    f"{self.base_url}/login/",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    },
                )

                # Step 2: POST JSON credentials
                response = await client.post(
                    f"{self.base_url}/login/",
                    json={
                        "email": email,
                        "password": password,
                        "staySignedIn": True,
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "*/*",
                        "Referer": f"{self.base_url}/login/",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    },
                )

                # Check if login succeeded (200 with valid response)
                if response.status_code == 200:
                    # Extract cookies
                    cookies = {}
                    for cookie in client.cookies.jar:
                        cookies[cookie.name] = cookie.value

                    # Verify we got auth cookies
                    if any("Application" in k or "cwUser" in k for k in cookies.keys()):
                        # Save session
                        self._save_session(
                            cookies=cookies,
                            expires_at=datetime.utcnow() + timedelta(hours=24),
                        )
                        return True
                    else:
                        logger.warning("Metro Wholesale login returned 200 but no auth cookies")
                        # Still might have worked - save and try
                        self._save_session(
                            cookies=cookies,
                            expires_at=datetime.utcnow() + timedelta(hours=24),
                        )
                        return True

                logger.error(f"Metro Wholesale auth failed: {response.status_code}")
                return False

        except Exception as e:
            logger.exception(f"Metro Wholesale authentication error: {e}")
            return False

    def _get_credentials(self) -> Optional[dict]:
        """Get credentials from Secret Manager or api_config."""
        return self.get_credentials()

    def _parse_price(self, price_str: str) -> int:
        """Parse formatted price string to cents.

        "$45.14" -> 4514
        "$1,234.56" -> 123456

        Args:
            price_str: Formatted price string

        Returns:
            Price in cents
        """
        if not price_str:
            return 0

        # Remove $ and commas, then convert to cents
        cleaned = re.sub(r'[$,]', '', price_str)
        try:
            return int(float(cleaned) * 100)
        except ValueError:
            logger.warning(f"Could not parse price: {price_str}")
            return 0

    def _make_product_code(self, sku: str) -> str:
        """Create product code in Metro Wholesale format.

        Format: JDE_{sku}-{businessUnitId}

        Args:
            sku: Base SKU

        Returns:
            Full product code
        """
        # If already in full format, return as-is
        if sku.startswith("JDE_"):
            return sku
        return f"JDE_{sku}-{self.business_unit}"

    async def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Search product catalog.

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            List of search results
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/search/Search/",
                params={"q": query},
                json={
                    "search": {
                        "page": 0,
                        "pageSize": min(limit, 50),
                        "searchText": query,
                        "removeWordsIfNoResults": False,
                        "pageToken": "",
                        "facets": [],
                        "sortBy": None,
                        "direction": None,
                        "pageNumber": 0,
                    }
                },
                headers={
                    "Accept": "*/*",
                    "Content-Type": "application/json",
                    "Referer": f"{self.base_url}/search/?q={query}",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Metro Wholesale search failed: {response.status_code}")
                return []

            data = response.json()
            results, variant_codes = self._parse_search_response(data, limit)

            # Fetch prices separately
            if variant_codes:
                prices = await self.get_prices(variant_codes)
                for result in results:
                    # Match by SKU prefix in variant code
                    for code, price in prices.items():
                        if result.sku in code:
                            result.price_cents = price
                            break

            return results

        except Exception as e:
            logger.exception(f"Metro Wholesale search error: {e}")
            return []

    def _parse_search_response(self, data: dict, limit: int) -> tuple[list[SearchResult], list[str]]:
        """Parse search response to SearchResult list.

        Returns:
            Tuple of (results list, variant codes for price lookup)
        """
        results = []
        variant_codes = []
        items = data.get("results", [])

        for item in items[:limit]:
            # Get first variant for pack info
            variants = item.get("variants", [])
            variant = variants[0] if variants else {}

            # Collect variant code for price lookup
            if variant.get("code"):
                variant_codes.append(variant["code"])

            # Stock from variant
            in_stock = variant.get("inStock", 0) > 0 if isinstance(variant.get("inStock"), int) else True

            results.append(SearchResult(
                sku=item.get("sku", ""),
                description=f"{item.get('brand', '')} {item.get('name', '')}".strip(),
                price_cents=None,  # Will be populated after price fetch
                pack_size=variant.get("weight") or item.get("weightDescription"),
                pack_unit=variant.get("primaryUnitOfMeasureCode", "CS"),
                in_stock=in_stock,
                image_url=item.get("imageUrl"),
                category=item.get("category"),
            ))

        return results, variant_codes

    async def get_prices(self, product_codes: list[str]) -> dict[str, int]:
        """Fetch prices for products.

        Args:
            product_codes: List of product codes (JDE_{sku}-{bu} format)

        Returns:
            Dict mapping product code to price in cents
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        # Build price request
        variants = []
        for code in product_codes:
            variants.append({
                "code": code,
                "productKey": None,
                "productClassificationCode": None,
                "uom": "CS",
                "checkAvailabilityFlag": True,
                "chefItemFlag": False,
                "bto": False,
                "supermarket": False,
                "specialOrderFlag": False,
                "stockingType": "P",
                "vendorId": None,
                "businessUnitId": self.business_unit,
            })

        try:
            response = await client.post(
                f"{self.base_url}/web-api/product/prices",
                json={"variants": variants},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Metro Wholesale price fetch failed: {response.status_code}")
                return {}

            prices = {}
            for item in response.json():
                code = item.get("code", "")
                primary_price = item.get("primaryUnitPrice", {})
                price_str = primary_price.get("price", "$0.00")
                prices[code] = self._parse_price(price_str)

            return prices

        except Exception as e:
            logger.exception(f"Metro Wholesale price fetch error: {e}")
            return {}

    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Add item to cart.

        Args:
            sku: Product SKU
            quantity: Quantity to add

        Returns:
            True if successful
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        product_code = self._make_product_code(sku)

        try:
            response = await client.post(
                f"{self.base_url}/web-api/cart/add",
                json=[{
                    "code": product_code,
                    "metadata": {
                        "unitOfMeasure": "CS",
                        "productKey": None,
                        "productClassificationCode": None,
                        "chefItemFlag": False,
                        "bto": False,
                        "supermarket": False,
                        "stockingType": "P",
                        "lineType": "S",
                        "vendorId": None,
                        "productionItem": False,
                        "orderCutoffOverride": None,
                    },
                    "isReserve": False,
                    "quantity": quantity,
                }],
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Metro Wholesale add to cart error: {e}")
            return False

    async def get_cart(self) -> Cart:
        """Get current cart contents.

        Returns:
            Cart with items and totals
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/web-api/cart",
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                return Cart(items=[], subtotal_cents=0, total_cents=0)

            data = response.json()
            self._cart_id = data.get("id")

            items = []
            subtotal = 0

            # Cart has cartGroups -> subCarts -> lines structure
            for group in data.get("cartGroups", []):
                for subcart in group.get("subCarts", []):
                    # Note: API uses "lines" not "lineItems"
                    for line in subcart.get("lines", []):
                        price_cents = self._parse_price(line.get("unitPrice", "$0"))
                        # Use totalPrice or totalPriceDecimal for extended price
                        extended_str = line.get("totalPrice") or line.get("totalPriceDecimal") or "$0"
                        if isinstance(extended_str, (int, float)):
                            extended = int(float(extended_str) * 100)
                        else:
                            extended = self._parse_price(str(extended_str))

                        items.append(CartItem(
                            sku=line.get("productSku") or line.get("code", ""),
                            description=line.get("description") or line.get("productTitle", ""),
                            quantity=int(line.get("quantity", 0)),
                            unit_price_cents=price_cents,
                            extended_price_cents=extended,
                            product_id=str(line.get("id", "")),
                        ))
                        subtotal += extended

            return Cart(
                items=items,
                subtotal_cents=subtotal,
                total_cents=subtotal,
                cart_id=str(self._cart_id) if self._cart_id else None,
            )

        except Exception as e:
            logger.exception(f"Metro Wholesale get cart error: {e}")
            return Cart(items=[], subtotal_cents=0, total_cents=0)

    async def clear_cart(self) -> bool:
        """Clear all items from cart.

        Returns:
            True if successful
        """
        cart = await self.get_cart()
        if not cart.items:
            return True

        success = True
        for item in cart.items:
            if item.product_id:
                if not await self._remove_cart_item(int(item.product_id)):
                    success = False

        return success

    async def _remove_cart_item(self, line_id: int) -> bool:
        """Remove a single item from cart."""
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/web-api/cart/remove-item",
                json={
                    "lineId": line_id,
                    "businessUnitId": self.business_unit,
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Metro Wholesale remove item error: {e}")
            return False

    async def get_delivery_dates(self) -> list[datetime]:
        """Get available delivery dates from cart.

        Delivery dates are returned in the cart response.

        Returns:
            List of available delivery dates
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/web-api/cart",
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                return []

            data = response.json()
            dates = []

            # Extract delivery dates from cart structure
            for group in data.get("cartGroups", []):
                for subcart in group.get("subCarts", []):
                    delivery_info = subcart.get("deliveryInformation", {})
                    for date_info in delivery_info.get("deliveryDates", []):
                        date_str = date_info.get("date")
                        if date_str:
                            try:
                                dates.append(datetime.fromisoformat(date_str))
                            except ValueError:
                                continue

            return sorted(set(dates))

        except Exception as e:
            logger.exception(f"Metro Wholesale get delivery dates error: {e}")
            return []

    async def set_delivery_date(self, delivery_date: datetime) -> bool:
        """Set delivery date for cart.

        Args:
            delivery_date: Desired delivery date

        Returns:
            True if successful
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/web-api/cart/update/deliveryDate",
                json={
                    "expectedDeliveryDate": delivery_date.strftime("%Y-%m-%d"),
                    "erpExpectedDeliveryDate": delivery_date.strftime("%Y-%m-%d"),
                    "orderCutoffOverride": None,
                    "businessUnitId": self.business_unit,
                    "isJIT": False,
                    "vendorId": None,
                    "shippingItem": None,
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            return response.status_code == 200

        except Exception as e:
            logger.exception(f"Metro Wholesale set delivery date error: {e}")
            return False
