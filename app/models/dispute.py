"""Dispute model for tracking issues with deliveries and invoices."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Text, TIMESTAMP,
    ForeignKey, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class Dispute(Base):
    """Track issues with deliveries and invoices."""

    __tablename__ = "disputes"
    __table_args__ = (
        Index("idx_disputes_open", "status", postgresql_where="status = 'open'"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    invoice_line_id = Column(UUID(as_uuid=True), ForeignKey("invoice_lines.id"))  # Nullable for invoice-level
    dispute_type = Column(String(30), nullable=False)
    # Types: 'wrong_item', 'bad_quality', 'missing', 'price_discrepancy', 'short_quantity'
    description = Column(Text, nullable=False)
    amount_disputed_cents = Column(Integer)
    photo_paths = Column(ARRAY(String(500)))  # Cloud Storage paths
    status = Column(String(20), nullable=False, default="open")
    # Statuses: 'open', 'contacted', 'resolved', 'written_off'
    resolution_notes = Column(Text)
    credit_received_cents = Column(Integer)
    resolved_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="disputes")
    invoice_line = relationship("InvoiceLine", back_populates="disputes")

    def __repr__(self):
        return f"<Dispute(type='{self.dispute_type}', status='{self.status}')>"
