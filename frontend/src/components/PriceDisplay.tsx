import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'

// Conversion constants (from base units)
const GRAMS_PER_OZ = 28.3495
const GRAMS_PER_LB = 453.592
const GRAMS_PER_KG = 1000

const ML_PER_FL_OZ = 29.5735
const ML_PER_CUP = 236.588
const ML_PER_GAL = 3785.41
const ML_PER_L = 1000

// Detect unit category from pack_unit
type UnitCategory = 'weight' | 'volume' | 'count' | 'unknown'

function detectUnitCategory(packUnit: string | null): UnitCategory {
  if (!packUnit) return 'unknown'
  const unit = packUnit.toLowerCase().trim()

  // Weight units
  if (['lb', 'lbs', 'pound', 'pounds', 'oz', 'ounce', 'ounces', 'kg', 'g', 'gram', 'grams'].includes(unit)) {
    return 'weight'
  }

  // Volume units
  if (['gal', 'gallon', 'gallons', 'l', 'liter', 'liters', 'ml', 'fl oz', 'floz', 'cup', 'cups', 'qt', 'quart', 'quarts', 'pt', 'pint', 'pints'].includes(unit)) {
    return 'volume'
  }

  // Count units
  if (['ea', 'each', 'ct', 'count', 'pc', 'pcs', 'piece', 'pieces', 'dz', 'dozen', 'case', 'cs', 'pk', 'pack'].includes(unit)) {
    return 'count'
  }

  return 'unknown'
}

// Unit display options per category
const unitDisplayOptions = {
  weight: [
    { label: 'per oz', unit: 'oz', factor: GRAMS_PER_OZ },
    { label: 'per lb', unit: 'lb', factor: GRAMS_PER_LB },
    { label: 'per kg', unit: 'kg', factor: GRAMS_PER_KG },
  ],
  volume: [
    { label: 'per fl oz', unit: 'fl oz', factor: ML_PER_FL_OZ },
    { label: 'per cup', unit: 'cup', factor: ML_PER_CUP },
    { label: 'per gal', unit: 'gal', factor: ML_PER_GAL },
    { label: 'per L', unit: 'L', factor: ML_PER_L },
  ],
  count: [
    { label: 'per each', unit: 'ea', factor: 1 },
  ],
  unknown: [],
}

// Default display units per category
const defaultDisplayUnit = {
  weight: 'lb',
  volume: 'gal',
  count: 'ea',
  unknown: null,
}

interface PriceDisplayProps {
  priceCents: number | null
  pricePerBaseUnitCents: number | null // per gram or per ml or per each
  packSize: string | null
  packUnit: string | null
  isBestPrice?: boolean
  compact?: boolean
  className?: string
}

