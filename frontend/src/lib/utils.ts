import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number | null | undefined): string {
  if (cents == null) return "-"
  return `$${(cents / 100).toFixed(2)}`
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return "-"
  return new Date(date).toLocaleDateString()
}

export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence == null) return "-"
  return `${Math.round(confidence * 100)}%`
}
