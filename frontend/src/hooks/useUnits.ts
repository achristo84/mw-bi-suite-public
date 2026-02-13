import { useQuery, useMutation } from '@tanstack/react-query'
import { getUnits, parsePack } from '@/lib/api'

/**
 * Hook for accessing unit conversions and pack parsing.
 *
 * Provides:
 * - units: Unit conversion factors for weight/volume/count
 * - convertToBase: Convert a quantity to base units (g, ml, each)
 * - parsePack: Parse a pack description like "36/1LB"
 * - getUnitType: Determine if a unit is weight/volume/count
 */
export function useUnits() {
  const { data: units, isLoading } = useQuery({
    queryKey: ['units'],
    queryFn: getUnits,
    staleTime: 1000 * 60 * 60, // Cache for 1 hour (units don't change)
  })

  const parsePackMutation = useMutation({
    mutationFn: parsePack,
  })

  /**
   * Get the type of a unit (weight, volume, or count)
   */
  const getUnitType = (unit: string): 'weight' | 'volume' | 'count' | null => {
    if (!units) return null
    const normalized = unit.toLowerCase().trim()

    if (normalized in units.weight || ['g', 'kg', 'oz', 'lb'].includes(normalized)) {
      return 'weight'
    }
    if (normalized in units.volume || ['ml', 'l', 'gal', 'qt', 'pt', 'fl oz'].includes(normalized)) {
      return 'volume'
    }
    if (normalized in units.count || ['ea', 'each', 'ct', 'doz', 'dozen'].includes(normalized)) {
      return 'count'
    }
    return null
  }

  /**
   * Convert a quantity to base units (g, ml, or each)
   */
  const convertToBase = (quantity: number, unit: string): { value: number; baseUnit: string } | null => {
    if (!units) return null
    const normalized = unit.toLowerCase().trim()

    // Weight -> grams
    if (normalized in units.weight) {
      return { value: quantity * units.weight[normalized], baseUnit: 'g' }
    }

    // Volume -> ml
    if (normalized in units.volume) {
      return { value: quantity * units.volume[normalized], baseUnit: 'ml' }
    }

    // Count -> each
    if (normalized in units.count) {
      return { value: quantity * units.count[normalized], baseUnit: 'each' }
    }

    return null
  }

  /**
   * Convert from base units to display units
   */
  const convertFromBase = (quantity: number, unit: string): number | null => {
    if (!units) return null
    const normalized = unit.toLowerCase().trim()

    // Find the conversion factor
    const weightFactor = units.weight[normalized]
    if (weightFactor) return quantity / weightFactor

    const volumeFactor = units.volume[normalized]
    if (volumeFactor) return quantity / volumeFactor

    const countFactor = units.count[normalized]
    if (countFactor) return quantity / countFactor

    return null
  }

  /**
   * Get the base unit for a unit type
   */
  const getBaseUnit = (unitType: 'weight' | 'volume' | 'count'): string => {
    switch (unitType) {
      case 'weight': return 'g'
      case 'volume': return 'ml'
      case 'count': return 'each'
    }
  }

  /**
   * Get common units for a dropdown, organized by type
   */
  const getUnitOptions = () => {
    return {
      weight: ['g', 'kg', 'oz', 'lb'],
      volume: ['ml', 'L', 'fl oz', 'cup', 'pt', 'qt', 'gal', 'tbsp', 'tsp'],
      count: ['each', 'doz'],
    }
  }

  return {
    units,
    isLoading,
    convertToBase,
    convertFromBase,
    getUnitType,
    getBaseUnit,
    getUnitOptions,
    parsePack: parsePackMutation.mutateAsync,
    isParsingPack: parsePackMutation.isPending,
  }
}
