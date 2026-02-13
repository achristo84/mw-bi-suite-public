import { formatCents } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Check, Loader2 } from 'lucide-react'
import type { InvoiceLine } from '@/types/invoice'

const COMMON_UNITS = ['EA', 'CS', 'LB', 'OZ', 'GAL', 'QT', 'PT', 'L', 'ML', 'KG', 'G', 'DOZ', 'PK', 'BG', 'BX', 'CT']

export interface EditValues {
  quantity: string
  unit: string
  unit_price_cents: string
  extended_price_cents: string
}

interface InvoiceLineEditorProps {
  line: InvoiceLine
  editValues: EditValues
  isSaving: boolean
  onQuantityChange: (value: string) => void
  onUnitPriceChange: (value: string) => void
  onUnitChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
  getDisplayedExtended: () => number
}

export function InvoiceLineEditor({
  line,
  editValues,
  isSaving,
  onQuantityChange,
  onUnitPriceChange,
  onUnitChange,
  onSave,
  onCancel,
  getDisplayedExtended,
}: InvoiceLineEditorProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {line.line_type === 'credit' && (
          <Badge variant="warning" className="text-xs">Credit</Badge>
        )}
        {line.raw_sku && (
          <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
            {line.raw_sku}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-900">{line.raw_description}</p>

      <div className="grid grid-cols-4 gap-2">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Qty</label>
          <Input
            type="number"
            step="0.01"
            value={editValues.quantity}
            onChange={(e) => onQuantityChange(e.target.value)}
            className="h-8 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Unit</label>
          <select
            value={editValues.unit}
            onChange={(e) => onUnitChange(e.target.value)}
            className="h-8 w-full border rounded px-2 text-sm bg-white"
          >
            <option value="">-</option>
            {COMMON_UNITS.map(u => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Unit $</label>
          <Input
            type="number"
            step="0.01"
            value={editValues.unit_price_cents}
            onChange={(e) => onUnitPriceChange(e.target.value)}
            className="h-8 text-sm"
            placeholder="0.00"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Extended</label>
          <div className="h-8 flex items-center text-sm font-medium text-gray-700">
            {formatCents(getDisplayedExtended())}
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={onSave}
          disabled={isSaving}
        >
          {isSaving ? (
            <Loader2 className="h-3 w-3 animate-spin mr-1" />
          ) : (
            <Check className="h-3 w-3 mr-1" />
          )}
          Save
        </Button>
      </div>
    </div>
  )
}
