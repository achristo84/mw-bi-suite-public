import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getOrderBuilderSummary,
  updateAssignment,
  deleteAssignment,
  finalizeOrders,
  getOrderCopyList,
} from '@/lib/api'
import type {
  DistributorCart,
  CartItem,
  OrderWithDetails,
} from '@/types/order-hub'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  ClipboardList,
  Truck,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
  Copy,
  ExternalLink,
  ShoppingCart,
  Package,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Format price
function formatPrice(cents: number | null): string {
  if (cents === null || cents === 0) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

// Format delivery days
function formatDeliveryDays(days: string[] | null): string {
  if (!days || days.length === 0) return 'No schedule'
  return days.map((d) => d.charAt(0).toUpperCase() + d.slice(1, 3)).join(', ')
}

// Format date
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

export function OrderBuilder() {
  const queryClient = useQueryClient()
  const [isOutputModalOpen, setIsOutputModalOpen] = useState(false)
  const [selectedOrders, setSelectedOrders] = useState<OrderWithDetails[]>([])

  const { data, isLoading, error } = useQuery({
    queryKey: ['order-builder-summary'],
    queryFn: getOrderBuilderSummary,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAssignment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      quantity,
    }: {
      id: string
      quantity: number
    }) => updateAssignment(id, { quantity }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
    },
  })

  const finalizeMutation = useMutation({
    mutationFn: finalizeOrders,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
      setSelectedOrders(result.orders)
      setIsOutputModalOpen(true)
    },
  })

  const handleDeleteItem = (assignmentId: string) => {
    if (confirm('Remove this item from the cart?')) {
      deleteMutation.mutate(assignmentId)
    }
  }

  const handleUpdateQuantity = (assignmentId: string, quantity: number) => {
    if (quantity < 1) return
    updateMutation.mutate({ id: assignmentId, quantity })
  }

  const handleFinalize = (distributorIds?: string[]) => {
    finalizeMutation.mutate(distributorIds ? { distributor_ids: distributorIds } : undefined)
  }

  const carts = data?.carts || []
  const totalItems = data?.total_items || 0
  const totalCents = data?.total_cents || 0
  const readyCount = data?.ready_to_order || 0

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">Failed to load carts. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cart Builder</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {totalItems} items across {carts.length} distributors -{' '}
            {formatPrice(totalCents)} total
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/orders/list">
            <Button variant="outline">
              <ClipboardList className="h-4 w-4 mr-2" />
              Order List
            </Button>
          </Link>
          <Button
            onClick={() => handleFinalize()}
            disabled={readyCount === 0 || finalizeMutation.isPending}
          >
            {finalizeMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            Finalize Orders ({readyCount})
          </Button>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && carts.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShoppingCart className="h-12 w-12 text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No items in carts</h3>
            <p className="text-sm text-gray-500 mt-1">
              Search for items from the Order List to add to carts
            </p>
            <Link to="/orders/list">
              <Button className="mt-4">
                <ClipboardList className="h-4 w-4 mr-2" />
                Go to Order List
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Distributor Carts */}
      <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {carts.map((cart) => (
          <DistributorCartCard
            key={cart.distributor_id}
            cart={cart}
            onDeleteItem={handleDeleteItem}
            onUpdateQuantity={handleUpdateQuantity}
            onFinalize={() => handleFinalize([cart.distributor_id])}
            isDeleting={deleteMutation.isPending}
            isFinalizing={finalizeMutation.isPending}
          />
        ))}
      </div>

      {/* Order Output Modal */}
      <OrderOutputModal
        open={isOutputModalOpen}
        onClose={() => setIsOutputModalOpen(false)}
        orders={selectedOrders}
      />
    </div>
  )
}

