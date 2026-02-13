"""Base class for distributor API clients.

This module provides the foundation for integrating with distributor
ordering portals. Each distributor gets a concrete implementation
that inherits from DistributorApiClient.
"""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
import httpx
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Distributor, DistributorSession

logger = logging.getLogger(__name__)

# Cache for secrets to avoid repeated API calls
_secrets_cache: dict[str, dict] = {}


def get_secret(secret_name: str, project_id: str = "") -> Optional[dict]:
    """Fetch credentials from GCP Secret Manager.

    Args:
        secret_name: Name of the secret (e.g., "distributor-credentials")
        project_id: GCP project ID (defaults to GCP_PROJECT_ID env var)

    Returns:
        Parsed JSON credentials or None
    """
    # Check cache first
    if secret_name in _secrets_cache:
        return _secrets_cache[secret_name]

    try:
        from google.cloud import secretmanager
        from app.config import get_settings

        if not project_id:
            project_id = get_settings().GCP_PROJECT_ID

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_data = response.payload.data.decode("UTF-8")
        credentials = json.loads(secret_data)

        # Cache for future use
        _secrets_cache[secret_name] = credentials
        return credentials

    except Exception as e:
        logger.warning(f"Failed to fetch secret {secret_name}: {e}")
        return None


@dataclass
class SearchResult:
    """Result from searching a distributor's catalog."""

    sku: str
    description: str
    price_cents: Optional[int] = None
    pack_size: Optional[str] = None
    pack_unit: Optional[str] = None
    in_stock: Optional[bool] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    product_id: Optional[str] = None  # Internal distributor product ID


@dataclass
class CartItem:
    """Item in a distributor's shopping cart."""

    sku: str
    description: str
    quantity: int
    unit_price_cents: Optional[int] = None
    extended_price_cents: Optional[int] = None
    product_id: Optional[str] = None  # Internal distributor product ID


@dataclass
class Cart:
    """Distributor shopping cart state."""

    items: list[CartItem]
    subtotal_cents: int
    tax_cents: int = 0
    shipping_cents: int = 0
    total_cents: int = 0
    cart_id: Optional[str] = None  # Internal distributor cart ID


