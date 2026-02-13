import { cn } from '@/lib/utils'
import { Package, Truck, AlertCircle, Check } from 'lucide-react'
import { SearchResultPrice } from '@/components/PriceDisplay'
import type { SearchResult, DistributorSearchResults } from '@/types/order-hub'

interface DistributorPanelProps {
  distributor: DistributorSearchResults
  selectedResult: SearchResult | null
  onSelect: (result: SearchResult) => void
  bestPricePerUnit: number | null
  canAddToCart: boolean
  className?: string
}

export function DistributorPanel({
  distributor,
  selectedResult,
  onSelect,
  bestPricePerUnit,
  canAddToCart,
  className,
}: DistributorPanelProps) {
  // Format delivery days
  const formatDeliveryDays = (days: string[] | null): string => {
    if (!days || days.length === 0) return ''
    return days.map(d => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ')
  }

  // Check if a result is the selected one for this distributor
  const isSelected = (result: SearchResult) => {
    return (
      selectedResult?.sku === result.sku &&
      selectedResult?.distributor_id === result.distributor_id
    )
  }

  // Find the currently selected result within this distributor's results
  const selectedInPanel = distributor.results.find(r => isSelected(r))

  // Get other results (not selected)
  const otherResults = distributor.results.filter(r => !isSelected(r))

  if (distributor.error) {
    return (
      <div className={cn('bg-white border border-red-200 rounded-lg flex flex-col', className)}>
        <div className="px-3 py-2 border-b bg-red-50 flex items-center justify-between">
          <h3 className="font-medium text-sm truncate">{distributor.distributor_name}</h3>
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
        </div>
        <div className="p-4 text-sm text-red-600 text-center">
          {distributor.error}
        </div>
      </div>
    )
  }

  if (distributor.results.length === 0) {
    return (
      <div className={cn('bg-white border rounded-lg flex flex-col opacity-60', className)}>
        <div className="px-3 py-2 border-b bg-gray-50 flex items-center justify-between">
          <h3 className="font-medium text-sm truncate">{distributor.distributor_name}</h3>
          <span className="text-xs text-gray-400">No results</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-4 text-gray-400 text-sm">
          No matching products
        </div>
      </div>
    )
  }

  const deliveryDays = distributor.results[0]?.delivery_days

  return (
    <div className={cn('bg-white border rounded-lg flex flex-col', className)}>
      {/* Header */}
      <div className="px-3 py-2 border-b bg-gray-50 flex items-center justify-between shrink-0">
        <h3 className="font-medium text-sm truncate">{distributor.distributor_name}</h3>
        <div className="flex items-center gap-3 text-xs text-gray-500 shrink-0">
          {deliveryDays && (
            <span className="flex items-center gap-1">
              <Truck className="h-3 w-3" />
              {formatDeliveryDays(deliveryDays)}
            </span>
          )}
          <span>{distributor.results.length} items</span>
        </div>
      </div>

      {/* Selected item pinned at top */}
      {selectedInPanel && (
        <div
          className="px-3 py-2 bg-blue-50 border-b border-blue-200 cursor-pointer"
          onClick={() => onSelect(selectedInPanel)}
        >
          <div className="flex items-start gap-3">
            <ProductImage
              imageUrl={selectedInPanel.image_url}
              description={selectedInPanel.description}
              size="lg"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm text-blue-900 truncate">
                  {selectedInPanel.description}
                </span>
                <Check className="h-4 w-4 text-blue-500 shrink-0" />
              </div>
              <div className="text-xs text-blue-700">SKU: {selectedInPanel.sku}</div>
            </div>
            <SearchResultPrice
              priceCents={selectedInPanel.price_cents}
              packSize={selectedInPanel.pack_size}
              packUnit={selectedInPanel.pack_unit}
              pricePerBaseUnitCents={selectedInPanel.price_per_base_unit_cents}
              isBestPrice={
                bestPricePerUnit !== null &&
                selectedInPanel.price_per_base_unit_cents === bestPricePerUnit
              }
              isOutOfStock={selectedInPanel.in_stock === false}
              className="shrink-0"
            />
          </div>
        </div>
      )}

      {/* Scrollable results list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {otherResults.map(result => {
          const isBestPrice =
            bestPricePerUnit !== null &&
            result.price_per_base_unit_cents === bestPricePerUnit

          return (
            <div
              key={`${result.distributor_id}-${result.sku}`}
              className={cn(
                'px-3 py-2 border-b last:border-b-0 transition-colors',
                canAddToCart && 'cursor-pointer hover:bg-gray-50'
              )}
              onClick={() => canAddToCart && onSelect(result)}
            >
              <div className="flex items-start gap-3">
                <ProductImage
                  imageUrl={result.image_url}
                  description={result.description}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {result.description}
                    </span>
                    {result.in_stock === false && (
                      <span className="text-xs text-red-500 shrink-0">Out of stock</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">SKU: {result.sku}</div>
                </div>
                <SearchResultPrice
                  priceCents={result.price_cents}
                  packSize={result.pack_size}
                  packUnit={result.pack_unit}
                  pricePerBaseUnitCents={result.price_per_base_unit_cents}
                  isBestPrice={isBestPrice}
                  className="shrink-0"
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Product image component with fallback
interface ProductImageProps {
  imageUrl: string | null
  description: string
  size?: 'sm' | 'lg'
}

function ProductImage({ imageUrl, description, size = 'sm' }: ProductImageProps) {
  const sizeClasses = size === 'lg' ? 'w-14 h-14' : 'w-10 h-10'
  const iconSize = size === 'lg' ? 'h-6 w-6' : 'h-5 w-5'

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={description}
        className={cn(
          sizeClasses,
          'object-contain rounded border bg-white shrink-0'
        )}
        onError={(e) => {
          // Hide broken images
          e.currentTarget.style.display = 'none'
        }}
      />
    )
  }

  return (
    <div
      className={cn(
        sizeClasses,
        'bg-gray-100 rounded border flex items-center justify-center shrink-0'
      )}
    >
      <Package className={cn(iconSize, 'text-gray-400')} />
    </div>
  )
}