// Distributor Cart Card
function DistributorCartCard({
  cart,
  onDeleteItem,
  onUpdateQuantity,
  onFinalize,
  isDeleting,
  isFinalizing,
}: {
  cart: DistributorCart
  onDeleteItem: (assignmentId: string) => void
  onUpdateQuantity: (assignmentId: string, quantity: number) => void
  onFinalize: () => void
  isDeleting: boolean
  isFinalizing: boolean
}) {
  const progressPercent = cart.minimum_order_cents > 0
    ? Math.min(100, (cart.subtotal_cents / cart.minimum_order_cents) * 100)
    : 100

  return (
    <Card
      className={cn(
        'flex flex-col',
        !cart.meets_minimum && 'border-yellow-300'
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{cart.distributor_name}</CardTitle>
          {cart.ordering_enabled && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
              API Ready
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          {cart.delivery_days && (
            <span className="flex items-center gap-1">
              <Truck className="h-4 w-4" />
              {formatDeliveryDays(cart.delivery_days)}
            </span>
          )}
          {cart.next_delivery_date && (
            <span>Next: {formatDate(cart.next_delivery_date)}</span>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col">
        {/* Items */}
        <div className="flex-1 space-y-2 mb-4">
          {cart.items.map((item) => (
            <CartItemRow
              key={item.assignment_id}
              item={item}
              onDelete={() => onDeleteItem(item.assignment_id)}
              onUpdateQuantity={(qty) =>
                onUpdateQuantity(item.assignment_id, qty)
              }
              isDeleting={isDeleting}
            />
          ))}
        </div>

        {/* Minimum Progress */}
        {cart.minimum_order_cents > 0 && (
          <div className="space-y-1 mb-4">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Order minimum</span>
              <span
                className={cn(
                  cart.meets_minimum ? 'text-green-600' : 'text-yellow-600'
                )}
              >
                {formatPrice(cart.subtotal_cents)} /{' '}
                {formatPrice(cart.minimum_order_cents)}
              </span>
            </div>
            <Progress
              value={progressPercent}
              className={cn(
                'h-2',
                cart.meets_minimum ? '[&>div]:bg-green-500' : '[&>div]:bg-yellow-500'
              )}
            />
          </div>
        )}

        {/* Footer */}
        <div className="border-t pt-4 flex items-center justify-between">
          <div>
            <p className="text-lg font-semibold">{formatPrice(cart.subtotal_cents)}</p>
            <p className="text-sm text-gray-500">{cart.items.length} items</p>
          </div>
          <Button
            size="sm"
            variant={cart.meets_minimum ? 'default' : 'outline'}
            onClick={onFinalize}
            disabled={!cart.meets_minimum || isFinalizing}
          >
            {isFinalizing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : cart.meets_minimum ? (
              <Check className="h-4 w-4 mr-2" />
            ) : (
              <AlertCircle className="h-4 w-4 mr-2" />
            )}
            {cart.meets_minimum ? 'Finalize' : 'Below Minimum'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// Cart Item Row
function CartItemRow({
  item,
  onDelete,
  onUpdateQuantity,
  isDeleting,
}: {
  item: CartItem
  onDelete: () => void
  onUpdateQuantity: (qty: number) => void
  isDeleting: boolean
}) {
  const [editQuantity, setEditQuantity] = useState(item.quantity.toString())

  const handleQuantityBlur = () => {
    const qty = parseInt(editQuantity)
    if (qty > 0 && qty !== item.quantity) {
      onUpdateQuantity(qty)
    } else {
      setEditQuantity(item.quantity.toString())
    }
  }

  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">
          {item.order_list_item_name}
        </p>
        <p className="text-xs text-gray-500 truncate">
          {item.sku && `${item.sku} - `}
          {item.description}
        </p>
      </div>
      <Input
        type="number"
        min="1"
        value={editQuantity}
        onChange={(e) => setEditQuantity(e.target.value)}
        onBlur={handleQuantityBlur}
        className="w-16 h-8 text-center text-sm"
      />
      <div className="text-right w-20">
        <p className="font-medium text-sm">
          {formatPrice(item.extended_price_cents)}
        </p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-gray-400 hover:text-red-500"
        onClick={onDelete}
        disabled={isDeleting}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  )
}

// Order Output Modal
function OrderOutputModal({
  open,
  onClose,
  orders,
}: {
  open: boolean
  onClose: () => void
  orders: OrderWithDetails[]
}) {
  const [copyStatus, setCopyStatus] = useState<Record<string, boolean>>({})

  const handleCopyList = async (orderId: string) => {
    try {
      const copyList = await getOrderCopyList(orderId)
      await navigator.clipboard.writeText(copyList.formatted_text)
      setCopyStatus((prev) => ({ ...prev, [orderId]: true }))
      setTimeout(() => {
        setCopyStatus((prev) => ({ ...prev, [orderId]: false }))
      }, 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
    }
  }

  const totalItems = orders.reduce((sum, o) => sum + o.lines.length, 0)
  const totalCents = orders.reduce((sum, o) => sum + o.subtotal_cents, 0)

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Orders Created
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            {orders.length} orders with {totalItems} items ({formatPrice(totalCents)} total)
          </p>

          {orders.map((order) => (
            <Card key={order.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="font-medium">{order.distributor_name}</h4>
                    <p className="text-sm text-gray-500">
                      {order.lines.length} items - {formatPrice(order.subtotal_cents)}
                      {order.expected_delivery && (
                        <span className="ml-2">
                          Expected: {formatDate(order.expected_delivery)}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopyList(order.id)}
                    >
                      {copyStatus[order.id] ? (
                        <Check className="h-4 w-4 mr-2 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4 mr-2" />
                      )}
                      Copy List
                    </Button>
                    <Button variant="outline" size="sm" disabled>
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Pre-fill Cart
                    </Button>
                  </div>
                </div>

                <div className="text-sm space-y-1 max-h-40 overflow-y-auto">
                  {order.lines.map((line) => (
                    <div
                      key={line.assignment_id}
                      className="flex justify-between py-1 border-b border-gray-100 last:border-0"
                    >
                      <span className="truncate flex-1">
                        {line.sku && <span className="text-gray-400 mr-2">{line.sku}</span>}
                        {line.description}
                      </span>
                      <span className="ml-4 shrink-0">
                        {line.quantity} x {formatPrice(line.unit_price_cents)}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <DialogFooter>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
