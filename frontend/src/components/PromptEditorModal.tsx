import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  getDistributorPrompts,
  updateDistributorPrompts,
} from '@/lib/api'
import type { InvoiceLine, PromptContentType } from '@/types/invoice'
import type { ParsedPriceItem } from '@/lib/api'
import {
  X,
  Loader2,
  RotateCcw,
  Check,
  FileText,
  Image as ImageIcon,
  Mail,
} from 'lucide-react'

type ResultItem = InvoiceLine | ParsedPriceItem

interface PromptEditorModalProps {
  isOpen: boolean
  onClose: () => void
  distributorId: string | null
  contentType: PromptContentType
  sourceContent: string | null // Base64 for images/PDF, text for email
  sourceContentMimeType: string // MIME type
  originalResults: ResultItem[]
  onAccept: (
    newPrompt: string,
    results: ResultItem[],
    updateTypes: { pdf: boolean; email: boolean; screenshot: boolean }
  ) => void
  onReparse: (prompt: string) => Promise<{ results: ResultItem[]; prompt_used: string }>
}

// Format result item for display
function formatResultItem(item: ResultItem, isInvoiceLine: boolean): string {
  if (isInvoiceLine) {
    const line = item as InvoiceLine
    return `${line.raw_description} | ${line.quantity ?? '-'} ${line.unit ?? ''} @ $${
      line.unit_price_cents ? (line.unit_price_cents / 100).toFixed(2) : '-'
    }`
  } else {
    const parsed = item as ParsedPriceItem
    return `${parsed.description} | ${parsed.pack_size ?? ''}${parsed.pack_unit ?? ''} @ $${
      (parsed.price_cents / 100).toFixed(2)
    }`
  }
}

