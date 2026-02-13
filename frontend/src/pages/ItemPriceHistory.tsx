import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { getIngredients, getIngredientPriceHistory } from '@/lib/api'
import type { IngredientPriceHistory, PriceHistoryEntry, DistributorPriceHistory } from '@/types/ingredient'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Search,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  Calendar,
  DollarSign,
  ArrowLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Format price
function formatPrice(cents: number | null): string {
  if (cents === null || cents === 0) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

// Format date
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

// Format full date
function formatFullDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// Flatten all entries from distributors for combined view
interface FlattenedEntry extends PriceHistoryEntry {
  distributor_name: string
  distributor_id: string
  description: string
}

function flattenEntries(priceHistory: IngredientPriceHistory): FlattenedEntry[] {
  const entries: FlattenedEntry[] = []
  for (const dist of priceHistory.distributors) {
    for (const entry of dist.history) {
      entries.push({
        ...entry,
        distributor_name: dist.distributor_name,
        distributor_id: dist.distributor_id,
        description: dist.description,
      })
    }
  }
  // Sort by date descending
  return entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export function ItemPriceHistory() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedIngredientId = searchParams.get('ingredient')
  const [searchTerm, setSearchTerm] = useState('')
  const [days, setDays] = useState('90')

  // Fetch ingredients list
  const { data: ingredientsData, isLoading: ingredientsLoading } = useQuery({
    queryKey: ['ingredients', searchTerm],
    queryFn: () => getIngredients({ search: searchTerm || undefined }),
  })

  // Fetch price history for selected ingredient
  const { data: priceHistory, isLoading: historyLoading } = useQuery({
    queryKey: ['ingredient-price-history', selectedIngredientId, days],
    queryFn: () => getIngredientPriceHistory(selectedIngredientId!, parseInt(days)),
    enabled: !!selectedIngredientId,
  })

  const ingredients = ingredientsData?.ingredients || []

  // Select an ingredient
  const selectIngredient = (id: string) => {
    setSearchParams({ ingredient: id })
  }

  // Go back to list
  const clearSelection = () => {
    setSearchParams({})
  }

  // Calculate stats from price history
  const calculateStats = (history: IngredientPriceHistory) => {
    const allEntries = flattenEntries(history)
    if (allEntries.length === 0) return { bestPrice: null, range: null, trend: null }

    const prices = allEntries
      .map(e => e.price_per_base_unit_cents)
      .filter((p): p is number => p !== null)

    if (prices.length === 0) return { bestPrice: null, range: null, trend: null }

    const bestPrice = Math.min(...prices)
    const range = { min: Math.min(...prices), max: Math.max(...prices) }

    // Calculate trend (recent vs older)
    const recent = prices.slice(0, Math.min(5, prices.length))
    const older = prices.slice(-Math.min(5, prices.length))
    const recentAvg = recent.reduce((sum, p) => sum + p, 0) / recent.length
    const olderAvg = older.reduce((sum, p) => sum + p, 0) / older.length

    const trend = olderAvg > 0 ? ((recentAvg - olderAvg) / olderAvg) * 100 : null

    return { bestPrice, range, trend, count: allEntries.length }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {selectedIngredientId && (
            <Button variant="ghost" size="icon" onClick={clearSelection}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
          )}
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">
              {selectedIngredientId ? 'Price History' : 'Price History'}
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {selectedIngredientId
                ? 'View price trends over time'
                : 'Select an ingredient to view price history'}
            </p>
          </div>
        </div>
        <Link to="/orders">
          <Button variant="outline">
            <Search className="h-4 w-4 mr-2" />
            Order Hub
          </Button>
        </Link>
      </div>

      {/* Ingredient Selection */}
      {!selectedIngredientId && (
        <>
          {/* Search */}
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search ingredients..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Ingredients List */}
          {ingredientsLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          )}

          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {ingredients.map((ingredient) => (
              <Card
                key={ingredient.id}
                className="cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => selectIngredient(ingredient.id)}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium">{ingredient.name}</h3>
                      <p className="text-sm text-gray-500">{ingredient.category}</p>
                    </div>
                    <DollarSign className="h-5 w-5 text-gray-400" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {!ingredientsLoading && ingredients.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No ingredients found. Try a different search term.
            </div>
          )}
        </>
      )}

      {/* Price History View */}
      {selectedIngredientId && (
        <>
          {/* Time Range Selector */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-gray-500" />
              <select
                value={days}
                onChange={(e) => setDays(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
                <option value="180">Last 6 months</option>
                <option value="365">Last year</option>
              </select>
            </div>
          </div>

          {/* Loading */}
          {historyLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          )}

          {/* Price History Data */}
          {priceHistory && (
            <div className="space-y-6">
              {/* Summary Header */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-xl">{priceHistory.ingredient_name}</CardTitle>
                </CardHeader>
                <CardContent>
                  {(() => {
                    const stats = calculateStats(priceHistory)
                    return (
                      <div className="grid grid-cols-3 gap-6">
                        {/* Current Best Price */}
                        <div>
                          <p className="text-sm text-gray-500">Current Best</p>
                          <p className="text-2xl font-semibold">
                            {stats.bestPrice ? formatPrice(stats.bestPrice) : '-'}
                          </p>
                          <p className="text-sm text-gray-500">
                            per {priceHistory.base_unit}
                          </p>
                        </div>

                        {/* Price Range */}
                        <div>
                          <p className="text-sm text-gray-500">Price Range</p>
                          <p className="text-lg">
                            {stats.range
                              ? `${formatPrice(stats.range.min)} - ${formatPrice(stats.range.max)}`
                              : '-'}
                          </p>
                          <p className="text-sm text-gray-500">
                            {stats.count || 0} price points
                          </p>
                        </div>

                        {/* Trend */}
                        <div>
                          <p className="text-sm text-gray-500">Trend</p>
                          {stats.trend === null ? (
                            <p className="text-lg">-</p>
                          ) : (
                            <div
                              className={cn(
                                'flex items-center gap-2',
                                stats.trend > 2 ? 'text-red-500' : stats.trend < -2 ? 'text-green-500' : 'text-gray-500'
                              )}
                            >
                              {stats.trend > 2 ? (
                                <TrendingUp className="h-5 w-5" />
                              ) : stats.trend < -2 ? (
                                <TrendingDown className="h-5 w-5" />
                              ) : (
                                <Minus className="h-5 w-5" />
                              )}
                              <span className="text-lg font-medium">
                                {stats.trend > 0 ? '+' : ''}{stats.trend.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          <p className="text-sm text-gray-500">vs period start</p>
                        </div>
                      </div>
                    )
                  })()}
                </CardContent>
              </Card>

              {/* Price Chart */}
              {priceHistory.distributors.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Price Over Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <PriceChart
                      distributors={priceHistory.distributors}
                      baseUnit={priceHistory.base_unit}
                    />
                  </CardContent>
                </Card>
              )}

              {/* Price Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Price History</CardTitle>
                </CardHeader>
                <CardContent>
                  {(() => {
                    const entries = flattenEntries(priceHistory)
                    if (entries.length === 0) {
                      return (
                        <p className="text-center py-8 text-gray-500">
                          No price history available for this time period.
                        </p>
                      )
                    }

                    return (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 border-b">
                            <th className="pb-2 font-medium">Date</th>
                            <th className="pb-2 font-medium">Distributor</th>
                            <th className="pb-2 font-medium">Description</th>
                            <th className="pb-2 font-medium text-right">Price</th>
                            <th className="pb-2 font-medium text-right">Per {priceHistory.base_unit}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {entries.map((entry, idx) => (
                            <tr key={idx}>
                              <td className="py-2">{formatFullDate(entry.date)}</td>
                              <td className="py-2">{entry.distributor_name}</td>
                              <td className="py-2 text-gray-600 truncate max-w-[200px]">
                                {entry.description}
                              </td>
                              <td className="py-2 text-right">
                                {formatPrice(entry.price_cents)}
                              </td>
                              <td className="py-2 text-right font-medium">
                                {formatPrice(entry.price_per_base_unit_cents)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  })()}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Simple SVG Price Chart
function PriceChart({
  distributors,
  baseUnit: _baseUnit,
}: {
  distributors: DistributorPriceHistory[]
  baseUnit: string
}) {
  // Collect all entries with dates
  const allEntries: Array<{ date: Date; price: number; distributor: string }> = []
  for (const dist of distributors) {
    for (const entry of dist.history) {
      if (entry.price_per_base_unit_cents !== null) {
        allEntries.push({
          date: new Date(entry.date),
          price: entry.price_per_base_unit_cents,
          distributor: dist.distributor_name,
        })
      }
    }
  }

  if (allEntries.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No price data available for chart.
      </div>
    )
  }

  // Sort by date
  allEntries.sort((a, b) => a.date.getTime() - b.date.getTime())

  // Chart dimensions
  const width = 800
  const height = 300
  const padding = { top: 20, right: 20, bottom: 40, left: 60 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  // Calculate scales
  const prices = allEntries.map((e) => e.price)
  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  const priceRange = maxPrice - minPrice || 1

  const minDate = allEntries[0].date.getTime()
  const maxDate = allEntries[allEntries.length - 1].date.getTime()
  const dateRange = maxDate - minDate || 1

  // Scale functions
  const scaleX = (date: number) =>
    padding.left + ((date - minDate) / dateRange) * chartWidth
  const scaleY = (price: number) =>
    padding.top + chartHeight - ((price - minPrice) / priceRange) * chartHeight

  // Group by distributor
  const distributorNames = Array.from(new Set(allEntries.map((e) => e.distributor)))
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

  // Generate path for each distributor
  const distributorPaths = distributorNames.map((distributorName, idx) => {
    const distributorEntries = allEntries
      .filter((e) => e.distributor === distributorName)
      .sort((a, b) => a.date.getTime() - b.date.getTime())

    if (distributorEntries.length === 0) return null

    const points = distributorEntries.map((e) => ({
      x: scaleX(e.date.getTime()),
      y: scaleY(e.price),
    }))

    const pathD = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`)
      .join(' ')

    return {
      distributor: distributorName,
      color: colors[idx % colors.length],
      pathD,
      points,
    }
  })

  // Y-axis labels
  const yLabels = Array.from({ length: 5 }, (_, i) => {
    const price = minPrice + (priceRange * i) / 4
    return {
      price,
      y: scaleY(price),
    }
  })

  // X-axis labels (show first, middle, last)
  const xLabels = [
    { date: new Date(minDate), x: scaleX(minDate) },
    { date: new Date((minDate + maxDate) / 2), x: scaleX((minDate + maxDate) / 2) },
    { date: new Date(maxDate), x: scaleX(maxDate) },
  ]

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ maxHeight: '300px' }}
      >
        {/* Grid lines */}
        {yLabels.map((label, idx) => (
          <line
            key={idx}
            x1={padding.left}
            y1={label.y}
            x2={width - padding.right}
            y2={label.y}
            stroke="#e5e7eb"
            strokeDasharray="4"
          />
        ))}

        {/* Y-axis labels */}
        {yLabels.map((label, idx) => (
          <text
            key={idx}
            x={padding.left - 8}
            y={label.y}
            textAnchor="end"
            alignmentBaseline="middle"
            className="fill-gray-500 text-xs"
          >
            ${(label.price / 100).toFixed(2)}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map((label, idx) => (
          <text
            key={idx}
            x={label.x}
            y={height - 10}
            textAnchor="middle"
            className="fill-gray-500 text-xs"
          >
            {formatDate(label.date.toISOString())}
          </text>
        ))}

        {/* Lines */}
        {distributorPaths.map(
          (dp) =>
            dp && (
              <g key={dp.distributor}>
                <path
                  d={dp.pathD}
                  fill="none"
                  stroke={dp.color}
                  strokeWidth="2"
                />
                {/* Points */}
                {dp.points.map((p, idx) => (
                  <circle
                    key={idx}
                    cx={p.x}
                    cy={p.y}
                    r="4"
                    fill={dp.color}
                  />
                ))}
              </g>
            )
        )}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-4 justify-center">
        {distributorPaths.map(
          (dp) =>
            dp && (
              <div key={dp.distributor} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: dp.color }}
                />
                <span className="text-sm text-gray-600">{dp.distributor}</span>
              </div>
            )
        )}
      </div>
    </div>
  )
}
