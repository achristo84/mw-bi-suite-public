import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getRecipes } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Search, Plus, ChevronRight } from 'lucide-react'

// Format yield in a compact way
function formatYield(quantity: number | string, unit: string): string {
  const unitDisplay: Record<string, string> = {
    qts: 'qt',
    qt: 'qt',
    quart: 'qt',
    quarts: 'qt',
    servings: 'srv',
    serving: 'srv',
    batch: 'batch',
    each: 'ea',
    oz: 'oz',
    g: 'g',
    ml: 'ml',
    l: 'L',
    liters: 'L',
  }
  const displayUnit = unitDisplay[unit.toLowerCase()] || unit
  // Ensure quantity is a number (API may return as string)
  const numQty = Number(quantity)
  const qty = numQty % 1 === 0 ? numQty : numQty.toFixed(1)
  return `${qty} ${displayUnit}`
}

export function Recipes() {
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['recipes'],
    queryFn: () => getRecipes(),
  })

  const recipes = data?.recipes || []

  // Filter recipes by search term
  const filteredRecipes = recipes.filter((recipe) =>
    recipe.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">Failed to load recipes. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Recipes</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {recipes.length} recipe{recipes.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Link to="/recipes/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Recipe
          </Button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search recipes..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Recipe List */}
      {isLoading ? (
        <Card>
          <CardContent className="p-0 divide-y">
            {[1, 2, 3, 4, 5].map((n) => (
              <div key={n} className="px-4 py-3 animate-pulse flex justify-between">
                <div className="h-5 bg-gray-200 rounded w-1/3" />
                <div className="h-5 bg-gray-100 rounded w-16" />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : filteredRecipes.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center">
            {searchTerm ? (
              <>
                <p className="text-gray-500">No recipes match "{searchTerm}"</p>
                <button
                  onClick={() => setSearchTerm('')}
                  className="mt-2 text-blue-600 hover:underline text-sm"
                >
                  Clear search
                </button>
              </>
            ) : (
              <p className="text-gray-500">No recipes yet</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 divide-y divide-gray-100">
            {filteredRecipes.map((recipe) => (
              <Link
                key={recipe.id}
                to={`/recipes/${recipe.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors group"
              >
                <span className="font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
                  {recipe.name}
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500 tabular-nums">
                    {formatYield(recipe.yield_quantity, recipe.yield_unit)}
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-blue-400 transition-colors" />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
