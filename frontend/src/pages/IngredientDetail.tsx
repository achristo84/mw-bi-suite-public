import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getIngredient, getIngredientPrices, getRecipes, updateIngredient, createRecipe } from '@/lib/api'
import type { DistributorPrice, DistIngredientVariant } from '@/types/ingredient'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ArrowLeft, ChefHat, Package, ExternalLink, Plus, DollarSign } from 'lucide-react'
import { PriceIngredientModal } from '@/components/PriceIngredientModal'

function formatPrice(cents: number | string | null): string {
  if (cents === null || cents === undefined) return '-'
  return `$${(Number(cents) / 100).toFixed(2)}`
}

function formatPricePerUnit(cents: number | string | null, unit: string): string {
  if (cents === null || cents === undefined) return '-'
  return `$${(Number(cents) / 100).toFixed(4)}/${unit}`
}

export function IngredientDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // UI State
  const [showCreateRecipe, setShowCreateRecipe] = useState(false)
  const [newRecipeYield, setNewRecipeYield] = useState('')
  const [selectedRecipeId, setSelectedRecipeId] = useState<string>('')
  const [showPriceModal, setShowPriceModal] = useState(false)

  const { data: ingredient, isLoading, error } = useQuery({
    queryKey: ['ingredient', id],
    queryFn: () => getIngredient(id!),
    enabled: !!id,
  })

  const { data: prices } = useQuery({
    queryKey: ['ingredient-prices', id],
    queryFn: () => getIngredientPrices(id!),
    enabled: !!id,
  })

  // Get recipes for linking
  const { data: recipesData } = useQuery({
    queryKey: ['recipes'],
    queryFn: () => getRecipes(),
  })
  const recipes = recipesData?.recipes || []

  // Mutation to update ingredient type
  const updateTypeMutation = useMutation({
    mutationFn: (newType: 'raw' | 'component') =>
      updateIngredient(id!, {
        ingredient_type: newType,
        source_recipe_id: newType === 'raw' ? null : ingredient?.source_recipe_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingredient', id] })
      queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
    },
  })

  // Mutation to link recipe
  const linkRecipeMutation = useMutation({
    mutationFn: (recipeId: string) =>
      updateIngredient(id!, {
        ingredient_type: 'component',
        source_recipe_id: recipeId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingredient', id] })
      queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
      setSelectedRecipeId('')
    },
  })

  // Mutation to create and link recipe
  const createRecipeMutation = useMutation({
    mutationFn: async () => {
      if (!ingredient || !newRecipeYield) return
      const yieldNum = parseFloat(newRecipeYield)
      const recipe = await createRecipe({
        name: ingredient.name,
        yield_quantity: yieldNum,
        yield_unit: ingredient.base_unit,
        instructions: '',
      })
      await updateIngredient(id!, {
        ingredient_type: 'component',
        source_recipe_id: recipe.id,
      })
      return recipe
    },
    onSuccess: (recipe) => {
      queryClient.invalidateQueries({ queryKey: ['ingredient', id] })
      queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
      queryClient.invalidateQueries({ queryKey: ['recipes'] })
      setShowCreateRecipe(false)
      setNewRecipeYield('')
      if (recipe) {
        navigate(`/recipes/${recipe.id}/edit`)
      }
    },
  })

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/4" />
          <div className="h-8 bg-gray-200 rounded w-1/2" />
        </div>
      </div>
    )
  }

  if (error || !ingredient) {
    return (
      <div className="max-w-2xl mx-auto">
        <Link to="/recipes" className="inline-flex items-center text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Link>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Ingredient not found</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back button */}
      <button
        onClick={() => window.history.back()}
        className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </button>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{ingredient.name}</h1>
        <p className="text-gray-500 mt-1">
          {ingredient.category} • Base unit: {ingredient.base_unit}
        </p>
      </div>

      {/* Ingredient Type Section */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Ingredient Type
        </h2>
        <Card>
          <CardContent className="py-4">
            <div className="flex gap-4 mb-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="ingredient_type"
                  checked={ingredient.ingredient_type === 'raw'}
                  onChange={() => updateTypeMutation.mutate('raw')}
                  className="w-4 h-4"
                />
                <Package className="h-4 w-4 text-gray-500" />
                <span className="text-sm">
                  <strong>Raw</strong> - Purchased from distributors
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="ingredient_type"
                  checked={ingredient.ingredient_type === 'component'}
                  onChange={() => updateTypeMutation.mutate('component')}
                  className="w-4 h-4"
                />
                <ChefHat className="h-4 w-4 text-blue-500" />
                <span className="text-sm">
                  <strong>Component</strong> - Made from a recipe
                </span>
              </label>
            </div>

            {/* Component-specific: Link to Recipe */}
            {ingredient.ingredient_type === 'component' && (
              <div className="border-t pt-4 mt-2">
                {ingredient.source_recipe_id && ingredient.source_recipe_name ? (
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Costed from recipe:</p>
                      <Link
                        to={`/recipes/${ingredient.source_recipe_id}`}
                        className="text-blue-600 hover:underline font-medium inline-flex items-center gap-1"
                      >
                        {ingredient.source_recipe_name}
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        updateIngredient(id!, { source_recipe_id: null })
                          .then(() => {
                            queryClient.invalidateQueries({ queryKey: ['ingredient', id] })
                            queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
                          })
                      }}
                    >
                      Unlink
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-sm text-orange-600 font-medium">
                      No recipe linked. Link an existing recipe or create a new one.
                    </p>

                    {/* Link existing recipe */}
                    <div className="flex gap-2">
                      <select
                        value={selectedRecipeId}
                        onChange={(e) => setSelectedRecipeId(e.target.value)}
                        className="flex-1 border rounded-md px-3 py-2 text-sm bg-white"
                      >
                        <option value="">Select existing recipe...</option>
                        {recipes.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name} ({r.yield_quantity} {r.yield_unit})
                          </option>
                        ))}
                      </select>
                      <Button
                        onClick={() => linkRecipeMutation.mutate(selectedRecipeId)}
                        disabled={!selectedRecipeId || linkRecipeMutation.isPending}
                      >
                        Link
                      </Button>
                    </div>

                    <div className="text-center text-sm text-gray-400">— or —</div>

                    {/* Create new recipe */}
                    {!showCreateRecipe ? (
                      <Button
                        variant="outline"
                        onClick={() => setShowCreateRecipe(true)}
                        className="w-full"
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Create Recipe for {ingredient.name}
                      </Button>
                    ) : (
                      <div className="border rounded-lg p-4 bg-gray-50 space-y-3">
                        <p className="text-sm font-medium">Create "{ingredient.name}" Recipe</p>
                        <div>
                          <Label htmlFor="yield">Batch yield (in {ingredient.base_unit})</Label>
                          <Input
                            id="yield"
                            type="number"
                            step="any"
                            value={newRecipeYield}
                            onChange={(e) => setNewRecipeYield(e.target.value)}
                            placeholder={`e.g., 1000 for 1000${ingredient.base_unit}`}
                            className="mt-1"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            How much does one batch produce?
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            onClick={() => {
                              setShowCreateRecipe(false)
                              setNewRecipeYield('')
                            }}
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={() => createRecipeMutation.mutate()}
                            disabled={!newRecipeYield || createRecipeMutation.isPending}
                          >
                            {createRecipeMutation.isPending ? 'Creating...' : 'Create & Edit Recipe'}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Pricing from distributors */}
      {prices && prices.distributor_prices && prices.distributor_prices.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Distributor Pricing
          </h2>
          <Card>
            <CardContent className="py-0">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-xs text-gray-500 uppercase">
                    <th className="py-2 pr-2">Distributor</th>
                    <th className="py-2 pr-2">Description</th>
                    <th className="py-2 pr-2 text-right">Pack Price</th>
                    <th className="py-2 text-right">Per {ingredient.base_unit}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {prices.distributor_prices.map((dp: DistributorPrice, idx: number) => (
                    <tr key={idx} className="text-sm">
                      <td className="py-2 pr-2 font-medium">{dp.distributor_name}</td>
                      <td className="py-2 pr-2 text-gray-600">{dp.description}</td>
                      <td className="py-2 pr-2 text-right tabular-nums">
                        {formatPrice(dp.price_cents)}
                      </td>
                      <td className="py-2 text-right tabular-nums font-medium">
                        {dp.price_per_base_unit_cents
                          ? formatPricePerUnit(dp.price_per_base_unit_cents, ingredient.base_unit)
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Distributor variants */}
      {ingredient.variants && ingredient.variants.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Distributor SKUs
          </h2>
          <Card>
            <CardContent className="py-0">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-xs text-gray-500 uppercase">
                    <th className="py-2 pr-2">Distributor</th>
                    <th className="py-2 pr-2">SKU</th>
                    <th className="py-2 pr-2">Description</th>
                    <th className="py-2">Pack</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ingredient.variants.map((v: DistIngredientVariant) => (
                    <tr key={v.id} className="text-sm">
                      <td className="py-2 pr-2 font-medium">{v.distributor_name}</td>
                      <td className="py-2 pr-2 text-gray-500">{v.sku || '-'}</td>
                      <td className="py-2 pr-2">{v.description}</td>
                      <td className="py-2 text-gray-500">
                        {v.pack_size && v.pack_unit
                          ? `${v.pack_size}× ${v.pack_unit}`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* No pricing data - show Add Price button */}
      {(!prices || !prices.distributor_prices || prices.distributor_prices.length === 0) &&
        (!ingredient.variants || ingredient.variants.length === 0) && (
        <Card>
          <CardContent className="py-8 text-center">
            <p className="text-gray-500 mb-4">No pricing data available for this ingredient.</p>
            <Button onClick={() => setShowPriceModal(true)}>
              <DollarSign className="h-4 w-4 mr-2" />
              Add Price
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Add Price button when we have some data but want to add more */}
      {((prices?.distributor_prices && prices.distributor_prices.length > 0) ||
        (ingredient.variants && ingredient.variants.length > 0)) && (
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={() => setShowPriceModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Price
          </Button>
        </div>
      )}

      {/* Price Modal */}
      {showPriceModal && (
        <PriceIngredientModal
          open={showPriceModal}
          onClose={() => setShowPriceModal(false)}
          ingredient={{
            id: ingredient.id,
            name: ingredient.name,
            base_unit: ingredient.base_unit,
            category: ingredient.category || undefined,
          }}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['ingredient', id] })
            queryClient.invalidateQueries({ queryKey: ['ingredient-prices', id] })
          }}
        />
      )}
    </div>
  )
}
