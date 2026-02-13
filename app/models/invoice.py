"""Invoice and InvoiceLine models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, TIMESTAMP, DATE,
    ForeignKey, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class Invoice(Base):
    """Invoices received from distributors."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("distributor_id", "invoice_number", name="uq_invoices_dist_number"),
        Index("idx_invoices_unpaid", "distributor_id", postgresql_where="paid_at IS NULL"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distributor_id = Column(UUID(as_uuid=True), ForeignKey("distributors.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))  # Nullable
    invoice_number = Column(String(50), nullable=False)
    invoice_date = Column(DATE, nullable=False)
    delivery_date = Column(DATE)  # May differ from invoice_date
    due_date = Column(DATE)
    account_number = Column(String(50))  # Customer account # with distributor
    sales_rep_name = Column(String(100))  # For relationship tracking
    sales_order_number = Column(String(50))  # Distributor's SO# for reconciliation
    subtotal_cents = Column(Integer)
    tax_cents = Column(Integer)
    total_cents = Column(Integer, nullable=False)
    pdf_path = Column(String(500))  # Cloud Storage path
    raw_text = Column(Text)  # Extracted text for search
    parsed_at = Column(TIMESTAMP)
    parse_confidence = Column(Numeric(3, 2))  # 0.0-1.0
    reviewed_by = Column(String(50))
    reviewed_at = Column(TIMESTAMP)
    paid_at = Column(TIMESTAMP)
    payment_reference = Column(String(100))  # Check number, transfer ID
    source = Column(String(20), default="email")  # email, manual, upload
    review_status = Column(String(20), default="pending")  # pending, approved, rejected
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Review status constants
    REVIEW_PENDING = "pending"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"

    # Source constants
    SOURCE_EMAIL = "email"
    SOURCE_MANUAL = "manual"
    SOURCE_UPLOAD = "upload"

    # Relationships
    distributor = relationship("Distributor", back_populates="invoices")
    order = relationship("Order", back_populates="invoices")
    lines = relationship("InvoiceLine", back_populates="invoice", foreign_keys="InvoiceLine.invoice_id")
    disputes = relationship("Dispute", back_populates="invoice")
    email_message = relationship("EmailMessage", back_populates="invoice", uselist=False)

    def __repr__(self):
        return f"<Invoice(number='{self.invoice_number}', total=${self.total_cents/100:.2f})>"


class InvoiceLine(Base):
    """Line items parsed from invoices."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        Index("idx_invoice_lines_invoice", "invoice_id"),
        Index("idx_invoice_lines_parent", "parent_line_id", postgresql_where="parent_line_id IS NOT NULL"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    dist_ingredient_id = Column(UUID(as_uuid=True), ForeignKey("dist_ingredients.id"))  # Nullable until matched
    raw_description = Column(String(255), nullable=False)
    raw_sku = Column(String(50))
    quantity_ordered = Column(Numeric(10, 3))  # Original order qty (if shown)
    quantity = Column(Numeric(10, 3))  # Quantity shipped/invoiced
    unit = Column(String(20))  # Unit of measure (EA, OZ, LB, CS, etc.)
    unit_price_cents = Column(Integer)  # List price per unit
    extended_price_cents = Column(Integer)  # Line total (negative for credits)
    is_taxable = Column(Boolean, default=False)
    line_type = Column(String(20), default="product")  # 'product', 'credit', 'fee'
    parent_line_id = Column(UUID(as_uuid=True), ForeignKey("invoice_lines.id"))  # For credits
    matched_order_line_id = Column(UUID(as_uuid=True), ForeignKey("order_lines.id"))
    match_status = Column(String(20))  # 'matched', 'price_mismatch', 'quantity_mismatch', 'unmatched'
    line_status = Column(String(20), default="pending")  # 'pending', 'confirmed', 'removed'
    notes = Column(Text)

    # Line status constants
    LINE_PENDING = "pending"
    LINE_CONFIRMED = "confirmed"
    LINE_REMOVED = "removed"

    # Relationships
    invoice = relationship("Invoice", back_populates="lines", foreign_keys=[invoice_id])
    dist_ingredient = relationship("DistIngredient", back_populates="invoice_lines")
    matched_order_line = relationship("OrderLine", back_populates="invoice_lines")
    parent_line = relationship("InvoiceLine", remote_side=[id], backref="credit_lines")
    disputes = relationship("Dispute", back_populates="invoice_line")

    def __repr__(self):
        return f"<InvoiceLine(sku='{self.raw_sku}', qty={self.quantity}, ${self.extended_price_cents/100:.2f})>"
