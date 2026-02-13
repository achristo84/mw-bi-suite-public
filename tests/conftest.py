"""Test fixtures and configuration."""
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session as SessionType
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.distributor import Distributor
from app.models.ingredient import DistIngredient, Ingredient, PriceHistory
from app.models.recipe import Recipe, RecipeComponent, RecipeIngredient


# Patch SQLite type compiler to handle PostgreSQL-specific types (ARRAY, JSONB).
# This lets us reuse the same ORM models with an in-memory SQLite test database.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "TEXT"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"


@pytest.fixture(scope="function")
def engine():
    """Create an in-memory SQLite engine for testing."""
    # Use check_same_thread=False for compatibility with FastAPI TestClient
    # Use StaticPool to ensure all connections use the same in-memory database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Clean up
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_uuid():
    return uuid.uuid4()


@pytest.fixture
def distributor_factory(db):
    """Factory to create test distributors."""
    def _create(name="Test Distributor", **kwargs):
        # Extract is_active before passing kwargs to avoid duplicate
        is_active = kwargs.pop("is_active", True)
        dist = Distributor(
            id=kwargs.pop("id", make_uuid()),
            name=name,
            is_active=is_active,
            **kwargs,
        )
        db.add(dist)
        db.flush()
        return dist
    return _create


@pytest.fixture
def ingredient_factory(db):
    """Factory to create test ingredients."""
    def _create(name="Test Ingredient", base_unit="g", **kwargs):
        ing = Ingredient(
            id=kwargs.pop("id", make_uuid()),
            name=name,
            base_unit=base_unit,
            ingredient_type=kwargs.pop("ingredient_type", "raw"),
            **kwargs,
        )
        db.add(ing)
        db.flush()
        return ing
    return _create


@pytest.fixture
def dist_ingredient_factory(db):
    """Factory to create test distributor ingredients."""
    def _create(distributor, ingredient=None, sku="SKU-001", description="Test Item", **kwargs):
        di = DistIngredient(
            id=kwargs.pop("id", make_uuid()),
            distributor_id=distributor.id,
            ingredient_id=ingredient.id if ingredient else None,
            sku=sku,
            description=description,
            is_active=kwargs.pop("is_active", True),
            grams_per_unit=kwargs.pop("grams_per_unit", Decimal("453.592")),
            **kwargs,
        )
        db.add(di)
        db.flush()
        return di
    return _create


@pytest.fixture
def price_factory(db):
    """Factory to create price history entries."""
    def _create(dist_ingredient, price_cents=1000, effective_date=None, **kwargs):
        ph = PriceHistory(
            id=kwargs.pop("id", make_uuid()),
            dist_ingredient_id=dist_ingredient.id,
            price_cents=price_cents,
            effective_date=effective_date or date.today(),
            source=kwargs.pop("source", "invoice"),
            **kwargs,
        )
        db.add(ph)
        db.flush()
        return ph
    return _create


@pytest.fixture
def recipe_factory(db):
    """Factory to create test recipes."""
    def _create(name="Test Recipe", yield_quantity=1, yield_unit="each", **kwargs):
        recipe = Recipe(
            id=kwargs.pop("id", make_uuid()),
            name=name,
            yield_quantity=yield_quantity,
            yield_unit=yield_unit,
            yield_weight_grams=kwargs.pop("yield_weight_grams", None),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **kwargs,
        )
        db.add(recipe)
        db.flush()
        return recipe
    return _create


@pytest.fixture
def recipe_ingredient_factory(db):
    """Factory to create recipe ingredients."""
    def _create(recipe, ingredient, quantity_grams=100, **kwargs):
        ri = RecipeIngredient(
            id=kwargs.pop("id", make_uuid()),
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
            quantity_grams=quantity_grams,
            **kwargs,
        )
        db.add(ri)
        db.flush()
        return ri
    return _create
