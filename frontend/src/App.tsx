import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { Layout } from '@/components/Layout'
import { InvoiceList } from '@/pages/InvoiceList'
import { InvoiceReview } from '@/pages/InvoiceReview'
import { Upload } from '@/pages/Upload'
import { Settings } from '@/pages/Settings'
import { IngredientsList } from '@/pages/IngredientsList'
import { MapSkus } from '@/pages/MapSkus'
import { Prices } from '@/pages/Prices'
import { Recipes } from '@/pages/Recipes'
import { RecipeDetail } from '@/pages/RecipeDetail'
import { RecipeEdit } from '@/pages/RecipeEdit'
import { IngredientDetail } from '@/pages/IngredientDetail'
import { OrderHub } from '@/pages/OrderHub'
import { CartBuilder } from '@/pages/CartBuilder'
import { OrderHistory } from '@/pages/OrderHistory'
import { ItemPriceHistory } from '@/pages/ItemPriceHistory'
import { Menu } from '@/pages/Menu'
import { MenuAnalyzer } from '@/pages/MenuAnalyzer'
import { MenuItemDetail } from '@/pages/MenuItemDetail'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
})

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<InvoiceList />} />
              <Route path="/invoices/:id" element={<InvoiceReview />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/orders" element={<OrderHub />} />
              <Route path="/orders/build" element={<CartBuilder />} />
              <Route path="/orders/history" element={<OrderHistory />} />
              <Route path="/orders/prices" element={<ItemPriceHistory />} />
              <Route path="/menu" element={<Menu />} />
              <Route path="/menu/analyze" element={<MenuAnalyzer />} />
              <Route path="/menu/:id" element={<MenuItemDetail />} />
              <Route path="/recipes" element={<Recipes />} />
              <Route path="/recipes/new" element={<RecipeEdit />} />
              <Route path="/recipes/:id" element={<RecipeDetail />} />
              <Route path="/recipes/:id/edit" element={<RecipeEdit />} />
              <Route path="/ingredients" element={<IngredientsList />} />
              <Route path="/ingredients/map" element={<MapSkus />} />
              <Route path="/ingredients/:id" element={<IngredientDetail />} />
              <Route path="/prices" element={<Prices />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
