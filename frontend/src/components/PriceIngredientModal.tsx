import { useState, useRef, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Dialog, DialogHeader, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PromptEditorModal } from '@/components/PromptEditorModal'
import {
  getDistributors,
  addManualPrice,
  getInvoicesWithStats,
  getInvoiceLinesForPricing,
  addPriceFromInvoice,
  parsePriceContentWithPrompt,
  saveParsedPrice,
  createDistributor,
  getUnmappedDistIngredients,
  mapDistIngredient,
  type InvoiceWithStats,
  type InvoiceLineForPricing,
  type ParsedPriceItem,
  type UnmappedDistIngredient,
} from '@/lib/api'
import type { PromptContentType } from '@/types/invoice'
import {
  AlertTriangle,
  DollarSign,
  Package,
  Calendar,
  FileText,
  Upload,
  ChevronDown,
  ChevronRight,
  Check,
  X,
  Loader2,
  Plus,
  Clipboard,
  Sparkles,
  Link2,
  RotateCcw,
} from 'lucide-react'

interface PriceIngredientModalProps {
  open: boolean
  onClose: () => void
  ingredient: {
    id: string
    name: string
    base_unit: string
    category?: string
  }
  onSuccess?: () => void
}

// Format price in dollars
function formatPrice(cents: number | null): string {
  if (cents === null) return '-'
  return `$${(cents / 100).toFixed(2)}`
}

