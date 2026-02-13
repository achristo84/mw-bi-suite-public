import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPriceComparisonMatrix, getDistributors } from '@/lib/api'
import type { IngredientPriceComparison, DistributorPrice } from '@/types/ingredient'
import { INGREDIENT_CATEGORIES } from '@/types/ingredient'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'

// Format cents as dollars
function formatPrice(cents: number | string | null): string {
  if (cents === null) return '-'
  return `$${(Number(cents) / 100).toFixed(2)}`
}

// Format price per base unit (very small numbers)
function formatPricePerUnit(cents: number | string | null, unit: string): string {
  if (cents === null) return '-'
  const numCents = Number(cents)
  // For small prices, show more decimal places
  if (numCents < 1) {
    return `$${(numCents / 100).toFixed(6)}/${unit}`
  }
  return `$${(numCents / 100).toFixed(4)}/${unit}`
}

// Format spread percentage
function formatSpread(spread: number | string | null): string {
  if (spread === null) return '-'
  return `${Number(spread).toFixed(1)}%`
}

export function Prices() {
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [distributorFilter, setDistributorFilter] = useState<string>('')
  const [expandedIngredient, setExpandedIngredient] = useState<string | null>(null)

  // Fetch price comparison matrix
  const { data: priceData, isLoading } = useQuery({
    queryKey: ['price-comparison', categoryFilter, distributorFilter, searchTerm],
    queryFn: () =>
      getPriceComparisonMatrix({
        category: categoryFilter || undefined,
        distributor_id: distributorFilter || undefined,
        search: searchTerm || undefined,
        mapped_only: true,
      }),
  })

  // Fetch distributors for filter
  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  const ingredients = priceData?.ingredients || []

  // Calculate summary stats
  const ingredientsWithPrices = ingredients.filter(
    (i) => i.distributor_prices.some((p) => p.price_cents !== null)
  )
  const multiSourceIngredients = ingredients.filter(
    (i) => i.distributor_prices.filter((p) => p.price_cents !== null).length > 1
  )
  const totalSpread = multiSourceIngredients.reduce(
    (sum, i) => sum + (Number(i.price_spread_percent) || 0),
    0
  )
  const avgSpread = multiSourceIngredients.length > 0 ? totalSpread / multiSourceIngredients.length : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Price Comparison</h1>
        <div className="flex gap-2">
          <Badge variant="secondary" className="px-3 py-1">
            {ingredientsWithPrices.length} priced
          </Badge>
          <Badge variant="outline" className="px-3 py-1">
            Avg spread: {avgSpread.toFixed(1)}%
          </Badge>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search ingredients..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <select
              className="border rounded px-3 py-2 min-w-[150px]"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">All Categories</option>
              {INGREDIENT_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.replace('_', ' ')}
                </option>
              ))}
            </select>
            <select
              className="border rounded px-3 py-2 min-w-[180px]"
              value={distributorFilter}
              onChange={(e) => setDistributorFilter(e.target.value)}
            >
              <option value="">All Distributors</option>
              {distributors?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Price Comparison Table */}
      <Card>
        <CardHeader>
          <CardTitle>Ingredient Prices by Distributor</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-gray-500">Loading prices...</p>
          ) : ingredients.length === 0 ? (
            <p className="text-gray-500">
              No mapped ingredients with prices found. Map some distributor SKUs first.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left p-3 font-medium">Ingredient</th>
                    <th className="text-left p-3 font-medium">Category</th>
                    <th className="text-right p-3 font-medium">Best Price</th>
                    <th className="text-right p-3 font-medium">Spread</th>
                    <th className="text-left p-3 font-medium">Best Source</th>
                  </tr>
                </thead>
                <tbody>
                  {ingredients.map((ingredient) => (
                    <IngredientRow
                      key={ingredient.ingredient_id}
                      ingredient={ingredient}
                      isExpanded={expandedIngredient === ingredient.ingredient_id}
                      onToggle={() =>
                        setExpandedIngredient(
                          expandedIngredient === ingredient.ingredient_id
                            ? null
                            : ingredient.ingredient_id
                        )
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-6 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-100 border border-green-500 rounded"></div>
              <span>Best price</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-yellow-100 border border-yellow-500 rounded"></div>
              <span>&gt;10% above best</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-red-100 border border-red-500 rounded"></div>
              <span>&gt;25% above best</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// Individual ingredient row with expandable details
function IngredientRow({
  ingredient,
  isExpanded,
  onToggle,
}: {
  ingredient: IngredientPriceComparison
  isExpanded: boolean
  onToggle: () => void
}) {
  const pricedVariants = ingredient.distributor_prices.filter((p) => p.price_cents !== null)
  const bestVariant = ingredient.distributor_prices.find((p) => p.is_best_price)

  return (
    <>
      <tr
        className="border-b hover:bg-gray-50 cursor-pointer"
        onClick={onToggle}
      >
        <td className="p-3">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">{isExpanded ? '▼' : '▶'}</span>
            <span className="font-medium">{ingredient.ingredient_name}</span>
            <span className="text-gray-400 text-xs">({ingredient.base_unit})</span>
          </div>
        </td>
        <td className="p-3 text-gray-600 capitalize">
          {ingredient.category?.replace('_', ' ') || '-'}
        </td>
        <td className="p-3 text-right font-mono">
          {formatPricePerUnit(ingredient.best_price_per_base_unit, ingredient.base_unit)}
        </td>
        <td className="p-3 text-right">
          {pricedVariants.length > 1 ? (
            <span
              className={
                ingredient.price_spread_percent && ingredient.price_spread_percent > 25
                  ? 'text-red-600 font-medium'
                  : ingredient.price_spread_percent && ingredient.price_spread_percent > 10
                  ? 'text-yellow-600'
                  : 'text-green-600'
              }
            >
              {formatSpread(ingredient.price_spread_percent)}
            </span>
          ) : (
            <span className="text-gray-400">-</span>
          )}
        </td>
        <td className="p-3">
          {bestVariant ? (
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              {bestVariant.distributor_name}
            </Badge>
          ) : (
            <span className="text-gray-400">-</span>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr className="bg-gray-50">
          <td colSpan={5} className="p-0">
            <ExpandedPriceDetails ingredient={ingredient} />
          </td>
        </tr>
      )}
    </>
  )
}

// Expanded view showing all distributor prices for an ingredient
function ExpandedPriceDetails({ ingredient }: { ingredient: IngredientPriceComparison }) {
  const pricedVariants = ingredient.distributor_prices.filter((p) => p.price_cents !== null)

  if (pricedVariants.length === 0) {
    return (
      <div className="p-4 text-gray-500 text-sm">
        No price data available for this ingredient.
      </div>
    )
  }

  return (
    <div className="p-4 pl-10">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-500 text-xs uppercase">
            <th className="text-left pb-2">Distributor</th>
            <th className="text-left pb-2">SKU / Description</th>
            <th className="text-left pb-2">Pack</th>
            <th className="text-right pb-2">Pack Price</th>
            <th className="text-right pb-2">Price/{ingredient.base_unit}</th>
            <th className="text-right pb-2">vs Best</th>
          </tr>
        </thead>
        <tbody>
          {pricedVariants.map((variant) => (
            <PriceRow
              key={variant.dist_ingredient_id}
              variant={variant}
              bestPrice={ingredient.best_price_per_base_unit}
              baseUnit={ingredient.base_unit}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Individual price row in expanded view
function PriceRow({
  variant,
  bestPrice,
  baseUnit,
}: {
  variant: DistributorPrice
  bestPrice: number | null
  baseUnit: string
}) {
  // Calculate percentage above best
  let pctAboveBest: number | null = null
  const numBestPrice = Number(bestPrice)
  const numVariantPrice = Number(variant.price_per_base_unit_cents)
  if (numBestPrice && numVariantPrice && numBestPrice > 0) {
    pctAboveBest = ((numVariantPrice - numBestPrice) / numBestPrice) * 100
  }

  // Determine row style based on price comparison
  let rowClass = ''
  if (variant.is_best_price) {
    rowClass = 'bg-green-50'
  } else if (pctAboveBest && pctAboveBest > 25) {
    rowClass = 'bg-red-50'
  } else if (pctAboveBest && pctAboveBest > 10) {
    rowClass = 'bg-yellow-50'
  }

  return (
    <tr className={`border-t ${rowClass}`}>
      <td className="py-2">
        <span className={variant.is_best_price ? 'font-medium text-green-700' : ''}>
          {variant.distributor_name}
        </span>
      </td>
      <td className="py-2 text-gray-600">
        <div className="truncate max-w-[250px]" title={variant.description || undefined}>
          {variant.sku && <span className="text-gray-400 mr-2">{variant.sku}</span>}
          {variant.description}
        </div>
      </td>
      <td className="py-2 text-gray-600">
        {variant.pack_size && variant.pack_unit
          ? `${variant.pack_size}x ${variant.pack_unit}`
          : variant.grams_per_unit
          ? `${variant.grams_per_unit.toLocaleString()}${baseUnit}`
          : '-'}
      </td>
      <td className="py-2 text-right font-mono">
        {formatPrice(variant.price_cents)}
      </td>
      <td className="py-2 text-right font-mono">
        {formatPricePerUnit(variant.price_per_base_unit_cents, baseUnit)}
      </td>
      <td className="py-2 text-right">
        {variant.is_best_price ? (
          <Badge variant="outline" className="bg-green-100 text-green-700 text-xs">
            BEST
          </Badge>
        ) : pctAboveBest !== null ? (
          <span
            className={
              pctAboveBest > 25
                ? 'text-red-600'
                : pctAboveBest > 10
                ? 'text-yellow-600'
                : 'text-gray-500'
            }
          >
            +{pctAboveBest.toFixed(1)}%
          </span>
        ) : (
          '-'
        )}
      </td>
    </tr>
  )
}
