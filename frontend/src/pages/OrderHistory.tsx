import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getOrders, getDistributors } from '@/lib/api'
import type { OrderWithDetails } from '@/types/order-hub'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Package,
  Truck,
  Calendar,
  Search,
  Loader2,
  ChevronDown,
  ChevronRight,
  ShoppingCart,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Format price
function formatPrice(cents: number | null): string {
  if (cents === null || cents === 0) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

// Format date
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// Status badge
function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
    draft: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Draft' },
    submitted: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Submitted' },
    confirmed: { bg: 'bg-green-100', text: 'text-green-700', label: 'Confirmed' },
    delivered: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Delivered' },
    invoiced: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Invoiced' },
  }

  const config = statusConfig[status] || statusConfig.draft

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        config.bg,
        config.text
      )}
    >
      {config.label}
    </span>
  )
}

export function OrderHistory() {
  const [distributorFilter, setDistributorFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [expandedOrders, setExpandedOrders] = useState<Set<string>>(new Set())

  // Fetch orders
  const { data: orders, isLoading, error } = useQuery({
    queryKey: ['orders', statusFilter === 'all' ? undefined : statusFilter],
    queryFn: () => getOrders(statusFilter === 'all' ? undefined : statusFilter),
  })

  // Fetch distributors for filter
  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  // Filter orders
  const filteredOrders = (orders || []).filter((order) => {
    if (distributorFilter !== 'all' && order.distributor_id !== distributorFilter) {
      return false
    }
    return true
  })

  // Group orders by date
  const ordersByDate = filteredOrders.reduce(
    (acc, order) => {
      const date = order.submitted_at
        ? new Date(order.submitted_at).toDateString()
        : order.created_at
          ? new Date(order.created_at).toDateString()
          : 'Unknown'

      if (!acc[date]) {
        acc[date] = []
      }
      acc[date].push(order)
      return acc
    },
    {} as Record<string, OrderWithDetails[]>
  )

  // Toggle order expansion
  const toggleOrder = (orderId: string) => {
    setExpandedOrders((prev) => {
      const next = new Set(prev)
      if (next.has(orderId)) {
        next.delete(orderId)
      } else {
        next.add(orderId)
      }
      return next
    })
  }

  // Calculate totals
  const totalOrders = filteredOrders.length
  const totalSpent = filteredOrders.reduce((sum, o) => sum + o.subtotal_cents, 0)

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">Failed to load order history. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Order History</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {totalOrders} orders - {formatPrice(totalSpent)} total
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/orders">
            <Button variant="outline">
              <Search className="h-4 w-4 mr-2" />
              New Order
            </Button>
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="flex items-center gap-2">
          <Truck className="h-4 w-4 text-gray-500" />
          <select
            value={distributorFilter}
            onChange={(e) => setDistributorFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-48"
          >
            <option value="all">All Distributors</option>
            {distributors?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <Package className="h-4 w-4 text-gray-500" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
          >
            <option value="all">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="confirmed">Confirmed</option>
            <option value="delivered">Delivered</option>
            <option value="invoiced">Invoiced</option>
          </select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredOrders.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShoppingCart className="h-12 w-12 text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No orders yet</h3>
            <p className="text-sm text-gray-500 mt-1">
              Orders will appear here once you finalize them
            </p>
            <Link to="/orders">
              <Button className="mt-4">
                <Search className="h-4 w-4 mr-2" />
                Create Order
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Orders grouped by date */}
      {Object.entries(ordersByDate)
        .sort(([a], [b]) => new Date(b).getTime() - new Date(a).getTime())
        .map(([date, dateOrders]) => (
          <div key={date} className="space-y-3">
            <h2 className="text-sm font-medium text-gray-500 flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              {date}
            </h2>

            <div className="space-y-2">
              {dateOrders.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  isExpanded={expandedOrders.has(order.id)}
                  onToggle={() => toggleOrder(order.id)}
                />
              ))}
            </div>
          </div>
        ))}
    </div>
  )
}

// Order Card Component
function OrderCard({
  order,
  isExpanded,
  onToggle,
}: {
  order: OrderWithDetails
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <Card>
      <CardContent className="py-4">
        {/* Header Row */}
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={onToggle}
        >
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="h-6 w-6">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-medium">{order.distributor_name}</h3>
                <StatusBadge status={order.status} />
              </div>
              <p className="text-sm text-gray-500">
                {order.lines.length} items
                {order.confirmation_number && (
                  <span className="ml-2">
                    Conf# {order.confirmation_number}
                  </span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {order.expected_delivery && (
              <div className="text-sm text-gray-500 flex items-center gap-1">
                <Truck className="h-4 w-4" />
                {formatDate(order.expected_delivery)}
              </div>
            )}
            <div className="text-right">
              <p className="font-semibold text-lg">
                {formatPrice(order.subtotal_cents)}
              </p>
            </div>
          </div>
        </div>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="pb-2 font-medium">SKU</th>
                  <th className="pb-2 font-medium">Description</th>
                  <th className="pb-2 font-medium text-center">Qty</th>
                  <th className="pb-2 font-medium text-right">Unit Price</th>
                  <th className="pb-2 font-medium text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {order.lines.map((line) => (
                  <tr key={line.assignment_id}>
                    <td className="py-2 text-gray-600">{line.sku || '-'}</td>
                    <td className="py-2">{line.description}</td>
                    <td className="py-2 text-center">{line.quantity}</td>
                    <td className="py-2 text-right">
                      {formatPrice(line.unit_price_cents)}
                    </td>
                    <td className="py-2 text-right font-medium">
                      {formatPrice(line.extended_price_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t">
                  <td colSpan={4} className="pt-2 text-right font-medium">
                    Subtotal:
                  </td>
                  <td className="pt-2 text-right font-semibold">
                    {formatPrice(order.subtotal_cents)}
                  </td>
                </tr>
              </tfoot>
            </table>

            {order.notes && (
              <div className="mt-4 p-3 bg-gray-50 rounded-lg text-sm">
                <span className="font-medium">Notes: </span>
                {order.notes}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
