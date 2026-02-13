import { cn } from '@/lib/utils'
import { Check, Circle, CircleDot } from 'lucide-react'
import type { OrderListItemWithDetails } from '@/types/order-hub'

// Derived status based on item properties
type DerivedStatus = 'new' | 'has_history' | 'assigned' | 'ordered' | 'arrived'

// Derive the visual status from item properties
export function deriveStatus(item: OrderListItemWithDetails): DerivedStatus {
  // Check explicit status first
  if (item.status === 'received') return 'arrived'
  if (item.status === 'ordered') return 'ordered'

  // Check for assignments
  if (item.assignments_count > 0) return 'assigned'

  // Check for order history
  if (item.last_ordered_at) return 'has_history'

  // Default to new
  return 'new'
}

// Status configuration
const statusConfig = {
  new: {
    label: 'New',
    description: 'No history, no assignment',
    bgColor: 'bg-gray-100',
    textColor: 'text-gray-600',
    borderColor: 'border-gray-300',
    dotColor: 'text-gray-400',
    Icon: Circle,
    iconFilled: false,
  },
  has_history: {
    label: 'History',
    description: 'Previously ordered',
    bgColor: 'bg-blue-100',
    textColor: 'text-blue-700',
    borderColor: 'border-blue-300',
    dotColor: 'text-blue-500',
    Icon: Circle,
    iconFilled: false,
  },
  assigned: {
    label: 'Assigned',
    description: 'Linked to vendor SKU',
    bgColor: 'bg-green-100',
    textColor: 'text-green-700',
    borderColor: 'border-green-300',
    dotColor: 'text-green-500',
    Icon: Circle,
    iconFilled: true,
  },
  ordered: {
    label: 'Ordered',
    description: 'In current order batch',
    bgColor: 'bg-orange-100',
    textColor: 'text-orange-700',
    borderColor: 'border-orange-300',
    dotColor: 'text-orange-500',
    Icon: CircleDot,
    iconFilled: true,
  },
  arrived: {
    label: 'Arrived',
    description: 'Received',
    bgColor: 'bg-emerald-100',
    textColor: 'text-emerald-700',
    borderColor: 'border-emerald-300',
    dotColor: 'text-emerald-500',
    Icon: Check,
    iconFilled: true,
  },
}

interface ListItemBadgeProps {
  item: OrderListItemWithDetails
  showLabel?: boolean
  size?: 'sm' | 'md'
  className?: string
}

export function ListItemBadge({
  item,
  showLabel = true,
  size = 'sm',
  className,
}: ListItemBadgeProps) {
  const derivedStatus = deriveStatus(item)
  const config = statusConfig[derivedStatus]
  const Icon = config.Icon

  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  if (!showLabel) {
    // Icon only mode
    return (
      <span
        className={cn('inline-flex items-center', className)}
        title={`${config.label}: ${config.description}`}
      >
        <Icon
          className={cn(
            iconSize,
            config.dotColor,
            config.iconFilled && derivedStatus === 'assigned' && 'fill-current'
          )}
        />
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium',
        config.bgColor,
        config.textColor,
        textSize,
        className
      )}
      title={config.description}
    >
      <Icon
        className={cn(
          iconSize,
          config.iconFilled && derivedStatus === 'assigned' && 'fill-current'
        )}
      />
      {config.label}
    </span>
  )
}

// Status dot for sidebar display
interface StatusDotProps {
  item: OrderListItemWithDetails
  className?: string
}

export function StatusDot({ item, className }: StatusDotProps) {
  const derivedStatus = deriveStatus(item)
  const config = statusConfig[derivedStatus]
  const Icon = config.Icon

  return (
    <span
      className={cn('inline-flex items-center', className)}
      title={`${config.label}: ${config.description}`}
    >
      <Icon
        className={cn(
          'h-3 w-3',
          config.dotColor,
          config.iconFilled && derivedStatus === 'assigned' && 'fill-current'
        )}
      />
    </span>
  )
}

// Export status config for use elsewhere
export { statusConfig }
export type { DerivedStatus }
