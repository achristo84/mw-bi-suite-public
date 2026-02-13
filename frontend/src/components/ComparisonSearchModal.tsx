import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { searchDistributors, createAssignment } from '@/lib/api'
import type {
  OrderListItemWithDetails,
  SearchResult,
  DistributorSearchResults,
  AssignmentCreate,
} from '@/types/order-hub'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Search,
  Loader2,
  Truck,
  AlertCircle,
  Check,
  Plus,
  Minus,
  ShoppingCart,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Format price
function formatPrice(cents: number | null): string {
  if (cents === null) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

// Format delivery days
function formatDeliveryDays(days: string[] | null): string {
  if (!days || days.length === 0) return 'No schedule'
  return days.map((d) => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ')
}

interface ComparisonSearchModalProps {
  open: boolean
  onClose: () => void
  item: OrderListItemWithDetails
}

export function ComparisonSearchModal({
  open,
  onClose,
  item,
}: ComparisonSearchModalProps) {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState(item.name)
  const [debouncedSearch, setDebouncedSearch] = useState(item.name)
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null)
  const [quantity, setQuantity] = useState(1)

  // Update search when item changes
  useEffect(() => {
    setSearchTerm(item.name)
    setDebouncedSearch(item.name)
  }, [item])

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  const { data, isLoading, error } = useQuery({
    queryKey: ['distributor-search', debouncedSearch],
    queryFn: () => searchDistributors(debouncedSearch, 10),
    enabled: debouncedSearch.length > 0,
  })

  const assignMutation = useMutation({
    mutationFn: createAssignment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      onClose()
    },
  })

  const handleAddToCart = () => {
    if (!selectedResult) return

    // Build assignment - use dist_ingredient_id if available, otherwise pass search result data
    const assignment: AssignmentCreate = {
      order_list_item_id: item.id,
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

  // Find best price per base unit across all results
  const allResults = data?.distributors.flatMap((d) => d.results) || []
  const bestPricePerUnit = allResults.reduce(
    (best: number | null, r: SearchResult) => {
      if (r.price_per_base_unit_cents === null) return best
      if (best === null) return r.price_per_base_unit_cents
      return Math.min(best, r.price_per_base_unit_cents)
    },
    null
  )

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Find: {item.name}
            {item.quantity && (
              <span className="text-sm font-normal text-gray-500">
                ({item.quantity})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search distributors..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            autoFocus
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-500">Searching distributors...</span>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-12 text-red-500">
              <AlertCircle className="h-5 w-5 mr-2" />
              Failed to search. Please try again.
            </div>
          )}

          {data && data.distributors.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No distributors enabled for Order Hub yet
            </div>
          )}

          {data &&
            data.distributors.map((distributor) => (
              <DistributorResultsSection
                key={distributor.distributor_id}
                distributor={distributor}
                selectedResult={selectedResult}
                onSelect={setSelectedResult}
                bestPricePerUnit={bestPricePerUnit}
              />
            ))}

          {data && data.total_results === 0 && (
            <div className="text-center py-12 text-gray-500">
              No results found. Try a different search term.
            </div>
          )}
        </div>

        {/* Selected Item Footer */}
        {selectedResult && (
          <div className="border-t pt-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{selectedResult.description}</p>
                <p className="text-sm text-gray-500">
                  {selectedResult.distributor_name} - {selectedResult.sku}
                  {selectedResult.pack_size && ` - ${selectedResult.pack_size}`}
                </p>
              </div>
              <div className="text-right">
                <p className="font-medium">{formatPrice(selectedResult.price_cents)}</p>
                {selectedResult.price_per_base_unit_cents && (
                  <p className="text-sm text-gray-500">
                    {formatPrice(selectedResult.price_per_base_unit_cents)}/unit
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Label>Quantity:</Label>
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
                    className="w-20 text-center"
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

              <div className="flex items-center gap-2">
                <Button variant="ghost" onClick={onClose}>
                  Cancel
                </Button>
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
                  {selectedResult.price_cents && (
                    <span className="ml-2">
                      ({formatPrice(selectedResult.price_cents * quantity)})
                    </span>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Search Stats */}
        {data && (
          <div className="text-xs text-gray-400 pt-2">
            {data.total_results} results in {data.search_duration_ms}ms
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// Distributor Results Section
function DistributorResultsSection({
  distributor,
  selectedResult,
  onSelect,
  bestPricePerUnit,
}: {
  distributor: DistributorSearchResults
  selectedResult: SearchResult | null
  onSelect: (result: SearchResult) => void
  bestPricePerUnit: number | null
}) {
  if (distributor.error) {
    return (
      <div className="border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium">{distributor.distributor_name}</h3>
          <span className="text-xs text-red-500">{distributor.error}</span>
        </div>
      </div>
    )
  }

  if (distributor.results.length === 0) {
    return (
      <div className="border rounded-lg p-4 opacity-60">
        <div className="flex items-center justify-between">
          <h3 className="font-medium">{distributor.distributor_name}</h3>
          <span className="text-xs text-gray-500">No results</span>
        </div>
      </div>
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 flex items-center justify-between">
        <h3 className="font-medium">{distributor.distributor_name}</h3>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          {distributor.results[0]?.delivery_days && (
            <span className="flex items-center gap-1">
              <Truck className="h-4 w-4" />
              {formatDeliveryDays(distributor.results[0].delivery_days)}
            </span>
          )}
          <span>{distributor.results.length} items</span>
        </div>
      </div>
      <div className="divide-y">
        {distributor.results.map((result) => (
          <ResultRow
            key={result.sku}
            result={result}
            isSelected={selectedResult?.sku === result.sku && selectedResult?.distributor_id === result.distributor_id}
            onSelect={() => onSelect(result)}
            isBestPrice={
              bestPricePerUnit !== null &&
              result.price_per_base_unit_cents === bestPricePerUnit
            }
          />
        ))}
      </div>
    </div>
  )
}

// Result Row Component
function ResultRow({
  result,
  isSelected,
  onSelect,
  isBestPrice,
}: {
  result: SearchResult
  isSelected: boolean
  onSelect: () => void
  isBestPrice: boolean
}) {
  return (
    <div
      className={cn(
        'px-4 py-3 flex items-center justify-between gap-4 transition-colors cursor-pointer hover:bg-gray-50',
        isSelected && 'bg-blue-50 border-l-4 border-blue-500'
      )}
      onClick={onSelect}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{result.description}</span>
          {isBestPrice && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
              Best Price
            </span>
          )}
          {result.in_stock === false && (
            <span className="text-xs text-red-500">Out of stock</span>
          )}
        </div>
        <div className="text-sm text-gray-500 flex items-center gap-2">
          <span>SKU: {result.sku}</span>
          {result.pack_size && <span>Pack: {result.pack_size}</span>}
        </div>
      </div>
      <div className="text-right shrink-0">
        <p className="font-medium">{formatPrice(result.price_cents)}</p>
        {result.price_per_base_unit_cents && (
          <p className="text-sm text-gray-500">
            {formatPrice(result.price_per_base_unit_cents)}/unit
          </p>
        )}
      </div>
      {isSelected && (
        <Check className="h-5 w-5 text-blue-500 shrink-0" />
      )}
    </div>
  )
}
