import { Link, Outlet, useLocation } from 'react-router-dom'
import { FileText, Upload, Settings, Menu, X, Package, DollarSign, ChefHat, Link2, ShoppingCart, Search, History, TrendingUp, UtensilsCrossed } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

// Navigation items grouped by section
const navigation = [
  // Order Hub section
  { name: 'Search & Order', href: '/orders', icon: Search, group: 'Order Hub' },
  { name: 'Cart Builder', href: '/orders/build', icon: ShoppingCart, group: 'Order Hub' },
  { name: 'Order History', href: '/orders/history', icon: History, group: 'Order Hub' },
  { name: 'Price History', href: '/orders/prices', icon: TrendingUp, group: 'Order Hub' },
  // Main section
  { name: 'Invoices', href: '/', icon: FileText },
  { name: 'Upload', href: '/upload', icon: Upload },
  { name: 'Menu', href: '/menu', icon: UtensilsCrossed },
  { name: 'Recipes', href: '/recipes', icon: ChefHat },
  { name: 'Ingredients', href: '/ingredients', icon: Package },
  { name: 'Map SKUs', href: '/ingredients/map', icon: Link2 },
  { name: 'Prices', href: '/prices', icon: DollarSign },
  { name: 'Settings', href: '/settings', icon: Settings },
]

// Group navigation items
const groupedNavigation = navigation.reduce((acc, item) => {
  const group = item.group || 'Main'
  if (!acc[group]) acc[group] = []
  acc[group].push(item)
  return acc
}, {} as Record<string, typeof navigation>)

export function Layout() {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 print:bg-white print:min-h-0">
      {/* Mobile menu button */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b px-4 py-3 flex items-center justify-between print:hidden">
        <h1 className="text-lg font-semibold text-gray-900">Mill & Whistle</h1>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </Button>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-white pt-16 overflow-y-auto">
          <nav className="px-4 py-4 space-y-6">
            {Object.entries(groupedNavigation).map(([group, items]) => (
              <div key={group}>
                {group !== 'Main' && (
                  <h3 className="px-4 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {group}
                  </h3>
                )}
                <div className="space-y-1">
                  {items.map((item) => {
                    const isActive = location.pathname === item.href ||
                      (item.href !== '/' && location.pathname.startsWith(item.href))
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={cn(
                          'flex items-center gap-3 px-4 py-3 rounded-lg text-base font-medium',
                          isActive
                            ? 'bg-gray-100 text-gray-900'
                            : 'text-gray-600 hover:bg-gray-50'
                        )}
                      >
                        <item.icon className="h-5 w-5" />
                        {item.name}
                      </Link>
                    )
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col print:!hidden">
        <div className="flex flex-col flex-grow bg-white border-r pt-5 pb-4 overflow-y-auto">
          <div className="flex items-center flex-shrink-0 px-6">
            <h1 className="text-xl font-bold text-gray-900">Mill & Whistle</h1>
          </div>
          <nav className="mt-8 flex-1 px-4 space-y-6">
            {Object.entries(groupedNavigation).map(([group, items]) => (
              <div key={group}>
                {group !== 'Main' && (
                  <h3 className="px-4 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {group}
                  </h3>
                )}
                <div className="space-y-1">
                  {items.map((item) => {
                    const isActive = location.pathname === item.href ||
                      (item.href !== '/' && location.pathname.startsWith(item.href))
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={cn(
                          'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium',
                          isActive
                            ? 'bg-gray-100 text-gray-900'
                            : 'text-gray-600 hover:bg-gray-50'
                        )}
                      >
                        <item.icon className="h-5 w-5" />
                        {item.name}
                      </Link>
                    )
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64 print:pl-0">
        <main className="pt-16 lg:pt-0 p-4 lg:p-8 print:p-0 print:pt-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
