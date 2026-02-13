import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'order-hub-distributor-toggles'

/**
 * Hook for managing distributor toggle state in Order Hub.
 *
 * Persists toggle state to localStorage so user preferences
 * are maintained across sessions.
 */
export function useDistributorToggles() {
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    if (typeof window === 'undefined') return {}
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : {}
    } catch {
      return {}
    }
  })

  // Persist to localStorage whenever toggles change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toggles))
    } catch {
      // Ignore localStorage errors
    }
  }, [toggles])

  /**
   * Set toggle state for a specific distributor
   */
  const setToggle = useCallback((distributorId: string, enabled: boolean) => {
    setToggles(prev => ({ ...prev, [distributorId]: enabled }))
  }, [])

  /**
   * Toggle a distributor's enabled state
   */
  const toggle = useCallback((distributorId: string) => {
    setToggles(prev => ({ ...prev, [distributorId]: prev[distributorId] === false }))
  }, [])

  /**
   * Check if a distributor is enabled (defaults to true if not set)
   */
  const isEnabled = useCallback((distributorId: string): boolean => {
    return toggles[distributorId] !== false
  }, [toggles])

  /**
   * Get list of enabled distributor IDs from a list
   */
  const getEnabledIds = useCallback((distributorIds: string[]): string[] => {
    return distributorIds.filter(id => isEnabled(id))
  }, [isEnabled])

  /**
   * Enable all distributors
   */
  const enableAll = useCallback((distributorIds: string[]) => {
    setToggles(prev => {
      const next = { ...prev }
      distributorIds.forEach(id => { next[id] = true })
      return next
    })
  }, [])

  /**
   * Disable all distributors
   */
  const disableAll = useCallback((distributorIds: string[]) => {
    setToggles(prev => {
      const next = { ...prev }
      distributorIds.forEach(id => { next[id] = false })
      return next
    })
  }, [])

  return {
    toggles,
    setToggle,
    toggle,
    isEnabled,
    getEnabledIds,
    enableAll,
    disableAll,
  }
}
