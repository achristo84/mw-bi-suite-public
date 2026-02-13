# Custom Parsing Prompts Feature

## Overview

Allow per-distributor custom prompts for invoice and price parsing to handle different invoice formats. Users can edit prompts via a retry modal when parsing fails or produces incorrect results.

## Requirements

1. **Per-distributor prompts**: Each distributor has 3 custom prompt columns:
   - `parsing_prompt_pdf` - For PDF invoice/price parsing
   - `parsing_prompt_email` - For email text parsing
   - `parsing_prompt_screenshot` - For image/screenshot parsing

2. **Prompt inheritance**: If no custom prompt exists, use the default system prompt

3. **Retry modal**: When clicking "retry" on parse results:
   - Show the source content (image/PDF preview/email text)
   - Left column: Original prompt + original parse results
   - Right column: Editable prompt + new results (after "Try")
   - User can iterate: edit prompt → Try → see results → repeat
   - Checkboxes to select which prompt types to update (PDF, email, screenshot)
   - "Save & Accept" commits the new prompt to distributor and accepts results

4. **Applies to both parsers**:
   - Invoice parsing (InvoiceReview page)
   - Price parsing (PriceIngredientModal Upload tab)

---

## Implementation Tasks

### Phase 1: Database & Backend Schema ✅ COMPLETE

#### 1.1 Migration ✅
- File: `alembic/versions/013_add_distributor_parsing_prompts.py`
- Adds: `parsing_prompt_pdf`, `parsing_prompt_email`, `parsing_prompt_screenshot` columns

```bash
DB_PASSWORD="$DB_PASSWORD" DB_PORT=5434 python3 -m alembic upgrade head
```

#### 1.2 Update Distributor Model ✅
- File: `app/models/distributor.py`
- Added columns: `parsing_prompt_pdf`, `parsing_prompt_email`, `parsing_prompt_screenshot`

#### 1.3 Update Distributor Schemas ✅
- File: `app/schemas/distributor.py`
- Added to `DistributorBase`, `DistributorUpdate`: prompt fields

---

### Phase 2: Parser Updates ✅ COMPLETE

#### 2.1 Invoice Parser ✅
- File: `app/services/invoice_parser.py`
- Added `custom_prompt` parameter to all parse methods
- Added `prompt_used` field to `ParsedInvoice` dataclass
- Methods: `parse_invoice`, `parse_invoice_from_gcs`, `parse_invoice_from_image`, `parse_invoice_from_text`

#### 2.2 Price Parser ✅
- File: `app/services/price_parser.py`
- Added `custom_prompt` parameter to `parse_price_content`
- Added `prompt_used` field to `ParseResult` dataclass
- Added `DEFAULT_PRICE_PARSE_PROMPT` constant and `get_default_price_prompt()` function

---

### Phase 3: API Endpoints ✅ COMPLETE

#### 3.1 Distributor Prompts API ✅
- File: `app/api/distributors.py`
- Added `GET /{distributor_id}/prompts` - returns all prompts (custom or default)
- Added `PATCH /{distributor_id}/prompts` - updates prompts based on checkboxes
- Added schemas: `DistributorPromptsResponse`, `DistributorPromptsUpdate`

#### 3.2 Invoice Reparse Preview ✅
- File: `app/api/invoices.py`
- Added `POST /{invoice_id}/reparse-preview` - preview parse without saving
- Accepts `custom_prompt` in request body
- Returns parsed line items AND `prompt_used`
- Does NOT modify database - for preview only

#### 3.3 Price Parse with Prompt ✅
- File: `app/api/ingredients.py`
- Updated `POST /prices/parse` to accept `custom_prompt` in request
- Updated response to include `prompt_used`
- Falls back to distributor's custom prompt if not provided

---

### Phase 4: Frontend Types ✅ COMPLETE

#### 4.1 Add types (`frontend/src/types/invoice.ts`) ✅

```typescript
interface DistributorPrompts {
  pdf: string
  email: string
  screenshot: string
  has_custom_pdf: boolean
  has_custom_email: boolean
  has_custom_screenshot: boolean
}

interface ReparseWithPromptResponse {
  results: InvoiceLine[] | ParsedPriceItem[]
  prompt_used: string
}
```

#### 4.2 Add API functions (`frontend/src/lib/api.ts`) ✅

