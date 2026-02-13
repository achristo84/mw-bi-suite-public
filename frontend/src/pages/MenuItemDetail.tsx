import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { getMenuItemCost } from '@/lib/api'
import type { IngredientCostBreakdown, PackagingCostItem } from '@/types/recipe'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatPrice(cents: number | null): string {
  if (cents === null) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

function formatPricePerUnit(cents: number | null, unit: string): string {
  if (cents === null) return '-'
  const numCents = Number(cents)
  if (numCents < 1) {
    return `$${(numCents / 100).toFixed(6)}/${unit}`
  }
  return `$${(numCents / 100).toFixed(4)}/${unit}`
}

function formatQuantity(value: number, unit: string | null): string {
  let display: string
  if (value >= 100) {
    display = Math.round(value).toString()
  } else if (value >= 10) {
    display = (Math.round(value * 10) / 10).toString()
  } else if (value >= 1) {
    display = (Math.round(value * 100) / 100).toString()
  } else {
    display = value.toFixed(2)
  }
  return unit ? `${display} ${unit}` : display
}

function statusLabel(status: string) {
  switch (status) {
    case 'healthy': return { text: 'Healthy', color: 'bg-green-100 text-green-700 border-green-300' }
    case 'warning': return { text: 'Warning', color: 'bg-yellow-100 text-yellow-700 border-yellow-300' }
    case 'danger': return { text: 'Danger', color: 'bg-red-100 text-red-700 border-red-300' }
    default: return { text: 'Unknown', color: 'bg-gray-100 text-gray-700' }
  }
}

export function MenuItemDetail() {
  const { id } = useParams<{ id: string }>()
  const [pricingMode, setPricingMode] = useState<'recent' | 'average'>('recent')

  const { data, isLoading, error } = useQuery({
    queryKey: ['menu-item-cost', id, pricingMode],
    queryFn: () => getMenuItemCost(id!, { pricing_mode: pricingMode }),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/4" />
          <div className="h-8 bg-gray-200 rounded w-1/2" />
          <div className="h-64 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-3xl mx-auto">
        <Link to="/menu" className="inline-flex items-center text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Menu
        </Link>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Menu item not found</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const status = statusLabel(data.margin_status)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Navigation */}
      <Link
        to="/menu"
        className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Menu
      </Link>

      {/* Header with margin display */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{data.name}</h1>
        <div className="flex items-center gap-3 mt-2">
          <Badge variant="outline" className={status.color}>
            {status.text}
          </Badge>
          <span className="text-gray-500 text-sm">
            Food Cost: <span className={cn(
              'font-semibold',
              data.margin_status === 'healthy' && 'text-green-600',
              data.margin_status === 'warning' && 'text-yellow-600',
              data.margin_status === 'danger' && 'text-red-600',
            )}>
              {Number(data.food_cost_percent).toFixed(1)}%
            </span>
          </span>
          {data.has_unpriced_ingredients && (
            <span className="inline-flex items-center gap-1 text-xs text-yellow-600">
              <AlertTriangle className="h-3.5 w-3.5" />
              Incomplete pricing
            </span>
          )}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Menu Price</p>
            <p className="text-xl font-bold text-gray-900 mt-1 tabular-nums">
              {formatPrice(data.menu_price_cents)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Total Cost</p>
            <p className="text-xl font-bold text-gray-900 mt-1 tabular-nums">
              {formatPrice(data.total_cost_cents)}
            </p>
          </CardContent>
        </Card>
        <Card className={cn(
          data.margin_status === 'healthy' && 'border-green-200',
          data.margin_status === 'warning' && 'border-yellow-200',
          data.margin_status === 'danger' && 'border-red-200',
        )}>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Gross Margin</p>
            <p className={cn(
              'text-xl font-bold mt-1 tabular-nums',
              data.margin_status === 'healthy' && 'text-green-600',
              data.margin_status === 'warning' && 'text-yellow-600',
              data.margin_status === 'danger' && 'text-red-600',
            )}>
              {formatPrice(data.gross_margin_cents)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recipe Cost Breakdown */}
      {data.recipe_cost_breakdown && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Recipe Cost
              {data.recipe_cost_breakdown && (
                <span className="ml-2 text-gray-400 normal-case font-normal">
                  ({data.recipe_cost_breakdown.recipe_name})
                </span>
              )}
            </h2>
            <div className="flex items-center gap-2">
              <select
                value={pricingMode}
                onChange={e => setPricingMode(e.target.value as 'recent' | 'average')}
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
                  {data.recipe_cost_breakdown.ingredients.map((ing: IngredientCostBreakdown) => {
                    // Scale by portion_of_recipe for display
                    const scaledQty = Number(ing.quantity_grams) * Number(data.recipe_cost_breakdown!.yield_quantity > 0
                      ? 1 : 1) // Use raw qty; cost is scaled below
                    return (
                      <tr
                        key={ing.ingredient_id}
                        className={cn('text-sm', !ing.has_price && 'bg-yellow-50')}
                      >
                        <td className="py-2 pr-2 text-right tabular-nums font-medium text-gray-900">
                          {formatQuantity(Number(ing.quantity_grams), ing.ingredient_base_unit)}
                        </td>
                        <td className="py-2 pr-2">
                          <Link
                            to={`/ingredients/${ing.ingredient_id}`}
                            className={cn(
                              'hover:text-blue-600 hover:underline transition-colors',
                              !ing.has_price ? 'text-yellow-700' : 'text-gray-900'
                            )}
                          >
                            {!ing.has_price && <AlertTriangle className="inline h-3.5 w-3.5 mr-1 text-yellow-600" />}
                            {ing.ingredient_name}
                          </Link>
                          {ing.distributor_name && (
                            <span className="text-gray-400 text-xs ml-1">({ing.distributor_name})</span>
                          )}
                        </td>
                        <td className="py-2 pr-2 text-right tabular-nums text-gray-600 text-xs">
                          {ing.has_price
                            ? formatPricePerUnit(ing.price_per_base_unit_cents, ing.ingredient_base_unit)
                            : '-'
                          }
                        </td>
                        <td className="py-2 text-right tabular-nums font-medium">
                          {ing.has_price ? formatPrice(ing.cost_cents) : '-'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot className="border-t-2 border-gray-200">
                  <tr className="text-sm">
                    <td colSpan={3} className="py-2 text-right text-gray-500">
                      Full recipe cost:
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-700">
                      {formatPrice(data.recipe_cost_breakdown.total_cost_cents)}
                    </td>
                  </tr>
                  <tr className="text-sm font-semibold">
                    <td colSpan={3} className="py-1 text-right text-gray-600">
                      Portion cost ({(Number(data.recipe_cost_breakdown.yield_quantity) > 0
                        ? `× ${Number(data.recipe_cost_breakdown.yield_quantity)} ${data.recipe_cost_breakdown.yield_unit}`
                        : ''
                      )}):
                    </td>
                    <td className="py-1 text-right tabular-nums text-gray-900">
                      {formatPrice(data.recipe_cost_cents)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Packaging Cost */}
      {data.packaging_breakdown.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Packaging Cost
          </h2>
          <Card>
            <CardContent className="py-0">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-xs text-gray-500 uppercase">
                    <th className="py-2 pr-2">Item</th>
                    <th className="py-2 pr-2 text-right">Qty</th>
                    <th className="py-2 pr-2 text-right">Usage Rate</th>
                    <th className="py-2 pr-2 text-right">Unit Cost</th>
                    <th className="py-2 text-right">Extended</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.packaging_breakdown.map((pkg: PackagingCostItem) => (
                    <tr
                      key={pkg.ingredient_id}
                      className={cn('text-sm', !pkg.has_price && 'bg-yellow-50')}
                    >
                      <td className="py-2 pr-2 text-gray-900">
                        <Link
                          to={`/ingredients/${pkg.ingredient_id}`}
                          className="hover:text-blue-600 hover:underline"
                        >
                          {pkg.ingredient_name}
                        </Link>
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums text-gray-700">
                        {Number(pkg.quantity)}
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums text-gray-500">
                        {(Number(pkg.usage_rate) * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 pr-2 text-right tabular-nums text-gray-600 text-xs">
                        {pkg.has_price ? formatPrice(Number(pkg.price_per_unit_cents)) : '-'}
                      </td>
                      <td className="py-2 text-right tabular-nums font-medium">
                        {pkg.has_price ? formatPrice(pkg.cost_cents) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t-2 border-gray-200">
                  <tr className="text-sm font-semibold">
                    <td colSpan={4} className="py-2 text-right text-gray-600">
                      Total Packaging:
                    </td>
                    <td className="py-2 text-right tabular-nums text-gray-900">
                      {formatPrice(data.packaging_cost_cents)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Total Summary */}
      <Card className={cn(
        'border-2',
        data.margin_status === 'healthy' && 'border-green-200',
        data.margin_status === 'warning' && 'border-yellow-200',
        data.margin_status === 'danger' && 'border-red-200',
      )}>
        <CardContent className="py-4">
          <table className="w-full text-sm">
            <tbody>
              <tr>
                <td className="py-1 text-gray-600">Recipe cost:</td>
                <td className="py-1 text-right tabular-nums text-gray-900">
                  {formatPrice(data.recipe_cost_cents)}
                </td>
              </tr>
              {data.packaging_cost_cents > 0 && (
                <tr>
                  <td className="py-1 text-gray-600">Packaging cost:</td>
                  <td className="py-1 text-right tabular-nums text-gray-900">
                    {formatPrice(data.packaging_cost_cents)}
                  </td>
                </tr>
              )}
              <tr className="border-t font-semibold">
                <td className="py-2 text-gray-900">Total Cost:</td>
                <td className="py-2 text-right tabular-nums text-gray-900">
                  {formatPrice(data.total_cost_cents)}
                </td>
              </tr>
              <tr>
                <td className="py-1 text-gray-600">Menu Price:</td>
                <td className="py-1 text-right tabular-nums text-gray-900">
                  {formatPrice(data.menu_price_cents)}
                </td>
              </tr>
              <tr className="border-t font-semibold">
                <td className={cn(
                  'py-2',
                  data.margin_status === 'healthy' && 'text-green-700',
                  data.margin_status === 'warning' && 'text-yellow-700',
                  data.margin_status === 'danger' && 'text-red-700',
                )}>
                  Gross Margin:
                </td>
                <td className={cn(
                  'py-2 text-right tabular-nums',
                  data.margin_status === 'healthy' && 'text-green-700',
                  data.margin_status === 'warning' && 'text-yellow-700',
                  data.margin_status === 'danger' && 'text-red-700',
                )}>
                  {formatPrice(data.gross_margin_cents)}
                  <span className="ml-2 text-sm">
                    ({Number(data.food_cost_percent).toFixed(1)}% food cost)
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
