import { useState } from 'react'
import { createIngredient } from '@/lib/api'
import { useQueryClient } from '@tanstack/react-query'
import type { Ingredient } from '@/types/ingredient'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Plus, Search, Loader2 } from 'lucide-react'

interface IngredientPickerProps {
  filteredIngredients: Ingredient[]
  ingredientSearch: string
  onSearchChange: (value: string) => void
  onAddIngredient: (ingredient: Ingredient) => void
  onClose: () => void
  onError: (message: string) => void
}

export function IngredientPicker({
  filteredIngredients,
  ingredientSearch,
  onSearchChange,
  onAddIngredient,
  onClose,
  onError,
}: IngredientPickerProps) {
  const queryClient = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newIngredientName, setNewIngredientName] = useState('')
  const [newIngredientBaseUnit, setNewIngredientBaseUnit] = useState<'g' | 'ml' | 'each'>('g')
  const [newIngredientCategory, setNewIngredientCategory] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleCreate = async () => {
    if (!newIngredientName.trim()) return

    setIsCreating(true)
    try {
      const newIng = await createIngredient({
        name: newIngredientName.trim(),
        base_unit: newIngredientBaseUnit,
        category: newIngredientCategory || undefined,
      })

      onAddIngredient({
        ...newIng,
        ingredient_type: 'raw',
        source_recipe_id: null,
        source_recipe_name: null,
        storage_type: null,
        shelf_life_days: null,
        par_level_base_units: null,
        yield_factor: 1,
        notes: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      queryClient.invalidateQueries({ queryKey: ['ingredients'] })
      setShowCreateForm(false)
      setNewIngredientName('')
      setNewIngredientBaseUnit('g')
      setNewIngredientCategory('')
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to create ingredient')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <Card className="mt-3 border-blue-200 bg-blue-50/50">
      <CardContent className="py-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium">Add Ingredient</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowCreateForm(false)
              onSearchChange('')
              onClose()
            }}
            className="h-6 w-6 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {!showCreateForm ? (
          <>
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search ingredients..."
                value={ingredientSearch}
                onChange={(e) => onSearchChange(e.target.value)}
                className="pl-9 bg-white"
                autoFocus
              />
            </div>
            <div className="max-h-48 overflow-y-auto bg-white rounded border">
              {filteredIngredients.length === 0 ? (
                <div className="p-3 text-center">
                  {ingredientSearch ? (
                    <>
                      <p className="text-sm text-gray-500 mb-2">No matching ingredients found</p>
                      <Button
                        size="sm"
                        onClick={() => {
                          setNewIngredientName(ingredientSearch)
                          setShowCreateForm(true)
                        }}
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        Create "{ingredientSearch}"
                      </Button>
                    </>
                  ) : (
                    <p className="text-sm text-gray-500">Start typing to search</p>
                  )}
                </div>
              ) : (
                <div className="divide-y">
                  {filteredIngredients.slice(0, 10).map((ing) => (
                    <button
                      key={ing.id}
                      onClick={() => onAddIngredient(ing)}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex justify-between items-center"
                    >
                      <span>{ing.name}</span>
                      <span className="text-xs text-gray-400">{ing.base_unit}</span>
                    </button>
                  ))}
                  {ingredientSearch && (
                    <button
                      onClick={() => {
                        setNewIngredientName(ingredientSearch)
                        setShowCreateForm(true)
                      }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 flex items-center text-blue-600"
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Create new: "{ingredientSearch}"
                    </button>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium">Create New Ingredient</p>
            <div>
              <Label htmlFor="newIngName">Name</Label>
              <Input
                id="newIngName"
                value={newIngredientName}
                onChange={(e) => setNewIngredientName(e.target.value)}
                className="mt-1 bg-white"
                autoFocus
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="newIngBaseUnit">Base Unit</Label>
                <select
                  id="newIngBaseUnit"
                  value={newIngredientBaseUnit}
                  onChange={(e) => setNewIngredientBaseUnit(e.target.value as 'g' | 'ml' | 'each')}
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-white"
                >
                  <option value="g">Grams (g) - for solids</option>
                  <option value="ml">Milliliters (ml) - for liquids</option>
                  <option value="each">Each - for countable items</option>
                </select>
              </div>
              <div>
                <Label htmlFor="newIngCategory">Category</Label>
                <select
                  id="newIngCategory"
                  value={newIngredientCategory}
                  onChange={(e) => setNewIngredientCategory(e.target.value)}
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-white"
                >
                  <option value="">Select...</option>
                  <option value="dairy">Dairy</option>
                  <option value="produce">Produce</option>
                  <option value="protein">Protein</option>
                  <option value="dry_goods">Dry Goods</option>
                  <option value="beverages">Beverages</option>
                  <option value="coffee">Coffee</option>
                  <option value="bakery">Bakery</option>
                  <option value="frozen">Frozen</option>
                  <option value="packaging">Packaging</option>
                  <option value="cleaning">Cleaning</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateForm(false)
                  setNewIngredientName('')
                }}
              >
                Back
              </Button>
              <Button
                onClick={handleCreate}
                disabled={!newIngredientName.trim() || isCreating}
              >
                {isCreating ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-1" />
                )}
                Create & Add
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
