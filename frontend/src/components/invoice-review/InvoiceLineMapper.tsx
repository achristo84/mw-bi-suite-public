import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Ingredient } from '@/types/ingredient'
import type { InvoiceLine } from '@/types/invoice'

interface InvoiceLineMapperProps {
  line: InvoiceLine
  ingredientSearch: string
  ingredients: Ingredient[]
  isMapping: boolean
  onSearchChange: (value: string) => void
  onMapToIngredient: (ingredientId: string) => void
  onCancel: () => void
}

export function InvoiceLineMapper({
  line,
  ingredientSearch,
  ingredients,
  isMapping,
  onSearchChange,
  onMapToIngredient,
  onCancel,
}: InvoiceLineMapperProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {line.raw_sku && (
          <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
            {line.raw_sku}
          </span>
        )}
        <span className="text-sm text-gray-700">{line.raw_description}</span>
      </div>

      <div className="border rounded-lg p-3 bg-gray-50">
        <label className="text-xs text-gray-500 block mb-2">Map to ingredient:</label>
        <Input
          type="text"
          placeholder="Search ingredients..."
          value={ingredientSearch}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-8 text-sm mb-2"
        />
        <div className="max-h-40 overflow-y-auto">
          {ingredients.length > 0 ? (
            <ul className="space-y-1">
              {ingredients.slice(0, 10).map((ing) => (
                <li key={ing.id}>
                  <button
                    onClick={() => onMapToIngredient(ing.id)}
                    disabled={isMapping}
                    className="w-full text-left px-2 py-1.5 text-sm rounded hover:bg-blue-50 hover:text-blue-700 flex items-center justify-between"
                  >
                    <span>{ing.name}</span>
                    <span className="text-xs text-gray-400">{ing.base_unit}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : ingredientSearch ? (
            <p className="text-xs text-gray-500 py-2">No matches found</p>
          ) : (
            <p className="text-xs text-gray-500 py-2">Type to search...</p>
          )}
        </div>
      </div>

      <div className="flex justify-between items-center">
        <Link
          to="/ingredients/map"
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          Advanced mapping <ExternalLink className="h-3 w-3" />
        </Link>
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={isMapping}
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}
