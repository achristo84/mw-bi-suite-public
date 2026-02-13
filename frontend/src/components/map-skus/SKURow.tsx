import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, FileText, Loader2, RefreshCw } from 'lucide-react'
import { recalculateDistIngredient } from '@/lib/api'
import { convertPrice, formatPrice, formatShortDate } from '@/lib/unitConversions'
import type { MappedSKU } from '@/types/ingredient'

interface SKURowProps {
  sku: MappedSKU
  baseUnit: string
  displayUnit: string
  onRecalculate: (skuId: string) => void
}

export function SKURow({ sku, baseUnit, displayUnit, onRecalculate }: SKURowProps) {
  const [expanded, setExpanded] = useState(false)
  const [isRecalculating, setIsRecalculating] = useState(false)

  const latestPricePerDisplayUnit = sku.price_history[0]?.price_per_base_unit_cents
    ? convertPrice(Number(sku.price_history[0].price_per_base_unit_cents), baseUnit, displayUnit)
    : null

  const hasPriceButNoBaseUnit = sku.latest_price_cents && latestPricePerDisplayUnit === null

  const handleRecalculate = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsRecalculating(true)
    try {
      await recalculateDistIngredient(sku.id)
      onRecalculate(sku.id)
    } finally {
      setIsRecalculating(false)
    }
  }

  return (
    <div className="p-3">
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {sku.sku && (
              <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
                {sku.sku}
              </span>
            )}
            <span className="text-sm text-gray-700">{sku.description}</span>
          </div>
          {sku.pack_unit && (
            <p className="text-xs text-gray-400 mt-0.5">Pack: {sku.pack_unit}</p>
          )}
        </div>
        <div className="text-right ml-4">
          {sku.latest_price_cents && (
            <>
              <p className="text-sm font-medium">{formatPrice(sku.latest_price_cents)}</p>
              {latestPricePerDisplayUnit !== null ? (
                <p className="text-xs text-gray-500">
                  {formatPrice(latestPricePerDisplayUnit)}/{displayUnit}
                </p>
              ) : hasPriceButNoBaseUnit && (
                <button
                  onClick={handleRecalculate}
                  disabled={isRecalculating}
                  className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1 ml-auto"
                >
                  {isRecalculating ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3" />
                  )}
                  Calc price
                </button>
              )}
              <p className="text-xs text-gray-400">{formatShortDate(sku.latest_price_date)}</p>
            </>
          )}
        </div>
      </div>

      {expanded && sku.price_history.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <p className="text-xs font-medium text-gray-500 mb-2">Price History</p>
          <div className="space-y-1.5">
            {sku.price_history.map((entry, idx) => {
              const pricePerDisplayUnit = entry.price_per_base_unit_cents
                ? convertPrice(Number(entry.price_per_base_unit_cents), baseUnit, displayUnit)
                : null
              return (
                <div key={idx} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-3 w-3 text-gray-400" />
                    <span className="text-gray-600">{formatShortDate(entry.effective_date)}</span>
                    {entry.invoice_number && (
                      <Link
                        to={entry.invoice_id ? `/invoices/${entry.invoice_id}` : '#'}
                        className="text-blue-600 hover:underline flex items-center gap-0.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <FileText className="h-3 w-3" />
                        #{entry.invoice_number}
                      </Link>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{formatPrice(entry.price_cents)}</span>
                    {pricePerDisplayUnit !== null && (
                      <span className="text-gray-400">
                        ({formatPrice(pricePerDisplayUnit)}/{displayUnit})
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
