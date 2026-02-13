"""Recipe, RecipeIngredient, and MenuItem models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, TIMESTAMP,
    ForeignKey, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from . import Base


class Recipe(Base):
    """Batch recipes with yields."""

    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    yield_quantity = Column(Numeric(10, 2), nullable=False)
    yield_unit = Column(String(20), nullable=False)  # 'servings', 'grams', 'each', 'quarts'
    yield_weight_grams = Column(Numeric(12, 3))  # Actual yield weight for component costing (when volume != weight)
    instructions = Column(Text)
    prep_time_minutes = Column(Integer)
    cook_time_minutes = Column(Integer)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ingredients = relationship("RecipeIngredient", back_populates="recipe")
    menu_items = relationship("MenuItem", back_populates="recipe")
    # Sub-recipes this recipe uses (e.g., mocha uses chocolate syrup)
    components = relationship(
        "RecipeComponent",
        foreign_keys="RecipeComponent.recipe_id",
        back_populates="recipe",
        cascade="all, delete-orphan",
    )
    # Recipes that use this recipe as a component
    used_in = relationship(
        "RecipeComponent",
        foreign_keys="RecipeComponent.component_recipe_id",
        back_populates="component_recipe",
    )

    def __repr__(self):
        return f"<Recipe(name='{self.name}')>"


class RecipeIngredient(Base):
    """Ingredients used in each recipe."""

    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients"),
        Index("idx_recipe_ingredients_recipe", "recipe_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False)
    quantity_grams = Column(Numeric(10, 3), nullable=False)  # Amount in base units
    prep_note = Column(String(100))  # "diced", "room temperature", etc.
    is_optional = Column(Boolean, default=False)

    # Relationships
    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipe_ingredients")

    def __repr__(self):
        return f"<RecipeIngredient(recipe_id={self.recipe_id}, ingredient_id={self.ingredient_id})>"


class RecipeComponent(Base):
    """Links a recipe to sub-recipes it uses as components.

    Example: Mocha recipe uses Chocolate Syrup recipe as a component.
    """

    __tablename__ = "recipe_components"
    __table_args__ = (
        UniqueConstraint("recipe_id", "component_recipe_id", name="uq_recipe_components"),
        Index("idx_recipe_components_recipe", "recipe_id"),
        Index("idx_recipe_components_component", "component_recipe_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    component_recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)  # Amount of component's yield_unit needed
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    recipe = relationship("Recipe", foreign_keys=[recipe_id], back_populates="components")
    component_recipe = relationship("Recipe", foreign_keys=[component_recipe_id], back_populates="used_in")

    def __repr__(self):
        return f"<RecipeComponent(recipe_id={self.recipe_id}, component_recipe_id={self.component_recipe_id})>"


class MenuItem(Base):
    """Items sold to customers with pricing."""

    __tablename__ = "menu_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"))  # Nullable for retail
    portion_of_recipe = Column(Numeric(5, 4), default=1.0)  # Fraction of recipe yield
    menu_price_cents = Column(Integer, nullable=False)
    category = Column(String(50))  # 'breakfast', 'drinks', 'retail', 'add-on'
    toast_id = Column(String(50))  # Toast menu item ID for sync
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    recipe = relationship("Recipe", back_populates="menu_items")
    packaging = relationship("MenuItemPackaging", back_populates="menu_item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MenuItem(name='{self.name}', price=${self.menu_price_cents/100:.2f})>"


class MenuItemPackaging(Base):
    """Packaging items for menu items (cups, lids, bags, etc.) with usage rate.

    Example: A latte needs 1x cup (100% usage) but only 0.5x bag (50% of customers take it to go).
    """

    __tablename__ = "menu_item_packaging"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "ingredient_id", name="uq_menu_item_packaging"),
        Index("idx_menu_item_packaging_menu_item", "menu_item_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)  # How many per menu item
    usage_rate = Column(Numeric(4, 3), nullable=False, default=1.0)  # 0.0-1.0, e.g., 0.5 = 50% of the time
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    menu_item = relationship("MenuItem", back_populates="packaging")
    ingredient = relationship("Ingredient", back_populates="menu_item_packaging")

    def __repr__(self):
        return f"<MenuItemPackaging(menu_item_id={self.menu_item_id}, ingredient_id={self.ingredient_id}, usage_rate={self.usage_rate})>"
