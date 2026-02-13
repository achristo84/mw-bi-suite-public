// Unit conversion factors (to base unit)
export const WEIGHT_UNITS = {
  g: { label: 'g', factor: 1 },
  oz: { label: 'oz', factor: 28.3495 },
  lb: { label: 'lb', factor: 453.592 },
  kg: { label: 'kg', factor: 1000 },
} as const

export const VOLUME_UNITS = {
  ml: { label: 'ml', factor: 1 },
  'fl oz': { label: 'fl oz', factor: 29.5735 },
  cup: { label: 'cup', factor: 236.588 },
  pt: { label: 'pt', factor: 473.176 },
  qt: { label: 'qt', factor: 946.353 },
  L: { label: 'L', factor: 1000 },
  gal: { label: 'gal', factor: 3785.41 },
} as const

// Full conversion table: display unit -> { factor to base, base unit }
export const UNIT_CONVERSIONS: Record<string, { factor: number; baseUnit: string }> = {
  g: { factor: 1, baseUnit: 'g' },
  kg: { factor: 1000, baseUnit: 'g' },
  lb: { factor: 453.592, baseUnit: 'g' },
  oz: { factor: 28.3495, baseUnit: 'g' },
  ml: { factor: 1, baseUnit: 'ml' },
  L: { factor: 1000, baseUnit: 'ml' },
  'fl oz': { factor: 29.5735, baseUnit: 'ml' },
  cup: { factor: 236.588, baseUnit: 'ml' },
  gal: { factor: 3785.41, baseUnit: 'ml' },
  each: { factor: 1, baseUnit: 'each' },
}

// Convert price from base unit to display unit
export function convertPrice(pricePerBaseUnit: number | null, baseUnit: string, displayUnit: string): number | null {
  if (pricePerBaseUnit === null) return null

  let factor = 1
  if (baseUnit === 'g' && displayUnit in WEIGHT_UNITS) {
    factor = WEIGHT_UNITS[displayUnit as keyof typeof WEIGHT_UNITS].factor
  } else if (baseUnit === 'ml' && displayUnit in VOLUME_UNITS) {
    factor = VOLUME_UNITS[displayUnit as keyof typeof VOLUME_UNITS].factor
  }

  return pricePerBaseUnit * factor
}

// Get available units for a base unit
export function getAvailableUnits(baseUnit: string): { value: string; label: string }[] {
  if (baseUnit === 'g') {
    return [
      { value: 'lb', label: 'per lb' },
      { value: 'oz', label: 'per oz' },
      { value: 'g', label: 'per g' },
      { value: 'kg', label: 'per kg' },
    ]
  }
  if (baseUnit === 'ml') {
    return [
      { value: 'gal', label: 'per gal' },
      { value: 'qt', label: 'per qt' },
      { value: 'L', label: 'per L' },
      { value: 'ml', label: 'per ml' },
    ]
  }
  return [{ value: 'each', label: 'each' }]
}

// Get available units for a base unit type (simple list)
export function getUnitsForBase(baseUnit: string): string[] {
  if (baseUnit === 'g') return ['g', 'kg', 'lb', 'oz']
  if (baseUnit === 'ml') return ['ml', 'L', 'fl oz', 'cup', 'gal']
  return ['each']
}

// Convert from display unit to base unit
export function toBaseUnit(value: number, unit: string): number {
  const conversion = UNIT_CONVERSIONS[unit]
  return conversion ? value * conversion.factor : value
}

// Format cents as dollars
export function formatPrice(cents: number | string | null): string {
  if (cents === null) return '-'
  return `$${(Number(cents) / 100).toFixed(2)}`
}

// Format date as short string
export function formatShortDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
