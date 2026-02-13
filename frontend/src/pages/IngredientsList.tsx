import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getUnifiedPricing, getIngredientCategories } from '@/lib/api'
import type { UnifiedPricingItem } from '@/types/ingredient'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Search, Plus, ArrowRight, AlertTriangle, Package, ChefHat, Beaker } from 'lucide-react'

// Format price in dollars
function formatPrice(cents: number | null): string {
  if (cents === null) return '-'
  const dollars = cents / 100
  if (dollars < 0.01) {
    return `$${dollars.toFixed(6)}`
  }
  if (dollars < 1) {
    return `$${dollars.toFixed(4)}`
  }
  return `$${dollars.toFixed(2)}`
}

// Format price per unit
function formatPricePerUnit(cents: number | null, unit: string): string {
  if (cents === null) return '-'
  return `${formatPrice(cents)}/${unit}`
}

export function IngredientsList() {
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [showIngredients, setShowIngredients] = useState(true)
  const [showComponents, setShowComponents] = useState(true)
  const [showRecipes, setShowRecipes] = useState(true)

  const { data: categoriesData } = useQuery({
    queryKey: ['ingredient-categories'],
    queryFn: getIngredientCategories,
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['unified-pricing', searchTerm, categoryFilter, showIngredients, showComponents, showRecipes],
    queryFn: () => getUnifiedPricing({
      search: searchTerm || undefined,
      category: categoryFilter || undefined,
      include_ingredients: showIngredients,
      include_components: showComponents,
      include_recipes: showRecipes,
    }),
  })

  const items = data?.items || []
  const categories = categoriesData || []

  // Count stats
  const unpricedCount = items.filter(i => !i.has_price).length

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">Failed to load items. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Pricing</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {data?.count || 0} item{(data?.count || 0) !== 1 ? 's' : ''}
            {data && (
              <span className="ml-2 text-gray-400">
                ({data.ingredient_count} ingredients, {data.component_count} components, {data.recipe_count} recipes)
              </span>
            )}
            {unpricedCount > 0 && (
              <span className="text-yellow-600 ml-2">
                ({unpricedCount} unpriced)
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/ingredients/map">
            <Button variant="outline">
              <Package className="h-4 w-4 mr-2" />
              Map SKUs
            </Button>
          </Link>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Ingredient
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search items..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm bg-white min-w-[150px]"
            >
              <option value="">All categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-4 border-l pl-4">
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showIngredients}
                  onChange={(e) => setShowIngredients(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="flex items-center gap-1">
                  <Package className="h-3.5 w-3.5" />
                  Ingredients
                </span>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showComponents}
                  onChange={(e) => setShowComponents(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="flex items-center gap-1">
                  <Beaker className="h-3.5 w-3.5" />
                  Components
                </span>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showRecipes}
                  onChange={(e) => setShowRecipes(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="flex items-center gap-1">
                  <ChefHat className="h-3.5 w-3.5" />
                  Recipes
                </span>
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Items List */}
      {isLoading ? (
        <Card>
          <CardContent className="p-0">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div key={n} className="px-4 py-3 border-b animate-pulse flex justify-between">
                <div className="h-5 bg-gray-200 rounded w-1/3" />
                <div className="h-5 bg-gray-100 rounded w-24" />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            {searchTerm || categoryFilter || !showIngredients || !showComponents || !showRecipes ? (
              <>
                <p className="text-gray-500">No items match your filters</p>
                <button
                  onClick={() => {
                    setSearchTerm('')
                    setCategoryFilter('')
                    setShowIngredients(true)
                    setShowComponents(true)
                    setShowRecipes(true)
                  }}
                  className="mt-2 text-blue-600 hover:underline text-sm"
                >
                  Clear filters
                </button>
              </>
            ) : (
              <p className="text-gray-500">No items yet</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500 uppercase bg-gray-50">
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Source</th>
                  <th className="px-4 py-2 text-right">Per Yield</th>
                  <th className="px-4 py-2 text-right">Per g</th>
                  <th className="px-4 py-2 text-right">Per oz</th>
                  <th className="px-4 py-2 text-right">Per lb</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((item: UnifiedPricingItem) => (
                  <tr
                    key={`${item.item_type}-${item.id}`}
                    className={`text-sm hover:bg-gray-50 ${
                      !item.has_price
                        ? 'bg-yellow-50'
                        : item.item_type === 'recipe'
                          ? 'bg-green-50'
                          : item.item_type === 'component'
                            ? 'bg-blue-50'
                            : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={item.item_type === 'recipe' ? `/recipes/${item.id}` : `/ingredients/${item.id}`}
                        className={`font-medium hover:text-blue-600 hover:underline ${
                          !item.has_price ? 'text-yellow-700' : 'text-gray-900'
                        }`}
                      >
                        {!item.has_price && (
                          <AlertTriangle className="inline h-3.5 w-3.5 mr-1 text-yellow-600" />
                        )}
                        {item.item_type === 'recipe' && (
                          <ChefHat className="inline h-3.5 w-3.5 mr-1 text-green-600" />
                        )}
                        {item.item_type === 'component' && (
                          <Beaker className="inline h-3.5 w-3.5 mr-1 text-blue-500" />
                        )}
                        {item.name}
                      </Link>
                      {item.source_recipe_name && (
                        <span className="ml-2 text-xs text-gray-400">
                          → {item.source_recipe_name}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      <span className={`px-2 py-0.5 rounded-full ${
                        item.item_type === 'recipe'
                          ? 'bg-green-100 text-green-700'
                          : item.item_type === 'component'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-600'
                      }`}>
                        {item.item_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {item.source || '-'}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {item.item_type === 'recipe' && item.cost_per_yield_cents != null ? (
                        <span className="font-medium text-gray-900">
                          {formatPricePerUnit(item.cost_per_yield_cents, item.yield_unit || 'unit')}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {item.pricing.per_g_cents != null ? (
                        <span className="font-medium text-gray-900">
                          {formatPricePerUnit(item.pricing.per_g_cents, 'g')}
                        </span>
                      ) : item.pricing.per_ml_cents != null ? (
                        <span className="font-medium text-gray-900">
                          {formatPricePerUnit(item.pricing.per_ml_cents, 'ml')}
                        </span>
                      ) : item.pricing.per_each_cents != null ? (
                        <span className="font-medium text-gray-900">
                          {formatPricePerUnit(item.pricing.per_each_cents, 'ea')}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {item.pricing.per_oz_cents != null ? (
                        <span className="text-gray-700">
                          {formatPricePerUnit(item.pricing.per_oz_cents, 'oz')}
                        </span>
                      ) : item.pricing.per_fl_oz_cents != null ? (
                        <span className="text-gray-700">
                          {formatPricePerUnit(item.pricing.per_fl_oz_cents, 'fl oz')}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {item.pricing.per_lb_cents != null ? (
                        <span className="text-gray-700">
                          {formatPricePerUnit(item.pricing.per_lb_cents, 'lb')}
                        </span>
                      ) : item.pricing.per_l_cents != null ? (
                        <span className="text-gray-700">
                          {formatPricePerUnit(item.pricing.per_l_cents, 'L')}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={item.item_type === 'recipe' ? `/recipes/${item.id}` : `/ingredients/${item.id}`}
                        className="text-gray-400 hover:text-blue-600"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
