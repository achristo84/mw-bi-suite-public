import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, ChevronRight, AlertCircle } from 'lucide-react'
import { getInvoices, getDistributors } from '@/lib/api'
import { formatCents, formatDate, formatConfidence } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ReviewStatus } from '@/types/invoice'

export function InvoiceList() {
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | 'all'>('all')

  const { data: invoicesData, isLoading, error } = useQuery({
    queryKey: ['invoices', statusFilter],
    queryFn: () => getInvoices({ status: statusFilter, limit: 50 }),
  })

  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  const distributorMap = new Map(distributors?.map(d => [d.id, d]) || [])

  const getConfidenceBadge = (confidence: number | null) => {
    if (confidence === null) return <Badge variant="outline">-</Badge>
    if (confidence >= 0.9) return <Badge variant="success">{formatConfidence(confidence)}</Badge>
    if (confidence >= 0.7) return <Badge variant="warning">{formatConfidence(confidence)}</Badge>
    return <Badge variant="destructive">{formatConfidence(confidence)}</Badge>
  }

  const getStatusBadge = (invoice: { review_status: string; paid_at: string | null }) => {
    if (invoice.paid_at) return <Badge variant="success">Paid</Badge>
    if (invoice.review_status === 'approved') return <Badge variant="secondary">Approved</Badge>
    if (invoice.review_status === 'rejected') return <Badge variant="destructive">Rejected</Badge>
    return <Badge variant="outline">Pending Review</Badge>
  }

  if (error) {
    return (
      <div className="p-6">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-red-800">Failed to load invoices: {(error as Error).message}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
          <p className="text-gray-500 mt-1">Review and approve parsed invoices</p>
        </div>
        <Link to="/upload">
          <Button>Upload Invoice</Button>
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {(['pending', 'approved', 'all'] as const).map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(status)}
            className="capitalize"
          >
            {status === 'all' ? 'All' : status}
          </Button>
        ))}
      </div>

      {/* Invoice list */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">
            {isLoading ? 'Loading...' : `${invoicesData?.total || 0} invoices`}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading invoices...</div>
          ) : invoicesData?.invoices.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No invoices found
            </div>
          ) : (
            <ul className="divide-y">
              {invoicesData?.invoices.map((invoice) => {
                const distributor = distributorMap.get(invoice.distributor_id)
                return (
                  <li key={invoice.id}>
                    <Link
                      to={`/invoices/${invoice.id}`}
                      className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="flex-shrink-0 w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                          <FileText className="h-5 w-5 text-gray-600" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-900 truncate">
                              {distributor?.name || 'Unknown'}
                            </p>
                            <span className="text-gray-400">#{invoice.invoice_number}</span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                            <span>{formatDate(invoice.invoice_date)}</span>
                            <span className="font-medium text-gray-900">
                              {formatCents(invoice.total_cents)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                        {getConfidenceBadge(invoice.parse_confidence)}
                        {getStatusBadge(invoice)}
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      </div>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
