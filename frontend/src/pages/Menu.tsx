import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMenuAnalysis } from '@/lib/api'
import type { MenuItemAnalysis } from '@/types/recipe'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowUpDown, AlertTriangle, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'

type SortKey = 'name' | 'category' | 'menu_price_cents' | 'total_cost_cents' | 'food_cost_percent' | 'gross_margin_cents'
type SortDir = 'asc' | 'desc'

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

function statusColor(status: string) {
  switch (status) {
    case 'healthy': return 'bg-green-50 text-green-700 border-green-200'
    case 'warning': return 'bg-yellow-50 text-yellow-700 border-yellow-200'
    case 'danger': return 'bg-red-50 text-red-700 border-red-200'
    default: return 'bg-gray-50 text-gray-700 border-gray-200'
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'healthy': return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-300">Healthy</Badge>
    case 'warning': return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-300">Warning</Badge>
    case 'danger': return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-300">Danger</Badge>
    default: return null
  }
}

export function Menu() {
  const [sortKey, setSortKey] = useState<SortKey>('food_cost_percent')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [filterCategory, setFilterCategory] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['menu-analysis'],
    queryFn: () => getMenuAnalysis(),
  })

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir(key === 'name' ? 'asc' : 'desc')
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/3" />
          <div className="h-64 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-5xl mx-auto">
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-500">Failed to load menu data</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const categories = Object.keys(data.summary.by_category).sort()

  let items = [...data.items]

  // Filter
  if (filterCategory) {
    items = items.filter(i => i.category === filterCategory)
  }
  if (filterStatus) {
    items = items.filter(i => i.margin_status === filterStatus)
  }

  // Sort
  items.sort((a, b) => {
    const valA = a[sortKey] ?? ''
    const valB = b[sortKey] ?? ''
    const cmp = valA < valB ? -1 : valA > valB ? 1 : 0
    return sortDir === 'asc' ? cmp : -cmp
  })

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      className="py-2 pr-2 text-left text-xs text-gray-500 uppercase cursor-pointer hover:text-gray-700 select-none"
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className={cn('h-3 w-3', sortKey === field ? 'text-gray-900' : 'text-gray-300')} />
      </span>
    </th>
  )

  const { summary } = data

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Menu</h1>
          <p className="text-gray-500 text-sm mt-1">{summary.total_items} items</p>
        </div>
        <Link
          to="/menu/analyze"
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
        >
          <BarChart3 className="h-4 w-4" />
          Analyzer
        </Link>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardContent className="py-3 text-center">
            <p className="text-2xl font-bold text-gray-900">{summary.avg_food_cost_percent}%</p>
            <p className="text-xs text-gray-500">Avg Food Cost</p>
          </CardContent>
        </Card>
        <Card className="border-green-200">
          <CardContent className="py-3 text-center">
            <p className="text-2xl font-bold text-green-600">{summary.healthy_count}</p>
            <p className="text-xs text-gray-500">Healthy (&lt;30%)</p>
          </CardContent>
        </Card>
        <Card className="border-yellow-200">
          <CardContent className="py-3 text-center">
            <p className="text-2xl font-bold text-yellow-600">{summary.warning_count}</p>
            <p className="text-xs text-gray-500">Warning (30-35%)</p>
          </CardContent>
        </Card>
        <Card className="border-red-200">
          <CardContent className="py-3 text-center">
            <p className="text-2xl font-bold text-red-600">{summary.danger_count}</p>
            <p className="text-xs text-gray-500">Danger (&gt;35%)</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={filterCategory}
          onChange={e => setFilterCategory(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5 bg-white"
        >
          <option value="">All Categories</option>
          {categories.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="text-sm border rounded-lg px-3 py-1.5 bg-white"
        >
          <option value="">All Status</option>
          <option value="healthy">Healthy</option>
          <option value="warning">Warning</option>
          <option value="danger">Danger</option>
        </select>
        {(filterCategory || filterStatus) && (
          <button
            onClick={() => { setFilterCategory(''); setFilterStatus('') }}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="py-0 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <SortHeader label="Name" field="name" />
                <SortHeader label="Category" field="category" />
                <SortHeader label="Menu Price" field="menu_price_cents" />
                <SortHeader label="Food Cost" field="total_cost_cents" />
                <SortHeader label="Food Cost %" field="food_cost_percent" />
                <SortHeader label="Margin" field="gross_margin_cents" />
                <th className="py-2 pr-2 text-left text-xs text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item: MenuItemAnalysis) => (
                <tr
                  key={item.id}
                  className={cn(
                    'text-sm hover:bg-gray-50 transition-colors',
                    item.margin_status === 'danger' && 'bg-red-50/50',
                    item.margin_status === 'warning' && 'bg-yellow-50/30',
                  )}
                >
                  <td className="py-2.5 pr-2">
                    <Link
                      to={`/menu/${item.id}`}
                      className="text-gray-900 hover:text-blue-600 hover:underline font-medium"
                    >
                      {item.name}
                    </Link>
                    {item.has_unpriced_ingredients && (
                      <AlertTriangle className="inline h-3.5 w-3.5 ml-1 text-yellow-500" />
                    )}
                  </td>
                  <td className="py-2.5 pr-2 text-gray-500 text-xs capitalize">{item.category || '-'}</td>
                  <td className="py-2.5 pr-2 tabular-nums text-gray-700">{formatPrice(item.menu_price_cents)}</td>
                  <td className="py-2.5 pr-2 tabular-nums text-gray-700">{formatPrice(item.total_cost_cents)}</td>
                  <td className={cn(
                    'py-2.5 pr-2 tabular-nums font-medium',
                    item.margin_status === 'healthy' && 'text-green-600',
                    item.margin_status === 'warning' && 'text-yellow-600',
                    item.margin_status === 'danger' && 'text-red-600',
                  )}>
                    {Number(item.food_cost_percent).toFixed(1)}%
                  </td>
                  <td className="py-2.5 pr-2 tabular-nums text-gray-700">{formatPrice(item.gross_margin_cents)}</td>
                  <td className="py-2.5 pr-2">
                    {statusBadge(item.margin_status)}
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-400">
                    No menu items found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
