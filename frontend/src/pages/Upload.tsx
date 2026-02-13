import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Upload as UploadIcon, FileText, Mail, Image, Loader2, AlertCircle } from 'lucide-react'
import { getDistributors, uploadInvoice } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type UploadMode = 'pdf' | 'image' | 'email'

export function Upload() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<UploadMode>('pdf')
  const [distributorId, setDistributorId] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [emailContent, setEmailContent] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const dropZoneRef = useRef<HTMLDivElement>(null)

  const { data: distributors } = useQuery({
    queryKey: ['distributors'],
    queryFn: getDistributors,
  })

  // Handle clipboard paste for images
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      if (mode !== 'image') return

      const items = e.clipboardData?.items
      if (!items) return

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const pastedFile = item.getAsFile()
          if (pastedFile) {
            setImageFile(pastedFile)
            const reader = new FileReader()
            reader.onload = (event) => {
              setImagePreview(event.target?.result as string)
            }
            reader.readAsDataURL(pastedFile)
          }
          break
        }
      }
    }

    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [mode])

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (mode === 'pdf' && file) {
        return uploadInvoice(distributorId, file)
      } else if (mode === 'image' && imageFile) {
        return uploadInvoice(distributorId, imageFile)
      } else if (mode === 'email' && emailContent) {
        return uploadInvoice(distributorId, undefined, emailContent)
      }
      throw new Error('Please provide a file or email content')
    },
    onSuccess: (invoice) => {
      navigate(`/invoices/${invoice.id}`)
    },
  })

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      if (droppedFile.type === 'application/pdf') {
        setFile(droppedFile)
        setMode('pdf')
      } else if (droppedFile.type.startsWith('image/')) {
        setImageFile(droppedFile)
        setMode('image')
        const reader = new FileReader()
        reader.onload = (event) => {
          setImagePreview(event.target?.result as string)
        }
        reader.readAsDataURL(droppedFile)
      }
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0]
      setImageFile(selectedFile)
      const reader = new FileReader()
      reader.onload = (event) => {
        setImagePreview(event.target?.result as string)
      }
      reader.readAsDataURL(selectedFile)
    }
  }

  const canSubmit = distributorId && (
    (mode === 'pdf' && file) ||
    (mode === 'image' && imageFile) ||
    (mode === 'email' && emailContent.trim())
  )

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Invoice</h1>
        <p className="text-gray-500 mt-1">Upload a PDF or paste email content to parse</p>
      </div>

      {/* Distributor selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Distributor</CardTitle>
          <CardDescription>Select which distributor this invoice is from</CardDescription>
        </CardHeader>
        <CardContent>
          <select
            value={distributorId}
            onChange={(e) => setDistributorId(e.target.value)}
            className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Select a distributor...</option>
            {distributors?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
            <option value="other">Other / One-off purchase</option>
          </select>
        </CardContent>
      </Card>

      {/* Upload mode toggle */}
      <div className="flex gap-2">
        <Button
          variant={mode === 'pdf' ? 'default' : 'outline'}
          onClick={() => setMode('pdf')}
          className="flex-1"
        >
          <FileText className="h-4 w-4 mr-2" />
          PDF
        </Button>
        <Button
          variant={mode === 'image' ? 'default' : 'outline'}
          onClick={() => setMode('image')}
          className="flex-1"
        >
          <Image className="h-4 w-4 mr-2" />
          Screenshot
        </Button>
        <Button
          variant={mode === 'email' ? 'default' : 'outline'}
          onClick={() => setMode('email')}
          className="flex-1"
        >
          <Mail className="h-4 w-4 mr-2" />
          Email
        </Button>
      </div>

      {/* PDF Upload */}
      {mode === 'pdf' && (
        <Card>
          <CardContent className="pt-6">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={cn(
                'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
                dragActive ? 'border-primary bg-primary/5' : 'border-gray-200',
                file ? 'bg-green-50 border-green-300' : ''
              )}
            >
              {file ? (
                <div className="space-y-2">
                  <FileText className="h-10 w-10 mx-auto text-green-600" />
                  <p className="font-medium text-green-800">{file.name}</p>
                  <p className="text-sm text-green-600">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFile(null)}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <UploadIcon className="h-10 w-10 mx-auto text-gray-400" />
                  <div>
                    <p className="text-gray-600">Drag and drop a PDF here, or</p>
                    <Label htmlFor="file-upload" className="cursor-pointer">
                      <span className="text-primary hover:underline">browse files</span>
                      <Input
                        id="file-upload"
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </Label>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Screenshot/Image Upload */}
      {mode === 'image' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Screenshot Upload</CardTitle>
            <CardDescription>
              Paste a screenshot (Cmd+V / Ctrl+V), drag and drop an image, or browse files
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              ref={dropZoneRef}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={cn(
                'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
                dragActive ? 'border-primary bg-primary/5' : 'border-gray-200',
                imagePreview ? 'bg-green-50 border-green-300' : ''
              )}
            >
              {imagePreview ? (
                <div className="space-y-4">
                  <img
                    src={imagePreview}
                    alt="Invoice preview"
                    className="max-h-64 mx-auto rounded border"
                  />
                  <p className="font-medium text-green-800">
                    {imageFile?.name || 'Pasted image'}
                  </p>
                  <p className="text-sm text-green-600">
                    {imageFile ? `${(imageFile.size / 1024).toFixed(1)} KB` : ''}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setImageFile(null)
                      setImagePreview(null)
                    }}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <Image className="h-10 w-10 mx-auto text-gray-400" />
                  <div className="space-y-2">
                    <p className="text-gray-600 font-medium">
                      Paste screenshot here (Cmd+V)
                    </p>
                    <p className="text-gray-500 text-sm">
                      or drag and drop an image, or{' '}
                      <Label htmlFor="image-upload" className="cursor-pointer">
                        <span className="text-primary hover:underline">browse files</span>
                        <Input
                          id="image-upload"
                          type="file"
                          accept="image/*"
                          onChange={handleImageFileChange}
                          className="hidden"
                        />
                      </Label>
                    </p>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Email Content */}
      {mode === 'email' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Email Content</CardTitle>
            <CardDescription>
              Paste the email body (HTML or plain text) containing invoice details
            </CardDescription>
          </CardHeader>
          <CardContent>
            <textarea
              value={emailContent}
              onChange={(e) => setEmailContent(e.target.value)}
              placeholder="Paste invoice email content here..."
              rows={12}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring font-mono"
            />
          </CardContent>
        </Card>
      )}

      {/* Error display */}
      {uploadMutation.isError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-red-800">{(uploadMutation.error as Error).message}</p>
          </CardContent>
        </Card>
      )}

      {/* Submit */}
      <Button
        onClick={() => uploadMutation.mutate()}
        disabled={!canSubmit || uploadMutation.isPending}
        className="w-full"
        size="lg"
      >
        {uploadMutation.isPending ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Parsing Invoice...
          </>
        ) : (
          <>
            <UploadIcon className="h-4 w-4 mr-2" />
            Upload & Parse
          </>
        )}
      </Button>
    </div>
  )
}
