import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, X, FileText, AlertCircle, Loader2, ExternalLink, Trash2, RefreshCw } from 'lucide-react'
import { getInvoice, approveInvoice, rejectInvoice, deleteInvoice, getInvoicePdfUrl, getDistributors, updateInvoiceLine, getIngredients, mapInvoiceLine, confirmInvoiceLine, removeInvoiceLine, resetInvoiceLineStatus, reparseInvoiceWithPrompt } from '@/lib/api'
import { formatCents, formatDate, formatConfidence, cn } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PromptEditorModal } from '@/components/PromptEditorModal'
import { InvoiceLineEditor } from '@/components/invoice-review/InvoiceLineEditor'
import { InvoiceLineMapper } from '@/components/invoice-review/InvoiceLineMapper'
import { InvoiceLineView } from '@/components/invoice-review/InvoiceLineView'
import type { InvoiceLine, PromptContentType } from '@/types/invoice'
import type { EditValues } from '@/components/invoice-review/InvoiceLineEditor'

export function InvoiceReview() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [editingLineId, setEditingLineId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<EditValues>({ quantity: '', unit: '', unit_price_cents: '', extended_price_cents: '' })
  const [mappingLineId, setMappingLineId] = useState<string | null>(null)
  const [ingredientSearch, setIngredientSearch] = useState('')
  const [mappedIngredients, setMappedIngredients] = useState<Record<string, string>>({})
  const [actionError, setActionError] = useState<string | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showPromptEditor, setShowPromptEditor] = useState(false)

  const { data: invoice, isLoading, error } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => getInvoice(id!),
    enabled: !!id,
  })

  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  const { data: ingredientsData } = useQuery({
    queryKey: ['ingredients-search', ingredientSearch],
    queryFn: () => getIngredients({ search: ingredientSearch || undefined }),
    enabled: mappingLineId !== null,
  })

  const approveMutation = useMutation({
    mutationFn: () => approveInvoice(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: () => rejectInvoice(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate('/')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteInvoice(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate('/')
    },
    onError: (err: Error) => {
      setActionError(err.message || 'Failed to delete invoice')
      setShowDeleteConfirm(false)
    },
  })

  const confirmLineMutation = useMutation({
    mutationFn: (lineId: string) => confirmInvoiceLine(id!, lineId),
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    },
    onError: (err: Error) => setActionError(err.message || 'Failed to confirm line'),
  })

  const removeLineMutation = useMutation({
    mutationFn: (lineId: string) => removeInvoiceLine(id!, lineId),
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    },
    onError: (err: Error) => setActionError(err.message || 'Failed to remove line'),
  })

  const resetLineStatusMutation = useMutation({
    mutationFn: (lineId: string) => resetInvoiceLineStatus(id!, lineId),
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    },
    onError: (err: Error) => setActionError(err.message || 'Failed to reset line status'),
  })

  const updateLineMutation = useMutation({
    mutationFn: ({ lineId, data }: { lineId: string; data: Parameters<typeof updateInvoiceLine>[2] }) =>
      updateInvoiceLine(id!, lineId, data),
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      setEditingLineId(null)
    },
    onError: (err: Error) => setActionError(err.message || 'Failed to update line'),
  })

  const mapLineMutation = useMutation({
    mutationFn: ({ lineId, ingredientId }: { lineId: string; ingredientId: string }) =>
      mapInvoiceLine(id!, lineId, ingredientId),
    onSuccess: (result, variables) => {
      setActionError(null)
      setMappedIngredients(prev => ({
        ...prev,
        [variables.lineId]: result.ingredient_name,
      }))
      setMappingLineId(null)
      setIngredientSearch('')
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
    },
    onError: (err: Error) => setActionError(err.message || 'Failed to map ingredient'),
  })

  const distributor = distributors?.find(d => d.id === invoice?.distributor_id)
  const pdfUrl = invoice ? getInvoicePdfUrl(invoice) : null
  const isReviewed = !!invoice?.reviewed_at
  const isPending = approveMutation.isPending || rejectMutation.isPending || deleteMutation.isPending
  const isImage = invoice?.pdf_path && /\.(png|jpg|jpeg|gif|webp)$/i.test(invoice.pdf_path)

  const startEditing = (line: InvoiceLine) => {
    setMappingLineId(null)
    setEditingLineId(line.id)
    setEditValues({
      quantity: line.quantity?.toString() || '',
      unit: line.unit || '',
      unit_price_cents: line.unit_price_cents ? (line.unit_price_cents / 100).toFixed(2) : '',
      extended_price_cents: line.extended_price_cents ? (line.extended_price_cents / 100).toFixed(2) : '',
    })
  }

  const cancelEditing = () => {
    setEditingLineId(null)
    setEditValues({ quantity: '', unit: '', unit_price_cents: '', extended_price_cents: '' })
  }

  const saveEditing = () => {
    if (!editingLineId) return
    const quantity = parseFloat(editValues.quantity) || 0
    const unitPriceDollars = parseFloat(editValues.unit_price_cents) || 0
    const extendedDollars = parseFloat(editValues.extended_price_cents) || 0
    updateLineMutation.mutate({
      lineId: editingLineId,
      data: {
        quantity,
        unit: editValues.unit || undefined,
        unit_price_cents: Math.round(unitPriceDollars * 100),
        extended_price_cents: Math.round(extendedDollars * 100),
      },
    })
  }

  const startMapping = (lineId: string) => {
    setEditingLineId(null)
    setMappingLineId(lineId)
    setIngredientSearch('')
  }

  const handleQuantityChange = (newQuantity: string) => {
    const qty = parseFloat(newQuantity) || 0
    const extended = parseFloat(editValues.extended_price_cents) || 0
    if (qty > 0 && extended > 0) {
      setEditValues({ ...editValues, quantity: newQuantity, unit_price_cents: (extended / qty).toFixed(2) })
    } else {
      setEditValues({ ...editValues, quantity: newQuantity })
    }
  }

  const handleUnitPriceChange = (newUnitPrice: string) => {
    const qty = parseFloat(editValues.quantity) || 0
    const unitPrice = parseFloat(newUnitPrice) || 0
    setEditValues({ ...editValues, unit_price_cents: newUnitPrice, extended_price_cents: (qty * unitPrice).toFixed(2) })
  }

  const getDisplayedExtended = (): number => {
    return Math.round((parseFloat(editValues.extended_price_cents) || 0) * 100)
  }

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[50vh]">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !invoice) {
    return (
      <div className="p-6">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-red-800">
              {error ? (error as Error).message : 'Invoice not found'}
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const getConfidenceColor = (confidence: number | null) => {
    if (confidence === null) return 'text-gray-500'
    if (confidence >= 0.9) return 'text-green-600'
    if (confidence >= 0.7) return 'text-yellow-600'
    return 'text-red-600'
  }

  const ingredients = ingredientsData?.ingredients || []

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="font-semibold text-gray-900">
                {distributor?.name || 'Unknown'} #{invoice.invoice_number}
              </h1>
              <p className="text-sm text-gray-500">
                {formatDate(invoice.invoice_date)} · {formatCents(invoice.total_cents)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isReviewed && (
              <>
                <Button
                  variant="outline"
                  onClick={() => rejectMutation.mutate()}
                  disabled={isPending}
                >
                  <X className="h-4 w-4 mr-2" />
                  Reject
                </Button>
                <Button
                  onClick={() => approveMutation.mutate()}
                  disabled={isPending}
                >
                  {approveMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4 mr-2" />
                  )}
                  Approve
                </Button>
              </>
            )}
            {isReviewed && (
              <Badge variant="success">Approved {formatDate(invoice.reviewed_at)}</Badge>
            )}
            {invoice.pdf_path && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowPromptEditor(true)}
                disabled={isPending}
                title="Re-parse with custom prompt"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2 bg-red-50 px-3 py-1.5 rounded-lg border border-red-200">
                <span className="text-sm text-red-700">Delete invoice?</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleteMutation.isPending}
                  className="h-7 px-2"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="h-7 px-2"
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    'Delete'
                  )}
                </Button>
              </div>
            ) : (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isPending}
                className="text-gray-400 hover:text-red-600"
                title="Delete invoice"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Content - Side by side on desktop, stacked on mobile */}
      <div className="flex flex-col lg:flex-row lg:h-[calc(100vh-60px)]">
        {/* Document Viewer */}
        <div className="lg:w-1/2 lg:border-r bg-gray-100 min-h-[400px] lg:min-h-0">
          {pdfUrl ? (
            isImage ? (
              <div className="w-full h-full min-h-[500px] lg:min-h-full overflow-auto flex items-start justify-center p-4">
                <img
                  src={pdfUrl}
                  alt="Invoice"
                  className="max-w-full h-auto shadow-lg rounded"
                />
              </div>
            ) : (
              <iframe
                src={pdfUrl}
                className="w-full h-full min-h-[500px] lg:min-h-full"
                title="Invoice PDF"
              />
            )
          ) : (
            <div className="flex flex-col items-center justify-center h-full p-8 text-gray-500">
              <FileText className="h-12 w-12 mb-4" />
              <p>No document available</p>
            </div>
          )}
        </div>

        {/* Invoice Details */}
        <div className="lg:w-1/2 overflow-y-auto p-4 lg:p-6 space-y-4">
          {actionError && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <p className="text-sm text-red-800">{actionError}</p>
                </div>
                <button
                  onClick={() => setActionError(null)}
                  className="text-red-600 hover:text-red-800"
                >
                  <X className="h-4 w-4" />
                </button>
              </CardContent>
            </Card>
          )}

          {/* Confidence indicator */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">Parse Confidence</span>
                <span className={cn('text-lg font-bold', getConfidenceColor(invoice.parse_confidence))}>
                  {formatConfidence(invoice.parse_confidence)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Invoice header info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Invoice Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Invoice #</span>
                  <p className="font-medium">{invoice.invoice_number}</p>
                </div>
                <div>
                  <span className="text-gray-500">Date</span>
                  <p className="font-medium">{formatDate(invoice.invoice_date)}</p>
                </div>
                <div>
                  <span className="text-gray-500">Delivery Date</span>
                  <p className="font-medium">{formatDate(invoice.delivery_date) || '-'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Due Date</span>
                  <p className="font-medium">{formatDate(invoice.due_date) || '-'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Account #</span>
                  <p className="font-medium">{invoice.account_number || '-'}</p>
                </div>
                <div>
                  <span className="text-gray-500">Sales Rep</span>
                  <p className="font-medium">{invoice.sales_rep_name || '-'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Totals */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Totals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Subtotal</span>
                  <span className="font-medium">{formatCents(invoice.subtotal_cents)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tax</span>
                  <span className="font-medium">{formatCents(invoice.tax_cents)}</span>
                </div>
                <div className="flex justify-between pt-2 border-t text-base">
                  <span className="font-medium">Total</span>
                  <span className="font-bold">{formatCents(invoice.total_cents)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Line items */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                Line Items ({invoice.lines?.length || 0})
              </CardTitle>
              <Link
                to="/ingredients/map"
                className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
              >
                Map SKUs <ExternalLink className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent className="p-0">
              {invoice.lines && invoice.lines.length > 0 ? (
                <ul className="divide-y">
                  {invoice.lines.map((line) => (
                    <li key={line.id} className="p-4">
                      {editingLineId === line.id ? (
                        <InvoiceLineEditor
                          line={line}
                          editValues={editValues}
                          isSaving={updateLineMutation.isPending}
                          onQuantityChange={handleQuantityChange}
                          onUnitPriceChange={handleUnitPriceChange}
                          onUnitChange={(value) => setEditValues({ ...editValues, unit: value })}
                          onSave={saveEditing}
                          onCancel={cancelEditing}
                          getDisplayedExtended={getDisplayedExtended}
                        />
                      ) : mappingLineId === line.id ? (
                        <InvoiceLineMapper
                          line={line}
                          ingredientSearch={ingredientSearch}
                          ingredients={ingredients}
                          isMapping={mapLineMutation.isPending}
                          onSearchChange={setIngredientSearch}
                          onMapToIngredient={(ingredientId) =>
                            mapLineMutation.mutate({ lineId: line.id, ingredientId })
                          }
                          onCancel={() => {
                            setMappingLineId(null)
                            setIngredientSearch('')
                          }}
                        />
                      ) : (
                        <InvoiceLineView
                          line={line}
                          mappedIngredientName={mappedIngredients[line.id]}
                          onStartEditing={() => startEditing(line)}
                          onStartMapping={() => startMapping(line.id)}
                          onConfirm={() => confirmLineMutation.mutate(line.id)}
                          onRemove={() => removeLineMutation.mutate(line.id)}
                          onResetStatus={() => resetLineStatusMutation.mutate(line.id)}
                          isConfirming={confirmLineMutation.isPending}
                          isRemoving={removeLineMutation.isPending}
                          isResetting={resetLineStatusMutation.isPending}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-8 text-center text-gray-500">
                  No line items
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Prompt Editor Modal */}
      <PromptEditorModal
        isOpen={showPromptEditor}
        onClose={() => setShowPromptEditor(false)}
        distributorId={invoice.distributor_id}
        contentType={determineContentType(invoice.pdf_path, invoice.source)}
        sourceContent={null}
        sourceContentMimeType={isImage ? 'image/png' : 'application/pdf'}
        originalResults={invoice.lines || []}
        onAccept={(_newPrompt, _results, _updateTypes) => {
          queryClient.invalidateQueries({ queryKey: ['invoice', id] })
          setShowPromptEditor(false)
        }}
        onReparse={async (prompt: string) => {
          const result = await reparseInvoiceWithPrompt(id!, prompt)
          return {
            results: result.lines,
            prompt_used: result.prompt_used,
          }
        }}
      />
    </div>
  )
}

function determineContentType(
  pdfPath: string | null,
  source: string
): PromptContentType {
  if (!pdfPath) {
    return source === 'email' ? 'email' : 'pdf'
  }
  if (/\.(png|jpg|jpeg|gif|webp)$/i.test(pdfPath)) {
    return 'screenshot'
  }
  return 'pdf'
}
