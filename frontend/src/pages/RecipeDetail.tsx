import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { getRecipe, getRecipeCost } from '@/lib/api'
import type { IngredientCostBreakdown } from '@/types/recipe'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PriceIngredientModal } from '@/components/PriceIngredientModal'
import { ArrowLeft, Pencil, Printer, AlertTriangle, DollarSign } from 'lucide-react'

// Format quantity for display with scaling
function formatQuantity(value: number | string, unit: string | null, multiplier: number): string {
  const scaled = Number(value) * multiplier
  // Smart rounding based on magnitude
  let display: string
  if (scaled >= 1000) {
    display = Math.round(scaled).toString()
  } else if (scaled >= 100) {
    display = Math.round(scaled).toString()
  } else if (scaled >= 10) {
    display = (Math.round(scaled * 10) / 10).toString()
  } else if (scaled >= 1) {
    display = (Math.round(scaled * 100) / 100).toString()
  } else {
    display = scaled.toFixed(2)
  }

  const unitDisplay = unit || ''
  return unitDisplay ? `${display} ${unitDisplay}` : display
}

// Format price display
function formatPrice(cents: number | string | null): string {
  if (cents === null) return '-'
  return `$${(Number(cents) / 100).toFixed(2)}`
}

function formatPricePerUnit(cents: number | string | null, unit: string): string {
  if (cents === null) return '-'
  const numCents = Number(cents)
  if (numCents < 1) {
    return `$${(numCents / 100).toFixed(6)}/${unit}`
  }
  return `$${(numCents / 100).toFixed(4)}/${unit}`
}