export function PriceDisplay({
  priceCents,
  pricePerBaseUnitCents,
  packSize,
  packUnit,
  isBestPrice = false,
  compact = false,
  className,
}: PriceDisplayProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 })
  const [selectedUnit, setSelectedUnit] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const unitCategory = detectUnitCategory(packUnit)
  const displayOptions = unitDisplayOptions[unitCategory]
  const currentUnit = selectedUnit || defaultDisplayUnit[unitCategory]

  // Calculate normalized price
  const normalizedPrice = (() => {
    if (!pricePerBaseUnitCents || !currentUnit) return null

    const option = displayOptions.find(o => o.unit === currentUnit)
    if (!option) return null

    // pricePerBaseUnitCents is per gram/ml/each, multiply by factor to get per lb/gal/etc
    const priceInUnit = pricePerBaseUnitCents * option.factor
    return priceInUnit
  })()

  // Format price
  const formatPrice = (cents: number | null): string => {
    if (cents === null) return '-'
    return `$${(cents / 100).toFixed(2)}`
  }

  // Handle right-click
  const handleContextMenu = (e: React.MouseEvent) => {
    if (displayOptions.length === 0) return
    e.preventDefault()
    setMenuPosition({ x: e.clientX, y: e.clientY })
    setMenuOpen(true)
  }

  // Close menu on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }

    if (menuOpen) {
      document.addEventListener('click', handleClick)
      return () => document.removeEventListener('click', handleClick)
    }
  }, [menuOpen])

  if (compact) {
    return (
      <div className={cn('text-right', className)} onContextMenu={handleContextMenu}>
        <p className="font-medium">{formatPrice(priceCents)}</p>
        {normalizedPrice !== null && (
          <p className="text-xs text-gray-500">
            {formatPrice(normalizedPrice)}/{currentUnit}
          </p>
        )}
        {menuOpen && (
          <ContextMenu
            menuRef={menuRef}
            position={menuPosition}
            options={displayOptions}
            selectedUnit={currentUnit}
            onSelect={(unit) => {
              setSelectedUnit(unit)
              setMenuOpen(false)
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div
      className={cn('space-y-0.5', className)}
      onContextMenu={handleContextMenu}
    >
      {/* Main price */}
      <div className="flex items-center gap-2">
        <span className="font-semibold text-lg">{formatPrice(priceCents)}</span>
        {isBestPrice && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            Best Price
          </span>
        )}
      </div>

      {/* Pack size description */}
      {packSize && (
        <p className="text-sm text-gray-600">{packSize}</p>
      )}

      {/* Normalized price */}
      {normalizedPrice !== null && (
        <p className="text-sm text-gray-500">
          {formatPrice(normalizedPrice)}/{currentUnit}
          {displayOptions.length > 1 && (
            <span className="text-xs text-gray-400 ml-1">(right-click to change)</span>
          )}
        </p>
      )}

      {/* Context menu */}
      {menuOpen && (
        <ContextMenu
          menuRef={menuRef}
          position={menuPosition}
          options={displayOptions}
          selectedUnit={currentUnit}
          onSelect={(unit) => {
            setSelectedUnit(unit)
            setMenuOpen(false)
          }}
        />
      )}
    </div>
  )
}

// Context menu component
interface ContextMenuProps {
  position: { x: number; y: number }
  options: typeof unitDisplayOptions.weight
  selectedUnit: string | null
  onSelect: (unit: string) => void
  menuRef: React.RefObject<HTMLDivElement | null>
}

function ContextMenu({ position, options, selectedUnit, onSelect, menuRef }: ContextMenuProps) {
  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[140px]"
      style={{ top: position.y, left: position.x }}
    >
      <div className="px-3 py-1.5 text-xs text-gray-500 border-b">
        Show price...
      </div>
      {options.map((option) => (
        <button
          key={option.unit}
          className={cn(
            'w-full px-3 py-1.5 text-left text-sm hover:bg-gray-100 flex items-center justify-between',
            selectedUnit === option.unit && 'bg-gray-50 font-medium'
          )}
          onClick={() => onSelect(option.unit)}
        >
          {option.label}
          {selectedUnit === option.unit && (
            <span className="text-blue-500">✓</span>
          )}
        </button>
      ))}
    </div>
  )
}

// Inline price display for search results
interface InlinePriceProps {
  priceCents: number | null
  pricePerBaseUnitCents: number | null
  packSize: string | null
  packUnit: string | null
  isBestPrice?: boolean
  className?: string
}

export function InlinePrice({
  priceCents,
  pricePerBaseUnitCents,
  packSize,
  packUnit,
  isBestPrice = false,
  className,
}: InlinePriceProps) {
  const unitCategory = detectUnitCategory(packUnit)
  const defaultUnit = defaultDisplayUnit[unitCategory]
  const displayOptions = unitDisplayOptions[unitCategory]

  // Calculate normalized price using default unit
  const normalizedPrice = (() => {
    if (!pricePerBaseUnitCents || !defaultUnit) return null

    const option = displayOptions.find(o => o.unit === defaultUnit)
    if (!option) return null

    return pricePerBaseUnitCents * option.factor
  })()

  const formatPrice = (cents: number | null): string => {
    if (cents === null) return '-'
    return `$${(cents / 100).toFixed(2)}`
  }

  return (
    <div className={cn('text-right', className)}>
      <div className="flex items-center justify-end gap-2">
        <span className="font-medium">{formatPrice(priceCents)}</span>
        {isBestPrice && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            Best
          </span>
        )}
      </div>
      {packSize && (
        <p className="text-xs text-gray-500">{packSize}</p>
      )}
      {normalizedPrice !== null && (
        <p className="text-xs text-gray-500">
          {formatPrice(normalizedPrice)}/{defaultUnit}
        </p>
      )}
    </div>
  )
}

// Pack size breakdown for SearchResultPrice
interface PackBreakdown {
  count: number
  unitSize: number
  unit: string
  total: number
}

/**
 * Parse pack size strings like "6x24 Oz" or "4x5 LB BC"
 * Returns { count: 6, unitSize: 24, unit: 'oz', total: 144 }
 */
function parsePackSizeString(packSize: string): PackBreakdown | null {
  if (!packSize) return null

  // Pattern: NxN UNIT [optional suffix like BC, FROZEN, etc]
  // Examples: "6x24 Oz", "4x5 LB BC", "1x10 Count Case"
  const match = packSize.match(/(\d+)\s*[xX]\s*(\d+\.?\d*)\s*(\w+)/i)
  if (!match) return null

  const [, countStr, sizeStr, rawUnit] = match
  const count = parseInt(countStr, 10)
  const unitSize = parseFloat(sizeStr)
  const unit = rawUnit.toLowerCase()

  if (isNaN(count) || isNaN(unitSize)) return null

  return {
    count,
    unitSize,
    unit,
    total: count * unitSize,
  }
}

/**
 * Format per-unit price with appropriate unit
 */
function formatPerUnitPrice(
  pricePerBaseUnitCents: number,
  packUnit: string | null
): string {
  const unitCategory = detectUnitCategory(packUnit)

  // Convert from base unit (g/ml/each) to display unit
  if (unitCategory === 'weight') {
    // Show per oz and per lb
    const perOz = (pricePerBaseUnitCents * GRAMS_PER_OZ) / 100
    const perLb = (pricePerBaseUnitCents * GRAMS_PER_LB) / 100
    if (perLb < 100) {
      return `$${perOz.toFixed(2)}/oz · $${perLb.toFixed(2)}/lb`
    }
    return `$${perOz.toFixed(2)}/oz`
  }

  if (unitCategory === 'volume') {
    // Show per fl oz and per gal
    const perFlOz = (pricePerBaseUnitCents * ML_PER_FL_OZ) / 100
    const perGal = (pricePerBaseUnitCents * ML_PER_GAL) / 100
    if (perGal < 500) {
      return `$${perFlOz.toFixed(2)}/fl oz · $${perGal.toFixed(2)}/gal`
    }
    return `$${perFlOz.toFixed(2)}/fl oz`
  }

  // Count
  const perEach = pricePerBaseUnitCents / 100
  return `$${perEach.toFixed(2)}/ea`
}

// Enhanced price display for Order Hub search results
interface SearchResultPriceProps {
  priceCents: number | null
  packSize: string | null
  packUnit: string | null
  pricePerBaseUnitCents: number | null
  isBestPrice?: boolean
  isOutOfStock?: boolean
  className?: string
}

export function SearchResultPrice({
  priceCents,
  packSize,
  packUnit,
  pricePerBaseUnitCents,
  isBestPrice = false,
  isOutOfStock = false,
  className,
}: SearchResultPriceProps) {
  const breakdown = packSize ? parsePackSizeString(packSize) : null

  const formatPrice = (cents: number): string => {
    return `$${(cents / 100).toFixed(2)}`
  }

  return (
    <div className={cn('text-right space-y-0.5', className)}>
      {/* Main price - large and bold */}
      <div className="flex items-center justify-end gap-2">
        <span className="text-lg font-bold">
          {priceCents !== null ? formatPrice(priceCents) : '-'}
        </span>
        {isBestPrice && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            Best
          </span>
        )}
      </div>

      {/* Pack breakdown - medium, gray */}
      {breakdown ? (
        <div className="text-sm text-gray-600">
          {breakdown.count} × {breakdown.unitSize}
          {breakdown.unit}
          <span className="text-gray-400 ml-1">
            = {breakdown.total}{breakdown.unit}
          </span>
        </div>
      ) : packSize ? (
        <div className="text-sm text-gray-600">{packSize}</div>
      ) : null}

      {/* Per-unit price - small, muted */}
      {pricePerBaseUnitCents !== null && (
        <div className="text-xs text-gray-500">
          {formatPerUnitPrice(pricePerBaseUnitCents, packUnit)}
        </div>
      )}

      {/* Out of stock indicator */}
      {isOutOfStock && (
        <span className="text-xs text-red-500 font-medium">Out of stock</span>
      )}
    </div>
  )
}
