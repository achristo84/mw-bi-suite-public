"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import (
    distributors,
    email_ingestion,
    ingredients,
    invoices,
    recipes,
    units,
    order_list,
    distributor_search,
    order_builder,
)

settings = get_settings()

app = FastAPI(
    title="Mill & Whistle BI Suite",
    description="Business intelligence for cafe operations",
    version="0.1.0",
)

# CORS configuration from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(distributors.router, prefix="/api/v1")
app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")
app.include_router(recipes.menu_router, prefix="/api/v1")
app.include_router(units.router, prefix="/api/v1")
app.include_router(email_ingestion.router)

# Order Hub routers
app.include_router(order_list.router, prefix="/api/v1")
app.include_router(distributor_search.router, prefix="/api/v1")
app.include_router(order_builder.router, prefix="/api/v1")
app.include_router(order_builder.orders_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Mill & Whistle BI Suite API", "docs": "/docs"}
