"""Farm Direct API client (NetSuite SuiteCommerce).

Cookie-based authentication with SHORT session timeout (~5 minutes).
Requires heartbeat mechanism to keep session alive.

The good news: login is trivially simple (one JSON POST), so
re-authentication is cheap.
"""
import logging
import time
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
_DEFAULT_COMPANY_ID = ""
_DEFAULT_SITE_ID = ""
_DEFAULT_PRICE_LEVEL = ""

# Session timeout is ~5 minutes, heartbeat at 2 minutes
HEARTBEAT_INTERVAL = 120  # seconds


class FarmDirectClient(DistributorApiClient):
    """Client for Farm Direct (NetSuite SuiteCommerce).

    IMPORTANT: Sessions timeout quickly (~5 minutes). This client
    implements a heartbeat pattern to keep sessions alive during
    cart building operations.

    The login is the simplest of all distributors (one JSON POST),
    so re-authentication is cheap and transparent.
    """

    def __init__(self, db: Session, distributor_id: UUID):
        super().__init__(db, distributor_id)
        self._last_activity: float = 0

    @property
    def base_url(self) -> str:
        return self.api_config.get("base_url", "")

    @property
    def company_id(self) -> str:
        return self.api_config.get("company_id", _DEFAULT_COMPANY_ID)

    @property
    def site_id(self) -> str:
        return self.api_config.get("site_id", _DEFAULT_SITE_ID)

    @property
    def price_level(self) -> str:
        return self.api_config.get("price_level", _DEFAULT_PRICE_LEVEL)

    async def authenticate(self) -> bool:
        """Authenticate via simple JSON POST.

        This is the simplest login of all distributors:
        POST {email, password, redirect} -> cookies set.

        Returns:
            True if authentication succeeded
        """
        credentials = self._get_credentials()
        if not credentials:
            logger.error("No credentials found for Farm Direct")
            return False

        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            logger.error("Missing email or password in Farm Direct credentials")
            return False

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.post(
                    f"{self.base_url}/scs/services/Account.Login.Service.ss",
                    params={"n": self.site_id, "c": self.company_id},
                    json={
                        "email": email,
                        "password": password,
                        "redirect": "true",
                    },
                    headers={
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-SC-Touchpoint": "checkout",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )

                if response.status_code == 200:
                    # Extract cookies
                    cookies = {}
                    for cookie in client.cookies.jar:
                        cookies[cookie.name] = cookie.value

                    # Save session with short expiry (5 minutes)
                    self._save_session(
                        cookies=cookies,
                        expires_at=datetime.utcnow() + timedelta(minutes=5),
                    )
                    self._last_activity = time.time()
                    return True
                else:
                    logger.error(
                        f"Farm Direct auth failed: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.exception(f"Farm Direct authentication error: {e}")
            return False

    def _get_credentials(self) -> Optional[dict]:
        """Get credentials from Secret Manager or api_config."""
        return self.get_credentials()

    async def _ensure_session_fresh(self) -> bool:
        """Ensure session is fresh, using heartbeat or re-auth.

        Called before any API operation. If session may have timed out,
        sends a heartbeat. If heartbeat fails, re-authenticates.

        Returns:
            True if session is valid
        """
        # Check if we need a heartbeat
        if time.time() - self._last_activity > HEARTBEAT_INTERVAL:
            # Try heartbeat
            if await self._heartbeat():
                return True
            # Heartbeat failed, re-authenticate
            logger.info("Farm Direct session expired, re-authenticating")
            return await self.authenticate()

        return True

    async def _heartbeat(self) -> bool:
        """Send lightweight request to keep session alive.

        Uses ProductList.Service.ss as it's tiny and doesn't modify state.

        Returns:
            True if session is still valid
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/scs/services/ProductList.Service.ss",
                params={"c": self.company_id, "n": self.site_id},
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                self._last_activity = time.time()
                return True

            # Check for session timeout error
            try:
                data = response.json()
                if data.get("errorCode") == "ERR_USER_SESSION_TIMED_OUT":
                    return False
            except Exception:
                pass

            return response.status_code == 200

        except Exception as e:
            logger.debug(f"Farm Direct heartbeat failed: {e}")
            return False

    async def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Search product catalog.

        Farm Direct includes prices in search results (no separate price API).
        Uses offset-based pagination (infinite scroll style).

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            List of search results with prices
        """
        await self._ensure_session_fresh()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/scs/searchApi.ssp",
                params={
                    "__country": "US",
                    "__currency": "USD",
                    "__fieldset": "search",
                    "__include": "facets",
                    "__language": "en",
                    "__pricelevel": self.price_level,
                    "__use_pcv": "T",
                    "c": self.company_id,
                    "n": self.site_id,
                    "limit": limit,
                    "offset": 0,
                    "q": query,
                    "sort": "relevance:asc",
                },
                headers={"Accept": "application/json"},
            )

            self._last_activity = time.time()

            if response.status_code != 200:
                # Check for session timeout
                if await self._handle_session_error(response):
                    # Retry after re-auth
                    return await self.search(query, limit)
                return []

            data = response.json()

            # Check for error response
            if "errorCode" in data:
                if await self._handle_session_error_data(data):
                    return await self.search(query, limit)
                return []

            return self._parse_search_response(data)

        except Exception as e:
            logger.exception(f"Farm Direct search error: {e}")
            return []

    def _parse_search_response(self, data: dict) -> list[SearchResult]:
        """Parse search response to SearchResult list."""
        results = []
        items = data.get("items", [])

        for item in items:
            # Price may be in onlinecustomerprice or pricelevel fields
            price = 0
            if "onlinecustomerprice" in item:
                try:
                    price = int(float(item["onlinecustomerprice"]) * 100)
                except (ValueError, TypeError):
                    pass

            results.append(SearchResult(
                sku=str(item.get("internalid", "")),
                description=item.get("displayname", item.get("storedisplayname2", "")),
                price_cents=price,
                pack_size=item.get("custitem_pack_size"),
                pack_unit=item.get("saleunit"),
                in_stock=item.get("isinstock", True),
                image_url=item.get("itemimages_detail", {}).get("url"),
                category=item.get("commercecategoryname"),
            ))

        return results

    async def _handle_session_error(self, response: httpx.Response) -> bool:
        """Handle potential session timeout from HTTP response.

        Returns True if re-authenticated successfully.
        """
        try:
            data = response.json()
            return await self._handle_session_error_data(data)
        except Exception:
            return False

    async def _handle_session_error_data(self, data: dict) -> bool:
        """Handle potential session timeout from JSON response.

        Returns True if re-authenticated successfully.
        """
        if data.get("errorCode") == "ERR_USER_SESSION_TIMED_OUT":
            logger.info("Farm Direct session timed out, re-authenticating")
            return await self.authenticate()
        return False

    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Add item to cart.

        Args:
            sku: Product internal ID (integer as string)
            quantity: Quantity to add

        Returns:
            True if successful
        """
        await self._ensure_session_fresh()
        client = await self.get_http_client()

        try:
            response = await client.post(
                f"{self.base_url}/scs/services/LiveOrder.Line.Service.ss",
                params={"c": self.company_id, "n": self.site_id},
                json=[{
                    "item": {"internalid": int(sku)},
                    "quantity": quantity,
                    "options": [],
                    "location": "",
                    "fulfillmentChoice": "ship",
                    "freeGift": False,
                }],
                headers={
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-SC-Touchpoint": "shopping",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            self._last_activity = time.time()

            if response.status_code == 200:
                return True

            # Check for session timeout
            if await self._handle_session_error(response):
                return await self.add_to_cart(sku, quantity)

            return False

        except Exception as e:
            logger.exception(f"Farm Direct add to cart error: {e}")
            return False

    async def get_cart(self) -> Cart:
        """Get current cart contents.

        Returns:
            Cart with items and totals
        """
        await self._ensure_session_fresh()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/scs/services/LiveOrder.Service.ss",
                params={
                    "c": self.company_id,
                    "n": self.site_id,
                    "cur": "1",
                    "internalid": "cart",
                },
                headers={"Accept": "application/json"},
            )

            self._last_activity = time.time()

            if response.status_code != 200:
                return Cart(items=[], subtotal_cents=0, total_cents=0)

            data = response.json()

            # Check for error
            if "errorCode" in data:
                if await self._handle_session_error_data(data):
                    return await self.get_cart()
                return Cart(items=[], subtotal_cents=0, total_cents=0)

            return self._parse_cart_response(data)

        except Exception as e:
            logger.exception(f"Farm Direct get cart error: {e}")
            return Cart(items=[], subtotal_cents=0, total_cents=0)

    def _parse_cart_response(self, data: dict) -> Cart:
        """Parse cart response to Cart."""
        items = []
        subtotal = 0

        for line in data.get("lines", []):
            item = line.get("item", {})
            price_cents = int(float(line.get("rate", 0)) * 100)
            extended = int(float(line.get("amount", 0)) * 100)

            items.append(CartItem(
                sku=str(item.get("internalid", "")),
                description=item.get("displayname", ""),
                quantity=int(line.get("quantity", 0)),
                unit_price_cents=price_cents,
                extended_price_cents=extended,
                product_id=str(line.get("internalid", "")),
            ))
            subtotal += extended

        total = int(float(data.get("summary", {}).get("total", 0)) * 100)

        return Cart(
            items=items,
            subtotal_cents=subtotal,
            total_cents=total,
            cart_id=str(data.get("internalid", "")),
        )

    async def clear_cart(self) -> bool:
        """Clear all items from cart.

        Farm Direct may not have a direct clear endpoint.
        Remove items one by one.

        Returns:
            True if successful
        """
        cart = await self.get_cart()
        if not cart.items:
            return True

        # Would need to find the remove endpoint or update quantities to 0
        # For now, return False if cart has items
        logger.warning("Farm Direct clear_cart not fully implemented")
        return False

    async def get_delivery_dates(self) -> list[datetime]:
        """Get available delivery dates.

        Delivery dates are in the checkout environment.

        Returns:
            List of available delivery dates
        """
        await self._ensure_session_fresh()
        client = await self.get_http_client()

        try:
            response = await client.get(
                f"{self.base_url}/scs/services/CheckoutEnvironment.Service.ss",
                params={
                    "lang": "en_US",
                    "cur": "USD",
                    "X-SC-Touchpoint": "checkout",
                },
                headers={"Accept": "application/json"},
            )

            self._last_activity = time.time()

            if response.status_code != 200:
                return []

            data = response.json()

            # Extract delivery dates from checkout environment
            # Structure depends on actual response
            dates = []
            shipping = data.get("shipping", {})
            for method in shipping.get("methods", []):
                for date_info in method.get("deliveryDates", []):
                    date_str = date_info.get("date")
                    if date_str:
                        try:
                            dates.append(datetime.fromisoformat(date_str))
                        except ValueError:
                            continue

            return sorted(set(dates))

        except Exception as e:
            logger.exception(f"Farm Direct get delivery dates error: {e}")
            return []
