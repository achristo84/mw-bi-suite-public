import { getUnitsForBase } from '@/lib/unitConversions'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Trash2 } from 'lucide-react'

export interface EditableIngredient {
  ingredient_id: string
  ingredient_name: string
  ingredient_base_unit: string
  quantity_grams: number
  display_quantity: number
  display_unit: string
  prep_note: string
  is_optional: boolean
  isNew?: boolean
  isModified?: boolean
}

interface IngredientTableProps {
  ingredients: EditableIngredient[]
  onIngredientChange: (index: number, field: string, value: string | number | boolean) => void
  onRemoveIngredient: (index: number) => void
}

export function IngredientTable({ ingredients, onIngredientChange, onRemoveIngredient }: IngredientTableProps) {
  if (ingredients.length === 0) {
    return (
      <Card>
        <CardContent className="py-0">
          <p className="py-8 text-center text-gray-500">
            No ingredients yet. Click "Add Ingredient" to get started.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent className="py-0">
        <table className="w-full">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500 uppercase">
              <th className="py-2 pr-2 w-24">Quantity</th>
              <th className="py-2 pr-2 w-12">Unit</th>
              <th className="py-2 pr-2">Ingredient</th>
              <th className="py-2 pr-2">Prep Note</th>
              <th className="py-2 w-10"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {ingredients.map((ing, index) => (
              <tr key={`${ing.ingredient_id}-${index}`} className="text-sm">
                <td className="py-2 pr-2">
                  <Input
                    type="number"
                    step="any"
                    min="0"
                    value={ing.display_quantity || ''}
                    onChange={(e) =>
                      onIngredientChange(
                        index,
                        'display_quantity',
                        parseFloat(e.target.value) || 0
                      )
                    }
                    className="w-24 text-right tabular-nums"
                  />
                </td>
                <td className="py-2 pr-2">
                  <select
                    value={ing.display_unit}
                    onChange={(e) =>
                      onIngredientChange(index, 'display_unit', e.target.value)
                    }
                    className="border rounded px-2 py-1 text-xs bg-white"
                  >
                    {getUnitsForBase(ing.ingredient_base_unit).map((unit) => (
                      <option key={unit} value={unit}>
                        {unit}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2 pr-2 font-medium">{ing.ingredient_name}</td>
                <td className="py-2 pr-2">
                  <Input
                    value={ing.prep_note}
                    onChange={(e) =>
                      onIngredientChange(index, 'prep_note', e.target.value)
                    }
                    placeholder="e.g., diced"
                    className="text-sm"
                  />
                </td>
                <td className="py-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemoveIngredient(index)}
                    className="h-8 w-8 p-0 text-gray-400 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
