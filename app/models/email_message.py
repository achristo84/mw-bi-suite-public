"""EmailMessage model for tracking processed emails."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class EmailMessage(Base):
    """Tracks emails processed from Gmail for invoice ingestion."""

    __tablename__ = "email_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gmail_message_id = Column(String(100), nullable=False, unique=True)
    gmail_thread_id = Column(String(100))
    from_address = Column(String(255), nullable=False)
    subject = Column(String(500))
    received_at = Column(TIMESTAMP, nullable=False)
    distributor_id = Column(UUID(as_uuid=True), ForeignKey("distributors.id"))
    status = Column(String(20), nullable=False, default="pending")
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    error_message = Column(Text)
    processed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    distributor = relationship("Distributor", back_populates="email_messages")
    invoice = relationship("Invoice", back_populates="email_message")

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"  # Currently being parsed
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_IGNORED = "ignored"  # No PDF or not relevant

    def __repr__(self):
        return f"<EmailMessage(from='{self.from_address}', subject='{self.subject[:30]}...')>"
