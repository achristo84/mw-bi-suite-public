"""Email ingestion API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.email_ingestion import run_email_ingestion

router = APIRouter(prefix="/api/v1/email", tags=["email"])


class IngestionResponse(BaseModel):
    """Response model for email ingestion."""
    searched: int = 0
    already_processed: int = 0
    new_processed: int = 0
    failed: int = 0
    no_pdf: int = 0
    unknown_sender: int = 0
    error: str | None = None


class IngestionRequest(BaseModel):
    """Request model for email ingestion."""
    lookback_days: int = 7


@router.post("/ingest", response_model=IngestionResponse)
def trigger_email_ingestion(
    request: IngestionRequest = IngestionRequest(),
    db: Session = Depends(get_db)
):
    """
    Trigger email ingestion to fetch and process new invoice emails.

    This endpoint is designed to be called by Cloud Scheduler every 15 minutes.
    It can also be triggered manually for testing.
    """
    try:
        result = run_email_ingestion(db, lookback_days=request.lookback_days)
        return IngestionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def email_service_health():
    """Check if email service can connect to Gmail."""
    from app.services.gmail_service import get_gmail_service

    try:
        gmail = get_gmail_service()
        # Try to get profile to verify connection
        profile = gmail.service.users().getProfile(userId='me').execute()
        return {
            "status": "healthy",
            "email": profile.get("emailAddress"),
            "messages_total": profile.get("messagesTotal")
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gmail connection failed: {e}")
