"""Recipe importer service - parses Google Sheets data into recipes."""
import logging
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.recipe import Recipe, RecipeIngredient
from app.services.units import convert_to_base_unit, normalize_unit, get_unit_type, BaseUnit

logger = logging.getLogger(__name__)


@dataclass
class ParsedIngredient:
    """Parsed ingredient from a recipe sheet."""
    name: str
    quantity: Decimal
    unit: str
    notes: Optional[str] = None
    # After matching
    matched_ingredient_id: Optional[uuid.UUID] = None
    matched_ingredient_name: Optional[str] = None
    quantity_in_base_units: Optional[Decimal] = None
    base_unit: Optional[str] = None


@dataclass
class ParsedRecipe:
    """Parsed recipe from a Google Sheet."""
    name: str
    yield_quantity: Decimal
    yield_unit: str
    ingredients: list[ParsedIngredient] = field(default_factory=list)
    instructions: str = ""
    # Import status
    unmapped_ingredients: list[ParsedIngredient] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RecipeImporter:
    """Service for importing recipes from Google Sheets."""

    def __init__(self, db: Session):
        self.db = db
        # Cache of canonical ingredients for matching
        self._ingredient_cache: dict[str, Ingredient] = {}
        self._load_ingredient_cache()

    def _load_ingredient_cache(self):
        """Load all canonical ingredients into cache for fuzzy matching."""
        ingredients = self.db.query(Ingredient).all()
        for ing in ingredients:
            # Index by lowercase name for fuzzy matching
            self._ingredient_cache[ing.name.lower()] = ing
            # Also index common variations
            # e.g., "whole milk" -> also match "milk, whole"
            words = ing.name.lower().split()
            if len(words) > 1:
                self._ingredient_cache[", ".join(reversed(words))] = ing

    def parse_recipe_sheet(self, sheet_data: list[list]) -> ParsedRecipe:
        """
        Parse a recipe from Google Sheets data.

        Expected format (based on Breakfast Creemee example):
        - Row 0: Recipe name in col A, "YIELD: Xunit" somewhere in row
        - Row 1: Headers - INGREDIENT, UNIT, AMOUNT, ...
        - Rows 2+: Ingredient data until empty row or "PROCEDURE"
        - PROCEDURE section: Numbered steps

        Args:
            sheet_data: 2D list from Sheets API

        Returns:
            ParsedRecipe with ingredients and instructions
        """
        if not sheet_data or len(sheet_data) < 3:
            raise ValueError("Sheet data too short to contain a recipe")

        # Parse header row (row 0)
        recipe_name, yield_qty, yield_unit = self._parse_header_row(sheet_data[0])

        recipe = ParsedRecipe(
            name=recipe_name,
            yield_quantity=yield_qty,
            yield_unit=yield_unit,
        )

        # Find column indices from row 1
        header_row = [str(cell).upper() if cell else "" for cell in sheet_data[1]]
        col_indices = self._find_column_indices(header_row)

        if col_indices['ingredient'] is None:
            recipe.warnings.append("Could not find INGREDIENT column header")
            return recipe

        # Parse ingredient rows
        procedure_started = False
        procedure_lines = []

        for row_idx, row in enumerate(sheet_data[2:], start=2):
            if not row or all(cell == "" or cell is None for cell in row):
                continue

            first_cell = str(row[0]).strip().upper() if row else ""

            # Check for PROCEDURE section
            if "PROCEDURE" in first_cell or "INSTRUCTIONS" in first_cell:
                procedure_started = True
                continue

            if procedure_started:
                # Collect procedure text
                line = str(row[0]).strip() if row else ""
                if line:
                    procedure_lines.append(line)
            else:
                # Parse as ingredient
                parsed = self._parse_ingredient_row(row, col_indices)
                if parsed:
                    recipe.ingredients.append(parsed)

        # Join procedure lines
        recipe.instructions = "\n".join(procedure_lines)

        return recipe

    def _parse_header_row(self, row: list) -> tuple[str, Decimal, str]:
        """Parse the header row to extract recipe name and yield."""
        recipe_name = str(row[0]).strip() if row else "Unnamed Recipe"

        # Look for YIELD pattern in any cell
        yield_qty = Decimal("1")
        yield_unit = "batch"

        for cell in row:
            cell_str = str(cell).upper() if cell else ""
            # Match patterns like "YIELD: 4qts" or "YIELD: 12 servings"
            match = re.search(r'YIELD[:\s]*(\d+\.?\d*)\s*(\w+)', cell_str, re.IGNORECASE)
            if match:
                try:
                    yield_qty = Decimal(match.group(1))
                    yield_unit = match.group(2).lower()
                except InvalidOperation:
                    pass
                break

        return recipe_name, yield_qty, yield_unit

    def _find_column_indices(self, header_row: list[str]) -> dict:
        """Find column indices for ingredient data."""
        indices = {
            'ingredient': None,
            'unit': None,
            'amount': None,
            'notes': None,
        }

        for idx, cell in enumerate(header_row):
            cell_upper = cell.upper()
            if 'INGREDIENT' in cell_upper:
                indices['ingredient'] = idx
            elif cell_upper == 'UNIT':
                indices['unit'] = idx
            elif 'AMOUNT' in cell_upper or cell_upper == 'QTY':
                indices['amount'] = idx
            elif 'NOTE' in cell_upper:
                indices['notes'] = idx

        return indices

    def _parse_ingredient_row(
        self,
        row: list,
        col_indices: dict
    ) -> Optional[ParsedIngredient]:
        """Parse a single ingredient row."""
        ing_idx = col_indices['ingredient']
        if ing_idx is None or ing_idx >= len(row):
            return None

        name = str(row[ing_idx]).strip() if row[ing_idx] else ""
        if not name or name.upper() in ('INGREDIENT', 'TOTAL', ''):
            return None

        # Get unit
        unit = "g"  # Default to grams
        unit_idx = col_indices['unit']
        if unit_idx is not None and unit_idx < len(row) and row[unit_idx]:
            unit = str(row[unit_idx]).strip()

        # Get amount
        amount = Decimal("0")
        amount_idx = col_indices['amount']
        if amount_idx is not None and amount_idx < len(row) and row[amount_idx]:
            try:
                amount = Decimal(str(row[amount_idx]))
            except InvalidOperation:
                pass

        # Get notes
        notes = None
        notes_idx = col_indices.get('notes')
        if notes_idx is not None and notes_idx < len(row) and row[notes_idx]:
            notes = str(row[notes_idx]).strip()

        return ParsedIngredient(
            name=name,
            quantity=amount,
            unit=unit,
            notes=notes,
        )

    def match_ingredients(self, recipe: ParsedRecipe) -> ParsedRecipe:
        """
        Match parsed ingredients to canonical ingredients.

        Updates recipe.unmapped_ingredients with any that couldn't be matched.
        """
        recipe.unmapped_ingredients = []

        for ing in recipe.ingredients:
            matched = self._find_matching_ingredient(ing.name)

            if matched:
                ing.matched_ingredient_id = matched.id
                ing.matched_ingredient_name = matched.name
                ing.base_unit = matched.base_unit

                # Convert quantity to base units
                try:
                    ing.quantity_in_base_units = convert_to_base_unit(
                        ing.quantity,
                        ing.unit,
                        matched.base_unit
                    )
                except Exception as e:
                    logger.warning(f"Could not convert {ing.quantity} {ing.unit} to {matched.base_unit}: {e}")
                    ing.quantity_in_base_units = ing.quantity
            else:
                recipe.unmapped_ingredients.append(ing)

        return recipe

    def _find_matching_ingredient(self, name: str) -> Optional[Ingredient]:
        """Find a matching canonical ingredient by name."""
        name_lower = name.lower().strip()

        # Exact match
        if name_lower in self._ingredient_cache:
            return self._ingredient_cache[name_lower]

        # Try partial matches
        for cached_name, ingredient in self._ingredient_cache.items():
            # Check if the ingredient name contains the search term
            if name_lower in cached_name or cached_name in name_lower:
                return ingredient

        # Try word-based matching
        name_words = set(name_lower.split())
        for cached_name, ingredient in self._ingredient_cache.items():
            cached_words = set(cached_name.split())
            # If significant word overlap
            if len(name_words & cached_words) >= min(len(name_words), 2):
                return ingredient

        return None

    def create_recipe(
        self,
        parsed: ParsedRecipe,
        skip_unmapped: bool = False
    ) -> Recipe:
        """
        Create a Recipe record from parsed data.

        Args:
            parsed: ParsedRecipe with matched ingredients
            skip_unmapped: If True, skip unmapped ingredients. If False, raise error.

        Returns:
            Created Recipe object (not yet committed)
        """
        if parsed.unmapped_ingredients and not skip_unmapped:
            unmapped_names = [i.name for i in parsed.unmapped_ingredients]
            raise ValueError(f"Cannot create recipe with unmapped ingredients: {unmapped_names}")

        # Check for duplicate recipe name
        existing = self.db.query(Recipe).filter(Recipe.name == parsed.name).first()
        if existing:
            raise ValueError(f"Recipe '{parsed.name}' already exists")

        recipe = Recipe(
            id=uuid.uuid4(),
            name=parsed.name,
            yield_quantity=parsed.yield_quantity,
            yield_unit=parsed.yield_unit,
            instructions=parsed.instructions,
            is_active=True,
        )
        self.db.add(recipe)

        # Add matched ingredients - combine duplicates by summing quantities
        ingredient_map: dict[uuid.UUID, dict] = {}
        for ing in parsed.ingredients:
            if ing.matched_ingredient_id:
                ing_id = ing.matched_ingredient_id
                qty = ing.quantity_in_base_units or ing.quantity
                if ing_id in ingredient_map:
                    # Combine with existing - sum quantities
                    ingredient_map[ing_id]['quantity'] += qty
                    # Append notes if different
                    if ing.notes and ing.notes not in (ingredient_map[ing_id]['notes'] or ''):
                        existing_notes = ingredient_map[ing_id]['notes'] or ''
                        ingredient_map[ing_id]['notes'] = f"{existing_notes}; {ing.notes}".strip('; ')
                else:
                    ingredient_map[ing_id] = {
                        'quantity': qty,
                        'notes': ing.notes,
                    }

        # Create recipe ingredients from combined map
        for ing_id, data in ingredient_map.items():
            recipe_ingredient = RecipeIngredient(
                id=uuid.uuid4(),
                recipe_id=recipe.id,
                ingredient_id=ing_id,
                quantity_grams=data['quantity'],
                prep_note=data['notes'],
                is_optional=False,
            )
            self.db.add(recipe_ingredient)

        return recipe

    def create_ingredients_from_unmapped(
        self,
        unmapped: list[ParsedIngredient],
        default_category: str = "uncategorized"
    ) -> list[Ingredient]:
        """
        Create new canonical ingredients from unmapped items.

        Args:
            unmapped: List of ParsedIngredient that weren't matched
            default_category: Category to assign to new ingredients

        Returns:
            List of created Ingredient objects
        """
        created = []

        for ing in unmapped:
            # Determine base unit from the source unit
            base_unit = "g"  # Default
            if ing.unit.lower() in ('ml', 'l', 'liter', 'litre', 'cup', 'cups', 'qt', 'qts', 'quart', 'quarts', 'gal', 'gallon'):
                base_unit = "ml"
            elif ing.unit.lower() in ('each', 'ea', 'ct', 'count', 'piece', 'pieces', 'pc', 'pcs'):
                base_unit = "each"

            # Check if already exists
            existing = self.db.query(Ingredient).filter(
                Ingredient.name.ilike(ing.name)
            ).first()
            if existing:
                # Update cache and link
                self._ingredient_cache[ing.name.lower()] = existing
                ing.matched_ingredient_id = existing.id
                ing.matched_ingredient_name = existing.name
                ing.base_unit = existing.base_unit
                continue

            ingredient = Ingredient(
                id=uuid.uuid4(),
                name=ing.name,
                category=default_category,
                base_unit=base_unit,
                ingredient_type="raw",
                yield_factor=Decimal("1.0"),
            )
            self.db.add(ingredient)
            created.append(ingredient)

            # Update cache
            self._ingredient_cache[ing.name.lower()] = ingredient

            # Update the parsed ingredient
            ing.matched_ingredient_id = ingredient.id
            ing.matched_ingredient_name = ingredient.name
            ing.base_unit = base_unit

            # Convert quantity
            try:
                ing.quantity_in_base_units = convert_to_base_unit(
                    ing.quantity,
                    ing.unit,
                    base_unit
                )
            except Exception:
                ing.quantity_in_base_units = ing.quantity

        return created


