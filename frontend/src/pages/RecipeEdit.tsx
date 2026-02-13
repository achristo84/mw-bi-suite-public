import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getRecipe,
  getIngredients,
  createRecipe,
  updateRecipe,
  addRecipeIngredient,
  updateRecipeIngredient,
  removeRecipeIngredient,
} from '@/lib/api'
import { toBaseUnit } from '@/lib/unitConversions'
import type { Ingredient } from '@/types/ingredient'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ArrowLeft, Save, X, Plus, Loader2 } from 'lucide-react'
import { IngredientTable } from '@/components/recipe-edit/IngredientTable'
import { IngredientPicker } from '@/components/recipe-edit/IngredientPicker'
import type { EditableIngredient } from '@/components/recipe-edit/IngredientTable'

export function RecipeEdit() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNewRecipe = !id || id === 'new'

  const [name, setName] = useState('')
  const [yieldQuantity, setYieldQuantity] = useState('')
  const [yieldUnit, setYieldUnit] = useState('')
  const [yieldWeightGrams, setYieldWeightGrams] = useState('')
  const [instructions, setInstructions] = useState('')
  const [notes, setNotes] = useState('')
  const [ingredients, setIngredients] = useState<EditableIngredient[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddIngredient, setShowAddIngredient] = useState(false)
  const [ingredientSearch, setIngredientSearch] = useState('')

  const { data: recipe, isLoading: recipeLoading } = useQuery({
    queryKey: ['recipe', id],
    queryFn: () => getRecipe(id!),
    enabled: !isNewRecipe,
  })

  const { data: allIngredientsData } = useQuery({
    queryKey: ['ingredients'],
    queryFn: () => getIngredients(),
  })
  const allIngredients = allIngredientsData?.ingredients || []

  const filteredIngredients = allIngredients.filter(
    (ing) =>
      ing.name.toLowerCase().includes(ingredientSearch.toLowerCase()) &&
      !ingredients.some((ri) => ri.ingredient_id === ing.id)
  )

  useEffect(() => {
    if (recipe) {
      setName(recipe.name)
      setYieldQuantity(recipe.yield_quantity.toString())
      setYieldUnit(recipe.yield_unit)
      setYieldWeightGrams(recipe.yield_weight_grams?.toString() || '')
      setInstructions(recipe.instructions || '')
      setNotes(recipe.notes || '')
      setIngredients(
        recipe.ingredients.map((ing) => {
          const baseUnit = ing.ingredient_base_unit || 'g'
          return {
            ingredient_id: ing.ingredient_id,
            ingredient_name: ing.ingredient_name || 'Unknown',
            ingredient_base_unit: baseUnit,
            quantity_grams: ing.quantity_grams,
            display_quantity: ing.quantity_grams,
            display_unit: baseUnit,
            prep_note: ing.prep_note || '',
            is_optional: ing.is_optional,
            isNew: false,
            isModified: false,
          }
        })
      )
    }
  }, [recipe])

  const handleIngredientChange = (index: number, field: string, value: string | number | boolean) => {
    setIngredients((prev) =>
      prev.map((ing, i) => {
        if (i !== index) return ing
        const updated = { ...ing, [field]: value, isModified: true }
        if (field === 'display_quantity') {
          updated.quantity_grams = toBaseUnit(value as number, ing.display_unit)
        }
        if (field === 'display_unit') {
          updated.quantity_grams = toBaseUnit(ing.display_quantity, value as string)
        }
        return updated
      })
    )
  }

  const handleAddIngredient = (ingredient: Ingredient) => {
    setIngredients((prev) => [
      ...prev,
      {
        ingredient_id: ingredient.id,
        ingredient_name: ingredient.name,
        ingredient_base_unit: ingredient.base_unit,
        quantity_grams: 0,
        display_quantity: 0,
        display_unit: ingredient.base_unit,
        prep_note: '',
        is_optional: false,
        isNew: true,
        isModified: true,
      },
    ])
    setShowAddIngredient(false)
    setIngredientSearch('')
  }

  const handleRemoveIngredient = (index: number) => {
    setIngredients((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSave = async () => {
    setError(null)
    setIsSaving(true)

    try {
      if (!name.trim()) throw new Error('Recipe name is required')
      if (!yieldQuantity || parseFloat(yieldQuantity) <= 0) throw new Error('Yield quantity must be greater than 0')
      if (!yieldUnit.trim()) throw new Error('Yield unit is required')

      if (isNewRecipe) {
        const newRecipe = await createRecipe({
          name: name.trim(),
          yield_quantity: parseFloat(yieldQuantity),
          yield_unit: yieldUnit.trim(),
          yield_weight_grams: yieldWeightGrams ? parseFloat(yieldWeightGrams) : undefined,
          instructions: instructions.trim() || undefined,
          notes: notes.trim() || undefined,
          ingredients: ingredients
            .filter((ing) => ing.quantity_grams > 0)
            .map((ing) => ({
              ingredient_id: ing.ingredient_id,
              quantity_grams: ing.quantity_grams,
              prep_note: ing.prep_note || undefined,
              is_optional: ing.is_optional,
            })),
        })
        queryClient.invalidateQueries({ queryKey: ['recipes'] })
        navigate(`/recipes/${newRecipe.id}`)
      } else {
        await updateRecipe(id!, {
          name: name.trim(),
          yield_quantity: parseFloat(yieldQuantity),
          yield_unit: yieldUnit.trim(),
          yield_weight_grams: yieldWeightGrams ? parseFloat(yieldWeightGrams) : undefined,
          instructions: instructions.trim() || undefined,
          notes: notes.trim() || undefined,
        })

        const originalIngredients = recipe?.ingredients || []
        const currentIds = new Set(ingredients.map((i) => i.ingredient_id))

        for (const orig of originalIngredients) {
          if (!currentIds.has(orig.ingredient_id)) {
            await removeRecipeIngredient(id!, orig.ingredient_id)
          }
        }

        for (const ing of ingredients) {
          if (ing.isNew && ing.quantity_grams > 0) {
            await addRecipeIngredient(id!, {
              ingredient_id: ing.ingredient_id,
              quantity_grams: ing.quantity_grams,
              prep_note: ing.prep_note || undefined,
              is_optional: ing.is_optional,
            })
          }
        }

        for (const ing of ingredients) {
          if (!ing.isNew && ing.isModified) {
            await updateRecipeIngredient(id!, ing.ingredient_id, {
              quantity_grams: ing.quantity_grams,
              prep_note: ing.prep_note,
              is_optional: ing.is_optional,
            })
          }
        }

        queryClient.invalidateQueries({ queryKey: ['recipe', id] })
        queryClient.invalidateQueries({ queryKey: ['recipes'] })
        navigate(`/recipes/${id}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save recipe')
    } finally {
      setIsSaving(false)
    }
  }

  if (recipeLoading) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/4" />
          <div className="h-10 bg-gray-200 rounded w-full" />
          <div className="h-10 bg-gray-100 rounded w-1/2" />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          to={isNewRecipe ? '/recipes' : `/recipes/${id}`}
          className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          {isNewRecipe ? 'Recipes' : 'Back to Recipe'}
        </Link>
        <div className="flex items-center gap-2">
          <Link to={isNewRecipe ? '/recipes' : `/recipes/${id}`}>
            <Button variant="outline" size="sm">
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
          </Link>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save
          </Button>
        </div>
      </div>

      <h1 className="text-2xl font-semibold text-gray-900">
        {isNewRecipe ? 'New Recipe' : 'Edit Recipe'}
      </h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Recipe Details */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div>
            <Label htmlFor="name">Recipe Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Breakfast Creemee"
              className="mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="yieldQuantity">Yield Quantity</Label>
              <Input
                id="yieldQuantity"
                type="number"
                step="0.25"
                min="0"
                value={yieldQuantity}
                onChange={(e) => setYieldQuantity(e.target.value)}
                placeholder="4"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="yieldUnit">Yield Unit</Label>
              <Input
                id="yieldUnit"
                value={yieldUnit}
                onChange={(e) => setYieldUnit(e.target.value)}
                placeholder="quarts"
                className="mt-1"
              />
            </div>
          </div>

          {yieldUnit && !['g', 'ml', 'each'].includes(yieldUnit.toLowerCase()) && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <Label htmlFor="yieldWeightGrams" className="text-blue-800">
                Yield Weight (grams)
              </Label>
              <p className="text-xs text-blue-600 mt-0.5 mb-2">
                Enter the actual weight of the finished product for accurate cost-per-gram calculations.
                This accounts for evaporation or weight changes during cooking.
              </p>
              <Input
                id="yieldWeightGrams"
                type="number"
                step="1"
                min="0"
                value={yieldWeightGrams}
                onChange={(e) => setYieldWeightGrams(e.target.value)}
                placeholder="e.g., 1200"
                className="bg-white"
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ingredients */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Ingredients
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddIngredient(true)}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Ingredient
          </Button>
        </div>

        <IngredientTable
          ingredients={ingredients}
          onIngredientChange={handleIngredientChange}
          onRemoveIngredient={handleRemoveIngredient}
        />

        {showAddIngredient && (
          <IngredientPicker
            filteredIngredients={filteredIngredients}
            ingredientSearch={ingredientSearch}
            onSearchChange={setIngredientSearch}
            onAddIngredient={handleAddIngredient}
            onClose={() => setShowAddIngredient(false)}
            onError={(msg) => setError(msg)}
          />
        )}
      </div>

      {/* Procedure */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Procedure
        </h2>
        <Card>
          <CardContent className="pt-4">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Enter procedure steps, one per line..."
              rows={8}
              className="w-full px-3 py-2 border rounded-md text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-2">
              Each line will be displayed as a numbered step.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Notes
        </h2>
        <Card>
          <CardContent className="pt-4">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes about this recipe..."
              rows={3}
              className="w-full px-3 py-2 border rounded-md text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </CardContent>
        </Card>
      </div>

      {/* Bottom Save Button */}
      <div className="flex justify-end gap-2 pt-4 border-t">
        <Link to={isNewRecipe ? '/recipes' : `/recipes/${id}`}>
          <Button variant="outline">Cancel</Button>
        </Link>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          {isNewRecipe ? 'Create Recipe' : 'Save Changes'}
        </Button>
      </div>
    </div>
  )
}
