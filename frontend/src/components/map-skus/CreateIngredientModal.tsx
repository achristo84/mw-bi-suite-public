import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createIngredient } from '@/lib/api'
import { INGREDIENT_CATEGORIES } from '@/types/ingredient'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X, Check, Loader2 } from 'lucide-react'

interface CreateIngredientModalProps {
  onClose: () => void
  onCreated: (id: string) => void
}

export function CreateIngredientModal({ onClose, onCreated }: CreateIngredientModalProps) {
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [baseUnit, setBaseUnit] = useState<'g' | 'ml' | 'each'>('g')
  const [error, setError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      createIngredient({
        name,
        category: category || undefined,
        base_unit: baseUnit,
      }),
    onSuccess: (data) => onCreated(data.id),
    onError: (err: Error) => setError(err.message),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setError(null)
    createMutation.mutate()
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[9999]">
      <Card className="w-full max-w-md mx-4 bg-white shadow-2xl">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">New Ingredient</CardTitle>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Whole Milk"
                className="mt-1"
                autoFocus
              />
            </div>

            <div>
              <Label>Category</Label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full mt-1 border rounded px-3 py-2"
              >
                <option value="">Select category...</option>
                {INGREDIENT_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1).replace('_', ' ')}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label>Base Unit</Label>
              <div className="flex gap-2 mt-1">
                {(['g', 'ml', 'each'] as const).map((unit) => (
                  <button
                    key={unit}
                    type="button"
                    onClick={() => setBaseUnit(unit)}
                    className={`flex-1 py-2 px-3 rounded border text-sm transition-colors ${
                      baseUnit === unit
                        ? 'bg-blue-100 border-blue-500 text-blue-700 font-medium'
                        : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {unit === 'g' ? 'Weight (g)' : unit === 'ml' ? 'Volume (ml)' : 'Count (each)'}
                  </button>
                ))}
              </div>
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Create
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