def import_recipe_from_sheet_data(
    db: Session,
    sheet_data: list[list],
    auto_create_ingredients: bool = False
) -> dict:
    """
    High-level function to import a recipe from sheet data.

    Args:
        db: Database session
        sheet_data: 2D list from Google Sheets
        auto_create_ingredients: If True, automatically create missing ingredients

    Returns:
        Dict with recipe info and any unmapped ingredients
    """
    importer = RecipeImporter(db)

    # Parse the sheet
    parsed = importer.parse_recipe_sheet(sheet_data)
    logger.info(f"Parsed recipe '{parsed.name}' with {len(parsed.ingredients)} ingredients")

    # Match ingredients
    parsed = importer.match_ingredients(parsed)
    logger.info(f"Matched {len(parsed.ingredients) - len(parsed.unmapped_ingredients)} ingredients, "
                f"{len(parsed.unmapped_ingredients)} unmapped")

    result = {
        'recipe_name': parsed.name,
        'yield_quantity': float(parsed.yield_quantity),
        'yield_unit': parsed.yield_unit,
        'total_ingredients': len(parsed.ingredients),
        'matched_ingredients': len(parsed.ingredients) - len(parsed.unmapped_ingredients),
        'unmapped_ingredients': [
            {
                'name': i.name,
                'quantity': float(i.quantity),
                'unit': i.unit,
            }
            for i in parsed.unmapped_ingredients
        ],
        'warnings': parsed.warnings,
        'recipe_id': None,
        'created': False,
    }

    # Handle unmapped ingredients
    if parsed.unmapped_ingredients:
        if auto_create_ingredients:
            created = importer.create_ingredients_from_unmapped(parsed.unmapped_ingredients)
            result['auto_created_ingredients'] = [i.name for i in created]
            # Re-match after creating
            parsed = importer.match_ingredients(parsed)

    # Create the recipe if all ingredients are mapped
    if not parsed.unmapped_ingredients:
        recipe = importer.create_recipe(parsed)
        db.commit()
        result['recipe_id'] = str(recipe.id)
        result['created'] = True
        logger.info(f"Created recipe '{recipe.name}' with ID {recipe.id}")

    return result
