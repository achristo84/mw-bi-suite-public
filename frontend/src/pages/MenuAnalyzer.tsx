import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMenuAnalysis, getMenuMovers } from '@/lib/api'
import type { MenuItemAnalysis, IngredientMover, ItemMover } from '@/types/recipe'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, TrendingUp, TrendingDown, AlertTriangle, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

function formatPriceSmall(cents: number): string {
  return `$${(cents / 100).toFixed(4)}`
}

function statusDot(status: string) {
  switch (status) {
    case 'healthy': return 'bg-green-400'
    case 'warning': return 'bg-yellow-400'
    case 'danger': return 'bg-red-400'
    default: return 'bg-gray-400'
  }
}

export function MenuAnalyzer() {
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [moverDays, setMoverDays] = useState(7)

  const { data: analysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['menu-analysis'],
    queryFn: () => getMenuAnalysis(),
  })

  const { data: movers, isLoading: moversLoading } = useQuery({
    queryKey: ['menu-movers', moverDays],
    queryFn: () => getMenuMovers(moverDays),
  })

  if (analysisLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3" />
          <div className="h-64 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="max-w-5xl mx-auto">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Failed to load analysis</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const categories = Object.keys(analysis.summary.by_category).sort()

  let items = [...analysis.items]
  if (categoryFilter) {
    items = items.filter(i => i.category === categoryFilter)
  }
  // Sort: danger first, then warning, then healthy
  const statusOrder = { danger: 0, warning: 1, healthy: 2 }
  items.sort((a, b) => {
    const oa = statusOrder[a.margin_status] ?? 3
    const ob = statusOrder[b.margin_status] ?? 3
    if (oa !== ob) return oa - ob
    return Number(b.food_cost_percent) - Number(a.food_cost_percent)
  })

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/menu"
            className="inline-flex items-center text-gray-500 hover:text-gray-900 transition-colors text-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Menu
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900">Menu Analyzer</h1>
        </div>
      </div>

      {/* Section 1: Margin Overview */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Margin Overview
          </h2>
          <div className="flex items-center gap-2">
            {categories.length > 1 && (
              <div className="flex gap-1">
                <button
                  onClick={() => setCategoryFilter('')}
                  className={cn(
                    'px-3 py-1 text-xs rounded-full border transition-colors',
                    !categoryFilter ? 'bg-gray-900 text-white border-gray-900' : 'text-gray-600 border-gray-200 hover:border-gray-400'
                  )}
                >
                  All
                </button>
                {categories.map(c => (
                  <button
                    key={c}
                    onClick={() => setCategoryFilter(c)}
                    className={cn(
                      'px-3 py-1 text-xs rounded-full border capitalize transition-colors',
                      categoryFilter === c ? 'bg-gray-900 text-white border-gray-900' : 'text-gray-600 border-gray-200 hover:border-gray-400'
                    )}
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {items.map((item: MenuItemAnalysis) => (
            <Link
              key={item.id}
              to={`/menu/${item.id}`}
              className={cn(
                'block rounded-lg border p-3 transition-all hover:shadow-md',
                item.margin_status === 'healthy' && 'border-green-200 bg-green-50/50 hover:bg-green-50',
                item.margin_status === 'warning' && 'border-yellow-200 bg-yellow-50/50 hover:bg-yellow-50',
                item.margin_status === 'danger' && 'border-red-200 bg-red-50/50 hover:bg-red-50',
              )}
            >
              <div className="flex items-start justify-between gap-1">
                <p className="text-sm font-medium text-gray-900 leading-tight truncate">{item.name}</p>
                <span className={cn('w-2 h-2 rounded-full flex-shrink-0 mt-1', statusDot(item.margin_status))} />
              </div>
              <p className={cn(
                'text-lg font-bold mt-1 tabular-nums',
                item.margin_status === 'healthy' && 'text-green-600',
                item.margin_status === 'warning' && 'text-yellow-600',
                item.margin_status === 'danger' && 'text-red-600',
              )}>
                {Number(item.food_cost_percent).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatPrice(item.total_cost_cents)} / {formatPrice(item.menu_price_cents)}
              </p>
              {item.has_unpriced_ingredients && (
                <div className="flex items-center gap-1 mt-1">
                  <AlertTriangle className="h-3 w-3 text-yellow-500" />
                  <span className="text-xs text-yellow-600">incomplete</span>
                </div>
              )}
            </Link>
          ))}
        </div>

        {items.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-gray-400">No menu items in this category</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Section 2: Price Movers */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Price Movers
          </h2>
          <select
            value={moverDays}
            onChange={e => setMoverDays(Number(e.target.value))}
            className="text-sm border rounded-lg px-3 py-1.5 bg-white"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </div>

        {moversLoading ? (
          <div className="animate-pulse h-32 bg-gray-100 rounded-lg" />
        ) : movers && (movers.ingredient_movers.length > 0 || movers.item_movers.length > 0) ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Ingredient Movers */}
            <Card>
              <CardContent className="py-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Ingredient Price Changes</h3>
                {movers.ingredient_movers.length === 0 ? (
                  <p className="text-sm text-gray-400">No significant changes</p>
                ) : (
                  <div className="space-y-3">
                    {movers.ingredient_movers.slice(0, 10).map((mover: IngredientMover) => {
                      const isUp = (mover.change_percent ?? 0) > 0
                      return (
                        <div key={mover.ingredient_id} className="text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-gray-900">{mover.ingredient_name}</span>
                            <span className={cn(
                              'inline-flex items-center gap-1 font-semibold tabular-nums',
                              isUp ? 'text-red-600' : 'text-green-600'
                            )}>
                              {isUp ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                              {isUp ? '+' : ''}{Number(mover.change_percent).toFixed(1)}%
                            </span>
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {mover.old_price_per_unit != null && mover.new_price_per_unit != null && (
                              <span>
                                {formatPriceSmall(Number(mover.old_price_per_unit))}
                                <ArrowRight className="inline h-3 w-3 mx-1" />
                                {formatPriceSmall(Number(mover.new_price_per_unit))}/unit
                              </span>
                            )}
                          </div>
                          {mover.affected_items.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {mover.affected_items.slice(0, 3).map((ai, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs">
                                  {ai.name}
                                  <span className={cn('ml-1', ai.cost_impact_cents > 0 ? 'text-red-500' : 'text-green-500')}>
                                    {ai.cost_impact_cents > 0 ? '+' : ''}{formatPrice(ai.cost_impact_cents)}
                                  </span>
                                </Badge>
                              ))}
                              {mover.affected_items.length > 3 && (
                                <span className="text-xs text-gray-400">+{mover.affected_items.length - 3} more</span>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Item Movers */}
            <Card>
              <CardContent className="py-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Menu Item Cost Changes</h3>
                {movers.item_movers.length === 0 ? (
                  <p className="text-sm text-gray-400">No significant changes</p>
                ) : (
                  <div className="space-y-3">
                    {movers.item_movers.slice(0, 10).map((mover: ItemMover) => {
                      const isUp = mover.cost_change_cents > 0
                      return (
                        <div key={mover.menu_item_id} className="text-sm">
                          <div className="flex items-center justify-between">
                            <Link
                              to={`/menu/${mover.menu_item_id}`}
                              className="font-medium text-gray-900 hover:text-blue-600 hover:underline"
                            >
                              {mover.menu_item_name}
                            </Link>
                            <span className={cn(
                              'font-semibold tabular-nums',
                              isUp ? 'text-red-600' : 'text-green-600'
                            )}>
                              {isUp ? '+' : ''}{formatPrice(mover.cost_change_cents)}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                            <span>
                              Cost: {formatPrice(mover.old_total_cost)}
                              <ArrowRight className="inline h-3 w-3 mx-1" />
                              {formatPrice(mover.new_total_cost)}
                            </span>
                            <span className="tabular-nums">
                              Food cost: {Number(mover.new_food_cost_percent).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-gray-400">No price movements in the selected period</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
