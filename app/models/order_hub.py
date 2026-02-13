"""Order Hub models for centralized ordering system."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Text, TIMESTAMP,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from . import Base


class OrderListItem(Base):
    """Items staff add to the shared 'need to order' list."""

    __tablename__ = "order_list_items"
    __table_args__ = (
        Index("idx_order_list_items_status", "status"),
    )

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_ORDERED = "ordered"
    STATUS_RECEIVED = "received"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    quantity = Column(String(100))  # Freeform: "2 cases", "about 20 lbs"
    notes = Column(Text)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id"))
    status = Column(String(20), nullable=False, default=STATUS_PENDING)
    created_by = Column(String(100))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ingredient = relationship("Ingredient", back_populates="order_list_items")
    assignments = relationship(
        "OrderListItemAssignment",
        back_populates="order_list_item",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<OrderListItem(name='{self.name}', status='{self.status}')>"


class OrderListItemAssignment(Base):
    """Links order list items to specific SKUs/distributors."""

    __tablename__ = "order_list_item_assignments"
    __table_args__ = (
        Index("idx_order_list_item_assignments_item", "order_list_item_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_list_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_list_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    dist_ingredient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dist_ingredients.id"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    order_list_item = relationship("OrderListItem", back_populates="assignments")
    dist_ingredient = relationship("DistIngredient", back_populates="order_list_assignments")
    order = relationship("Order", back_populates="list_item_assignments")

    def __repr__(self):
        return f"<OrderListItemAssignment(qty={self.quantity})>"


class DistributorSession(Base):
    """Cached API sessions for distributors."""

    __tablename__ = "distributor_sessions"
    __table_args__ = (
        Index("idx_distributor_sessions_distributor", "distributor_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distributor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("distributors.id", ondelete="CASCADE"),
        nullable=False,
    )
    cookies = Column(JSONB)
    headers = Column(JSONB)
    auth_token = Column(Text)
    expires_at = Column(TIMESTAMP)
    last_used_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    distributor = relationship("Distributor", back_populates="sessions")

    def __repr__(self):
        return f"<DistributorSession(distributor_id={self.distributor_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
