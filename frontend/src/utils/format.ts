import type { CallScenario } from '../api/client'

export const SCENARIO_LABELS: Record<CallScenario, string> = {
  booking: 'RDV',
  cancellation: 'Annulation',
  faq: 'FAQ',
  out_of_scope: 'Hors perimetre',
  error: 'Erreur',
}

export const SCENARIO_COLORS: Record<CallScenario, string> = {
  booking: 'bg-teal-500',
  cancellation: 'bg-amber-500',
  faq: 'bg-stone-400',
  out_of_scope: 'bg-slate-400',
  error: 'bg-rose-500',
}

/** "26/03/2026 14:30" */
export function formatDate(iso: string) {
  const d = new Date(iso)
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** "2min 30s" or "45s" */
export function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m === 0) return `${s}s`
  return `${m}min ${s > 0 ? `${s}s` : ''}`.trim()
}
