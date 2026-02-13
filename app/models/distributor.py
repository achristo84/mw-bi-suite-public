"""Distributor model."""
import uuid
from datetime import datetime, time

from sqlalchemy import Column, String, Integer, Boolean, Text, TIMESTAMP, ARRAY, Time
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from . import Base


class Distributor(Base):
    """Central registry of all suppliers."""

    __tablename__ = "distributors"

    # Capture status constants
    CAPTURE_NOT_STARTED = "not_started"
    CAPTURE_LOGIN = "login_captured"
    CAPTURE_SEARCH = "search_captured"
    CAPTURE_CART = "cart_captured"
    CAPTURE_ORDER = "order_captured"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    rep_name = Column(String(100))
    rep_email = Column(String(255))
    rep_phone = Column(String(20))
    portal_url = Column(String(500))
    portal_username = Column(String(100))
    portal_password_encrypted = Column(Text)
    scraper_module = Column(String(100))
    scrape_frequency = Column(String(20), default="weekly")
    last_successful_scrape = Column(TIMESTAMP)
    order_email = Column(String(255))
    invoice_email = Column(String(255))  # Email address invoices arrive from
    filename_pattern = Column(String(100))  # Regex pattern to match invoice filenames
    minimum_order_cents = Column(Integer, default=0)
    order_minimum_items = Column(Integer)  # Minimum item count if applicable
    delivery_days = Column(ARRAY(String(50)))
    order_deadline = Column(String(100))
    order_cutoff_hours = Column(Integer)  # Hours before delivery day
    order_cutoff_time = Column(Time)  # Specific cutoff time
    payment_terms_days = Column(Integer, default=15)
    vendor_category = Column(String(50))
    is_active = Column(Boolean, default=True)
    scraping_enabled = Column(Boolean, default=False)
    ordering_enabled = Column(Boolean, default=False)  # Ready for Order Hub
    notes = Column(Text)
    # Custom parsing prompts per content type
    parsing_prompt_pdf = Column(Text)
    parsing_prompt_email = Column(Text)
    parsing_prompt_screenshot = Column(Text)
    # Order Hub API integration
    api_config = Column(JSONB)  # Endpoints, auth patterns, headers
    platform_id = Column(String(50))  # Groups distributors on same platform
    capture_status = Column(String(20), default=CAPTURE_NOT_STARTED)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dist_ingredients = relationship("DistIngredient", back_populates="distributor")
    invoices = relationship("Invoice", back_populates="distributor")
    orders = relationship("Order", back_populates="distributor")
    email_messages = relationship("EmailMessage", back_populates="distributor")
    sessions = relationship("DistributorSession", back_populates="distributor")

    def __repr__(self):
        return f"<Distributor(name='{self.name}')>"
