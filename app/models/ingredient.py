"""Ingredient, DistIngredient, and PriceHistory models."""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, TIMESTAMP, DATE,
    ForeignKey, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class Ingredient(Base):
    """Canonical ingredient list with normalized base units."""

    __tablename__ = "ingredients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50))
    base_unit = Column(String(10), nullable=False)  # 'g', 'ml', 'each'
    ingredient_type = Column(String(20), nullable=False, default="raw")  # 'raw', 'component', 'packaging'
    source_recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"))  # For component ingredients
    storage_type = Column(String(20))  # 'refrigerated', 'frozen', 'dry', 'ambient'
    shelf_life_days = Column(Integer)
    par_level_base_units = Column(Numeric(10, 2))
    yield_factor = Column(Numeric(4, 3), default=1.0)
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dist_ingredients = relationship("DistIngredient", back_populates="ingredient")
    recipe_ingredients = relationship("RecipeIngredient", back_populates="ingredient")
    menu_item_packaging = relationship("MenuItemPackaging", back_populates="ingredient")
    source_recipe = relationship("Recipe", foreign_keys=[source_recipe_id])
    order_list_items = relationship("OrderListItem", back_populates="ingredient")

    def __repr__(self):
        return f"<Ingredient(name='{self.name}')>"


class DistIngredient(Base):
    """Distributor-specific variants/SKUs mapped to canonical ingredients."""

    __tablename__ = "dist_ingredients"
    __table_args__ = (
        UniqueConstraint("distributor_id", "sku", name="uq_dist_ingredients_dist_sku"),
        Index("idx_dist_ingredients_distributor", "distributor_id"),
        Index("idx_dist_ingredients_ingredient", "ingredient_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distributor_id = Column(UUID(as_uuid=True), ForeignKey("distributors.id"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id"))  # Nullable if unmapped
    sku = Column(String(50))
    description = Column(String(255), nullable=False)
    pack_size = Column(Numeric(10, 3))  # e.g., 12 (units per case)
    pack_unit = Column(String(20))  # e.g., 'carton', '32oz bottle'
    units_per_pack = Column(Integer, default=1)  # For nested packs
    grams_per_unit = Column(Numeric(12, 4))  # Conversion factor to base unit
    is_active = Column(Boolean, default=True)
    quality_tier = Column(String(20))  # 'premium', 'standard', 'commodity'
    quality_notes = Column(Text)
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    distributor = relationship("Distributor", back_populates="dist_ingredients")
    ingredient = relationship("Ingredient", back_populates="dist_ingredients")
    price_history = relationship("PriceHistory", back_populates="dist_ingredient")
    invoice_lines = relationship("InvoiceLine", back_populates="dist_ingredient")
    order_lines = relationship("OrderLine", back_populates="dist_ingredient")
    order_list_assignments = relationship("OrderListItemAssignment", back_populates="dist_ingredient")

    def __repr__(self):
        return f"<DistIngredient(sku='{self.sku}', description='{self.description[:30]}...')>"


class PriceHistory(Base):
    """Track price changes over time for analysis and alerts."""

    __tablename__ = "price_history"
    __table_args__ = (
        Index("idx_price_history_lookup", "dist_ingredient_id", "effective_date"),
        Index("idx_price_history_source", "dist_ingredient_id", "source", "effective_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dist_ingredient_id = Column(UUID(as_uuid=True), ForeignKey("dist_ingredients.id"), nullable=False)
    price_cents = Column(Integer, nullable=False)
    effective_date = Column(DATE, nullable=False)
    source = Column(String(20))  # 'invoice', 'catalog', 'manual', 'quote'
    source_reference = Column(String(100))  # Invoice number, catalog date, etc.
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    dist_ingredient = relationship("DistIngredient", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory(price_cents={self.price_cents}, source='{self.source}')>"
