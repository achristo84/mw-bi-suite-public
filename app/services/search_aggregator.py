"""Search aggregator service for Order Hub.

Searches all enabled distributors in parallel and normalizes results
for cross-distributor price comparison.
"""
import asyncio
import logging
import time
from typing import Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Distributor, DistIngredient, PriceHistory
from app.services.distributor_client import (
    get_distributor_client,
    SearchResult as ClientSearchResult,
)
from app.services.units import parse_pack_description

logger = logging.getLogger(__name__)


class SearchAggregator:
    """Aggregates search results from multiple distributors."""

    def __init__(self, db: Session):
        self.db = db

    async def search_all(
        self,
        query: str,
        distributor_ids: Optional[list[UUID]] = None,
        limit_per_distributor: int = 20,
    ) -> dict:
        """Search all enabled distributors in parallel.

        Args:
            query: Search term
            distributor_ids: Optional list of specific distributors to search
            limit_per_distributor: Max results per distributor

        Returns:
            Aggregated results with timing info
        """
        start_time = time.time()

        # Get distributors to search
        dist_query = self.db.query(Distributor).filter(
            Distributor.is_active == True,
            Distributor.ordering_enabled == True,
        )

        if distributor_ids:
            dist_query = dist_query.filter(Distributor.id.in_(distributor_ids))

        distributors = dist_query.all()

        if not distributors:
            return {
                "query": query,
                "distributors": [],
                "total_results": 0,
                "search_duration_ms": 0,
            }

        # Search each distributor in parallel
        tasks = [
            self._search_distributor(d, query, limit_per_distributor)
            for d in distributors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        distributor_results = []
        total_results = 0

        for distributor, result in zip(distributors, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {distributor.name}: {result}")
                distributor_results.append({
                    "distributor_id": distributor.id,
                    "distributor_name": distributor.name,
                    "results": [],
                    "error": str(result),
                })
            else:
                distributor_results.append({
                    "distributor_id": distributor.id,
                    "distributor_name": distributor.name,
                    "results": result,
                    "error": None,
                })
                total_results += len(result)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "query": query,
            "distributors": distributor_results,
            "total_results": total_results,
            "search_duration_ms": duration_ms,
        }

    async def _search_distributor(
        self,
        distributor: Distributor,
        query: str,
        limit: int,
    ) -> list[dict]:
        """Search a single distributor.

        First tries the API client, falls back to database search
        if API is not available.
        """
        results = []

        # Try API search first
        try:
            client = get_distributor_client(self.db, distributor.id)
            await client.ensure_authenticated()
            api_results = await client.search(query, limit)
            await client.close()

            # Convert API results to normalized format
            for r in api_results:
                normalized = self._normalize_result(distributor, r)
                results.append(normalized)

        except Exception as e:
            logger.warning(f"API search failed for {distributor.name}: {e}")
            # Fall back to database search
            results = self._search_database(distributor, query, limit)

        return results

    def _search_database(
        self,
        distributor: Distributor,
        query: str,
        limit: int,
    ) -> list[dict]:
        """Search distributor's products in our database.

        Uses existing dist_ingredients table for offline/fallback search.
        """
        # Simple ILIKE search on description and SKU
        search_pattern = f"%{query}%"

        dist_ingredients = self.db.query(DistIngredient).filter(
            DistIngredient.distributor_id == distributor.id,
            DistIngredient.is_active == True,
            (
                DistIngredient.description.ilike(search_pattern) |
                DistIngredient.sku.ilike(search_pattern)
            ),
        ).limit(limit).all()

        results = []
        for di in dist_ingredients:
            # Get latest price
            latest_price = self.db.query(PriceHistory).filter(
                PriceHistory.dist_ingredient_id == di.id,
            ).order_by(desc(PriceHistory.effective_date)).first()

            price_cents = latest_price.price_cents if latest_price else None

            results.append({
                "dist_ingredient_id": di.id,
                "distributor_id": distributor.id,
                "distributor_name": distributor.name,
                "sku": di.sku,
                "description": di.description,
                "pack_size": str(di.pack_size) if di.pack_size else None,
                "pack_unit": di.pack_unit,
                "price_cents": price_cents,
                "price_per_base_unit_cents": self._calculate_base_price(
                    price_cents, di.pack_size, di.grams_per_unit
                ),
                "in_stock": None,  # Unknown from database
                "delivery_days": distributor.delivery_days,
                "last_ordered_date": None,  # Not yet tracked in database search
                "image_url": None,  # Not available from database
            })

        return results

    def _normalize_result(
        self,
        distributor: Distributor,
        api_result: ClientSearchResult,
    ) -> dict:
        """Normalize an API search result.

        Looks up or creates dist_ingredient entry and calculates
        normalized price per base unit.
        """
        # Try to find existing dist_ingredient
        dist_ingredient = self.db.query(DistIngredient).filter(
            DistIngredient.distributor_id == distributor.id,
            DistIngredient.sku == api_result.sku,
        ).first()

        dist_ingredient_id = dist_ingredient.id if dist_ingredient else None

        # Parse pack size for normalization
        pack_info = None
        if api_result.pack_size:
            try:
                pack_info = parse_pack_description(api_result.pack_size)
            except Exception:
                pass

        # Calculate normalized price
        price_per_base_unit = None
        if api_result.price_cents and pack_info:
            try:
                total_grams = pack_info.get("total_grams") or pack_info.get("total_ml")
                if total_grams:
                    price_per_base_unit = int(api_result.price_cents / total_grams)
            except Exception:
                pass

        return {
            "dist_ingredient_id": dist_ingredient_id,
            "distributor_id": distributor.id,
            "distributor_name": distributor.name,
            "sku": api_result.sku,
            "description": api_result.description,
            "pack_size": api_result.pack_size,
            "pack_unit": api_result.pack_unit,
            "price_cents": api_result.price_cents,
            "price_per_base_unit_cents": price_per_base_unit,
            "in_stock": api_result.in_stock,
            "delivery_days": distributor.delivery_days,
            "last_ordered_date": None,  # Not yet tracked in API search
            "image_url": api_result.image_url,
        }

    def _calculate_base_price(
        self,
        price_cents: Optional[int],
        pack_size: Optional[Decimal],
        grams_per_unit: Optional[Decimal],
    ) -> Optional[int]:
        """Calculate price per base unit (gram or ml).

        Returns price in cents per gram/ml.
        """
        if price_cents is None:
            return None

        if pack_size and grams_per_unit:
            total_grams = float(pack_size) * float(grams_per_unit)
            if total_grams > 0:
                return int(price_cents / total_grams)

        return None


async def search_distributors(
    db: Session,
    query: str,
    distributor_ids: Optional[list[UUID]] = None,
    limit_per_distributor: int = 20,
) -> dict:
    """Convenience function to search distributors.

    Args:
        db: Database session
        query: Search term
        distributor_ids: Optional specific distributors to search
        limit_per_distributor: Max results per distributor

    Returns:
        Aggregated search results
    """
    aggregator = SearchAggregator(db)
    return await aggregator.search_all(query, distributor_ids, limit_per_distributor)
