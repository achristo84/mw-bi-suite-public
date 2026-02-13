"""Pydantic schemas for Distributor."""
from datetime import datetime, time
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DistributorBase(BaseModel):
    """Base distributor fields."""

    name: str
    rep_name: Optional[str] = None
    rep_email: Optional[str] = None
    rep_phone: Optional[str] = None
    portal_url: Optional[str] = None
    portal_username: Optional[str] = None
    scraper_module: Optional[str] = None
    scrape_frequency: Optional[str] = "weekly"
    order_email: Optional[str] = None
    invoice_email: Optional[str] = None
    filename_pattern: Optional[str] = None
    minimum_order_cents: Optional[int] = 0
    order_minimum_items: Optional[int] = None
    delivery_days: Optional[list[str]] = None
    order_deadline: Optional[str] = None
    order_cutoff_hours: Optional[int] = None
    order_cutoff_time: Optional[time] = None
    payment_terms_days: Optional[int] = 15
    vendor_category: Optional[str] = None
    scraping_enabled: Optional[bool] = False
    ordering_enabled: Optional[bool] = False
    notes: Optional[str] = None
    # Custom parsing prompts
    parsing_prompt_pdf: Optional[str] = None
    parsing_prompt_email: Optional[str] = None
    parsing_prompt_screenshot: Optional[str] = None
    # Order Hub API integration
    api_config: Optional[dict[str, Any]] = None
    platform_id: Optional[str] = None
    capture_status: Optional[str] = "not_started"


class DistributorCreate(DistributorBase):
    """Schema for creating a distributor."""

    pass


class DistributorUpdate(BaseModel):
    """Schema for updating a distributor. All fields optional."""

    name: Optional[str] = None
    rep_name: Optional[str] = None
    rep_email: Optional[str] = None
    rep_phone: Optional[str] = None
    portal_url: Optional[str] = None
    portal_username: Optional[str] = None
    scraper_module: Optional[str] = None
    scrape_frequency: Optional[str] = None
    order_email: Optional[str] = None
    invoice_email: Optional[str] = None
    filename_pattern: Optional[str] = None
    minimum_order_cents: Optional[int] = None
    order_minimum_items: Optional[int] = None
    delivery_days: Optional[list[str]] = None
    order_deadline: Optional[str] = None
    order_cutoff_hours: Optional[int] = None
    order_cutoff_time: Optional[time] = None
    payment_terms_days: Optional[int] = None
    vendor_category: Optional[str] = None
    is_active: Optional[bool] = None
    scraping_enabled: Optional[bool] = None
    ordering_enabled: Optional[bool] = None
    notes: Optional[str] = None
    # Custom parsing prompts
    parsing_prompt_pdf: Optional[str] = None
    parsing_prompt_email: Optional[str] = None
    parsing_prompt_screenshot: Optional[str] = None
    # Order Hub API integration
    api_config: Optional[dict[str, Any]] = None
    platform_id: Optional[str] = None
    capture_status: Optional[str] = None


class DistributorResponse(DistributorBase):
    """Schema for distributor response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    scraping_enabled: bool
    ordering_enabled: bool
    capture_status: str
    last_successful_scrape: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DistributorList(BaseModel):
    """Schema for list of distributors."""

    distributors: list[DistributorResponse]
    count: int


class DistributorPromptsResponse(BaseModel):
    """Response with all parsing prompts for a distributor."""

    pdf: str
    email: str
    screenshot: str
    has_custom_pdf: bool
    has_custom_email: bool
    has_custom_screenshot: bool


class DistributorPromptsUpdate(BaseModel):
    """Request to update distributor prompts."""

    prompt: str
    update_pdf: bool = False
    update_email: bool = False
    update_screenshot: bool = False
