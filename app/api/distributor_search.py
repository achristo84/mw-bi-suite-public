"""Distributor Search API endpoints.

Provides parallel search across all distributors with normalized
price comparison for the Order Hub.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Distributor
from app.services.search_aggregator import search_distributors
from app.schemas.order_hub import (
    AggregatedSearchResults,
    DistributorSearchResults,
    SearchResult,
)

router = APIRouter(prefix="/distributor-search", tags=["distributor-search"])


@router.get("", response_model=AggregatedSearchResults)
async def search_all_distributors(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Results per distributor"),
    db: Session = Depends(get_db),
):
    """Search all enabled distributors in parallel.

    Returns results grouped by distributor with normalized prices
    for cross-distributor comparison.
    """
    results = await search_distributors(
        db=db,
        query=q,
        limit_per_distributor=limit,
    )

    # Convert to response model
    distributor_results = []
    for dr in results["distributors"]:
        search_results = [
            SearchResult(
                dist_ingredient_id=r.get("dist_ingredient_id"),
                distributor_id=r["distributor_id"],
                distributor_name=r["distributor_name"],
                sku=r["sku"],
                description=r["description"],
                pack_size=r.get("pack_size"),
                pack_unit=r.get("pack_unit"),
                price_cents=r.get("price_cents"),
                price_per_base_unit_cents=r.get("price_per_base_unit_cents"),
                in_stock=r.get("in_stock"),
                delivery_days=r.get("delivery_days"),
                last_ordered_date=r.get("last_ordered_date"),
            )
            for r in dr["results"]
        ]

        distributor_results.append(
            DistributorSearchResults(
                distributor_id=dr["distributor_id"],
                distributor_name=dr["distributor_name"],
                results=search_results,
                error=dr.get("error"),
            )
        )

    return AggregatedSearchResults(
        query=results["query"],
        distributors=distributor_results,
        total_results=results["total_results"],
        search_duration_ms=results["search_duration_ms"],
    )


@router.get("/enabled", response_model=list[dict])
def get_enabled_distributors(
    db: Session = Depends(get_db),
):
    """Get list of distributors enabled for Order Hub.

    Returns basic info for each distributor that can be searched.
    """
    distributors = db.query(Distributor).filter(
        Distributor.is_active == True,
        Distributor.ordering_enabled == True,
    ).all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "delivery_days": d.delivery_days,
            "order_cutoff_hours": d.order_cutoff_hours,
            "order_cutoff_time": d.order_cutoff_time.isoformat() if d.order_cutoff_time else None,
            "minimum_order_cents": d.minimum_order_cents,
            "order_minimum_items": d.order_minimum_items,
            "capture_status": d.capture_status,
        }
        for d in distributors
    ]


@router.get("/debug/status")
async def get_debug_status(
    db: Session = Depends(get_db),
):
    """Debug endpoint to check auth status of all distributors."""
    from app.models import DistributorSession
    from app.services.distributor_client import get_distributor_client

    distributors = db.query(Distributor).filter(
        Distributor.is_active == True,
        Distributor.ordering_enabled == True,
    ).all()

    results = []
    for d in distributors:
        session = db.query(DistributorSession).filter(
            DistributorSession.distributor_id == d.id
        ).first()

        status = {
            "name": d.name,
            "platform_id": d.platform_id,
            "api_config": d.api_config,
            "has_session": session is not None,
            "session_expired": session.is_expired if session else None,
            "auth_token": bool(session.auth_token) if session else False,
            "cookies": bool(session.cookies) if session else False,
        }

        # Try to authenticate
        try:
            client = get_distributor_client(db, d.id)
            auth_ok = await client.ensure_authenticated()
            status["auth_ok"] = auth_ok

            # Try a quick search
            if auth_ok:
                search_results = await client.search("test", limit=1)
                status["search_ok"] = True
                status["search_count"] = len(search_results)
            else:
                status["search_ok"] = False
                status["search_count"] = 0

            await client.close()
        except Exception as e:
            status["auth_ok"] = False
            status["auth_error"] = str(e)
            status["search_ok"] = False

        results.append(status)

    return results


@router.post("/debug/fix-configs")
def fix_distributor_configs(
    db: Session = Depends(get_db),
):
    """Fix distributor api_config to include secret_name for credentials."""
    import json

    # Platform-specific configs - base_url and secret_name should be set
    # in each distributor's api_config column in the database.
    # This endpoint merges secret_name into existing api_config.
    CONFIGS = {
        "valleyfoods": {
            "secret_name": "distributor-valleyfoods-credentials",
        },
        "metrowholesale": {
            "secret_name": "distributor-metro-wholesale-credentials",
        },
        "farmdirect": {
            "secret_name": "distributor-farm-direct-credentials",
        },
        "greenmarket": {
            "secret_name": "distributor-green-market-credentials",
        },
    }

    distributors = db.query(Distributor).filter(
        Distributor.ordering_enabled == True,
    ).all()

    results = []
    for d in distributors:
        if d.platform_id and d.platform_id in CONFIGS:
            new_config = CONFIGS[d.platform_id]
            # Merge with existing config
            if d.api_config:
                merged = {**d.api_config, **new_config}
            else:
                merged = new_config

            d.api_config = merged
            results.append({
                "name": d.name,
                "platform_id": d.platform_id,
                "api_config": merged,
                "status": "updated",
            })
        else:
            results.append({
                "name": d.name,
                "platform_id": d.platform_id,
                "status": "no_mapping",
            })

    db.commit()
    return results


@router.post("/debug/clear-sessions")
def clear_expired_sessions(
    db: Session = Depends(get_db),
):
    """Clear expired sessions to force re-authentication."""
    from app.models import DistributorSession

    sessions = db.query(DistributorSession).all()
    results = []

    for s in sessions:
        distributor = db.query(Distributor).filter(Distributor.id == s.distributor_id).first()
        name = distributor.name if distributor else "Unknown"

        if s.is_expired:
            db.delete(s)
            results.append({"name": name, "action": "deleted", "was_expired": True})
        else:
            results.append({"name": name, "action": "kept", "was_expired": False})

    db.commit()
    return results


@router.delete("/debug/sessions/{distributor_name}")
def delete_distributor_session(
    distributor_name: str,
    db: Session = Depends(get_db),
):
    """Delete session for a specific distributor by name."""
    from app.models import DistributorSession

    distributor = db.query(Distributor).filter(
        Distributor.name.ilike(f"%{distributor_name}%")
    ).first()

    if not distributor:
        raise HTTPException(status_code=404, detail=f"Distributor '{distributor_name}' not found")

    session = db.query(DistributorSession).filter(
        DistributorSession.distributor_id == distributor.id
    ).first()

    if session:
        # Log session details before deleting
        session_info = {
            "name": distributor.name,
            "had_auth_token": bool(session.auth_token),
            "had_cookies": bool(session.cookies),
            "headers": session.headers,
            "was_expired": session.is_expired,
        }
        db.delete(session)
        db.commit()
        return {"action": "deleted", "session_info": session_info}
    else:
        return {"action": "no_session", "distributor": distributor.name}


@router.get("/{distributor_id}", response_model=DistributorSearchResults)
async def search_single_distributor(
    distributor_id: UUID,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
):
    """Search a single distributor's catalog.

    Useful for getting more results from a specific distributor
    after seeing aggregated results.
    """
    # Verify distributor exists and is enabled
    distributor = db.query(Distributor).filter(
        Distributor.id == distributor_id,
        Distributor.is_active == True,
    ).first()

    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    results = await search_distributors(
        db=db,
        query=q,
        distributor_ids=[distributor_id],
        limit_per_distributor=limit,
    )

    if not results["distributors"]:
        return DistributorSearchResults(
            distributor_id=distributor_id,
            distributor_name=distributor.name,
            results=[],
            error="Search returned no results",
        )

    dr = results["distributors"][0]

    search_results = [
        SearchResult(
            dist_ingredient_id=r.get("dist_ingredient_id"),
            distributor_id=r["distributor_id"],
            distributor_name=r["distributor_name"],
            sku=r["sku"],
            description=r["description"],
            pack_size=r.get("pack_size"),
            pack_unit=r.get("pack_unit"),
            price_cents=r.get("price_cents"),
            price_per_base_unit_cents=r.get("price_per_base_unit_cents"),
            in_stock=r.get("in_stock"),
            delivery_days=r.get("delivery_days"),
            last_ordered_date=r.get("last_ordered_date"),
        )
        for r in dr["results"]
    ]

    return DistributorSearchResults(
        distributor_id=dr["distributor_id"],
        distributor_name=dr["distributor_name"],
        results=search_results,
        error=dr.get("error"),
    )
