import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getIngredientsWithPrices,
  getIngredientMappingView,
  getUnmappedDistIngredients,
} from '@/lib/api'
import { convertPrice, getAvailableUnits, formatPrice } from '@/lib/unitConversions'
import type { UnmappedDistIngredient } from '@/types/ingredient'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ChevronRight, Package, Check } from 'lucide-react'
import { SKURow } from '@/components/map-skus/SKURow'
import { MappingModal } from '@/components/map-skus/MappingModal'
import { CreateIngredientModal } from '@/components/map-skus/CreateIngredientModal'

export function MapSkus() {
  const queryClient = useQueryClient()
  const [selectedIngredientId, setSelectedIngredientId] = useState<string | null>(null)
  const [ingredientSearch, setIngredientSearch] = useState('')
  const [unmappedSearch, setUnmappedSearch] = useState('')
  const [mappingItem, setMappingItem] = useState<UnmappedDistIngredient | null>(null)
  const [showUnmappedOnly, setShowUnmappedOnly] = useState(false)
  const [displayUnit, setDisplayUnit] = useState<string>('lb')
  const [showUnmappedView, setShowUnmappedView] = useState(false)
  const [showCreateIngredient, setShowCreateIngredient] = useState(false)

  const { data: ingredientsData, isLoading: ingredientsLoading } = useQuery({
    queryKey: ['ingredients-with-prices', ingredientSearch],
    queryFn: () => getIngredientsWithPrices({ search: ingredientSearch || undefined }),
  })

  const filteredIngredients = (ingredientsData?.ingredients || []).filter(
    (ing) => !showUnmappedOnly || ing.variant_count === 0
  )

  const { data: mappingView, isLoading: mappingViewLoading } = useQuery({
    queryKey: ['ingredient-mapping-view', selectedIngredientId],
    queryFn: () => getIngredientMappingView(selectedIngredientId!, 10),
    enabled: !!selectedIngredientId,
  })

  const { data: unmappedData, isLoading: unmappedLoading } = useQuery({
    queryKey: ['unmapped-ingredients', unmappedSearch],
    queryFn: () => getUnmappedDistIngredients({ search: unmappedSearch || undefined }),
  })

  const unmappedItems = unmappedData?.items || []
  const unmappedIngredientCount = (ingredientsData?.ingredients || []).filter(i => i.variant_count === 0).length

  const handleIngredientSelect = (id: string) => {
    setSelectedIngredientId(id)
    setMappingItem(null)
    setShowUnmappedView(false)
  }

  const handleShowUnmappedView = () => {
    setSelectedIngredientId(null)
    setShowUnmappedView(true)
  }

  const currentBaseUnit = mappingView?.base_unit || 'g'
  const availableUnits = getAvailableUnits(currentBaseUnit)

  const validDisplayUnit = availableUnits.some(u => u.value === displayUnit)
    ? displayUnit
    : availableUnits[0]?.value || currentBaseUnit

  const handleMappingComplete = () => {
    setMappingItem(null)
    queryClient.invalidateQueries({ queryKey: ['ingredient-mapping-view', selectedIngredientId] })
    queryClient.invalidateQueries({ queryKey: ['unmapped-ingredients'] })
    queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
  }

  return (
    <>
      <div className="h-[calc(100vh-4rem)] flex flex-col">
        <div className="px-6 py-4 border-b bg-white">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Ingredient Mapping</h1>
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCreateIngredient(true)}
              >
                <Package className="h-4 w-4 mr-2" />
                New Ingredient
              </Button>
              <button
                onClick={handleShowUnmappedView}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  showUnmappedView
                    ? 'bg-amber-100 text-amber-700 font-medium'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {unmappedItems.length} unmapped SKUs
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Ingredient List */}
        <div className="w-80 border-r bg-gray-50 flex flex-col">
          <div className="p-3 border-b bg-white space-y-2">
            <Input
              placeholder="Search ingredients..."
              value={ingredientSearch}
              onChange={(e) => setIngredientSearch(e.target.value)}
              className="h-9"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowUnmappedOnly(false)}
                className={`flex-1 text-xs py-1.5 px-2 rounded transition-colors ${
                  !showUnmappedOnly
                    ? 'bg-blue-100 text-blue-700 font-medium'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                All ({ingredientsData?.ingredients?.length || 0})
              </button>
              <button
                onClick={() => setShowUnmappedOnly(true)}
                className={`flex-1 text-xs py-1.5 px-2 rounded transition-colors ${
                  showUnmappedOnly
                    ? 'bg-amber-100 text-amber-700 font-medium'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                No SKUs ({unmappedIngredientCount})
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {ingredientsLoading ? (
              <div className="p-4 text-center text-gray-500">Loading...</div>
            ) : filteredIngredients.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                {showUnmappedOnly ? 'All ingredients have SKUs mapped' : 'No ingredients found'}
              </div>
            ) : (
              <div className="divide-y">
                {filteredIngredients.map((ing) => (
                  <button
                    key={ing.id}
                    onClick={() => handleIngredientSelect(ing.id)}
                    className={`w-full text-left p-3 hover:bg-gray-100 transition-colors ${
                      selectedIngredientId === ing.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-gray-900 truncate">{ing.name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-gray-500">{ing.base_unit}</span>
                          {ing.category && (
                            <span className="text-xs text-gray-400">· {ing.category}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-2">
                        {ing.variant_count > 0 && (
                          <Badge variant="outline" className="text-xs">
                            {ing.variant_count} SKU{ing.variant_count !== 1 ? 's' : ''}
                          </Badge>
                        )}
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Selected Ingredient Details + Unmapped SKUs */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedIngredientId ? (
            <>
              {/* Top: Mapped SKUs by Distributor */}
              <div className="flex-1 overflow-y-auto p-4">
                {mappingViewLoading ? (
                  <div className="text-center py-8 text-gray-500">Loading...</div>
                ) : mappingView ? (
                  <div className="space-y-4">
                    {/* Ingredient Header */}
                    <div className="flex items-start justify-between">
                      <div>
                        <h2 className="text-xl font-bold text-gray-900">{mappingView.name}</h2>
                        <p className="text-sm text-gray-500">
                          {mappingView.category || 'Uncategorized'} · Base unit: {mappingView.base_unit}
                        </p>
                      </div>
                      <div className="text-right">
                        {mappingView.has_price && (
                          <>
                            <p className="text-xs text-gray-500">Best price</p>
                            <p className="font-bold text-green-600">
                              {formatPrice(convertPrice(
                                Number(mappingView.best_price_per_base_unit_cents),
                                mappingView.base_unit,
                                validDisplayUnit
                              ))}/{validDisplayUnit}
                            </p>
                            <p className="text-xs text-gray-500 mb-2">{mappingView.best_distributor_name}</p>
                          </>
                        )}
                        <select
                          value={validDisplayUnit}
                          onChange={(e) => setDisplayUnit(e.target.value)}
                          className="text-xs border rounded px-2 py-1 bg-white"
                        >
                          {availableUnits.map((u) => (
                            <option key={u.value} value={u.value}>
                              {u.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Mapped SKUs by Distributor */}
                    {mappingView.distributor_groups.length === 0 ? (
                      <Card>
                        <CardContent className="py-8 text-center text-gray-500">
                          <Package className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                          <p>No SKUs mapped to this ingredient yet</p>
                          <p className="text-sm mt-1">Select an unmapped SKU below to map it</p>
                        </CardContent>
                      </Card>
                    ) : (
                      mappingView.distributor_groups.map((group) => (
                        <Card key={group.distributor_id}>
                          <CardHeader className="py-3 px-4 bg-gray-50">
                            <CardTitle className="text-sm font-medium flex items-center justify-between">
                              <span>{group.distributor_name}</span>
                              <Badge variant="outline" className="text-xs">
                                {group.sku_count} SKU{group.sku_count !== 1 ? 's' : ''}
                              </Badge>
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="p-0 divide-y">
                            {group.skus.map((sku) => (
                              <SKURow
                                key={sku.id}
                                sku={sku}
                                baseUnit={mappingView.base_unit}
                                displayUnit={validDisplayUnit}
                                onRecalculate={() => {
                                  queryClient.invalidateQueries({ queryKey: ['ingredient-mapping-view', selectedIngredientId] })
                                }}
                              />
                            ))}
                          </CardContent>
                        </Card>
                      ))
                    )}
                  </div>
                ) : null}
              </div>

              {/* Bottom: Unmapped SKUs Panel */}
              <div className="h-64 border-t bg-gray-50 flex flex-col">
                <div className="p-3 border-b bg-white flex items-center justify-between">
                  <h3 className="font-medium text-gray-700">Unmapped SKUs</h3>
                  <Input
                    placeholder="Search unmapped..."
                    value={unmappedSearch}
                    onChange={(e) => setUnmappedSearch(e.target.value)}
                    className="h-8 w-64"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                  {unmappedLoading ? (
                    <div className="p-4 text-center text-gray-500">Loading...</div>
                  ) : unmappedItems.length === 0 ? (
                    <div className="p-4 text-center text-gray-500">
                      {unmappedSearch ? 'No matches found' : 'All SKUs are mapped!'}
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {unmappedItems.slice(0, 20).map((item) => (
                        <div
                          key={item.id}
                          className={`p-2 bg-white rounded border hover:border-blue-300 cursor-pointer transition-colors ${
                            mappingItem?.id === item.id ? 'border-blue-500 ring-1 ring-blue-500' : ''
                          }`}
                          onClick={() => setMappingItem(item)}
                        >
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium truncate">{item.description}</p>
                              <p className="text-xs text-gray-500">
                                {item.distributor_name}
                                {item.sku && <span className="ml-2">SKU: {item.sku}</span>}
                              </p>
                            </div>
                            {item.last_price_cents && (
                              <span className="text-xs font-medium text-gray-600 ml-2">
                                {formatPrice(item.last_price_cents)}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : showUnmappedView ? (
            /* Unmapped SKUs Full View */
            <div className="flex-1 overflow-y-auto p-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Unmapped SKUs</h2>
                    <p className="text-sm text-gray-500">
                      {unmappedItems.length} SKUs need to be mapped to ingredients
                    </p>
                  </div>
                  <Input
                    placeholder="Search unmapped..."
                    value={unmappedSearch}
                    onChange={(e) => setUnmappedSearch(e.target.value)}
                    className="h-9 w-64"
                  />
                </div>

                {unmappedLoading ? (
                  <div className="text-center py-8 text-gray-500">Loading...</div>
                ) : unmappedItems.length === 0 ? (
                  <Card>
                    <CardContent className="py-8 text-center text-gray-500">
                      <Check className="h-8 w-8 mx-auto mb-2 text-green-500" />
                      <p>All SKUs are mapped!</p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {unmappedItems.map((item) => (
                      <Card
                        key={item.id}
                        className="cursor-pointer hover:border-blue-300 transition-colors"
                        onClick={() => setMappingItem(item)}
                      >
                        <CardContent className="p-3">
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-gray-900 truncate">{item.description}</p>
                              <p className="text-xs text-gray-500 mt-1">
                                {item.distributor_name}
                                {item.sku && <span className="ml-2">· SKU: {item.sku}</span>}
                              </p>
                            </div>
                            {item.last_price_cents && (
                              <span className="text-sm font-medium text-gray-600 ml-2">
                                {formatPrice(item.last_price_cents)}
                              </span>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <Package className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium">Select an ingredient</p>
                <p className="text-sm mt-1">Choose an ingredient from the list to view and manage its SKU mappings</p>
                <p className="text-sm mt-3">
                  Or click{' '}
                  <button
                    onClick={handleShowUnmappedView}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    unmapped SKUs
                  </button>
                  {' '}to see all SKUs that need mapping
                </p>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>

    {/* Modals rendered via portal for proper overlay */}
    {mappingItem && createPortal(
      <MappingModal
        item={mappingItem}
        ingredients={ingredientsData?.ingredients || []}
        selectedIngredientId={selectedIngredientId}
        selectedIngredientName={mappingView?.name}
        onClose={() => setMappingItem(null)}
        onMapped={handleMappingComplete}
      />,
      document.body
    )}

    {showCreateIngredient && createPortal(
      <CreateIngredientModal
        onClose={() => setShowCreateIngredient(false)}
        onCreated={(newId) => {
          setShowCreateIngredient(false)
          setSelectedIngredientId(newId)
          queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
        }}
      />,
      document.body
    )}
  </>
  )
}