export function RecipeDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [multiplier, setMultiplier] = useState(1)
  const [pricingMode, setPricingMode] = useState<'recent' | 'average'>('recent')
  const [pricingIngredient, setPricingIngredient] = useState<{
    id: string
    name: string
    base_unit: string
  } | null>(null)

  const { data: recipe, isLoading, error } = useQuery({
    queryKey: ['recipe', id],
    queryFn: () => getRecipe(id!),
    enabled: !!id,
  })

  const { data: costData } = useQuery({
    queryKey: ['recipe-cost', id, pricingMode],
    queryFn: () => getRecipeCost(id!, { pricing_mode: pricingMode }),
    enabled: !!id,
  })

  const handleMultiplierChange = (value: string) => {
    const num = parseFloat(value)
    if (!isNaN(num) && num > 0) {
      setMultiplier(num)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/4" />
          <div className="h-8 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-100 rounded w-1/3" />
        </div>
      </div>
    )
  }

  if (error || !recipe) {
    return (
      <div className="max-w-3xl mx-auto">
        <Link to="/recipes" className="inline-flex items-center text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Recipes
        </Link>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Recipe not found</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const scaledYield = Number(recipe.yield_quantity) * multiplier
  const yieldDisplay = scaledYield % 1 === 0 ? scaledYield : scaledYield.toFixed(1)

  return (
    <>
      {/* Screen version */}
      <div className="max-w-3xl mx-auto space-y-6 print:hidden">
        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Link
            to="/recipes"
            className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Recipes
          </Link>
          <div className="flex items-center gap-2">
            <Link to={`/recipes/${id}/edit`}>
              <Button variant="outline" size="sm">
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
            </Link>
            <Button variant="outline" size="sm" onClick={handlePrint}>
              <Printer className="h-4 w-4 mr-2" />
              Print
            </Button>
          </div>
        </div>

        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{recipe.name}</h1>
          <p className="text-gray-500 mt-1">
            Base yield: {recipe.yield_quantity} {recipe.yield_unit}
            {recipe.yield_weight_grams && (
              <span className="ml-2 text-gray-400">
                ({Number(recipe.yield_weight_grams).toLocaleString()}g)
              </span>
            )}
          </p>
        </div>

        {/* Scaling Control */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <span className="text-sm font-medium text-gray-700">Scale:</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMultiplier(0.5)}
                  className={multiplier === 0.5 ? 'bg-gray-100' : ''}
                >
                  ½×
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMultiplier(1)}
                  className={multiplier === 1 ? 'bg-gray-100' : ''}
                >
                  1×
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMultiplier(2)}
                  className={multiplier === 2 ? 'bg-gray-100' : ''}
                >
                  2×
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMultiplier(3)}
                  className={multiplier === 3 ? 'bg-gray-100' : ''}
                >
                  3×
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  step="0.25"
                  min="0.25"
                  value={multiplier}
                  onChange={(e) => handleMultiplierChange(e.target.value)}
                  className="w-20 text-center"
                />
                <span className="text-sm text-gray-500">×</span>
              </div>
              <span className="text-sm text-gray-600 ml-auto">
                → <strong>{yieldDisplay} {recipe.yield_unit}</strong>
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Ingredients */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Ingredients
          </h2>
          <Card>
            <CardContent className="py-0">
              <table className="w-full">
                <tbody className="divide-y divide-gray-100">
                  {recipe.ingredients.map((ing) => (
                    <tr key={ing.id} className="text-sm">
                      <td className="py-2.5 pr-4 text-right tabular-nums font-medium text-gray-900 w-24">
                        {formatQuantity(ing.quantity_grams, ing.ingredient_base_unit, multiplier)}
                      </td>
                      <td className="py-2.5 text-gray-700">
                        <Link
                          to={`/ingredients/${ing.ingredient_id}`}
                          className="text-gray-900 hover:text-blue-600 hover:underline transition-colors"
                        >
                          {ing.ingredient_name || 'Unknown'}
                        </Link>
                        {ing.prep_note && (
                          <span className="text-gray-400 ml-1">— {ing.prep_note}</span>
                        )}
                        {ing.is_optional && (
                          <span className="text-gray-400 ml-1">(optional)</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>

        {/* Cost Breakdown */}
        {costData && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
                Cost Breakdown
              </h2>
              <div className="flex items-center gap-2">
                <select
                  value={pricingMode}
                  onChange={(e) => setPricingMode(e.target.value as 'recent' | 'average')}
                  className="text-xs border rounded px-2 py-1 bg-white"
                >
                  <option value="recent">Most Recent</option>
                  <option value="average">Avg (30 days)</option>
                </select>
              </div>
            </div>
            <Card>
              <CardContent className="py-0">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-left text-xs text-gray-500 uppercase">
                      <th className="py-2 pr-2 w-24 text-right">Qty</th>
                      <th className="py-2 pr-2">Ingredient</th>
                      <th className="py-2 pr-2 text-right">Unit Cost</th>
                      <th className="py-2 text-right">Extended</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {costData.ingredients.map((ing: IngredientCostBreakdown) => (
                      <tr
                        key={ing.ingredient_id}
                        className={`text-sm ${!ing.has_price ? 'bg-yellow-50' : ''}`}
                      >
                        <td className="py-2 pr-2 text-right tabular-nums font-medium text-gray-900">
                          {formatQuantity(Number(ing.quantity_grams) * multiplier, ing.ingredient_base_unit, 1)}
                        </td>
                        <td className="py-2 pr-2">
                          <Link
                            to={`/ingredients/${ing.ingredient_id}`}
                            className={`hover:text-blue-600 hover:underline transition-colors ${
                              !ing.has_price ? 'text-yellow-700' : 'text-gray-900'
                            }`}
                          >
                            {!ing.has_price && (
                              <AlertTriangle className="inline h-3.5 w-3.5 mr-1 text-yellow-600" />
                            )}
                            {ing.ingredient_name}
                          </Link>
                          {ing.distributor_name && (
                            <span className="text-gray-400 text-xs ml-1">({ing.distributor_name})</span>
                          )}
                        </td>
                        <td className="py-2 pr-2 text-right tabular-nums text-gray-600 text-xs">
                          {ing.has_price
                            ? formatPricePerUnit(ing.price_per_base_unit_cents, ing.ingredient_base_unit)
                            : (
                              <button
                                onClick={() => setPricingIngredient({
                                  id: ing.ingredient_id,
                                  name: ing.ingredient_name,
                                  base_unit: ing.ingredient_base_unit,
                                })}
                                className="text-yellow-600 hover:text-yellow-700 font-medium hover:underline inline-flex items-center gap-1"
                              >
                                <DollarSign className="h-3 w-3" />
                                add
                              </button>
                            )
                          }
                        </td>
                        <td className="py-2 text-right tabular-nums font-medium">
                          {ing.has_price
                            ? formatPrice(Math.round(Number(ing.cost_cents || 0) * multiplier))
                            : '-'
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="border-t-2 border-gray-200">
                    <tr className="text-sm font-semibold">
                      <td colSpan={3} className="py-2 text-right text-gray-600">
                        Total Cost:
                      </td>
                      <td className="py-2 text-right tabular-nums text-gray-900">
                        {formatPrice(Math.round(costData.total_cost_cents * multiplier))}
                      </td>
                    </tr>
                    <tr className="text-sm">
                      <td colSpan={3} className="py-1 text-right text-gray-500">
                        Per {recipe.yield_unit}:
                      </td>
                      <td className="py-1 text-right tabular-nums text-gray-700">
                        ${(Number(costData.cost_per_unit_cents) * multiplier / 100).toFixed(4)}
                      </td>
                    </tr>
                    {costData.cost_per_gram_cents && (
                      <tr className="text-sm">
                        <td colSpan={3} className="py-1 text-right text-gray-500">
                          Per g:
                          {costData.yield_weight_grams && (
                            <span className="text-xs text-gray-400 ml-1">
                              (yield: {Number(costData.yield_weight_grams).toLocaleString()}g)
                            </span>
                          )}
                        </td>
                        <td className="py-1 text-right tabular-nums text-gray-700">
                          ${(Number(costData.cost_per_gram_cents) / 100).toFixed(4)}
                        </td>
                      </tr>
                    )}
                  </tfoot>
                </table>
                {costData.has_unpriced_ingredients && (
                  <div className="py-3 px-2 border-t bg-yellow-50 text-yellow-700 text-xs flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    {costData.unpriced_count} ingredient{costData.unpriced_count > 1 ? 's' : ''} missing price data.
                    Cost is incomplete.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Components (sub-recipes) */}
        {recipe.components.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Components
            </h2>
            <Card>
              <CardContent className="py-0">
                <table className="w-full">
                  <tbody className="divide-y divide-gray-100">
                    {recipe.components.map((comp) => (
                      <tr key={comp.id} className="text-sm">
                        <td className="py-2.5 pr-4 text-right tabular-nums font-medium text-gray-900 w-24">
                          {(Number(comp.quantity) * multiplier).toFixed(1)} {comp.component_recipe_yield_unit}
                        </td>
                        <td className="py-2.5">
                          <Link
                            to={`/recipes/${comp.component_recipe_id}`}
                            className="text-blue-600 hover:underline"
                          >
                            {comp.component_recipe_name || 'Unknown'}
                          </Link>
                          {comp.notes && (
                            <span className="text-gray-400 ml-1">— {comp.notes}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Procedure */}
        {recipe.instructions && (
          <div>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Procedure
            </h2>
            <Card>
              <CardContent className="py-4">
                <ol className="space-y-4">
                  {recipe.instructions.split('\n').filter(line => line.trim()).map((line, idx) => {
                    // Strip existing numbering if present
                    const text = line.replace(/^\d+[.\)]\s*/, '').trim()
                    if (!text) return null
                    return (
                      <li key={idx} className="flex gap-4 text-sm leading-relaxed">
                        <span className="flex-shrink-0 w-6 h-6 bg-gray-100 text-gray-600 rounded text-xs font-medium flex items-center justify-center">
                          {idx + 1}
                        </span>
                        <span className="text-gray-700 pt-0.5">{text}</span>
                      </li>
                    )
                  })}
                </ol>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Notes */}
        {recipe.notes && (
          <div>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Notes
            </h2>
            <Card>
              <CardContent className="py-4">
                <p className="text-sm text-gray-600">{recipe.notes}</p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Print version - completely separate layout */}
      <div className="hidden print:block">
        <style>{`
          @media print {
            @page {
              margin: 0.75in;
              size: letter;
            }
            body {
              -webkit-print-color-adjust: exact;
              print-color-adjust: exact;
            }
          }
        `}</style>

        {/* Print Header */}
        <div className="border-b-2 border-gray-900 pb-4 mb-6">
          <h1 className="text-2xl font-bold text-gray-900 uppercase tracking-wide">
            {recipe.name}
          </h1>
          <div className="flex justify-between items-baseline mt-2 text-sm text-gray-600">
            <span>
              Yield: <strong>{yieldDisplay} {recipe.yield_unit}</strong>
              {multiplier !== 1 && (
                <span className="ml-2 text-gray-400">
                  (base: {recipe.yield_quantity} {recipe.yield_unit} × {multiplier})
                </span>
              )}
            </span>
            <span>
              {new Date().toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
              })}
            </span>
          </div>
        </div>

        {/* Print Ingredients - compact two-column layout */}
        <div className="mb-4">
          <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
            Ingredients
          </h2>
          <div className="grid grid-cols-2 gap-x-4 text-xs">
            {recipe.ingredients.map((ing, idx) => (
              <div key={ing.id} className={`flex py-0.5 ${idx % 2 === 0 ? '' : ''}`}>
                <span className="w-16 text-right tabular-nums font-mono font-medium pr-2 flex-shrink-0">
                  {formatQuantity(ing.quantity_grams, ing.ingredient_base_unit, multiplier)}
                </span>
                <span className="text-gray-800">
                  {ing.ingredient_name}
                  {ing.prep_note && <span className="text-gray-500"> — {ing.prep_note}</span>}
                  {ing.is_optional && <span className="text-gray-400"> (opt)</span>}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Print Components */}
        {recipe.components.length > 0 && (
          <div className="mb-4">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Components
            </h2>
            <div className="grid grid-cols-2 gap-x-4 text-xs">
              {recipe.components.map((comp) => (
                <div key={comp.id} className="flex py-0.5">
                  <span className="w-16 text-right tabular-nums font-mono font-medium pr-2 flex-shrink-0">
                    {(Number(comp.quantity) * multiplier).toFixed(1)} {comp.component_recipe_yield_unit}
                  </span>
                  <span className="text-gray-800">
                    {comp.component_recipe_name}
                    {comp.notes && <span className="text-gray-500"> — {comp.notes}</span>}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Print Procedure */}
        {recipe.instructions && (
          <div className="mb-4">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Procedure
            </h2>
            <ol className="text-xs space-y-1.5">
              {recipe.instructions.split('\n').filter(line => line.trim()).map((line, idx) => {
                const text = line.replace(/^\d+[.\)]\s*/, '').trim()
                if (!text) return null
                return (
                  <li key={idx} className="flex gap-2">
                    <span className="font-mono font-bold text-gray-400 w-4 text-right flex-shrink-0">
                      {idx + 1}.
                    </span>
                    <span className="leading-snug">{text}</span>
                  </li>
                )
              })}
            </ol>
          </div>
        )}

        {/* Print Notes */}
        {recipe.notes && (
          <div className="mb-4">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Notes
            </h2>
            <p className="text-xs text-gray-600 leading-snug">{recipe.notes}</p>
          </div>
        )}

        {/* Print Footer */}
        <div className="border-t border-gray-300 pt-3 mt-8 text-xs text-gray-400 text-center">
          Mill & Whistle Kitchen • Confidential
        </div>
      </div>

      {/* Pricing Modal */}
      {pricingIngredient && (
        <PriceIngredientModal
          open={!!pricingIngredient}
          onClose={() => setPricingIngredient(null)}
          ingredient={pricingIngredient}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['recipe-cost', id] })
          }}
        />
      )}
    </>
  )
}
