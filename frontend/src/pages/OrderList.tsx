import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getOrderListItems,
  createOrderListItem,
  deleteOrderListItem,
} from '@/lib/api'
import type { OrderListItemWithDetails, OrderListItemCreate } from '@/types/order-hub'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Plus,
  Search,
  Trash2,
  ShoppingCart,
  Package,
  Clock,
  Check,
  Loader2,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ComparisonSearchModal } from '@/components/ComparisonSearchModal'

// Format relative time
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

// Format price
function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const statusConfig = {
    pending: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-800',
      icon: Clock,
      label: 'Pending',
    },
    ordered: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      icon: Check,
      label: 'Ordered',
    },
    received: {
      bg: 'bg-blue-100',
      text: 'text-blue-800',
      icon: Package,
      label: 'Received',
    },
  }

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending
  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        config.bg,
        config.text
      )}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  )
}

export function OrderList() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<OrderListItemWithDetails | null>(null)
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false)

  // Add item form state
  const [newItemName, setNewItemName] = useState('')
  const [newItemQuantity, setNewItemQuantity] = useState('')
  const [newItemNotes, setNewItemNotes] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['order-list', statusFilter],
    queryFn: () => getOrderListItems(statusFilter || undefined),
  })

  const createMutation = useMutation({
    mutationFn: createOrderListItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      setIsAddModalOpen(false)
      setNewItemName('')
      setNewItemQuantity('')
      setNewItemNotes('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteOrderListItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
    },
  })

  const items = data?.items || []

  // Filter by search term (client-side)
  const filteredItems = items.filter(
    (item) =>
      item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.notes?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Group by status
  const pendingItems = filteredItems.filter((item) => item.status === 'pending')
  const orderedItems = filteredItems.filter((item) => item.status === 'ordered')
  const receivedItems = filteredItems.filter((item) => item.status === 'received')

  const handleAddItem = () => {
    if (!newItemName.trim()) return

    const data: OrderListItemCreate = {
      name: newItemName.trim(),
      quantity: newItemQuantity.trim() || undefined,
      notes: newItemNotes.trim() || undefined,
    }

    createMutation.mutate(data)
  }

  const handleItemClick = (item: OrderListItemWithDetails) => {
    if (item.status === 'pending') {
      setSelectedItem(item)
      setIsSearchModalOpen(true)
    }
  }

  const handleDeleteItem = (e: React.MouseEvent, itemId: string) => {
    e.stopPropagation()
    if (confirm('Remove this item from the order list?')) {
      deleteMutation.mutate(itemId)
    }
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">Failed to load order list. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Order List</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {pendingItems.length} pending, {orderedItems.length} ordered
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/orders/build">
            <Button variant="outline">
              <ShoppingCart className="h-4 w-4 mr-2" />
              Cart Builder
            </Button>
          </Link>
          <Button onClick={() => setIsAddModalOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Item
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-1">
          {['', 'pending', 'ordered', 'received'].map((status) => (
            <Button
              key={status || 'all'}
              variant={statusFilter === status ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setStatusFilter(status)}
            >
              {status ? status.charAt(0).toUpperCase() + status.slice(1) : 'All'}
            </Button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredItems.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Package className="h-12 w-12 text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No items yet</h3>
            <p className="text-sm text-gray-500 mt-1">
              Add items you need to order
            </p>
            <Button onClick={() => setIsAddModalOpen(true)} className="mt-4">
              <Plus className="h-4 w-4 mr-2" />
              Add First Item
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Pending Items */}
      {pendingItems.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Pending ({pendingItems.length})
          </h2>
          <div className="grid gap-2">
            {pendingItems.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={() => handleItemClick(item)}
                onDelete={(e) => handleDeleteItem(e, item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Ordered Items */}
      {orderedItems.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <ShoppingCart className="h-4 w-4" />
            Ordered ({orderedItems.length})
          </h2>
          <div className="grid gap-2">
            {orderedItems.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={() => handleItemClick(item)}
                onDelete={(e) => handleDeleteItem(e, item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Received Items */}
      {receivedItems.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Check className="h-4 w-4" />
            Received ({receivedItems.length})
          </h2>
          <div className="grid gap-2">
            {receivedItems.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={() => handleItemClick(item)}
                onDelete={(e) => handleDeleteItem(e, item.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Add Item Modal */}
      <Dialog open={isAddModalOpen} onOpenChange={setIsAddModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add to Order List</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Item Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Eggs, Whole Milk, Bread"
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quantity">Quantity</Label>
              <Input
                id="quantity"
                placeholder="e.g., 2 cases, about 20 lbs"
                value={newItemQuantity}
                onChange={(e) => setNewItemQuantity(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                placeholder="Any additional details..."
                value={newItemNotes}
                onChange={(e) => setNewItemNotes(e.target.value)}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddItem}
              disabled={!newItemName.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Plus className="h-4 w-4 mr-2" />
              )}
              Add Item
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Comparison Search Modal */}
      {selectedItem && (
        <ComparisonSearchModal
          open={isSearchModalOpen}
          onClose={() => {
            setIsSearchModalOpen(false)
            setSelectedItem(null)
          }}
          item={selectedItem}
        />
      )}
    </div>
  )
}

// Item Card Component
function ItemCard({
  item,
  onClick,
  onDelete,
}: {
  item: OrderListItemWithDetails
  onClick: () => void
  onDelete: (e: React.MouseEvent) => void
}) {
  const isPending = item.status === 'pending'

  return (
    <Card
      className={cn(
        'transition-colors',
        isPending && 'cursor-pointer hover:bg-gray-50 border-yellow-200 bg-yellow-50/50'
      )}
      onClick={isPending ? onClick : undefined}
    >
      <CardContent className="py-3 px-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900 truncate">
                {item.name}
              </span>
              {item.quantity && (
                <span className="text-sm text-gray-500 shrink-0">
                  ({item.quantity})
                </span>
              )}
              <StatusBadge status={item.status} />
            </div>
            <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
              {item.ingredient_name && (
                <span className="flex items-center gap-1">
                  <Package className="h-3 w-3" />
                  {item.ingredient_name}
                </span>
              )}
              {item.last_ordered_distributor && (
                <span>
                  Last: {item.last_ordered_distributor}
                  {item.last_ordered_price_cents &&
                    ` (${formatPrice(item.last_ordered_price_cents)})`}
                </span>
              )}
              {item.notes && (
                <span className="truncate italic">{item.notes}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-gray-400">
              {item.created_by && `${item.created_by} - `}
              {formatRelativeTime(item.created_at)}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-gray-400 hover:text-red-500"
              onClick={onDelete}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            {isPending && (
              <ChevronRight className="h-5 w-5 text-gray-400" />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
