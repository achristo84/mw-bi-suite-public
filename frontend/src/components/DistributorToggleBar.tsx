import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

interface DistributorToggleBarProps {
  distributors: Array<{
    id: string
    name: string
  }>
  isEnabled: (id: string) => boolean
  onToggle: (id: string) => void
  className?: string
}

export function DistributorToggleBar({
  distributors,
  isEnabled,
  onToggle,
  className,
}: DistributorToggleBarProps) {
  if (distributors.length === 0) return null

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <span className="text-sm text-gray-500 mr-1">Distributors:</span>
      {distributors.map(dist => {
        const enabled = isEnabled(dist.id)
        return (
          <button
            key={dist.id}
            type="button"
            onClick={() => onToggle(dist.id)}
            className={cn(
              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium transition-colors',
              enabled
                ? 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            )}
          >
            <span
              className={cn(
                'w-4 h-4 rounded border flex items-center justify-center transition-colors',
                enabled
                  ? 'bg-blue-500 border-blue-500'
                  : 'bg-white border-gray-300'
              )}
            >
              {enabled && <Check className="h-3 w-3 text-white" />}
            </span>
            {dist.name}
          </button>
        )
      })}
    </div>
  )
}
