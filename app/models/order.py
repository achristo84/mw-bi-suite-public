"""Order and OrderLine models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Text, TIMESTAMP, DATE,
    ForeignKey, Numeric, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from . import Base


class Order(Base):
    """Orders placed with distributors."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_status", "distributor_id", "status"),
    )

    # Status constants
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DELIVERED = "delivered"
    STATUS_INVOICED = "invoiced"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distributor_id = Column(UUID(as_uuid=True), ForeignKey("distributors.id"), nullable=False)
    status = Column(String(20), nullable=False, default=STATUS_DRAFT)
    submitted_at = Column(TIMESTAMP)
    expected_delivery = Column(DATE)
    actual_delivery_date = Column(DATE)
    received_at = Column(TIMESTAMP)
    submitted_by = Column(String(50))
    confirmation_number = Column(String(100))
    confirmation_data = Column(JSONB)  # Full API response
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    distributor = relationship("Distributor", back_populates="orders")
    lines = relationship("OrderLine", back_populates="order")
    invoices = relationship("Invoice", back_populates="order")
    list_item_assignments = relationship("OrderListItemAssignment", back_populates="order")

    def __repr__(self):
        return f"<Order(status='{self.status}', distributor_id={self.distributor_id})>"


class OrderLine(Base):
    """Line items on orders."""

    __tablename__ = "order_lines"
    __table_args__ = (
        Index("idx_order_lines_order", "order_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    dist_ingredient_id = Column(UUID(as_uuid=True), ForeignKey("dist_ingredients.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)  # Number of units ordered
    expected_price_cents = Column(Integer)  # Catalog price at time of order
    actual_quantity = Column(Numeric(10, 3))  # What was actually received
    actual_price_cents = Column(Integer)  # Actual invoiced price
    notes = Column(Text)

    # Relationships
    order = relationship("Order", back_populates="lines")
    dist_ingredient = relationship("DistIngredient", back_populates="order_lines")
    invoice_lines = relationship("InvoiceLine", back_populates="matched_order_line")

    def __repr__(self):
        return f"<OrderLine(qty={self.quantity}, dist_ingredient_id={self.dist_ingredient_id})>"
