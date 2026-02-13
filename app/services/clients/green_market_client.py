"""Green Market API client (Ruby on Rails / LocalFoodHQ).

Cookie-based authentication with CSRF token required for form POSTs.

IMPORTANT: Order-first workflow - must create a purchase order
BEFORE adding items (unlike other distributors).
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

# Defaults are read from distributor api_config
_DEFAULT_BUYER_ID = 0
_DEFAULT_SELLER_ID = 0


class GreenMarketClient(DistributorApiClient):
    """Client for Green Market (LocalFoodHQ platform).

    Key differences from other distributors:
    1. ORDER-FIRST WORKFLOW: Must create purchase order before adding items
    2. CSRF tokens required for form POSTs (login, delivery date)
    3. JSON APIs work with session cookie only

    Workflow:
    1. Login (form POST with CSRF)
    2. Create purchase order with delivery date
    3. Add items to the order
    4. Optionally update delivery date (form POST with CSRF)
    """

    def __init__(self, db: Session, distributor_id: UUID):
        super().__init__(db, distributor_id)
        self._csrf_token: Optional[str] = None
        self._current_order_id: Optional[int] = None

    @property
    def base_url(self) -> str:
        return self.api_config.get("base_url", "")

    @property
    def buyer_id(self) -> int:
        return self.api_config.get("buyer_id", _DEFAULT_BUYER_ID)

    @property
    def seller_id(self) -> int:
        return self.api_config.get("seller_id", _DEFAULT_SELLER_ID)

    async def authenticate(self) -> bool:
        """Authenticate via Rails form POST.

        Requires CSRF token from login page.

        Returns:
            True if authentication succeeded
        """
        credentials = self._get_credentials()
        if not credentials:
            logger.error("No credentials found for Green Market")
            return False

        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            logger.error("Missing email or password in Green Market credentials")
            return False

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # First, get the login page to extract CSRF token
                login_page = await client.get(f"{self.base_url}/users/sign_in")
                csrf_token = self._extract_csrf_token(login_page.text)

                if not csrf_token:
                    logger.error("Could not extract CSRF token from Green Market login page")
                    return False

                # Submit login form
                response = await client.post(
                    f"{self.base_url}/users/sign_in",
                    data={
                        "authenticity_token": csrf_token,
                        "user[email]": email,
                        "user[password]": password,
                        "user[remember_me]": "0",
                        "commit": "Sign in",
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                # Check if login succeeded (should redirect to dashboard or home)
                if response.status_code == 200 and "/users/sign_in" not in str(response.url):
                    # Extract cookies
                    cookies = {}
                    for cookie in client.cookies.jar:
                        cookies[cookie.name] = cookie.value

                    # Save session
                    self._save_session(
                        cookies=cookies,
                        expires_at=datetime.utcnow() + timedelta(hours=24),
                    )
                    return True
                else:
                    logger.error(f"Green Market auth failed: redirected to {response.url}")
                    return False

        except Exception as e:
            logger.exception(f"Green Market authentication error: {e}")
            return False

    def _get_credentials(self) -> Optional[dict]:
        """Get credentials from Secret Manager or api_config."""
        return self.get_credentials()

    def _extract_csrf_token(self, html: str) -> Optional[str]:
        """Extract CSRF token from HTML page.

        Rails embeds it in: <meta name="csrf-token" content="...">

        Args:
            html: HTML page content

        Returns:
            CSRF token or None
        """
        match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        if match:
            return match.group(1)
        return None

    async def _get_csrf_token(self) -> Optional[str]:
        """Get fresh CSRF token from an authenticated page.

        Returns:
            CSRF token or None
        """
        if self._csrf_token:
            return self._csrf_token

        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/admin/dashboard",
                headers={"Accept": "text/html"},
            )

            if response.status_code == 200:
                self._csrf_token = self._extract_csrf_token(response.text)
                return self._csrf_token

        except Exception as e:
            logger.debug(f"Could not get CSRF token: {e}")

        return None

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

        # Get next delivery date for availability filtering
        delivery_date = datetime.now().strftime("%Y-%m-%d")

        try:
            response = await client.get(
                f"{self.base_url}/api/sellers/{self.seller_id}/products/",
                params={
                    "page": 1,
                    "per_page": limit,
                    "buyer_id": self.buyer_id,
                    "in_stock_on": delivery_date,
                    "text": query,
                    "sort_by": "popularity",
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                logger.warning(f"Green Market search failed: {response.status_code}")
                return []

            data = response.json()
            return self._parse_search_response(data)

        except Exception as e:
            logger.exception(f"Green Market search error: {e}")
            return []

    def _parse_search_response(self, data: dict) -> list[SearchResult]:
        """Parse search response to SearchResult list."""
        results = []

        # Response structure: {products: [...]}
        products = data.get("products", data) if isinstance(data, dict) else data

        if isinstance(products, list):
            items = products
        else:
            items = products.get("items", [])

        for item in items:
            # Get price - check final_price first (from search), then product_units
            price_cents = 0
            price_str = item.get("final_price") or item.get("price")
            if price_str:
                try:
                    price_cents = int(float(price_str) * 100)
                except (ValueError, TypeError):
                    pass

            # Fallback to product_units if available
            if not price_cents:
                units = item.get("product_units", [])
                if units:
                    price = units[0].get("price", 0)
                    try:
                        price_cents = int(float(price) * 100)
                    except (ValueError, TypeError):
                        pass

            # Get the product unit ID (needed for adding to cart)
            # Could be at top level (product_unit_id) or nested
            product_unit_id = str(item.get("product_unit_id") or item.get("id", ""))

            results.append(SearchResult(
                sku=product_unit_id,
                description=item.get("name", ""),
                price_cents=price_cents,
                pack_size=item.get("unit") or item.get("unit_description"),
                pack_unit=item.get("individual_unit_name") or item.get("unit_name"),
                in_stock=item.get("available", True) if "available" in item else item.get("published", True),
                image_url=item.get("product_photo", {}).get("small_url") if isinstance(item.get("product_photo"), dict) else item.get("image_url"),
                category=item.get("category_name"),
            ))

        return results

    async def _ensure_order_exists(self) -> Optional[int]:
        """Ensure we have a purchase order to add items to.

        Green Market requires creating an order BEFORE adding items.

        Returns:
            Order ID or None
        """
        if self._current_order_id:
            return self._current_order_id

        # Create a new purchase order
        return await self._create_order()

    async def _create_order(self, delivery_date: Optional[datetime] = None) -> Optional[int]:
        """Create a new purchase order.

        Args:
            delivery_date: Requested delivery date (defaults to tomorrow)

        Returns:
            New order ID or None
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        if delivery_date is None:
            delivery_date = datetime.now() + timedelta(days=1)

        try:
            response = await client.post(
                f"{self.base_url}/api/purchase_orders",
                json={
                    "purchase_order": {
                        "seller_id": self.seller_id,
                        "buyer_id": self.buyer_id,
                        "requested_on": delivery_date.strftime("%Y-%m-%d"),
                    }
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            if response.status_code in (200, 201):
                data = response.json()
                self._current_order_id = data.get("id")
                return self._current_order_id
            else:
                logger.error(f"Green Market create order failed: {response.status_code}")
                return None

        except Exception as e:
            logger.exception(f"Green Market create order error: {e}")
            return None

    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Add item to cart (purchase order).

        IMPORTANT: Requires an existing order. Creates one if needed.

        Args:
            sku: Product unit ID
            quantity: Quantity to add

        Returns:
            True if successful
        """
        order_id = await self._ensure_order_exists()
        if not order_id:
            logger.error("Could not get/create order for Green Market cart add")
            return False

        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/api/purchase_order_items",
                json={
                    "product_unit_id": int(sku),
                    "quantity": str(quantity),
                    "buyer_order_id": order_id,
                    "src": "api",
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            return response.status_code in (200, 201)

        except Exception as e:
            logger.exception(f"Green Market add to cart error: {e}")
            return False

    async def get_cart(self) -> Cart:
        """Get current cart (purchase order) contents.

        Returns:
            Cart with items and totals
        """
        if not self._current_order_id:
            return Cart(items=[], subtotal_cents=0, total_cents=0)

        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            # Get order details
            response = await client.get(
                f"{self.base_url}/api/purchase_orders/{self._current_order_id}",
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                return Cart(items=[], subtotal_cents=0, total_cents=0)

            data = response.json()
            return self._parse_order_to_cart(data)

        except Exception as e:
            logger.exception(f"Green Market get cart error: {e}")
            return Cart(items=[], subtotal_cents=0, total_cents=0)

    def _parse_order_to_cart(self, data: dict) -> Cart:
        """Parse order response to Cart."""
        items = []
        subtotal = 0

        for line in data.get("purchase_order_items", data.get("items", [])):
            product = line.get("product", {})
            unit = line.get("product_unit", {})

            price_cents = int(float(unit.get("price", 0)) * 100)
            quantity = int(line.get("quantity", 0))
            extended = price_cents * quantity

            items.append(CartItem(
                sku=str(unit.get("id", "")),
                description=product.get("name", ""),
                quantity=quantity,
                unit_price_cents=price_cents,
                extended_price_cents=extended,
                product_id=str(line.get("id", "")),
            ))
            subtotal += extended

        total = int(float(data.get("total", subtotal / 100)) * 100)

        return Cart(
            items=items,
            subtotal_cents=subtotal,
            total_cents=total,
            cart_id=str(data.get("id", "")),
        )

    async def clear_cart(self) -> bool:
        """Clear all items from cart.

        For Green Market, this means deleting all items from the order.

        Returns:
            True if successful
        """
        if not self._current_order_id:
            return True

        cart = await self.get_cart()
        if not cart.items:
            return True

        # Would need to delete each item
        # API endpoint TBD based on captured traffic
        logger.warning("Green Market clear_cart not fully implemented")
        return False

    async def set_delivery_date(self, delivery_date: datetime) -> bool:
        """Set delivery date for order.

        Requires CSRF token (form POST).

        Args:
            delivery_date: Desired delivery date

        Returns:
            True if successful
        """
        if not self._current_order_id:
            logger.warning("No order to set delivery date for")
            return False

        csrf_token = await self._get_csrf_token()
        if not csrf_token:
            logger.error("Could not get CSRF token for delivery date update")
            return False

        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/admin/purchase_orders/{self._current_order_id}/request_delivery_on",
                data={
                    "authenticity_token": csrf_token,
                    "requested_on": delivery_date.strftime("%Y-%m-%d"),
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            # Clear cached CSRF token as it may be invalidated
            self._csrf_token = None

            return response.status_code in (200, 302)  # 302 = redirect on success

        except Exception as e:
            logger.exception(f"Green Market set delivery date error: {e}")
            return False

    async def get_delivery_dates(self) -> list[datetime]:
        """Get available delivery dates.

        Green Market delivery dates are shown in the checkout UI.
        May need to parse from HTML or find an API.

        Returns:
            List of available delivery dates
        """
        # For now, generate reasonable dates (Tue/Thu delivery typical for local)
        dates = []
        today = datetime.now()

        for i in range(1, 15):
            date = today + timedelta(days=i)
            # Assume delivery on weekdays
            if date.weekday() < 5:  # Mon-Fri
                dates.append(date)

        return dates[:7]  # Return next 7 delivery days