export function PriceIngredientModal({
  open,
  onClose,
  ingredient,
  onSuccess,
}: PriceIngredientModalProps) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'map' | 'manual' | 'invoice' | 'upload'>('map')

  // ============================================================================
  // Manual Tab State
  // ============================================================================
  const [distributorId, setDistributorId] = useState('')
  const [priceDollars, setPriceDollars] = useState('')
  const [totalBaseUnits, setTotalBaseUnits] = useState('')
  const [packDescription, setPackDescription] = useState('')
  const [effectiveDate, setEffectiveDate] = useState(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  // ============================================================================
  // Invoice Tab State
  // ============================================================================
  const [expandedInvoiceId, setExpandedInvoiceId] = useState<string | null>(null)
  const [selectedLine, setSelectedLine] = useState<InvoiceLineForPricing | null>(null)
  const [invoiceGramsPerUnit, setInvoiceGramsPerUnit] = useState('')
  const [showRemapWarning, setShowRemapWarning] = useState(false)

  // ============================================================================
  // Upload Tab State
  // ============================================================================
  const [uploadDistributorId, setUploadDistributorId] = useState('')
  const [showNewDistributor, setShowNewDistributor] = useState(false)
  const [newDistributorName, setNewDistributorName] = useState('')
  const [uploadContent, setUploadContent] = useState<string | null>(null)
  const [uploadContentType, setUploadContentType] = useState<string>('')
  const [uploadFileName, setUploadFileName] = useState<string>('')
  const [parsedItems, setParsedItems] = useState<ParsedPriceItem[]>([])
  const [selectedParsedItems, setSelectedParsedItems] = useState<Set<number>>(new Set())
  const [isParsing, setIsParsing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [_promptUsed, setPromptUsed] = useState<string>('')
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropZoneRef = useRef<HTMLDivElement>(null)

  // ============================================================================
  // Map SKU Tab State
  // ============================================================================
  const [unmappedSearch, setUnmappedSearch] = useState('')
  const [selectedUnmapped, setSelectedUnmapped] = useState<UnmappedDistIngredient | null>(null)
  const [mapPackSize, setMapPackSize] = useState('')
  const [mapPackUnit, setMapPackUnit] = useState('')
  const [mapTotalBaseUnits, setMapTotalBaseUnits] = useState('')

  // Fetch distributors
  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  // Fetch unmapped SKUs for Map tab
  const { data: unmappedData } = useQuery({
    queryKey: ['unmapped-ingredients', unmappedSearch],
    queryFn: () => getUnmappedDistIngredients({ search: unmappedSearch || undefined }),
    enabled: activeTab === 'map',
  })
  const unmappedItems = unmappedData?.items || []

  // Fetch invoices with stats
  const { data: invoicesData } = useQuery({
    queryKey: ['invoices-with-stats'],
    queryFn: () => getInvoicesWithStats(),
    enabled: activeTab === 'invoice',
  })

  // Fetch lines for expanded invoice
  const { data: invoiceLinesData } = useQuery({
    queryKey: ['invoice-lines-for-pricing', expandedInvoiceId, ingredient.id],
    queryFn: () => getInvoiceLinesForPricing(expandedInvoiceId!, ingredient.id),
    enabled: !!expandedInvoiceId,
  })

  // ============================================================================
  // Mutations
  // ============================================================================

  const addPriceMutation = useMutation({
    mutationFn: () => {
      const priceCents = Math.round(parseFloat(priceDollars) * 100)
      return addManualPrice(ingredient.id, {
        distributor_id: distributorId,
        price_cents: priceCents,
        total_base_units: parseFloat(totalBaseUnits),
        pack_description: packDescription || undefined,
        effective_date: effectiveDate || undefined,
        notes: notes || undefined,
      })
    },
    onSuccess: () => {
      invalidateAndClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const addFromInvoiceMutation = useMutation({
    mutationFn: (remap: boolean) => {
      if (!selectedLine) throw new Error('No line selected')
      return addPriceFromInvoice(ingredient.id, {
        invoice_line_id: selectedLine.id,
        grams_per_unit: parseFloat(invoiceGramsPerUnit),
        remap_to_ingredient: remap,
      })
    },
    onSuccess: () => {
      invalidateAndClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const saveParsedMutation = useMutation({
    mutationFn: async () => {
      const selected = parsedItems.filter((_, i) => selectedParsedItems.has(i))
      for (const item of selected) {
        await saveParsedPrice(ingredient.id, {
          description: item.description,
          sku: item.sku || undefined,
          pack_description: item.pack_size ? `${item.pack_size} x ${item.unit_contents}${item.unit_contents_unit}` : undefined,
          total_base_units: item.total_base_units || 1,
          price_cents: item.price_cents,
          distributor_id: uploadDistributorId || undefined,
        })
      }
    },
    onSuccess: () => {
      invalidateAndClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const createDistributorMutation = useMutation({
    mutationFn: () => createDistributor({ name: newDistributorName }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['distributors'] })
      setUploadDistributorId(data.id)
      setShowNewDistributor(false)
      setNewDistributorName('')
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const mapSkuMutation = useMutation({
    mutationFn: () => {
      if (!selectedUnmapped) throw new Error('No SKU selected')
      return mapDistIngredient(selectedUnmapped.id, {
        ingredient_id: ingredient.id,
        pack_size: mapPackSize ? parseFloat(mapPackSize) : undefined,
        pack_unit: mapPackUnit || undefined,
        grams_per_unit: mapTotalBaseUnits ? parseFloat(mapTotalBaseUnits) : undefined,
      })
    },
    onSuccess: () => {
      invalidateAndClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  // ============================================================================
  // Handlers
  // ============================================================================

  const invalidateAndClose = () => {
    queryClient.invalidateQueries({ queryKey: ['ingredients-with-prices'] })
    queryClient.invalidateQueries({ queryKey: ['ingredients'] })
    queryClient.invalidateQueries({ queryKey: ['recipe-cost'] })
    onSuccess?.()
    handleClose()
  }

  const handleClose = () => {
    // Reset all state
    setDistributorId('')
    setPriceDollars('')
    setTotalBaseUnits('')
    setPackDescription('')
    setNotes('')
    setError(null)
    setExpandedInvoiceId(null)
    setSelectedLine(null)
    setInvoiceGramsPerUnit('')
    setShowRemapWarning(false)
    setUploadContent(null)
    setUploadContentType('')
    setUploadFileName('')
    setParsedItems([])
    setSelectedParsedItems(new Set())
    setParseError(null)
    setPromptUsed('') // eslint-disable-line @typescript-eslint/no-unused-vars
    setShowPromptEditor(false)
    // Map tab state
    setUnmappedSearch('')
    setSelectedUnmapped(null)
    setMapPackSize('')
    setMapPackUnit('')
    setMapTotalBaseUnits('')
    onClose()
  }

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!distributorId) {
      setError('Please select a distributor')
      return
    }
    if (!priceDollars || parseFloat(priceDollars) <= 0) {
      setError('Please enter a valid price')
      return
    }
    if (!totalBaseUnits || parseFloat(totalBaseUnits) <= 0) {
      setError('Please enter the total base units in the pack')
      return
    }

    addPriceMutation.mutate()
  }

  const handleLineSelect = (line: InvoiceLineForPricing) => {
    setSelectedLine(line)
    setShowRemapWarning(false)

    // Pre-fill grams per unit if we can calculate it
    if (line.quantity && line.unit_price_cents) {
      // User will need to enter the conversion
    }
  }

  const handleInvoiceSubmit = () => {
    setError(null)

    if (!selectedLine) {
      setError('Please select an invoice line')
      return
    }
    if (!invoiceGramsPerUnit || parseFloat(invoiceGramsPerUnit) <= 0) {
      setError('Please enter the base units per invoice unit')
      return
    }

    // Check if remapping is needed
    if (selectedLine.status === 'grey') {
      setShowRemapWarning(true)
      return
    }

    addFromInvoiceMutation.mutate(false)
  }

  const handleRemapConfirm = () => {
    addFromInvoiceMutation.mutate(true)
  }

  // File/paste handling
  const handleFileSelect = async (file: File) => {
    setParseError(null)

    // Determine content type
    let contentType = file.type
    if (file.name.endsWith('.eml') || file.name.endsWith('.txt')) {
      contentType = 'text/email'
    }

    // Read file
    const reader = new FileReader()
    reader.onload = async (e) => {
      const result = e.target?.result
      if (!result) return

      if (contentType.startsWith('image/') || contentType === 'application/pdf') {
        // Binary - convert to base64
        const base64 = (result as string).split(',')[1]
        setUploadContent(base64)
      } else {
        // Text
        setUploadContent(result as string)
      }
      setUploadContentType(contentType)
      setUploadFileName(file.name)
    }

    if (file.type.startsWith('image/') || file.type === 'application/pdf') {
      reader.readAsDataURL(file)
    } else {
      reader.readAsText(file)
    }
  }

  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLDivElement>) => {
    if (activeTab !== 'upload') return

    const items = e.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        // Image paste
        const file = item.getAsFile()
        if (file) {
          e.preventDefault()
          await handleFileSelect(file)
          return
        }
      }
    }

    // Text paste
    const text = e.clipboardData?.getData('text')
    if (text) {
      // Check if it looks like email headers
      const isEmail = text.includes('From:') || text.includes('Subject:') || text.includes('Delivered-To:')
      setUploadContent(text)
      setUploadContentType(isEmail ? 'text/email' : 'text/plain')
      setUploadFileName(isEmail ? 'Pasted email' : 'Pasted text')
    }
  }, [activeTab])

  // Handle drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  // Parse content
  const handleParse = async (customPrompt?: string) => {
    if (!uploadContent) return

    setIsParsing(true)
    setParseError(null)

    try {
      const result = await parsePriceContentWithPrompt({
        content: uploadContent,
        content_type: uploadContentType,
        distributor_id: uploadDistributorId || undefined,
        ingredient_name: ingredient.name,
        ingredient_category: ingredient.category,
        ingredient_base_unit: ingredient.base_unit,
        custom_prompt: customPrompt,
      })

      setParsedItems(result.items)
      setPromptUsed(result.prompt_used || '')
      // Auto-select high confidence items
      const autoSelected = new Set<number>()
      result.items.forEach((item, i) => {
        if (item.confidence >= 0.7) {
          autoSelected.add(i)
        }
      })
      setSelectedParsedItems(autoSelected)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to parse content')
    } finally {
      setIsParsing(false)
    }
  }

  // Fuzzy match button
  const handleFuzzyMatch = () => {
    // Select items with confidence > 0.5
    const matched = new Set<number>()
    parsedItems.forEach((item, i) => {
      if (item.confidence >= 0.5) {
        matched.add(i)
      }
    })
    setSelectedParsedItems(matched)
  }

  // Calculate price per unit preview
  const pricePerUnit = priceDollars && totalBaseUnits
    ? (parseFloat(priceDollars) / parseFloat(totalBaseUnits)).toFixed(6)
    : null

  // Invoice price per unit
  const invoicePricePerUnit = selectedLine && invoiceGramsPerUnit && selectedLine.unit_price_cents
    ? (selectedLine.unit_price_cents / 100 / parseFloat(invoiceGramsPerUnit)).toFixed(6)
    : null

  return (
    <Dialog open={open} onClose={handleClose}>
      <DialogHeader onClose={handleClose}>
        Price: {ingredient.name}
      </DialogHeader>

      <DialogContent>
        {/* Ingredient Info */}
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-2">
          <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-yellow-800">No price on file</p>
            <p className="text-sm text-yellow-700">
              Add a price to enable cost calculations for recipes using this ingredient.
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b">
          <button
            type="button"
            onClick={() => setActiveTab('map')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1 ${
              activeTab === 'map'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Link2 className="h-4 w-4" />
            Map SKU
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('manual')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'manual'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Manual
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('invoice')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1 ${
              activeTab === 'invoice'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <FileText className="h-4 w-4" />
            Invoice
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1 ${
              activeTab === 'upload'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Upload className="h-4 w-4" />
            Upload
          </button>
        </div>

        {/* ================================================================== */}
        {/* Map SKU Tab */}
        {/* ================================================================== */}
        {activeTab === 'map' && (
          <div className="space-y-4">
            {/* Search unmapped SKUs */}
            <div>
              <Label>Search Unmapped SKUs</Label>
              <Input
                placeholder="Search by description..."
                value={unmappedSearch}
                onChange={(e) => setUnmappedSearch(e.target.value)}
                className="mt-1"
              />
            </div>

            {/* SKU List */}
            <div className="max-h-48 overflow-y-auto border rounded-lg divide-y">
              {unmappedItems.length === 0 ? (
                <div className="p-4 text-center text-gray-500">
                  {unmappedSearch ? 'No matches found' : 'No unmapped SKUs available'}
                </div>
              ) : (
                unmappedItems.slice(0, 20).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSelectedUnmapped(item)
                      // Pre-fill parsed values if available
                      if (item.parsed_pack_quantity) {
                        setMapPackSize(item.parsed_pack_quantity.toString())
                      }
                      if (item.parsed_unit_quantity && item.parsed_unit) {
                        setMapPackUnit(`${item.parsed_unit_quantity}${item.parsed_unit}`)
                      }
                      if (item.parsed_total_base_units) {
                        setMapTotalBaseUnits(item.parsed_total_base_units.toString())
                      }
                    }}
                    className={`w-full p-3 text-left hover:bg-gray-50 ${
                      selectedUnmapped?.id === item.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
                    }`}
                  >
                    <p className="font-medium text-sm truncate">{item.description}</p>
                    <p className="text-xs text-gray-500 flex items-center gap-2">
                      {item.distributor_name}
                      {item.sku && <span>· SKU: {item.sku}</span>}
                      {item.last_price_cents && (
                        <span className="text-green-600 font-medium">
                          {formatPrice(item.last_price_cents)}
                        </span>
                      )}
                    </p>
                  </button>
                ))
              )}
            </div>

            {/* Selected SKU Details */}
            {selectedUnmapped && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
                <div>
                  <p className="font-medium text-blue-800">{selectedUnmapped.description}</p>
                  <p className="text-sm text-blue-700">
                    {selectedUnmapped.distributor_name}
                    {selectedUnmapped.last_price_cents && (
                      <span className="ml-2">· Last price: {formatPrice(selectedUnmapped.last_price_cents)}</span>
                    )}
                  </p>
                </div>

                {/* Pack Info */}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label className="text-xs">Pack Qty</Label>
                    <Input
                      type="number"
                      step="any"
                      value={mapPackSize}
                      onChange={(e) => setMapPackSize(e.target.value)}
                      placeholder="e.g. 36"
                      className="mt-1 h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Pack Unit</Label>
                    <Input
                      value={mapPackUnit}
                      onChange={(e) => setMapPackUnit(e.target.value)}
                      placeholder="e.g. 1LB"
                      className="mt-1 h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Total {ingredient.base_unit}</Label>
                    <Input
                      type="number"
                      step="any"
                      value={mapTotalBaseUnits}
                      onChange={(e) => setMapTotalBaseUnits(e.target.value)}
                      placeholder="e.g. 16329"
                      className="mt-1 h-8 text-sm"
                    />
                  </div>
                </div>

                {selectedUnmapped.parsed_total_base_units && (
                  <p className="text-xs text-gray-600">
                    Parsed: {selectedUnmapped.parsed_pack_quantity}×{selectedUnmapped.parsed_unit_quantity}{selectedUnmapped.parsed_unit} ={' '}
                    {Number(selectedUnmapped.parsed_total_base_units).toFixed(1)} {selectedUnmapped.parsed_base_unit}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ================================================================== */}
        {/* Manual Entry Tab */}
        {/* ================================================================== */}
        {activeTab === 'manual' && (
          <form onSubmit={handleManualSubmit} className="space-y-4">
            {/* Distributor */}
            <div>
              <Label htmlFor="distributor">Distributor *</Label>
              <select
                id="distributor"
                value={distributorId}
                onChange={(e) => setDistributorId(e.target.value)}
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-white"
              >
                <option value="">Select a distributor...</option>
                {distributors?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Price and Units Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="price">
                  <DollarSign className="inline h-3.5 w-3.5 mr-1" />
                  Pack Price *
                </Label>
                <div className="relative mt-1">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
                  <Input
                    id="price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={priceDollars}
                    onChange={(e) => setPriceDollars(e.target.value)}
                    className="pl-7"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="units">
                  <Package className="inline h-3.5 w-3.5 mr-1" />
                  Total {ingredient.base_unit} *
                </Label>
                <Input
                  id="units"
                  type="number"
                  step="0.01"
                  min="0"
                  value={totalBaseUnits}
                  onChange={(e) => setTotalBaseUnits(e.target.value)}
                  className="mt-1"
                  placeholder={`Total ${ingredient.base_unit} in pack`}
                />
              </div>
            </div>

            {/* Price Preview */}
            {pricePerUnit && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm text-green-800">
                  <span className="font-medium">Price per {ingredient.base_unit}:</span>{' '}
                  ${pricePerUnit}
                </p>
              </div>
            )}

            {/* Pack Description */}
            <div>
              <Label htmlFor="packDesc">Pack Description (optional)</Label>
              <Input
                id="packDesc"
                value={packDescription}
                onChange={(e) => setPackDescription(e.target.value)}
                className="mt-1"
                placeholder="e.g., 12 x 1LB, Case of 6"
              />
            </div>

            {/* Effective Date */}
            <div>
              <Label htmlFor="date">
                <Calendar className="inline h-3.5 w-3.5 mr-1" />
                Effective Date
              </Label>
              <Input
                id="date"
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="mt-1"
              />
            </div>

            {/* Notes */}
            <div>
              <Label htmlFor="notes">Notes (optional)</Label>
              <Input
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="mt-1"
                placeholder="Source, context, etc."
              />
            </div>
          </form>
        )}

        {/* ================================================================== */}
        {/* From Invoice Tab */}
        {/* ================================================================== */}
        {activeTab === 'invoice' && (
          <div className="space-y-4">
            {/* Invoice List */}
            <div className="max-h-64 overflow-y-auto border rounded-lg divide-y">
              {invoicesData?.invoices.map((invoice) => (
                <InvoiceRow
                  key={invoice.id}
                  invoice={invoice}
                  isExpanded={expandedInvoiceId === invoice.id}
                  onToggle={() => setExpandedInvoiceId(
                    expandedInvoiceId === invoice.id ? null : invoice.id
                  )}
                  lines={expandedInvoiceId === invoice.id ? invoiceLinesData?.lines : undefined}
                  selectedLineId={selectedLine?.id}
                  onSelectLine={handleLineSelect}
                />
              ))}
              {!invoicesData?.invoices.length && (
                <div className="p-4 text-center text-gray-500">
                  No invoices found
                </div>
              )}
            </div>

            {/* Selected Line Details */}
            {selectedLine && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
                <div>
                  <p className="font-medium text-blue-800">{selectedLine.raw_description}</p>
                  <p className="text-sm text-blue-700">
                    {selectedLine.quantity} {selectedLine.unit} @ {formatPrice(selectedLine.unit_price_cents)}
                  </p>
                </div>

                <div>
                  <Label htmlFor="gramsPerUnit">
                    {ingredient.base_unit} per {selectedLine.unit || 'unit'} *
                  </Label>
                  <Input
                    id="gramsPerUnit"
                    type="number"
                    step="0.01"
                    value={invoiceGramsPerUnit}
                    onChange={(e) => setInvoiceGramsPerUnit(e.target.value)}
                    className="mt-1"
                    placeholder={`How many ${ingredient.base_unit} per ${selectedLine.unit || 'unit'}?`}
                  />
                </div>

                {invoicePricePerUnit && (
                  <div className="p-2 bg-green-100 rounded">
                    <p className="text-sm text-green-800">
                      <span className="font-medium">Price per {ingredient.base_unit}:</span>{' '}
                      ${invoicePricePerUnit}
                    </p>
                  </div>
                )}

                {selectedLine.status === 'grey' && (
                  <div className="p-2 bg-yellow-100 rounded">
                    <p className="text-sm text-yellow-800">
                      <AlertTriangle className="inline h-4 w-4 mr-1" />
                      This line is mapped to <strong>{selectedLine.mapped_ingredient_name}</strong>.
                      You can remap it to {ingredient.name}.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Remap Warning Modal */}
            {showRemapWarning && selectedLine && (
              <div className="p-3 bg-orange-50 border border-orange-300 rounded-lg space-y-2">
                <p className="text-sm text-orange-800">
                  <AlertTriangle className="inline h-4 w-4 mr-1" />
                  This will remap the invoice line from <strong>{selectedLine.mapped_ingredient_name}</strong> to <strong>{ingredient.name}</strong>. Continue?
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowRemapWarning(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleRemapConfirm}
                    disabled={addFromInvoiceMutation.isPending}
                  >
                    {addFromInvoiceMutation.isPending ? 'Saving...' : 'Remap & Save'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================== */}
        {/* Upload Tab */}
        {/* ================================================================== */}
        {activeTab === 'upload' && (
          <div className="space-y-4">
            {/* Distributor Selection */}
            <div>
              <Label>Distributor</Label>
              <div className="flex gap-2 mt-1">
                <select
                  value={uploadDistributorId}
                  onChange={(e) => {
                    if (e.target.value === 'new') {
                      setShowNewDistributor(true)
                    } else {
                      setUploadDistributorId(e.target.value)
                    }
                  }}
                  className="flex-1 border rounded-md px-3 py-2 text-sm bg-white"
                >
                  <option value="">One-off / Unknown</option>
                  {distributors?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                  <option value="new">+ Add new distributor...</option>
                </select>
              </div>

              {showNewDistributor && (
                <div className="mt-2 flex gap-2">
                  <Input
                    placeholder="Distributor name"
                    value={newDistributorName}
                    onChange={(e) => setNewDistributorName(e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    size="sm"
                    onClick={() => createDistributorMutation.mutate()}
                    disabled={!newDistributorName || createDistributorMutation.isPending}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowNewDistributor(false)
                      setNewDistributorName('')
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>

            {/* Drop Zone / Paste Area */}
            {!uploadContent && (
              <div
                ref={dropZoneRef}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onPaste={handlePaste}
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,.pdf,.txt,.eml"
                  onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                  className="hidden"
                />
                <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                <p className="text-gray-600">
                  Drop file here, click to browse, or paste
                </p>
                <p className="text-sm text-gray-400 mt-1">
                  PDF, Image, Email, or Text
                </p>
                <div className="flex items-center justify-center gap-2 mt-3">
                  <Clipboard className="h-4 w-4 text-gray-400" />
                  <span className="text-xs text-gray-400">Ctrl+V to paste screenshot</span>
                </div>
              </div>
            )}

            {/* Uploaded Content Preview */}
            {uploadContent && !parsedItems.length && (
              <div className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium">{uploadFileName}</span>
                    <span className="text-xs text-gray-400">({uploadContentType})</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setUploadContent(null)
                      setUploadFileName('')
                      setUploadContentType('')
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <Button
                  onClick={() => handleParse()}
                  disabled={isParsing}
                  className="w-full"
                >
                  {isParsing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Parsing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 mr-2" />
                      Extract Prices with AI
                    </>
                  )}
                </Button>

                {parseError && (
                  <p className="text-sm text-red-600 mt-2">{parseError}</p>
                )}
              </div>
            )}

            {/* Parsed Items Table */}
            {parsedItems.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    Found {parsedItems.length} item(s)
                  </span>
                  <div className="flex gap-2">
                    {/* Retry with custom prompt button */}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowPromptEditor(true)}
                      title="Retry with custom prompt"
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      Retry
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedParsedItems(new Set(parsedItems.map((_, i) => i)))}
                    >
                      Select All
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleFuzzyMatch}
                    >
                      <Sparkles className="h-3 w-3 mr-1" />
                      Fuzzy Match
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setParsedItems([])
                        setSelectedParsedItems(new Set())
                        setUploadContent(null)
                        setPromptUsed('')
                      }}
                    >
                      Clear
                    </Button>
                  </div>
                </div>

                <div className="border rounded-lg divide-y max-h-64 overflow-y-auto">
                  {parsedItems.map((item, index) => (
                    <div
                      key={index}
                      className={`p-2 flex items-start gap-2 ${
                        selectedParsedItems.has(index) ? 'bg-blue-50' : ''
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedParsedItems.has(index)}
                        onChange={(e) => {
                          const newSelected = new Set(selectedParsedItems)
                          if (e.target.checked) {
                            newSelected.add(index)
                          } else {
                            newSelected.delete(index)
                          }
                          setSelectedParsedItems(newSelected)
                        }}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{item.description}</p>
                        <p className="text-xs text-gray-500">
                          {item.pack_size && `${item.pack_size}× `}
                          {item.unit_contents}{item.unit_contents_unit} @ {formatPrice(item.price_cents)}
                          {item.total_base_units && item.price_per_base_unit_cents && (
                            <span className="text-green-600 ml-2">
                              (${(item.price_per_base_unit_cents / 100).toFixed(4)}/{item.base_unit})
                            </span>
                          )}
                        </p>
                      </div>
                      <div className="text-xs">
                        <span className={`px-1.5 py-0.5 rounded ${
                          item.confidence >= 0.7 ? 'bg-green-100 text-green-700' :
                          item.confidence >= 0.4 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {Math.round(item.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
      </DialogContent>

      <DialogFooter>
        <Button variant="outline" onClick={handleClose}>
          Cancel
        </Button>
        {activeTab === 'map' && (
          <Button
            onClick={() => mapSkuMutation.mutate()}
            disabled={!selectedUnmapped || mapSkuMutation.isPending}
          >
            {mapSkuMutation.isPending ? 'Mapping...' : 'Map & Save'}
          </Button>
        )}
        {activeTab === 'manual' && (
          <Button
            onClick={handleManualSubmit}
            disabled={addPriceMutation.isPending}
          >
            {addPriceMutation.isPending ? 'Saving...' : 'Save Price'}
          </Button>
        )}
        {activeTab === 'invoice' && (
          <Button
            onClick={handleInvoiceSubmit}
            disabled={!selectedLine || !invoiceGramsPerUnit || addFromInvoiceMutation.isPending}
          >
            {addFromInvoiceMutation.isPending ? 'Saving...' : 'Save Price'}
          </Button>
        )}
        {activeTab === 'upload' && parsedItems.length > 0 && (
          <Button
            onClick={() => saveParsedMutation.mutate()}
            disabled={selectedParsedItems.size === 0 || saveParsedMutation.isPending}
          >
            {saveParsedMutation.isPending ? 'Saving...' : `Save ${selectedParsedItems.size} Item(s)`}
          </Button>
        )}
      </DialogFooter>

      {/* Prompt Editor Modal for retrying with custom prompt */}
      <PromptEditorModal
        isOpen={showPromptEditor}
        onClose={() => setShowPromptEditor(false)}
        distributorId={uploadDistributorId || null}
        contentType={getUploadContentType()}
        sourceContent={uploadContent}
        sourceContentMimeType={uploadContentType}
        originalResults={parsedItems}
        onAccept={(_newPrompt, results, _updateTypes) => {
          // Update the parsed items with the new results
          setParsedItems(results as ParsedPriceItem[])
          // Auto-select high confidence items
          const autoSelected = new Set<number>()
          ;(results as ParsedPriceItem[]).forEach((item, i) => {
            if (item.confidence >= 0.7) {
              autoSelected.add(i)
            }
          })
          setSelectedParsedItems(autoSelected)
          setShowPromptEditor(false)
        }}
        onReparse={async (prompt: string) => {
          const result = await parsePriceContentWithPrompt({
            content: uploadContent!,
            content_type: uploadContentType,
            distributor_id: uploadDistributorId || undefined,
            ingredient_name: ingredient.name,
            ingredient_category: ingredient.category,
            ingredient_base_unit: ingredient.base_unit,
            custom_prompt: prompt,
          })
          setPromptUsed(result.prompt_used || '')
          return {
            results: result.items,
            prompt_used: result.prompt_used || '',
          }
        }}
      />
    </Dialog>
  )

  // Helper to determine content type for prompt editor
  function getUploadContentType(): PromptContentType {
    if (uploadContentType.startsWith('image/')) {
      return 'screenshot'
    }
    if (uploadContentType === 'text/email') {
      return 'email'
    }
    return 'pdf'
  }
}

// ============================================================================
// Invoice Row Component
// ============================================================================

function InvoiceRow({
  invoice,
  isExpanded,
  onToggle,
  lines,
  selectedLineId,
  onSelectLine,
}: {
  invoice: InvoiceWithStats
  isExpanded: boolean
  onToggle: () => void
  lines?: InvoiceLineForPricing[]
  selectedLineId?: string
  onSelectLine: (line: InvoiceLineForPricing) => void
}) {
  return (
    <div>
      {/* Invoice Header */}
      <button
        onClick={onToggle}
        className="w-full p-3 flex items-center gap-3 hover:bg-gray-50 text-left"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-400" />
        )}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">
            {invoice.distributor_name} - #{invoice.invoice_number}
          </p>
          <p className="text-xs text-gray-500">
            {invoice.invoice_date} • {formatPrice(invoice.total_cents)}
          </p>
        </div>
        <div className="text-xs text-right">
          <div className="text-gray-600">{invoice.stats.total_lines} lines</div>
          <div className="text-green-600">{invoice.stats.mapped_lines} mapped</div>
          {invoice.stats.unmapped_lines > 0 && (
            <div className="text-yellow-600">{invoice.stats.unmapped_lines} unmapped</div>
          )}
        </div>
      </button>

      {/* Expanded Lines */}
      {isExpanded && lines && (
        <div className="border-t bg-gray-50">
          {lines.map((line) => (
            <button
              key={line.id}
              onClick={() => onSelectLine(line)}
              className={`w-full p-2 pl-10 flex items-center gap-2 text-left text-sm hover:bg-gray-100 ${
                selectedLineId === line.id ? 'bg-blue-100' : ''
              } ${
                line.status === 'green' ? 'border-l-4 border-l-green-500' :
                line.status === 'orange' ? 'border-l-4 border-l-orange-500' :
                line.status === 'yellow' ? 'border-l-4 border-l-yellow-500' :
                'border-l-4 border-l-gray-300'
              }`}
            >
              <div className="flex-1 min-w-0">
                <p className="truncate">{line.raw_description}</p>
                <p className="text-xs text-gray-500">
                  {line.quantity} {line.unit} @ {formatPrice(line.unit_price_cents)}
                </p>
              </div>
              {line.status === 'green' && (
                <Check className="h-4 w-4 text-green-500" />
              )}
              {line.status === 'grey' && line.mapped_ingredient_name && (
                <span className="text-xs text-gray-500 truncate max-w-24">
                  → {line.mapped_ingredient_name}
                </span>
              )}
            </button>
          ))}
          {lines.length === 0 && (
            <p className="p-3 pl-10 text-sm text-gray-500">No product lines</p>
          )}
        </div>
      )}
    </div>
  )
}
