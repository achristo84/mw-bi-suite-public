import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Pencil, Trash2, Check, X, Loader2, Zap, ZapOff, ShoppingCart } from 'lucide-react'
import { getDistributors, createDistributor, updateDistributor, deleteDistributor } from '@/lib/api'
import type { Distributor } from '@/types/invoice'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'

export function Settings() {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)

  const { data: distributors, isLoading } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Manage distributors and system configuration</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                Distributors
              </CardTitle>
              <CardDescription>
                Manage your distributors and their settings
              </CardDescription>
            </div>
            <Button onClick={() => setShowAddForm(true)} disabled={showAddForm}>
              <Plus className="h-4 w-4 mr-2" />
              Add Distributor
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Add Form */}
          {showAddForm && (
            <DistributorForm
              onSave={() => {
                setShowAddForm(false)
                queryClient.invalidateQueries({ queryKey: ['distributors'] })
              }}
              onCancel={() => setShowAddForm(false)}
            />
          )}

          {/* Distributor List */}
          {isLoading ? (
            <p className="text-gray-500 py-4">Loading...</p>
          ) : distributors?.length === 0 ? (
            <p className="text-gray-500 py-4">No distributors configured</p>
          ) : (
            <div className="divide-y border rounded-lg">
              {distributors?.map((distributor) => (
                <div key={distributor.id}>
                  {editingId === distributor.id ? (
                    <DistributorForm
                      distributor={distributor}
                      onSave={() => {
                        setEditingId(null)
                        queryClient.invalidateQueries({ queryKey: ['distributors'] })
                      }}
                      onCancel={() => setEditingId(null)}
                    />
                  ) : (
                    <DistributorRow
                      distributor={distributor}
                      onEdit={() => setEditingId(distributor.id)}
                      onToggleScraping={() => {
                        updateDistributor(distributor.id, {
                          scraping_enabled: !distributor.scraping_enabled,
                        }).then(() => {
                          queryClient.invalidateQueries({ queryKey: ['distributors'] })
                        })
                      }}
                      onToggleOrdering={() => {
                        updateDistributor(distributor.id, {
                          ordering_enabled: !distributor.ordering_enabled,
                        }).then(() => {
                          queryClient.invalidateQueries({ queryKey: ['distributors'] })
                        })
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// Distributor Row Component
function DistributorRow({
  distributor,
  onEdit,
  onToggleScraping,
  onToggleOrdering,
}: {
  distributor: Distributor
  onEdit: () => void
  onToggleScraping: () => void
  onToggleOrdering: () => void
}) {
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: () => deleteDistributor(distributor.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['distributors'] })
    },
  })

  return (
    <div className="p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-gray-900">{distributor.name}</p>
            {!distributor.is_active && (
              <Badge variant="secondary">Inactive</Badge>
            )}
          </div>
          <div className="mt-1 text-sm text-gray-500 space-y-0.5">
            {distributor.invoice_email && (
              <p>Invoice email: {distributor.invoice_email}</p>
            )}
            {distributor.filename_pattern && (
              <p className="font-mono text-xs">Pattern: {distributor.filename_pattern}</p>
            )}
            {distributor.last_successful_scrape && (
              <p>Last scrape: {new Date(distributor.last_successful_scrape).toLocaleDateString()}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 ml-4">
          {/* Ordering Toggle */}
          <button
            onClick={onToggleOrdering}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              distributor.ordering_enabled
                ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            title={distributor.ordering_enabled ? 'Order Hub enabled' : 'Order Hub disabled'}
          >
            <ShoppingCart className="h-3.5 w-3.5" />
            {distributor.ordering_enabled ? 'Order Hub' : 'No Orders'}
          </button>

          {/* Scraping Toggle */}
          <button
            onClick={onToggleScraping}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              distributor.scraping_enabled
                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            title={distributor.scraping_enabled ? 'Scraping enabled' : 'Scraping disabled'}
          >
            {distributor.scraping_enabled ? (
              <>
                <Zap className="h-3.5 w-3.5" />
                Scraping On
              </>
            ) : (
              <>
                <ZapOff className="h-3.5 w-3.5" />
                Scraping Off
              </>
            )}
          </button>

          {/* Edit Button */}
          <Button variant="ghost" size="sm" onClick={onEdit}>
            <Pencil className="h-4 w-4" />
          </Button>

          {/* Delete Button */}
          {showDeleteConfirm ? (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDeleteConfirm(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
              className="text-gray-400 hover:text-red-600"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// Distributor Form Component
function DistributorForm({
  distributor,
  onSave,
  onCancel,
}: {
  distributor?: Distributor
  onSave: () => void
  onCancel: () => void
}) {
  const [name, setName] = useState(distributor?.name || '')
  const [invoiceEmail, setInvoiceEmail] = useState(distributor?.invoice_email || '')
  const [filenamePattern, setFilenamePattern] = useState(distributor?.filename_pattern || '')
  const [scrapingEnabled, setScrapingEnabled] = useState(distributor?.scraping_enabled || false)
  const [orderingEnabled, setOrderingEnabled] = useState(distributor?.ordering_enabled || false)
  const [notes, setNotes] = useState(distributor?.notes || '')
  const [error, setError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      createDistributor({
        name,
        invoice_email: invoiceEmail || undefined,
        filename_pattern: filenamePattern || undefined,
        scraping_enabled: scrapingEnabled,
        ordering_enabled: orderingEnabled,
        notes: notes || undefined,
      }),
    onSuccess: onSave,
    onError: (err: Error) => setError(err.message),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      updateDistributor(distributor!.id, {
        name,
        invoice_email: invoiceEmail || undefined,
        filename_pattern: filenamePattern || undefined,
        scraping_enabled: scrapingEnabled,
        ordering_enabled: orderingEnabled,
        notes: notes || undefined,
      }),
    onSuccess: onSave,
    onError: (err: Error) => setError(err.message),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    if (distributor) {
      updateMutation.mutate()
    } else {
      createMutation.mutate()
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <form onSubmit={handleSubmit} className="p-4 bg-gray-50 rounded-lg space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="name">Name *</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Amazon"
            className="mt-1"
            autoFocus
          />
        </div>
        <div>
          <Label htmlFor="invoiceEmail">Invoice Email</Label>
          <Input
            id="invoiceEmail"
            type="email"
            value={invoiceEmail}
            onChange={(e) => setInvoiceEmail(e.target.value)}
            placeholder="invoices@example.com"
            className="mt-1"
          />
        </div>
      </div>

      <div>
        <Label htmlFor="filenamePattern">Filename Pattern (regex)</Label>
        <Input
          id="filenamePattern"
          value={filenamePattern}
          onChange={(e) => setFilenamePattern(e.target.value)}
          placeholder="e.g., amazon.*invoice"
          className="mt-1 font-mono text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">
          Used to match invoice files from email attachments
        </p>
      </div>

      <div>
        <Label htmlFor="notes">Notes</Label>
        <Input
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional notes..."
          className="mt-1"
        />
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="scrapingEnabled"
            checked={scrapingEnabled}
            onChange={(e) => setScrapingEnabled(e.target.checked)}
            className="h-4 w-4 rounded"
          />
          <Label htmlFor="scrapingEnabled" className="cursor-pointer">
            Enable automatic scraping
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="orderingEnabled"
            checked={orderingEnabled}
            onChange={(e) => setOrderingEnabled(e.target.checked)}
            className="h-4 w-4 rounded"
          />
          <Label htmlFor="orderingEnabled" className="cursor-pointer">
            Enable for Order Hub
          </Label>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : null}
          {distributor ? 'Save Changes' : 'Add Distributor'}
        </Button>
      </div>
    </form>
  )
}
