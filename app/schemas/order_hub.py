"""Pydantic schemas for Order Hub."""
from datetime import datetime, date
from typing import Optional, Any
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# Order List Item Schemas

class OrderListItemBase(BaseModel):
    """Base fields for order list item."""

    name: str
    quantity: Optional[str] = None
    notes: Optional[str] = None
    ingredient_id: Optional[UUID] = None


class OrderListItemCreate(OrderListItemBase):
    """Schema for creating an order list item."""

    created_by: Optional[str] = None


class OrderListItemUpdate(BaseModel):
    """Schema for updating an order list item."""

    name: Optional[str] = None
    quantity: Optional[str] = None
    notes: Optional[str] = None
    ingredient_id: Optional[UUID] = None
    status: Optional[str] = None


class OrderListItemResponse(OrderListItemBase):
    """Response schema for order list item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OrderListItemWithDetails(OrderListItemResponse):
    """Order list item with ingredient and assignment details."""

    ingredient_name: Optional[str] = None
    assignments_count: int = 0
    last_ordered_at: Optional[datetime] = None
    last_ordered_distributor: Optional[str] = None
    last_ordered_price_cents: Optional[int] = None


class OrderListItemList(BaseModel):
    """List of order list items."""

    items: list[OrderListItemWithDetails]
    count: int


# Order List Item Assignment Schemas

class AssignmentCreate(BaseModel):
    """Schema for creating an assignment.

    Either dist_ingredient_id OR (distributor_id + sku) must be provided.
    If dist_ingredient_id is not provided, a new dist_ingredient will be
    created from the search result data.
    """

    order_list_item_id: UUID
    quantity: int = Field(gt=0)

    # Option 1: Reference existing dist_ingredient
    dist_ingredient_id: Optional[UUID] = None

    # Option 2: Create from search result (used when dist_ingredient doesn't exist)
    distributor_id: Optional[UUID] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    pack_size: Optional[str] = None
    pack_unit: Optional[str] = None
    price_cents: Optional[int] = None


class AssignmentUpdate(BaseModel):
    """Schema for updating an assignment."""

    quantity: Optional[int] = Field(default=None, gt=0)
    dist_ingredient_id: Optional[UUID] = None


class AssignmentResponse(BaseModel):
    """Response schema for assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_list_item_id: UUID
    dist_ingredient_id: UUID
    quantity: int
    order_id: Optional[UUID] = None
    created_at: datetime


class AssignmentWithDetails(AssignmentResponse):
    """Assignment with product and distributor details."""

    distributor_id: UUID
    distributor_name: str
    sku: Optional[str] = None
    description: str
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    unit_price_cents: Optional[int] = None
    extended_price_cents: Optional[int] = None


# Distributor Search Schemas

class SearchResult(BaseModel):
    """Single search result from a distributor."""

    dist_ingredient_id: Optional[UUID] = None  # None if not in DB
    distributor_id: UUID
    distributor_name: str
    sku: str
    description: str
    pack_size: Optional[str] = None
    pack_unit: Optional[str] = None
    price_cents: Optional[int] = None
    price_per_base_unit_cents: Optional[int] = None  # Normalized price
    in_stock: Optional[bool] = None
    delivery_days: Optional[list[str]] = None
    last_ordered_date: Optional[date] = None
    image_url: Optional[str] = None


class DistributorSearchResults(BaseModel):
    """Search results from a single distributor."""

    distributor_id: UUID
    distributor_name: str
    results: list[SearchResult]
    error: Optional[str] = None


class AggregatedSearchResults(BaseModel):
    """Aggregated search results from all distributors."""

    query: str
    distributors: list[DistributorSearchResults]
    total_results: int
    search_duration_ms: int


# Cart Builder Schemas

class CartItem(BaseModel):
    """Item in a distributor cart."""

    assignment_id: UUID
    order_list_item_id: UUID
    order_list_item_name: str
    dist_ingredient_id: UUID
    sku: Optional[str] = None
    description: str
    quantity: int
    unit_price_cents: Optional[int] = None
    extended_price_cents: Optional[int] = None


class DistributorCart(BaseModel):
    """Cart for a single distributor."""

    distributor_id: UUID
    distributor_name: str
    delivery_days: Optional[list[str]] = None
    order_cutoff_time: Optional[str] = None
    next_delivery_date: Optional[date] = None
    minimum_order_cents: int = 0
    order_minimum_items: Optional[int] = None
    items: list[CartItem]
    subtotal_cents: int
    meets_minimum: bool
    ordering_enabled: bool


class OrderBuilderSummary(BaseModel):
    """Summary of all carts being built."""

    carts: list[DistributorCart]
    total_items: int
    total_cents: int
    ready_to_order: int  # Number of carts meeting minimums


# Order Finalization Schemas

class FinalizeRequest(BaseModel):
    """Request to finalize orders from assignments."""

    distributor_ids: Optional[list[UUID]] = None  # None means all with assignments


class OrderLineCreate(BaseModel):
    """Line item in a created order."""

    dist_ingredient_id: UUID
    quantity: int
    unit_price_cents: Optional[int] = None


class OrderCreate(BaseModel):
    """Request to create an order."""

    distributor_id: UUID
    expected_delivery: Optional[date] = None
    notes: Optional[str] = None
    lines: list[OrderLineCreate]


class OrderResponse(BaseModel):
    """Response for a created order."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    distributor_id: UUID
    status: str
    submitted_at: Optional[datetime] = None
    expected_delivery: Optional[date] = None
    confirmation_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OrderWithDetails(OrderResponse):
    """Order with distributor and line details."""

    distributor_name: str
    lines: list[CartItem]
    subtotal_cents: int


class FinalizeResponse(BaseModel):
    """Response from order finalization."""

    orders: list[OrderWithDetails]
    items_ordered: int
    total_cents: int


# Order History Schemas

class OrderHistoryEntry(BaseModel):
    """Historical order for an ingredient or list item."""

    order_id: UUID
    order_date: datetime
    distributor_name: str
    sku: Optional[str] = None
    description: str
    quantity: int
    price_cents: int
    status: str


class OrderHistoryResponse(BaseModel):
    """Order history for an item."""

    item_name: str
    entries: list[OrderHistoryEntry]
    count: int


# Pre-fill Cart Schemas

class PrefillCartRequest(BaseModel):
    """Request to pre-fill a distributor cart."""

    order_id: UUID


class PrefillCartResponse(BaseModel):
    """Response from pre-filling a cart."""

    success: bool
    distributor_name: str
    items_added: int
    cart_url: Optional[str] = None
    error: Optional[str] = None


# Copy List Schemas

class CopyListItem(BaseModel):
    """Item formatted for copy-paste ordering."""

    sku: str
    description: str
    quantity: int
    notes: Optional[str] = None


class CopyListResponse(BaseModel):
    """Formatted list for manual order entry."""

    distributor_name: str
    items: list[CopyListItem]
    formatted_text: str  # Ready to copy/paste


# Distributor Session Schemas

class DistributorSessionResponse(BaseModel):
    """Response for distributor session status."""

    model_config = ConfigDict(from_attributes=True)

    distributor_id: UUID
    distributor_name: str
    has_session: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_expired: bool


class TestAuthResponse(BaseModel):
    """Response from testing distributor auth."""

    success: bool
    message: str
    session_expires_at: Optional[datetime] = None
