import { useState, useEffect, useRef, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getOrderListItems,
  createOrderListItem,
  deleteOrderListItem,
  searchDistributors,
  createAssignment,
  getEnabledDistributors,
} from '@/lib/api'
import type {
  OrderListItemWithDetails,
  OrderListItemCreate,
  SearchResult,
  AssignmentCreate,
} from '@/types/order-hub'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Search,
  Plus,
  Trash2,
  ShoppingCart,
  Loader2,
  ChevronRight,
  ChevronLeft,
  Package,
  Minus,
  AlertTriangle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { StatusDot, ListItemBadge } from '@/components/ListItemBadge'
import { DistributorPanel } from '@/components/DistributorPanel'
import { DistributorToggleBar } from '@/components/DistributorToggleBar'
import { useDistributorToggles } from '@/hooks/useDistributorToggles'

export function OrderHub() {
  const queryClient = useQueryClient()

  // State
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [quickAddValue, setQuickAddValue] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [selectedItem, setSelectedItem] = useState<OrderListItemWithDetails | null>(null)
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [duplicateError, setDuplicateError] = useState<string | null>(null)

  const searchInputRef = useRef<HTMLInputElement>(null)

  // Distributor toggles (persisted to localStorage)
  const { isEnabled, toggle } = useDistributorToggles()

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Fetch enabled distributors
  const { data: enabledDistributors } = useQuery({
    queryKey: ['enabled-distributors'],
    queryFn: getEnabledDistributors,
  })

  // Fetch order list
  const { data: listData, isLoading: listLoading } = useQuery({
    queryKey: ['order-list', 'pending'],
    queryFn: () => getOrderListItems('pending'),
  })

  // Search distributors
  const { data: searchData, isLoading: searchLoading, error: searchError } = useQuery({
    queryKey: ['distributor-search', debouncedQuery],
    queryFn: () => searchDistributors(debouncedQuery, 10),
    enabled: debouncedQuery.length > 0,
  })

  // Create order list item
  const createMutation = useMutation({
    mutationFn: createOrderListItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      setQuickAddValue('')
      setDuplicateError(null)
    },
    onError: (error: Error) => {
      // Handle 409 duplicate error
      if (error.message.includes('already on the list')) {
        setDuplicateError(error.message)
        // Clear error after 5 seconds
        setTimeout(() => setDuplicateError(null), 5000)
      }
    },
  })

  // Delete order list item
  const deleteMutation = useMutation({
    mutationFn: deleteOrderListItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      if (selectedItem) setSelectedItem(null)
    },
  })

  // Create assignment
  const assignMutation = useMutation({
    mutationFn: createAssignment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      setSelectedResult(null)
      setQuantity(1)
    },
  })

  const items = listData?.items || []
  const pendingItems = items.filter((item) => item.status === 'pending')

  // Filter distributors by toggle state
  const filteredDistributors = useMemo(() => {
    if (!searchData?.distributors) return []
    return searchData.distributors.filter(d => isEnabled(d.distributor_id))
  }, [searchData?.distributors, isEnabled])

  // Build list of all distributors for toggle bar
  const allDistributors = useMemo(() => {
    // Combine enabled distributors from API with any from search results
    const distMap = new Map<string, { id: string; name: string }>()

    enabledDistributors?.forEach(d => {
      distMap.set(d.id, { id: d.id, name: d.name })
    })

    searchData?.distributors?.forEach(d => {
      if (!distMap.has(d.distributor_id)) {
        distMap.set(d.distributor_id, { id: d.distributor_id, name: d.distributor_name })
      }
    })

    return Array.from(distMap.values())
  }, [enabledDistributors, searchData?.distributors])

  // Find best price per base unit across all filtered results
  const bestPricePerUnit = useMemo(() => {
    const allResults = filteredDistributors.flatMap(d => d.results)
    return allResults.reduce((best: number | null, r: SearchResult) => {
      if (r.price_per_base_unit_cents === null) return best
      if (best === null) return r.price_per_base_unit_cents
      return Math.min(best, r.price_per_base_unit_cents)
    }, null)
  }, [filteredDistributors])

  // Quick add handler
  const handleQuickAdd = () => {
    if (!quickAddValue.trim()) return
    setDuplicateError(null)
    const data: OrderListItemCreate = {
      name: quickAddValue.trim(),
    }
    createMutation.mutate(data)
  }

  // Handle Enter key for quick add
  const handleQuickAddKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleQuickAdd()
    }
  }

  // Handle Enter key for search
  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      setDebouncedQuery(searchQuery)
    }
  }

  // Handle item click in sidebar
  const handleItemClick = (item: OrderListItemWithDetails) => {
    setSelectedItem(item)
    setSearchQuery(item.name)
    setDebouncedQuery(item.name)
    searchInputRef.current?.focus()
  }

  // Handle delete item
  const handleDeleteItem = (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation()
    if (confirm('Remove this item from the order list?')) {
      deleteMutation.mutate(itemId)
    }
  }

  // Handle result selection from any panel
  const handleSelectResult = (result: SearchResult) => {
    setSelectedResult(result)
    setQuantity(1)
  }

  // Handle add to cart
  const handleAddToCart = () => {
    if (!selectedResult || !selectedItem) return

    const assignment: AssignmentCreate = {
      order_list_item_id: selectedItem.id,
      quantity,
      ...(selectedResult.dist_ingredient_id
        ? { dist_ingredient_id: selectedResult.dist_ingredient_id }
        : {
            distributor_id: selectedResult.distributor_id,
            sku: selectedResult.sku,
            description: selectedResult.description,
            pack_size: selectedResult.pack_size ?? undefined,
            pack_unit: selectedResult.pack_unit ?? undefined,
            price_cents: selectedResult.price_cents ?? undefined,
          }),
    }

    assignMutation.mutate(assignment)
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-4 mb-4">
        {/* Search Input */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            ref={searchInputRef}
            placeholder="Search distributors... (press Enter to search)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            className="pl-10"
          />
        </div>

        {/* Quick Add */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <Input
              placeholder="Quick add item..."
              value={quickAddValue}
              onChange={(e) => {
                setQuickAddValue(e.target.value)
                setDuplicateError(null)
              }}
              onKeyDown={handleQuickAddKeyDown}
              className={cn('w-48', duplicateError && 'border-amber-500')}
            />
            {duplicateError && (
              <div className="absolute top-full left-0 mt-1 px-2 py-1 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700 flex items-center gap-1 whitespace-nowrap z-10">
                <AlertTriangle className="h-3 w-3" />
                {duplicateError}
              </div>
            )}
          </div>
          <Button
            size="icon"
            variant="outline"
            onClick={handleQuickAdd}
            disabled={!quickAddValue.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Cart Builder Link */}
        <Link to="/orders/build">
          <Button>
            <ShoppingCart className="h-4 w-4 mr-2" />
            Cart Builder
          </Button>
        </Link>
      </div>

      {/* Search context header with toggles */}
      {(selectedItem || debouncedQuery) && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-blue-700">
                Searching for: <strong>{selectedItem?.name || debouncedQuery}</strong>
              </span>
              {selectedItem && <ListItemBadge item={selectedItem} />}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelectedItem(null)
                setSearchQuery('')
                setDebouncedQuery('')
                setSelectedResult(null)
              }}
            >
              Clear
            </Button>
          </div>

          {/* Distributor toggles */}
          {allDistributors.length > 0 && (
            <DistributorToggleBar
              distributors={allDistributors}
              isEnabled={isEnabled}
              onToggle={toggle}
            />
          )}
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Sidebar */}
        <div
          className={cn(
            'bg-white border rounded-lg flex flex-col transition-all duration-200',
            sidebarCollapsed ? 'w-12' : 'w-64'
          )}
        >
          {/* Sidebar Header */}
          <div className="p-3 border-b flex items-center justify-between">
            {!sidebarCollapsed && (
              <div className="flex items-center gap-2">
                <Package className="h-4 w-4 text-gray-500" />
                <span className="font-medium text-sm">
                  Items ({pendingItems.length})
                </span>
              </div>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            >
              {sidebarCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronLeft className="h-4 w-4" />
              )}
            </Button>
          </div>

          {/* Sidebar Items */}
          {!sidebarCollapsed && (
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {listLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              )}

              {!listLoading && pendingItems.length === 0 && (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No items yet. Add items using the quick add input.
                </div>
              )}

              {pendingItems.map((item) => (
                <SidebarItem
                  key={item.id}
                  item={item}
                  isSelected={selectedItem?.id === item.id}
                  onClick={() => handleItemClick(item)}
                  onDelete={(e) => handleDeleteItem(e, item.id)}
                />
              ))}
            </div>
          )}

          {/* Sidebar Footer */}
          {!sidebarCollapsed && (
            <div className="p-3 border-t">
              <Link to="/orders/build" className="block">
                <Button variant="outline" size="sm" className="w-full">
                  <ShoppingCart className="h-4 w-4 mr-2" />
                  View Cart
                </Button>
              </Link>
            </div>
          )}
        </div>

        {/* Search Results Grid */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Loading */}
          {searchLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-500">Searching distributors...</span>
            </div>
          )}

          {/* Error */}
          {searchError && (
            <div className="flex items-center justify-center py-12 text-red-500">
              <AlertTriangle className="h-5 w-5 mr-2" />
              Failed to search. Please try again.
            </div>
          )}

          {/* Empty state */}
          {!searchLoading && !searchError && !debouncedQuery && (
            <div className="flex flex-col items-center justify-center py-16 text-gray-500">
              <Search className="h-12 w-12 mb-4 text-gray-300" />
              <h3 className="text-lg font-medium text-gray-700">Search for products</h3>
              <p className="text-sm mt-1">
                Enter a search term or click an item from the sidebar
              </p>
            </div>
          )}

          {/* No results */}
          {searchData && searchData.total_results === 0 && (
            <div className="text-center py-12 text-gray-500">
              No results found for "{debouncedQuery}". Try a different search term.
            </div>
          )}

          {/* Grid of distributor panels - max 2 rows x 3 cols */}
          {filteredDistributors.length > 0 && (
            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-fr min-h-0 overflow-auto">
              {filteredDistributors.slice(0, 6).map((distributor) => (
                <DistributorPanel
                  key={distributor.distributor_id}
                  distributor={distributor}
                  selectedResult={selectedResult}
                  onSelect={handleSelectResult}
                  bestPricePerUnit={bestPricePerUnit}
                  canAddToCart={!!selectedItem}
                  className="min-h-[200px] max-h-[400px]"
                />
              ))}
            </div>
          )}

          {/* Search stats */}
          {searchData && filteredDistributors.length > 0 && (
            <div className="text-xs text-gray-400 pt-2 text-center shrink-0">
              {filteredDistributors.reduce((sum, d) => sum + d.results.length, 0)} results
              from {filteredDistributors.length} distributors
              in {searchData.search_duration_ms}ms
            </div>
          )}
        </div>
      </div>

      {/* Bottom Action Bar - when result selected */}
      {selectedResult && selectedItem && (
        <div className="border-t bg-white p-4 mt-4 rounded-lg shadow-lg">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <p className="font-medium">{selectedResult.description}</p>
              <p className="text-sm text-gray-500">
                {selectedResult.distributor_name} - {selectedResult.sku}
                {selectedResult.pack_size && ` - ${selectedResult.pack_size}`}
              </p>
            </div>

            <div className="flex items-center gap-4">
              {/* Quantity */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Qty:</span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <Input
                    type="number"
                    min="1"
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-16 h-8 text-center"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setQuantity(quantity + 1)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* Price */}
              <div className="text-right">
                <p className="font-medium">
                  ${selectedResult.price_cents ? ((selectedResult.price_cents * quantity) / 100).toFixed(2) : '-'}
                </p>
                <p className="text-xs text-gray-500">
                  ${selectedResult.price_cents ? (selectedResult.price_cents / 100).toFixed(2) : '-'} each
                </p>
              </div>

              {/* Add button */}
              <Button
                onClick={handleAddToCart}
                disabled={assignMutation.isPending}
              >
                {assignMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <ShoppingCart className="h-4 w-4 mr-2" />
                )}
                Add to Cart
              </Button>

              {/* Cancel */}
              <Button
                variant="ghost"
                onClick={() => setSelectedResult(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Sidebar Item Component
function SidebarItem({
  item,
  isSelected,
  onClick,
  onDelete,
}: {
  item: OrderListItemWithDetails
  isSelected: boolean
  onClick: () => void
  onDelete: (e: React.MouseEvent) => void
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-colors group',
        isSelected
          ? 'bg-blue-100 border border-blue-300'
          : 'hover:bg-gray-100'
      )}
      onClick={onClick}
    >
      <StatusDot item={item} />
      <span className="flex-1 text-sm truncate">{item.name}</span>
      {item.quantity && (
        <span className="text-xs text-gray-400 shrink-0">({item.quantity})</span>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
        onClick={onDelete}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  )
}
