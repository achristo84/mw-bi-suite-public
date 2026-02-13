"""Distributor CRUD endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.distributor import Distributor
from app.schemas.distributor import (
    DistributorCreate,
    DistributorUpdate,
    DistributorResponse,
    DistributorList,
    DistributorPromptsResponse,
    DistributorPromptsUpdate,
)
from app.services.invoice_parser import INVOICE_PARSE_PROMPT
from app.services.price_parser import get_default_price_prompt

router = APIRouter(prefix="/distributors", tags=["distributors"])


@router.get("", response_model=DistributorList)
def list_distributors(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List all distributors."""
    query = db.query(Distributor)
    if not include_inactive:
        query = query.filter(Distributor.is_active == True)
    distributors = query.order_by(Distributor.name).all()
    return DistributorList(distributors=distributors, count=len(distributors))


@router.get("/{distributor_id}", response_model=DistributorResponse)
def get_distributor(
    distributor_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single distributor by ID."""
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")
    return distributor


@router.post("", response_model=DistributorResponse, status_code=201)
def create_distributor(
    data: DistributorCreate,
    db: Session = Depends(get_db),
):
    """Create a new distributor."""
    existing = db.query(Distributor).filter(Distributor.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Distributor with this name already exists")

    distributor = Distributor(**data.model_dump())
    db.add(distributor)
    db.commit()
    db.refresh(distributor)
    return distributor


@router.patch("/{distributor_id}", response_model=DistributorResponse)
def update_distributor(
    distributor_id: UUID,
    data: DistributorUpdate,
    db: Session = Depends(get_db),
):
    """Update a distributor."""
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(distributor, field, value)

    db.commit()
    db.refresh(distributor)
    return distributor


@router.delete("/{distributor_id}", status_code=204)
def delete_distributor(
    distributor_id: UUID,
    db: Session = Depends(get_db),
):
    """Soft delete a distributor (sets is_active=False)."""
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    distributor.is_active = False
    db.commit()
    return None


@router.get("/{distributor_id}/prompts", response_model=DistributorPromptsResponse)
def get_distributor_prompts(
    distributor_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all parsing prompts for a distributor.

    Returns custom prompts if set, otherwise returns default prompts.
    """
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    default_invoice_prompt = INVOICE_PARSE_PROMPT
    default_price_prompt = get_default_price_prompt()

    return DistributorPromptsResponse(
        pdf=distributor.parsing_prompt_pdf or default_invoice_prompt,
        email=distributor.parsing_prompt_email or default_invoice_prompt,
        screenshot=distributor.parsing_prompt_screenshot or default_price_prompt,
        has_custom_pdf=distributor.parsing_prompt_pdf is not None,
        has_custom_email=distributor.parsing_prompt_email is not None,
        has_custom_screenshot=distributor.parsing_prompt_screenshot is not None,
    )


@router.patch("/{distributor_id}/prompts", response_model=DistributorPromptsResponse)
def update_distributor_prompts(
    distributor_id: UUID,
    data: DistributorPromptsUpdate,
    db: Session = Depends(get_db),
):
    """Update parsing prompts for a distributor.

    Only updates the prompt types where update_X is True.
    """
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    if data.update_pdf:
        distributor.parsing_prompt_pdf = data.prompt
    if data.update_email:
        distributor.parsing_prompt_email = data.prompt
    if data.update_screenshot:
        distributor.parsing_prompt_screenshot = data.prompt

    db.commit()
    db.refresh(distributor)

    default_invoice_prompt = INVOICE_PARSE_PROMPT
    default_price_prompt = get_default_price_prompt()

    return DistributorPromptsResponse(
        pdf=distributor.parsing_prompt_pdf or default_invoice_prompt,
        email=distributor.parsing_prompt_email or default_invoice_prompt,
        screenshot=distributor.parsing_prompt_screenshot or default_price_prompt,
        has_custom_pdf=distributor.parsing_prompt_pdf is not None,
        has_custom_email=distributor.parsing_prompt_email is not None,
        has_custom_screenshot=distributor.parsing_prompt_screenshot is not None,
    )
