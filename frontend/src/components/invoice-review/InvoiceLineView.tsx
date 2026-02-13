import { Link } from 'react-router-dom'
import { formatCents } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CheckCircle2, XCircle, RotateCcw, Pencil, Link2, ExternalLink } from 'lucide-react'
import type { InvoiceLine } from '@/types/invoice'

interface InvoiceLineViewProps {
  line: InvoiceLine
  mappedIngredientName: string | undefined
  onStartEditing: () => void
  onStartMapping: () => void
  onConfirm: () => void
  onRemove: () => void
  onResetStatus: () => void
  isConfirming: boolean
  isRemoving: boolean
  isResetting: boolean
}

export function InvoiceLineView({
  line,
  mappedIngredientName,
  onStartEditing,
  onStartMapping,
  onConfirm,
  onRemove,
  onResetStatus,
  isConfirming,
  isRemoving,
  isResetting,
}: InvoiceLineViewProps) {
  return (
    <div className={cn(
      "flex items-start justify-between gap-4",
      line.line_status === 'confirmed' && "bg-green-50 -mx-4 px-4 py-2 rounded",
      line.line_status === 'removed' && "bg-gray-100 -mx-4 px-4 py-2 rounded opacity-60"
    )}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {line.line_status === 'confirmed' && (
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          )}
          {line.line_status === 'removed' && (
            <XCircle className="h-4 w-4 text-gray-400" />
          )}
          {line.line_type === 'credit' && (
            <Badge variant="warning" className="text-xs">Credit</Badge>
          )}
          {line.raw_sku && (
            <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">
              {line.raw_sku}
            </span>
          )}
          {mappedIngredientName ? (
            <Badge variant="success" className="text-xs">
              <Link2 className="h-2.5 w-2.5 mr-1" />
              {mappedIngredientName}
            </Badge>
          ) : line.line_type === 'product' && line.line_status !== 'removed' && (
            <button
              onClick={onStartMapping}
              className="text-xs text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-0.5"
            >
              <Link2 className="h-3 w-3" />
              Map
            </button>
          )}
        </div>
        <p className={cn(
          "text-sm mt-1",
          line.line_status === 'removed' ? "text-gray-500 line-through" : "text-gray-900"
        )}>
          {line.raw_description}
        </p>
        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
          <span>Qty: {line.quantity || '-'} {line.unit || ''}</span>
          <span>@ {formatCents(line.unit_price_cents)}{line.unit ? `/${line.unit}` : ''}</span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <div className={cn(
          'text-right font-medium tabular-nums mr-2',
          line.line_type === 'credit' ? 'text-green-600' :
          line.line_status === 'removed' ? 'text-gray-400 line-through' : 'text-gray-900'
        )}>
          {formatCents(line.extended_price_cents)}
        </div>
        {line.line_status === 'pending' && (
          <>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-green-600 hover:text-green-700 hover:bg-green-50"
              onClick={onConfirm}
              disabled={isConfirming}
              title="Confirm item"
            >
              <CheckCircle2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-red-500 hover:text-red-600 hover:bg-red-50"
              onClick={onRemove}
              disabled={isRemoving}
              title="Remove item (didn't arrive)"
            >
              <XCircle className="h-4 w-4" />
            </Button>
          </>
        )}
        {(line.line_status === 'confirmed' || line.line_status === 'removed') && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-gray-400 hover:text-gray-600"
            onClick={onResetStatus}
            disabled={isResetting}
            title="Reset to pending"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-gray-400 hover:text-gray-600"
          onClick={onStartEditing}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
