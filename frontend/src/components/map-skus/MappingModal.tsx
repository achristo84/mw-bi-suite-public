import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { mapDistIngredient } from '@/lib/api'
import { formatPrice } from '@/lib/unitConversions'
import type { UnmappedDistIngredient, IngredientWithPrice } from '@/types/ingredient'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Check, Loader2 } from 'lucide-react'

interface MappingModalProps {
  item: UnmappedDistIngredient
  ingredients: IngredientWithPrice[]
  selectedIngredientId: string | null
  selectedIngredientName: string | undefined
  onClose: () => void
  onMapped: () => void
}

export function MappingModal({
  item,
  ingredients,
  selectedIngredientId,
  selectedIngredientName,
  onClose,
  onMapped,
}: MappingModalProps) {
  const [ingredientId, setIngredientId] = useState<string>(selectedIngredientId || '')
  const [ingredientSearch, setIngredientSearch] = useState(selectedIngredientName || '')
  const [showDropdown, setShowDropdown] = useState(false)
  const [packSize, setPackSize] = useState<string>(item.parsed_pack_quantity?.toString() || '')
  const [packUnit, setPackUnit] = useState<string>(
    item.parsed_unit_quantity && item.parsed_unit
      ? `${item.parsed_unit_quantity}${item.parsed_unit}`
      : ''
  )
  const [gramsPerUnit, setGramsPerUnit] = useState<string>(
    item.parsed_total_base_units?.toString() || ''
  )
  const [error, setError] = useState<string | null>(null)

  const selectedIngredient = ingredients.find(i => i.id === ingredientId)
  const filteredIngredients = ingredients.filter(i =>
    i.name.toLowerCase().includes(ingredientSearch.toLowerCase())
  )

  const mapMutation = useMutation({
    mutationFn: () =>
      mapDistIngredient(item.id, {
        ingredient_id: ingredientId,
        pack_size: packSize ? parseFloat(packSize) : undefined,
        pack_unit: packUnit || undefined,
        grams_per_unit: gramsPerUnit ? parseFloat(gramsPerUnit) : undefined,
      }),
    onSuccess: onMapped,
    onError: (err: Error) => setError(err.message),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!ingredientId) {
      setError('Please select an ingredient')
      return
    }
    setError(null)
    mapMutation.mutate()
  }

  const selectIngredient = (ing: IngredientWithPrice) => {
    setIngredientId(ing.id)
    setIngredientSearch(ing.name)
    setShowDropdown(false)
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[9999]">
      <Card className="w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto bg-white shadow-2xl">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Map SKU</CardTitle>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* SKU Info */}
            <div className="p-3 bg-gray-50 rounded text-sm">
              <p className="font-medium">{item.description}</p>
              <p className="text-gray-500 text-xs mt-1">
                {item.distributor_name}
                {item.sku && <span className="ml-2">· SKU: {item.sku}</span>}
              </p>
            </div>

            {/* Ingredient Selection */}
            <div className="relative">
              <Label>Map to Ingredient</Label>
              <Input
                value={ingredientSearch}
                onChange={(e) => {
                  setIngredientSearch(e.target.value)
                  setShowDropdown(true)
                  if (selectedIngredient && e.target.value !== selectedIngredient.name) {
                    setIngredientId('')
                  }
                }}
                onFocus={() => setShowDropdown(true)}
                placeholder="Search ingredients..."
                className="mt-1"
              />
              {selectedIngredient && (
                <p className="text-xs text-green-600 mt-1">
                  Selected: {selectedIngredient.name} ({selectedIngredient.base_unit})
                </p>
              )}
              {showDropdown && ingredientSearch && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-md shadow-lg max-h-48 overflow-auto">
                  {filteredIngredients.length === 0 ? (
                    <div className="p-3 text-sm text-gray-500">No matches found</div>
                  ) : (
                    filteredIngredients.slice(0, 15).map((ing) => (
                      <button
                        key={ing.id}
                        type="button"
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-blue-50 flex justify-between items-center ${
                          ingredientId === ing.id ? 'bg-blue-100' : ''
                        }`}
                        onClick={() => selectIngredient(ing)}
                      >
                        <span>{ing.name}</span>
                        <span className="text-gray-400 text-xs">{ing.base_unit}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Pack Info */}
            <div className="border-t pt-4">
              <p className="text-sm font-medium mb-3">Pack Information</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-xs">Pack Qty</Label>
                  <Input
                    type="number"
                    step="any"
                    value={packSize}
                    onChange={(e) => setPackSize(e.target.value)}
                    placeholder="e.g. 36"
                    className="mt-1 h-9"
                  />
                </div>
                <div>
                  <Label className="text-xs">Pack Unit</Label>
                  <Input
                    value={packUnit}
                    onChange={(e) => setPackUnit(e.target.value)}
                    placeholder="e.g. 1LB"
                    className="mt-1 h-9"
                  />
                </div>
                <div>
                  <Label className="text-xs">Total Base Units</Label>
                  <Input
                    type="number"
                    step="any"
                    value={gramsPerUnit}
                    onChange={(e) => setGramsPerUnit(e.target.value)}
                    placeholder="e.g. 16329"
                    className="mt-1 h-9"
                  />
                </div>
              </div>
              {item.parsed_total_base_units && (
                <p className="text-xs text-gray-500 mt-2">
                  Parsed: {item.parsed_pack_quantity}x{item.parsed_unit_quantity}{item.parsed_unit} ={' '}
                  {Number(item.parsed_total_base_units).toFixed(1)} {item.parsed_base_unit}
                </p>
              )}
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={mapMutation.isPending || !ingredientId}>
                {mapMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Map SKU
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
