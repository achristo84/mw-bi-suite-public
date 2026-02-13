import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragStartEvent, DragEndEvent } from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  getOrderBuilderSummary,
  getOrderListItems,
  updateAssignment,
  deleteAssignment,
  finalizeOrders,
  getOrderCopyList,
} from '@/lib/api'
import type {
  DistributorCart,
  CartItem,
  OrderWithDetails,
  OrderListItemWithDetails,
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
  GripVertical,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { StatusDot } from '@/components/ListItemBadge'

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

export function CartBuilder() {
  const queryClient = useQueryClient()
  const [isOutputModalOpen, setIsOutputModalOpen] = useState(false)
  const [selectedOrders, setSelectedOrders] = useState<OrderWithDetails[]>([])
  const [activeItem, setActiveItem] = useState<CartItem | OrderListItemWithDetails | null>(null)
  const [hoveredItem, setHoveredItem] = useState<CartItem | null>(null)

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor)
  )

  // Fetch cart summary
  const { data, isLoading, error } = useQuery({
    queryKey: ['order-builder-summary'],
    queryFn: getOrderBuilderSummary,
  })

  // Fetch pending items (unassigned)
  const { data: listData } = useQuery({
    queryKey: ['order-list', 'pending'],
    queryFn: () => getOrderListItems('pending'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAssignment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['order-builder-summary'] })
      queryClient.invalidateQueries({ queryKey: ['order-list'] })
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

  // DnD handlers
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event
    // Find the item being dragged
    const allItems = data?.carts.flatMap((c) => c.items) || []
    const cartItem = allItems.find((item) => item.assignment_id === active.id)
    if (cartItem) {
      setActiveItem(cartItem)
    }
  }

  const handleDragEnd = (_event: DragEndEvent) => {
    setActiveItem(null)
    // For now, drag-drop between columns is not implemented
    // This would require API changes to move assignments between distributors
  }

  const carts = data?.carts || []
  const totalItems = data?.total_items || 0
  const totalCents = data?.total_cents || 0
  const readyCount = data?.ready_to_order || 0

  // Get unassigned items
  const allAssignedItemIds = new Set(
    carts.flatMap((c) => c.items.map((i) => i.order_list_item_id))
  )
  const unassignedItems = (listData?.items || []).filter(
    (item) => item.status === 'pending' && !allAssignedItemIds.has(item.id)
  )

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
          <Link to="/orders">
            <Button variant="outline">
              <Search className="h-4 w-4 mr-2" />
              Search & Order
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

      {/* Main content - multi-column layout */}
      {!isLoading && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 overflow-x-auto pb-4">
            {/* Unassigned Items Column */}
            <div className="w-64 shrink-0">
              <Card className="h-full">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <ClipboardList className="h-5 w-5" />
                    Items to Assign
                  </CardTitle>
                  <p className="text-sm text-gray-500">
                    {unassignedItems.length} unassigned
                  </p>
                </CardHeader>
                <CardContent>
                  {unassignedItems.length === 0 ? (
                    <div className="text-center py-8 text-gray-500 text-sm">
                      <Package className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                      All items assigned
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {unassignedItems.map((item) => (
                        <UnassignedItemCard
                          key={item.id}
                          item={item}
                        />
                      ))}
                    </div>
                  )}

                  <div className="mt-4 pt-4 border-t">
                    <Link to="/orders">
                      <Button variant="outline" size="sm" className="w-full">
                        <Search className="h-4 w-4 mr-2" />
                        Add via Search
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Empty state */}
            {carts.length === 0 && (
              <div className="flex-1 flex items-center justify-center">
                <Card className="w-96">
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <ShoppingCart className="h-12 w-12 text-gray-300 mb-4" />
                    <h3 className="text-lg font-medium text-gray-900">No items in carts</h3>
                    <p className="text-sm text-gray-500 mt-1 text-center">
                      Search for items and add them to carts
                    </p>
                    <Link to="/orders">
                      <Button className="mt-4">
                        <Search className="h-4 w-4 mr-2" />
                        Search & Order
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Distributor Carts */}
            {carts.map((cart) => (
              <DistributorColumn
                key={cart.distributor_id}
                cart={cart}
                onDeleteItem={handleDeleteItem}
                onUpdateQuantity={handleUpdateQuantity}
                onFinalize={() => handleFinalize([cart.distributor_id])}
                isDeleting={deleteMutation.isPending}
                isFinalizing={finalizeMutation.isPending}
                hoveredItem={hoveredItem}
                onHoverItem={setHoveredItem}
              />
            ))}
          </div>

          {/* Drag overlay */}
          <DragOverlay>
            {activeItem && 'assignment_id' in activeItem && (
              <div className="bg-white border rounded-lg p-2 shadow-lg opacity-90">
                <p className="font-medium text-sm">{activeItem.order_list_item_name}</p>
                <p className="text-xs text-gray-500">{activeItem.description}</p>
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {/* Order Output Modal */}
      <OrderOutputModal
        open={isOutputModalOpen}
        onClose={() => setIsOutputModalOpen(false)}
        orders={selectedOrders}
      />

      {/* Price Comparison Tooltip */}
      {hoveredItem && (
        <PriceComparisonTooltip item={hoveredItem} allCarts={carts} />
      )}
    </div>
  )
}

// Unassigned Item Card
function UnassignedItemCard({ item }: { item: OrderListItemWithDetails }) {
  return (
    <Link to={`/orders?search=${encodeURIComponent(item.name)}`}>
      <div className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 hover:bg-gray-100 cursor-pointer transition-colors">
        <StatusDot item={item} />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{item.name}</p>
          {item.quantity && (
            <p className="text-xs text-gray-500">{item.quantity}</p>
          )}
        </div>
      </div>
    </Link>
  )
}

// Distributor Column
function DistributorColumn({
  cart,
  onDeleteItem,
  onUpdateQuantity,
  onFinalize,
  isDeleting,
  isFinalizing,
  hoveredItem,
  onHoverItem,
}: {
  cart: DistributorCart
  onDeleteItem: (assignmentId: string) => void
  onUpdateQuantity: (assignmentId: string, quantity: number) => void
  onFinalize: () => void
  isDeleting: boolean
  isFinalizing: boolean
  hoveredItem: CartItem | null
  onHoverItem: (item: CartItem | null) => void
}) {
  const progressPercent = cart.minimum_order_cents > 0
    ? Math.min(100, (cart.subtotal_cents / cart.minimum_order_cents) * 100)
    : 100

  return (
    <div className="w-72 shrink-0">
      <Card
        className={cn(
          'h-full flex flex-col',
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

          {/* Subtotal */}
          <div className="text-2xl font-semibold">{formatPrice(cart.subtotal_cents)}</div>

          {/* Minimum Progress */}
          {cart.minimum_order_cents > 0 && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">
                  Min: {formatPrice(cart.minimum_order_cents)}
                </span>
                <span
                  className={cn(
                    cart.meets_minimum ? 'text-green-600' : 'text-yellow-600'
                  )}
                >
                  {cart.meets_minimum ? '✓' : `${formatPrice(cart.minimum_order_cents - cart.subtotal_cents)} needed`}
                </span>
              </div>
              <Progress
                value={progressPercent}
                className={cn(
                  'h-1.5',
                  cart.meets_minimum ? '[&>div]:bg-green-500' : '[&>div]:bg-yellow-500'
                )}
              />
            </div>
          )}

          {/* Delivery info */}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            {cart.delivery_days && (
              <span className="flex items-center gap-1">
                <Truck className="h-3 w-3" />
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
          <SortableContext
            items={cart.items.map((i) => i.assignment_id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="flex-1 space-y-2">
              {cart.items.map((item) => (
                <SortableCartItem
                  key={item.assignment_id}
                  item={item}
                  onDelete={() => onDeleteItem(item.assignment_id)}
                  onUpdateQuantity={(qty) => onUpdateQuantity(item.assignment_id, qty)}
                  isDeleting={isDeleting}
                  isHovered={hoveredItem?.assignment_id === item.assignment_id}
                  onHover={() => onHoverItem(item)}
                  onHoverEnd={() => onHoverItem(null)}
                />
              ))}
            </div>
          </SortableContext>

          {/* Footer */}
          <div className="border-t pt-4 mt-4">
            <Button
              size="sm"
              variant={cart.meets_minimum ? 'default' : 'outline'}
              className="w-full"
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
    </div>
  )
}

// Sortable Cart Item
function SortableCartItem({
  item,
  onDelete,
  onUpdateQuantity,
  isDeleting,
  isHovered,
  onHover,
  onHoverEnd,
}: {
  item: CartItem
  onDelete: () => void
  onUpdateQuantity: (qty: number) => void
  isDeleting: boolean
  isHovered: boolean
  onHover: () => void
  onHoverEnd: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.assignment_id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

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
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center gap-2 p-2 rounded-lg bg-gray-50 group',
        isHovered && 'ring-2 ring-blue-300 bg-blue-50'
      )}
      onMouseEnter={onHover}
      onMouseLeave={onHoverEnd}
    >
      {/* Drag handle */}
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab text-gray-400 hover:text-gray-600"
      >
        <GripVertical className="h-4 w-4" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">
          {item.order_list_item_name}
        </p>
        <p className="text-xs text-gray-500 truncate">
          {item.sku && `${item.sku} - `}
          {item.description}
        </p>
      </div>

      {/* Quantity */}
      <Input
        type="number"
        min="1"
        value={editQuantity}
        onChange={(e) => setEditQuantity(e.target.value)}
        onBlur={handleQuantityBlur}
        className="w-12 h-7 text-center text-xs"
      />

      {/* Price */}
      <div className="text-right w-16">
        <p className="font-medium text-sm">
          {formatPrice(item.extended_price_cents)}
        </p>
      </div>

      {/* Delete */}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"
        onClick={onDelete}
        disabled={isDeleting}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  )
}

// Price Comparison Tooltip
function PriceComparisonTooltip({
  item,
  allCarts,
}: {
  item: CartItem
  allCarts: DistributorCart[]
}) {
  // This would ideally fetch prices from other distributors
  // For now, just show the current item info
  const currentCart = allCarts.find((c) =>
    c.items.some((i) => i.assignment_id === item.assignment_id)
  )

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-white border rounded-lg shadow-lg p-4 w-72">
      <h4 className="font-medium text-sm mb-2">
        {item.order_list_item_name} @ {currentCart?.distributor_name}
      </h4>
      <p className="text-lg font-semibold">{formatPrice(item.unit_price_cents)}</p>
      <p className="text-xs text-gray-500">{item.description}</p>
      <hr className="my-2" />
      <p className="text-xs text-gray-400">
        Hover over items to see price comparison
        <br />
        (Full comparison coming soon)
      </p>
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