class DistributorApiClient(ABC):
    """Base class for distributor API integrations.

    Each distributor has unique API patterns. Concrete implementations
    provide the specific logic for authentication, searching, and
    cart management.

    Usage:
        client = ValleyFoodsClient(db, distributor_id)
        await client.ensure_authenticated()
        results = await client.search("eggs")
        await client.add_to_cart("SKU123", 2)
        cart = await client.get_cart()
    """

    def __init__(self, db: Session, distributor_id: UUID):
        """Initialize client with database session and distributor.

        Args:
            db: SQLAlchemy session for database access
            distributor_id: UUID of the distributor
        """
        self.db = db
        self.distributor_id = distributor_id
        self._distributor: Optional[Distributor] = None
        self._session: Optional[DistributorSession] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def distributor(self) -> Distributor:
        """Lazily load distributor from database."""
        if self._distributor is None:
            self._distributor = self.db.query(Distributor).filter(
                Distributor.id == self.distributor_id
            ).first()
            if self._distributor is None:
                raise ValueError(f"Distributor {self.distributor_id} not found")
        return self._distributor

    @property
    def api_config(self) -> dict[str, Any]:
        """Get API configuration for this distributor."""
        return self.distributor.api_config or {}

    @property
    def base_url(self) -> str:
        """Get base URL from API config."""
        return self.api_config.get("base_url", "")

    def get_credentials(self) -> Optional[dict]:
        """Get credentials from Secret Manager or api_config.

        First checks for secret_name in api_config and fetches from
        GCP Secret Manager. Falls back to inline credentials in api_config.

        Returns:
            Dict with 'email' and 'password' keys, or None
        """
        config = self.api_config

        # Try Secret Manager first
        secret_name = config.get("secret_name")
        if secret_name:
            credentials = get_secret(secret_name)
            if credentials:
                return credentials

        # Fall back to inline credentials (for development)
        if "email" in config and "password" in config:
            return {"email": config["email"], "password": config["password"]}

        return None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with session cookies."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
            )

            # Apply session cookies if we have them
            session = self._load_session()
            if session and session.cookies:
                for name, value in session.cookies.items():
                    self._http_client.cookies.set(name, value)

            # Apply custom headers from API config
            headers = self.api_config.get("headers", {})
            self._http_client.headers.update(headers)

            # Apply auth token if we have one
            if session and session.auth_token:
                token_header = self.api_config.get("auth", {}).get("token_header", "Authorization")
                self._http_client.headers[token_header] = session.auth_token

        return self._http_client

    def _load_session(self) -> Optional[DistributorSession]:
        """Load existing session from database."""
        if self._session is None:
            self._session = self.db.query(DistributorSession).filter(
                DistributorSession.distributor_id == self.distributor_id
            ).first()
        return self._session

    def _save_session(
        self,
        cookies: Optional[dict] = None,
        headers: Optional[dict] = None,
        auth_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> DistributorSession:
        """Save or update session in database."""
        session = self._load_session()

        if session is None:
            import uuid
            session = DistributorSession(
                id=uuid.uuid4(),
                distributor_id=self.distributor_id,
            )
            self.db.add(session)

        if cookies is not None:
            session.cookies = cookies
        if headers is not None:
            session.headers = headers
        if auth_token is not None:
            session.auth_token = auth_token
        if expires_at is not None:
            session.expires_at = expires_at

        session.last_used_at = datetime.utcnow()
        self.db.commit()
        self._session = session
        return session

    def _clear_session(self) -> None:
        """Clear session from database."""
        session = self._load_session()
        if session:
            self.db.delete(session)
            self.db.commit()
            self._session = None

    async def ensure_authenticated(self) -> bool:
        """Ensure we have a valid session, authenticating if needed.

        Returns:
            True if authenticated, False if authentication failed
        """
        session = self._load_session()

        # Check if we have a valid session
        if session and not session.is_expired:
            return True

        # Try to authenticate
        logger.info(f"Authenticating with {self.distributor.name}")
        success = await self.authenticate()

        if success:
            logger.info(f"Successfully authenticated with {self.distributor.name}")
        else:
            logger.warning(f"Failed to authenticate with {self.distributor.name}")

        return success

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the distributor's API.

        Implementations should:
        1. Get credentials from distributor config
        2. Call login endpoint
        3. Save session cookies/token via _save_session()

        Returns:
            True if authentication succeeded
        """
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Search the distributor's product catalog.

        Args:
            query: Search term
            limit: Maximum results to return

        Returns:
            List of matching products
        """
        pass

    @abstractmethod
    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Add an item to the shopping cart.

        Args:
            sku: Product SKU
            quantity: Quantity to add

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def get_cart(self) -> Cart:
        """Get current shopping cart contents.

        Returns:
            Current cart state
        """
        pass

    @abstractmethod
    async def clear_cart(self) -> bool:
        """Clear all items from the cart.

        Returns:
            True if successful
        """
        pass

    async def remove_from_cart(self, sku: str) -> bool:
        """Remove an item from the cart.

        Default implementation clears and re-adds other items.
        Override for distributors with a remove endpoint.

        Args:
            sku: Product SKU to remove

        Returns:
            True if successful
        """
        cart = await self.get_cart()
        items_to_keep = [item for item in cart.items if item.sku != sku]

        if len(items_to_keep) == len(cart.items):
            return False  # Item wasn't in cart

        await self.clear_cart()

        for item in items_to_keep:
            await self.add_to_cart(item.sku, item.quantity)

        return True

    async def update_cart_quantity(self, sku: str, quantity: int) -> bool:
        """Update quantity of an item in cart.

        Default implementation removes and re-adds.
        Override for distributors with an update endpoint.

        Args:
            sku: Product SKU
            quantity: New quantity

        Returns:
            True if successful
        """
        if quantity <= 0:
            return await self.remove_from_cart(sku)

        # Default: remove and re-add
        await self.remove_from_cart(sku)
        return await self.add_to_cart(sku, quantity)

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


class MockDistributorClient(DistributorApiClient):
    """Mock client for testing and development.

    Returns fake data without making real API calls.
    Useful for UI development before API capture is complete.
    """

    async def authenticate(self) -> bool:
        """Mock authentication always succeeds."""
        self._save_session(
            cookies={"mock_session": "test123"},
            expires_at=datetime.utcnow(),
        )
        return True

    async def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Return mock search results."""
        return [
            SearchResult(
                sku=f"MOCK-{i}",
                description=f"Mock Product {i} - {query}",
                price_cents=999 + (i * 100),
                pack_size="1",
                pack_unit="each",
                in_stock=True,
            )
            for i in range(min(5, limit))
        ]

    async def add_to_cart(self, sku: str, quantity: int) -> bool:
        """Mock add to cart always succeeds."""
        return True

    async def get_cart(self) -> Cart:
        """Return empty mock cart."""
        return Cart(items=[], subtotal_cents=0, total_cents=0)

    async def clear_cart(self) -> bool:
        """Mock clear cart always succeeds."""
        return True


def get_distributor_client(db: Session, distributor_id: UUID) -> DistributorApiClient:
    """Factory function to get the appropriate client for a distributor.

    Args:
        db: Database session
        distributor_id: UUID of the distributor

    Returns:
        Appropriate client implementation for the distributor
    """
    # Import here to avoid circular imports
    from app.services.clients import (
        ValleyFoodsClient,
        MetroWholesaleClient,
        FarmDirectClient,
        GreenMarketClient,
    )

    distributor = db.query(Distributor).filter(
        Distributor.id == distributor_id
    ).first()

    if distributor is None:
        raise ValueError(f"Distributor {distributor_id} not found")

    # Map platform_id to client class
    platform_clients: dict[str, type[DistributorApiClient]] = {
        "valleyfoods": ValleyFoodsClient,
        "metrowholesale": MetroWholesaleClient,
        "farmdirect": FarmDirectClient,
        "greenmarket": GreenMarketClient,
    }

    platform_id = distributor.platform_id

    if platform_id and platform_id in platform_clients:
        return platform_clients[platform_id](db, distributor_id)

    # Default to mock client for development
    logger.warning(
        f"No client implementation for distributor {distributor.name} "
        f"(platform_id={platform_id}), using mock client"
    )
    return MockDistributorClient(db, distributor_id)
