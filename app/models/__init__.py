"""SQLAlchemy models for mw-bi-suite."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models to register them with Base.metadata
from .distributor import Distributor
from .ingredient import Ingredient, DistIngredient, PriceHistory
from .invoice import Invoice, InvoiceLine
from .order import Order, OrderLine
from .dispute import Dispute
from .email_message import EmailMessage
from .recipe import Recipe, RecipeIngredient, RecipeComponent, MenuItem, MenuItemPackaging
from .order_hub import OrderListItem, OrderListItemAssignment, DistributorSession

__all__ = [
    "Base",
    "Distributor",
    "Ingredient",
    "DistIngredient",
    "PriceHistory",
    "Invoice",
    "InvoiceLine",
    "Order",
    "OrderLine",
    "Dispute",
    "EmailMessage",
    "Recipe",
    "RecipeIngredient",
    "RecipeComponent",
    "MenuItem",
    "MenuItemPackaging",
    "OrderListItem",
    "OrderListItemAssignment",
    "DistributorSession",
]
