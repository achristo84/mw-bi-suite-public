"""Valley Foods platform client for multi-distributor OAuth2 API.

This client serves distributors that share the same B2C OAuth2 platform
but have separate catalogs, pricing, and orders. One login provides
access to all distributors on the platform - switch via the CustomerId parameter.

Authentication Flow:
1. Try stored session (check expiry)
2. Try refresh token (API call)
3. Try browser auto-login (SeleniumBase UC + Playwright CDP)
4. Fail with actionable error

The browser auto-login is transparent to callers - it runs when needed
and captures new tokens automatically.
"""
import logging
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

# Common request parameters
BUSINESS_UNIT_KEY = 3


class ValleyFoodsClient(DistributorApiClient):
    """Client for Valley Foods platform (multi-distributor OAuth2).

    Multiple distributors share:
    - Login credentials (one account)
    - Bearer token (one token works for all)
    - API endpoints (same base URL)

    Each distributor has separate:
    - Product catalogs
    - Pricing
    - Delivery schedules
    - Orders/carts
    """

    def __init__(self, db: Session, distributor_id: UUID, customer_id: Optional[str] = None):
        """Initialize Valley Foods client.

        Args:
            db: Database session
            distributor_id: UUID of the distributor
            customer_id: Override customer ID (for testing)
        """
        super().__init__(db, distributor_id)
        self._customer_id = customer_id
        self._active_order_id: Optional[str] = None
        self._operation_company_number: Optional[str] = None

    @property
    def customer_id(self) -> str:
        """Get the CustomerId for API requests.

        Reads from the distributor's api_config JSONB column.
        Set customer_id in the distributor's api_config to configure.
        """
        if self._customer_id:
            return self._customer_id

        config = self.api_config
        if "customer_id" in config:
            return config["customer_id"]
        raise ValueError(
            f"Cannot determine CustomerId for distributor {self.distributor.name}. "
            "Set customer_id in the distributor's api_config column."
        )

    @property
    def base_url(self) -> str:
        """Valley Foods API base URL. Must be set in distributor api_config."""
        url = self.api_config.get("base_url", "")
        if not url:
            raise ValueError(
                f"No base_url configured for distributor {self.distributor.name}. "
                "Set base_url in the distributor's api_config column."
            )
        return url

    @property
    def operation_company_number(self) -> str:
        """Get the OperationCompanyNumber for API requests.

        Each distributor on the platform has a different operation company number.
        Must be configured in the distributor's api_config.
        """
        if self._operation_company_number:
            return self._operation_company_number

        config = self.api_config
        if "operation_company_number" in config:
            self._operation_company_number = config["operation_company_number"]
            return self._operation_company_number

        raise ValueError(
            f"No operation_company_number configured for distributor {self.distributor.name}. "
            "Set operation_company_number in the distributor's api_config column."
        )

    async def authenticate(self) -> bool:
        """Authenticate via Azure B2C OAuth2.

        Valley Foods uses PKCE authorization code flow, which requires browser login.
        Authentication attempts in order:

        1. Refresh token (from session headers): Fastest, no browser needed
        2. Token file (from previous capture): Use if still valid, refresh if not
        3. Browser auto-login: Automated login via SeleniumBase UC + Playwright CDP
        4. Fail with actionable error

        Returns:
            True if authentication succeeded
        """
        # 1. Try to use refresh token from current session
        session = self._load_session()
        if session and session.headers and session.headers.get("refresh_token"):
            if await self._refresh_access_token(session.headers["refresh_token"]):
                return True
            logger.info("Session refresh token expired, trying alternatives")

        # 2. Try to use refresh token from credentials (Secret Manager)
        credentials = self._get_credentials()
        if credentials and credentials.get("refresh_token"):
            if await self._refresh_access_token(credentials["refresh_token"]):
                return True
            logger.info("Credentials refresh token expired, trying token file")

        # 3. Check for token file (from browser capture)
        token_data = self._load_token_file()
        if token_data:
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            # Check if token is still valid
            captured_at = token_data.get("captured_at", "")
            if captured_at:
                try:
                    captured_time = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
                    age_seconds = (datetime.now(captured_time.tzinfo) - captured_time).total_seconds()
                    if age_seconds < expires_in - 60:
                        # Token still valid
                        self._save_session(
                            auth_token=f"Bearer {access_token}",
                            headers={"refresh_token": refresh_token} if refresh_token else None,
                            expires_at=datetime.utcnow() + timedelta(seconds=expires_in - age_seconds - 60),
                        )
                        logger.info("Using captured access token")
                        return True
                except Exception as e:
                    logger.debug(f"Could not parse captured_at: {e}")

            # Token expired, try to refresh
            if refresh_token:
                if await self._refresh_access_token(refresh_token):
                    return True
                logger.info("Token file refresh failed, trying browser auto-login")

        # 4. Try browser auto-login (requires credentials with email/password)
        if credentials and credentials.get("email") and credentials.get("password"):
            auth_result = await self._browser_auto_login(
                email=credentials["email"],
                password=credentials["password"],
            )
            if auth_result:
                return True
            logger.warning("Browser auto-login failed")

        # All methods failed
        logger.error(
            "Valley Foods authentication failed. Ensure credentials are configured in "
            "Secret Manager with email, password, "
            "and optionally refresh_token."
        )
        return False

    async def _browser_auto_login(self, email: str, password: str) -> bool:
        """Authenticate using browser automation.

        Uses browser automation to complete the OAuth2 login flow
        and capture tokens. Requires platform-specific automation scripts.

        Args:
            email: Login email
            password: Login password

        Returns:
            True if login succeeded and tokens were captured
        """
        # Browser auto-login requires platform-specific automation scripts.
        # Implement per deployment as needed.
        logger.warning(
            "Browser auto-login not available. "
            "Ensure a valid refresh_token is stored in credentials."
        )
        return False

    def _load_token_file(self) -> Optional[dict]:
        """Load tokens from browser capture files.

        Checks for token files saved by browser automation scripts.
        """
        import os
        import json

        # Check for token file path in api_config
        token_path = self.api_config.get("token_file_path")
        if token_path and os.path.exists(token_path):
            try:
                with open(token_path) as f:
                    data = json.load(f)
                    logger.debug(f"Loaded tokens from {token_path}")
                    return data
            except Exception as e:
                logger.debug(f"Could not load token file {token_path}: {e}")

        return None

    @property
    def oauth_config(self) -> dict:
        """Get OAuth2 configuration from distributor api_config."""
        config = self.api_config
        return {
            "tenant": config.get("oauth_tenant", ""),
            "policy": config.get("oauth_policy", ""),
            "client_id": config.get("oauth_client_id", ""),
            "scope": config.get("oauth_scope", "openid profile offline_access"),
        }

    async def _refresh_access_token(self, refresh_token: str) -> bool:
        """Use refresh token to get a new access token.

        Args:
            refresh_token: The refresh token

        Returns:
            True if refresh succeeded
        """
        oauth = self.oauth_config
        token_url = (
            f"https://{oauth['tenant']}.b2clogin.com/"
            f"{oauth['tenant']}.onmicrosoft.com/"
            f"{oauth['policy']}/oauth2/v2.0/token"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": oauth["client_id"],
                        "refresh_token": refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")

                    # Azure B2C may only return id_token (not access_token) on refresh
                    # depending on policy configuration. We need access_token for API calls.
                    if not access_token:
                        logger.warning(
                            "Valley Foods refresh returned 200 but no access_token "
                            "(only id_token). Need browser re-auth."
                        )
                        return False

                    expires_in = token_data.get("expires_in", 3600)
                    new_refresh_token = token_data.get("refresh_token", refresh_token)

                    # Save session
                    self._save_session(
                        auth_token=f"Bearer {access_token}",
                        headers={"refresh_token": new_refresh_token},
                        expires_at=datetime.utcnow() + timedelta(seconds=expires_in - 60),
                    )
                    logger.info("Valley Foods token refreshed successfully")
                    return True
                else:
                    logger.warning(f"Valley Foods token refresh failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.exception(f"Valley Foods token refresh error: {e}")
            return False

    def _get_credentials(self) -> Optional[dict]:
        """Get credentials from Secret Manager or api_config."""
        return self.get_credentials()

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /Product/V1/SearchProductCatalog)
            json_data: JSON body for POST requests
            params: Query parameters for GET requests

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: On non-2xx response
        """
        await self.ensure_authenticated()
        client = await self.get_http_client()

        url = f"{self.base_url}{endpoint}"

        # Merge headers - don't override Authorization from client
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": self.api_config.get("origin_url", self.base_url),
            "Referer": self.api_config.get("referer_url", f"{self.base_url}/"),
        }
        # Copy Authorization from client headers if present
        if "Authorization" in client.headers:
            request_headers["Authorization"] = client.headers["Authorization"]

        response = await client.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            headers=request_headers,
        )

        response.raise_for_status()
        return response.json()

    async def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Search product catalog.

        Args:
            query: Search term
            limit: Maximum results (default 50)

        Returns:
            List of search results with prices
        """
        # Get next delivery date for search context
        delivery_date = await self._get_next_delivery_date()

        response = await self._api_request(
            "POST",
            "/ProductCatalog/V1/SearchProductCatalog",
            json_data={
                "BusinessUnitKey": BUSINESS_UNIT_KEY,
                "OperationCompanyNumber": self.operation_company_number,
                "CustomerId": self.customer_id,
                "DeliveryDate": delivery_date.isoformat() if delivery_date else None,
                "CurrentPageNumber": 0,
                "PageSize": limit,
                "QueryText": query,
                "Skip": 0,
                "OrderEntryHeaderId": "00000000-0000-0000-0000-000000000000",
                "LoadPricing": True,
                "AdvanceFilter": {},
            },
        )

        if not response.get("IsSuccess"):
            logger.warning(f"Valley Foods search failed: {response.get('ErrorMessages')}")
            return []

        result = response.get("ResultObject", {})
        products = result.get("CatalogProducts", [])

        if not products:
            return []

        # Valley Foods requires separate price lookup - LoadPricing returns 0
        product_keys = [p.get("ProductKey") for p in products if p.get("ProductKey")]
        prices = await self.get_prices(product_keys) if product_keys else {}

        # Parse products with prices
        results = []
        for p in products:
            search_result = self._parse_product(p)
            # Merge in price from separate lookup
            product_key = p.get("ProductKey", "").lower()
            if product_key in prices:
                search_result.price_cents = prices[product_key]
            results.append(search_result)

        return results

    def _parse_product(self, product: dict) -> SearchResult:
        """Parse Valley Foods product to SearchResult."""
        # Get pack size from first UOM
        pack_sizes = product.get("ProductPackSizes", [])
        uom_list = product.get("UnitOfMeasureOrderQuantities", [])

        pack_size = pack_sizes[0] if pack_sizes else None
        pack_unit = None
        price_cents = None

        # Extract price from UOM data (when LoadPricing=True)
        if uom_list:
            first_uom = uom_list[0]
            pack_unit = first_uom.get("UnitOfMeasureAbbreviation", "CS")
            # Price is in dollars, convert to cents
            price_dollars = first_uom.get("Price") or first_uom.get("CustomerPrice")
            if price_dollars:
                price_cents = int(float(price_dollars) * 100)

        # Fallback: check product-level price
        if price_cents is None:
            price_dollars = product.get("Price") or product.get("CustomerPrice")
            if price_dollars:
                price_cents = int(float(price_dollars) * 100)

        return SearchResult(
            sku=product.get("ProductNumber", ""),
            description=product.get("ProductDescription", ""),
            price_cents=price_cents,
            pack_size=pack_size,
            pack_unit=pack_unit,
            in_stock=not product.get("IsOutOfStock", False),
            product_url=None,
            image_url=product.get("ProductImageUrlThumbnail"),
            category=product.get("ProductCategory"),
            product_id=product.get("ProductKey"),  # Required for add_to_cart
        )

    async def get_prices(self, product_keys: list[str]) -> dict[str, int]:
        """Fetch prices for products.

        Args:
            product_keys: List of ProductKey UUIDs

        Returns:
            Dict mapping ProductKey to price in cents
        """
        if not product_keys:
            return {}

        delivery_date = await self._get_next_delivery_date()

        # Build price requests
        price_requests = [
            {"ProductKey": pk, "UnitOfMeasureType": 0}  # 0 = case
            for pk in product_keys
        ]

        response = await self._api_request(
            "POST",
            "/CustomerProductPrice/V1/GetCustomerProductPrice",
            json_data={
                "BusinessUnitKey": BUSINESS_UNIT_KEY,
                "OperationCompanyNumber": self.operation_company_number,
                "CustomerId": self.customer_id,
                "DeliveryDate": delivery_date.isoformat() if delivery_date else None,
                "CustomerProductPriceRequests": price_requests,
                "IgnoreRetry": False,
            },
        )

        if not response.get("IsSuccess"):
            logger.warning(f"Valley Foods price fetch failed: {response.get('ErrorMessages')}")
            return {}

        prices = {}
        for item in response.get("ResultObject", []):
            product_key = item.get("ProductKey", "").lower()
            price_dollars = item.get("Price", 0)
            # Convert dollars to cents
            prices[product_key] = int(price_dollars * 100)

        return prices

    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Add item to cart.

        Valley Foods uses "UpdateOrderEntryDetail" for both add and update (upsert).

        Args:
            sku: Product SKU (ProductNumber)
            quantity: Quantity to add

        Returns:
            True if successful
        """
        # First search for the product to get full details including ProductKey
        results = await self.search(sku, limit=1)
        if not results:
            logger.warning(f"Product {sku} not found in Valley Foods catalog")
            return False

        product = results[0]

        if not product.product_id:
            logger.warning(f"Product {sku} has no ProductKey, cannot add to cart")
            return False

        # Get or create active order
        order_id = await self._get_or_create_order()
        if not order_id:
            logger.error("Failed to get/create order for cart add")
            return False

        # Use price from search result, or 0 if not available
        price = product.price_cents / 100 if product.price_cents else 0

        try:
            response = await self._api_request(
                "POST",
                "/OrderEntryDetail/V1/UpdateOrderEntryDetail",
                json_data={
                    "OrderEntryHeaderId": order_id,
                    "BusinessUnitKey": BUSINESS_UNIT_KEY,
                    "BusinessUnitERPKey": BUSINESS_UNIT_KEY,
                    "CustomerId": self.customer_id,
                    "ProductKey": product.product_id,
                    "UnitOfMeasureType": 0,  # Case
                    "Quantity": quantity,
                    "Price": price,
                    "ProductNumber": sku,
                    "ProductDescription": product.description,
                    "ProductBrand": "",
                    "ProductPackSize": product.pack_size or "",
                    "ProductIsCatchWeight": False,
                    "ProductAverageWeight": 1,
                    "ShipLaterMaxEstimatedDays": 0,
                    "CutoffDateTime": None,
                    "UOMOrderQuantityAlertThresholdMin": 0,
                    "UOMOrderQuantityAlertThresholdMax": 0,
                },
            )

            return response.get("IsSuccess", False)

        except Exception as e:
            logger.exception(f"Valley Foods add to cart error: {e}")
            return False

    async def get_cart(self) -> Cart:
        """Get current cart contents.

        Note: Valley Foods's GetOrderEntryDetails endpoint may return 404 for some
        accounts/tokens. In this case, we return cart totals from GetOrder
        without line item details.

        Returns:
            Cart with items and totals
        """
        order_id = await self._get_active_order_id()
        if not order_id:
            return Cart(items=[], subtotal_cents=0, total_cents=0)

        try:
            response = await self._api_request(
                "GET",
                "/Order/V1/GetOrder",
                params={"orderEntryHeaderId": order_id},
            )

            if not response.get("IsSuccess"):
                return Cart(items=[], subtotal_cents=0, total_cents=0)

            order = response.get("ResultObject", {})
            total_cents = int(order.get("TotalOrderPrice", 0) * 100)
            total_lines = order.get("TotalLines", 0)
            total_quantity = order.get("TotalQuantity", 0)

            # Try to get order line details (may 404 for some accounts)
            items = []
            try:
                lines_response = await self._api_request(
                    "GET",
                    "/OrderEntryDetail/V1/GetOrderEntryDetails",
                    params={"orderEntryHeaderId": order_id},
                )

                if lines_response.get("IsSuccess"):
                    for line in lines_response.get("ResultObject", []):
                        items.append(CartItem(
                            sku=line.get("ProductNumber", ""),
                            description=line.get("ProductDescription", ""),
                            quantity=line.get("Quantity", 0),
                            unit_price_cents=int(line.get("Price", 0) * 100),
                            extended_price_cents=int(line.get("ExtendedPrice", 0) * 100),
                            product_id=line.get("ProductKey"),
                        ))
            except Exception as e:
                # GetOrderEntryDetails may 404 for some accounts
                # Use order summary instead
                logger.debug(f"Could not get line items (using summary): {e}")
                if total_lines > 0:
                    # Create placeholder item showing cart has items
                    items.append(CartItem(
                        sku="(items in cart)",
                        description=f"{total_lines} item(s), {total_quantity} total qty",
                        quantity=total_quantity,
                        unit_price_cents=None,
                        extended_price_cents=total_cents,
                        product_id=None,
                    ))

            return Cart(
                items=items,
                subtotal_cents=total_cents,
                total_cents=total_cents,
                cart_id=order_id,
            )

        except Exception as e:
            logger.exception(f"Valley Foods get cart error: {e}")
            return Cart(items=[], subtotal_cents=0, total_cents=0)

    async def clear_cart(self) -> bool:
        """Clear all items from cart.

        Valley Foods doesn't have a direct clear endpoint.
        We need to delete each line item individually.

        Returns:
            True if successful
        """
        cart = await self.get_cart()
        if not cart.items:
            return True

        success = True
        for item in cart.items:
            if not await self._remove_cart_item(item.product_id):
                success = False

        return success

    async def _remove_cart_item(self, product_key: str) -> bool:
        """Remove a single item from cart."""
        order_id = self._active_order_id
        if not order_id or not product_key:
            return False

        try:
            response = await self._api_request(
                "POST",
                "/OrderEntryDetail/V1/DeleteOrderEntryDetail",
                json_data={
                    "OrderEntryHeaderId": order_id,
                    "ProductKey": product_key,
                },
            )
            return response.get("IsSuccess", False)
        except Exception as e:
            logger.exception(f"Valley Foods remove item error: {e}")
            return False

    async def get_delivery_dates(self) -> list[datetime]:
        """Get available delivery dates.

        Returns:
            List of available delivery dates
        """
        try:
            response = await self._api_request(
                "GET",
                "/Customer/V1/GetCustomerDeliveryDates",
                params={"customerId": self.customer_id},
            )

            if not response.get("IsSuccess"):
                return []

            dates = []
            for date_str in response.get("ResultObject", []):
                try:
                    dates.append(datetime.fromisoformat(date_str.replace("Z", "+00:00")))
                except ValueError:
                    continue

            return dates

        except Exception as e:
            logger.exception(f"Valley Foods get delivery dates error: {e}")
            return []

    async def _get_next_delivery_date(self) -> Optional[datetime]:
        """Get the next available delivery date."""
        dates = await self.get_delivery_dates()
        if dates:
            return dates[0]
        return None

    async def _get_active_order_id(self) -> Optional[str]:
        """Get the active order ID if one exists."""
        if self._active_order_id:
            return self._active_order_id

        try:
            response = await self._api_request(
                "GET",
                "/OrderEntryHeader/V1/GetActiveOrder",
                params={"CustomerId": self.customer_id},
            )

            if response.get("IsSuccess") and response.get("ResultObject"):
                self._active_order_id = response["ResultObject"].get("OrderEntryHeaderId")
                return self._active_order_id

        except Exception as e:
            logger.debug(f"No active order: {e}")

        return None

    async def _get_or_create_order(self) -> Optional[str]:
        """Get active order or create new one."""
        order_id = await self._get_active_order_id()
        if order_id:
            return order_id

        try:
            response = await self._api_request(
                "POST",
                "/OrderEntryHeader/V1/CreateOrderEntryHeader",
                json_data={
                    "CustomerId": self.customer_id,
                    "PurchaseOrderNumber": "",
                },
            )

            if response.get("IsSuccess") and response.get("ResultObject"):
                self._active_order_id = response["ResultObject"].get("OrderEntryHeaderId")
                return self._active_order_id

        except Exception as e:
            logger.exception(f"Valley Foods create order error: {e}")

        return None