```typescript
export async function getDistributorPrompts(distributorId: string): Promise<DistributorPrompts>
export async function updateDistributorPrompts(distributorId: string, update: {
  prompt: string
  update_pdf?: boolean
  update_email?: boolean
  update_screenshot?: boolean
}): Promise<void>
export async function reparseInvoiceWithPrompt(invoiceId: string, customPrompt?: string): Promise<ReparseWithPromptResponse>
export async function parsePriceContentWithPrompt(
  content: string,
  contentType: string,
  distributorId?: string,
  customPrompt?: string
): Promise<{ items: ParsedPriceItem[], prompt_used: string }>
```

---

### Phase 5: Prompt Editor Modal ✅ COMPLETE

#### 5.1 Create Component ✅
- File: `frontend/src/components/PromptEditorModal.tsx`

**Props:**
```typescript
interface PromptEditorModalProps {
  isOpen: boolean
  onClose: () => void
  distributorId: string | null
  contentType: 'pdf' | 'email' | 'screenshot'
  sourceContent: string | null  // Base64 for images, text for email
  sourceContentType: string  // MIME type
  originalPrompt: string
  originalResults: any[]
  onAccept: (newPrompt: string, results: any[], updateTypes: {pdf: boolean, email: boolean, screenshot: boolean}) => void
  onReparse: (prompt: string) => Promise<{results: any[], prompt_used: string}>
}
```

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Edit Parsing Prompt                                                     [×] │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │              SOURCE CONTENT (image preview / email text)                │ │
│ │                        (scrollable, max-height)                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│   ORIGINAL                          │   NEW                                 │
│ ┌─────────────────────────────────┐ │ ┌─────────────────────────────────┐   │
│ │ Prompt (read-only)              │ │ │ Prompt (editable textarea)      │   │
│ │                                 │ │ │                                 │   │
│ └─────────────────────────────────┘ │ └─────────────────────────────────┘   │
│ Results:                            │ Results: (after Try)                  │
│ ┌─────────────────────────────────┐ │ ┌─────────────────────────────────┐   │
│ │ • Line 1: Milk, 9 QT, $28.21   │ │ │ • Line 1: Milk, 9 QT, $28.21   │   │
│ │ • Line 2: Cheese, 20 LB, $151  │ │ │ • Line 2: Cheese, 20 LB, $151  │   │
│ └─────────────────────────────────┘ │ └─────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Save this prompt for:                                                       │
│ ☑ PDF invoices  ☑ Email invoices  ☐ Screenshots                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                              [Try]  [Cancel]  [Save & Accept]│
└─────────────────────────────────────────────────────────────────────────────┘
```

**Behavior:**
1. Opens with original prompt in both columns
2. User edits prompt in right column
3. User clicks "Try" → calls onReparse → shows new results
4. User can iterate (edit → try → see results)
5. User checks which prompt types to update
6. User clicks "Save & Accept":
   - Calls onAccept with new prompt, results, and update flags
   - Parent updates distributor prompts and accepts results
7. "Cancel" closes without saving

---

### Phase 6: Integration ✅ COMPLETE

#### 6.1 InvoiceReview Page ✅
- File: `frontend/src/pages/InvoiceReview.tsx`

Replace existing "Reparse" button behavior:
1. On click, fetch current prompt for distributor
2. Open PromptEditorModal with:
   - sourceContent: invoice PDF (stored or re-fetched)
   - originalPrompt: distributor's prompt or default
   - originalResults: current invoice lines
3. onReparse: call `reparseInvoiceWithPrompt()`
4. onAccept: update distributor prompts + refresh invoice data

#### 6.2 PriceIngredientModal ✅
- File: `frontend/src/components/PriceIngredientModal.tsx`

In Upload tab:
1. After parse completes, show "Retry" button next to results
2. Store the source content and results
3. On retry click, open PromptEditorModal
4. onReparse: call `parsePriceContentWithPrompt()`
5. onAccept: update distributor prompts + use new results

---

## Default Prompts Reference

### Invoice Prompt (PDF/Email)
Located in `app/services/invoice_parser.py` as `INVOICE_PARSE_PROMPT`
- ~110 lines covering quantity calculation, pack patterns, unit extraction

### Price Prompt (Screenshot)
Located in `app/services/price_parser.py` as `_build_parse_prompt()` function
- ~50 lines covering item extraction, unit conversion

---

## Testing Checklist

- [ ] Migration runs successfully
- [ ] Distributor prompts API works (GET/PATCH)
- [ ] Invoice reparse with custom prompt works
- [ ] Price parse with custom prompt works
- [ ] PromptEditorModal displays correctly
- [ ] Side-by-side comparison works
- [ ] "Try" re-parses with new prompt
- [ ] Checkboxes correctly control which prompts get updated
- [ ] "Save & Accept" persists prompts and results
- [ ] Default prompts used when no custom prompt exists