export function PromptEditorModal({
  isOpen,
  onClose,
  distributorId,
  contentType,
  sourceContent,
  sourceContentMimeType,
  originalResults,
  onAccept,
  onReparse,
}: PromptEditorModalProps) {
  const [newPrompt, setNewPrompt] = useState('')
  const [originalPrompt, setOriginalPrompt] = useState('')
  const [newResults, setNewResults] = useState<ResultItem[] | null>(null)
  const [isReparsing, setIsReparsing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Checkboxes for which prompt types to update
  const [updatePdf, setUpdatePdf] = useState(false)
  const [updateEmail, setUpdateEmail] = useState(false)
  const [updateScreenshot, setUpdateScreenshot] = useState(false)

  // Determine if results are invoice lines or parsed price items
  const isInvoiceLine = originalResults.length > 0 && 'invoice_id' in originalResults[0]

  // Fetch current prompts for distributor
  const { data: prompts, isLoading: promptsLoading } = useQuery({
    queryKey: ['distributor-prompts', distributorId],
    queryFn: () => (distributorId ? getDistributorPrompts(distributorId) : null),
    enabled: isOpen && !!distributorId,
  })

  // Initialize prompts when modal opens
  useEffect(() => {
    if (prompts) {
      const prompt = prompts[contentType]
      setOriginalPrompt(prompt)
      setNewPrompt(prompt)

      // Pre-check the current content type
      setUpdatePdf(contentType === 'pdf')
      setUpdateEmail(contentType === 'email')
      setUpdateScreenshot(contentType === 'screenshot')
    }
  }, [prompts, contentType])

  // Update distributor prompts mutation
  const updatePromptsMutation = useMutation({
    mutationFn: () => {
      if (!distributorId) throw new Error('No distributor selected')
      return updateDistributorPrompts(distributorId, {
        prompt: newPrompt,
        update_pdf: updatePdf,
        update_email: updateEmail,
        update_screenshot: updateScreenshot,
      })
    },
    onSuccess: () => {
      // Call onAccept with results and update flags
      const results = newResults || originalResults
      onAccept(newPrompt, results, {
        pdf: updatePdf,
        email: updateEmail,
        screenshot: updateScreenshot,
      })
      handleClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const handleClose = () => {
    setNewPrompt('')
    setOriginalPrompt('')
    setNewResults(null)
    setError(null)
    setUpdatePdf(false)
    setUpdateEmail(false)
    setUpdateScreenshot(false)
    onClose()
  }

  const handleTry = async () => {
    setIsReparsing(true)
    setError(null)

    try {
      const result = await onReparse(newPrompt)
      setNewResults(result.results)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reparse')
    } finally {
      setIsReparsing(false)
    }
  }

  const handleSaveAndAccept = () => {
    if (!distributorId) {
      // No distributor - just accept results without saving prompt
      const results = newResults || originalResults
      onAccept(newPrompt, results, { pdf: false, email: false, screenshot: false })
      handleClose()
      return
    }

    // Check if any update checkbox is selected
    if (!updatePdf && !updateEmail && !updateScreenshot) {
      setError('Please select at least one prompt type to update, or cancel.')
      return
    }

    updatePromptsMutation.mutate()
  }

  if (!isOpen) return null

  // Render source content preview
  const renderSourceContent = () => {
    if (!sourceContent) {
      return (
        <div className="flex items-center justify-center h-32 text-gray-400">
          No source content available
        </div>
      )
    }

    if (sourceContentMimeType.startsWith('image/')) {
      return (
        <img
          src={`data:${sourceContentMimeType};base64,${sourceContent}`}
          alt="Source content"
          className="max-h-48 mx-auto object-contain"
        />
      )
    }

    if (sourceContentMimeType === 'application/pdf') {
      return (
        <div className="flex items-center justify-center h-32 bg-gray-100 rounded">
          <FileText className="h-8 w-8 text-gray-400 mr-2" />
          <span className="text-gray-600">PDF Document</span>
        </div>
      )
    }

    // Text/email content
    return (
      <pre className="text-xs whitespace-pre-wrap max-h-48 overflow-y-auto bg-gray-50 p-2 rounded">
        {sourceContent.slice(0, 2000)}
        {sourceContent.length > 2000 && '...(truncated)'}
      </pre>
    )
  }

  // Render results list
  const renderResults = (results: ResultItem[], label: string) => (
    <div>
      <p className="text-sm font-medium text-gray-700 mb-2">{label}</p>
      <div className="max-h-40 overflow-y-auto border rounded bg-gray-50">
        {results.length === 0 ? (
          <p className="p-2 text-sm text-gray-400 italic">No results</p>
        ) : (
          <ul className="divide-y text-xs">
            {results.map((item, index) => (
              <li key={index} className="p-2 hover:bg-gray-100">
                {formatResultItem(item, isInvoiceLine)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )

  const contentTypeIcon = {
    pdf: <FileText className="h-4 w-4" />,
    email: <Mail className="h-4 w-4" />,
    screenshot: <ImageIcon className="h-4 w-4" />,
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50" onClick={handleClose} />

      {/* Modal - wider for side-by-side */}
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-5xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Edit Parsing Prompt</h2>
            <span className="text-sm text-gray-500 flex items-center gap-1">
              {contentTypeIcon[contentType]}
              {contentType}
            </span>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {/* Source Content Preview */}
          <div className="mb-4 p-3 border rounded-lg bg-gray-50">
            <p className="text-xs text-gray-500 mb-2 font-medium uppercase">Source Content</p>
            {renderSourceContent()}
          </div>

          {promptsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-500">Loading prompts...</span>
            </div>
          ) : (
            <>
              {/* Side-by-side comparison */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                {/* Original Column */}
                <div className="space-y-3">
                  <div>
                    <Label className="text-sm font-medium">Original Prompt</Label>
                    <textarea
                      value={originalPrompt}
                      readOnly
                      className="mt-1 w-full h-48 p-3 border rounded-md bg-gray-100 text-xs font-mono resize-none"
                    />
                  </div>
                  {renderResults(originalResults, 'Original Results')}
                </div>

                {/* New Column */}
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">New Prompt (editable)</Label>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setNewPrompt(originalPrompt)}
                        className="text-xs"
                      >
                        Reset
                      </Button>
                    </div>
                    <textarea
                      value={newPrompt}
                      onChange={(e) => setNewPrompt(e.target.value)}
                      className="mt-1 w-full h-48 p-3 border rounded-md text-xs font-mono resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter your custom parsing prompt..."
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      onClick={handleTry}
                      disabled={isReparsing || !newPrompt.trim()}
                      variant="outline"
                      className="flex-1"
                    >
                      {isReparsing ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Parsing...
                        </>
                      ) : (
                        <>
                          <RotateCcw className="h-4 w-4 mr-2" />
                          Try
                        </>
                      )}
                    </Button>
                  </div>

                  {newResults ? (
                    renderResults(newResults, 'New Results')
                  ) : (
                    <div className="max-h-40 border rounded bg-gray-50 flex items-center justify-center text-gray-400 text-sm">
                      Click "Try" to see new results
                    </div>
                  )}
                </div>
              </div>

              {/* Update checkboxes */}
              {distributorId && (
                <div className="p-3 border rounded-lg bg-blue-50 mb-4">
                  <p className="text-sm font-medium text-blue-800 mb-2">
                    Save this prompt for:
                  </p>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={updatePdf}
                        onChange={(e) => setUpdatePdf(e.target.checked)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <FileText className="h-4 w-4 text-gray-600" />
                      PDF invoices
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={updateEmail}
                        onChange={(e) => setUpdateEmail(e.target.checked)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <Mail className="h-4 w-4 text-gray-600" />
                      Email invoices
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={updateScreenshot}
                        onChange={(e) => setUpdateScreenshot(e.target.checked)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <ImageIcon className="h-4 w-4 text-gray-600" />
                      Screenshots
                    </label>
                  </div>
                </div>
              )}

              {/* Error display */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg mb-4">
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 sticky bottom-0">
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveAndAccept}
            disabled={updatePromptsMutation.isPending || promptsLoading}
          >
            {updatePromptsMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check className="h-4 w-4 mr-2" />
                Save & Accept
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
