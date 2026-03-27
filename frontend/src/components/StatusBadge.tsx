import type { CallScenario } from '../api/client'

const SCENARIO_CONFIG: Record<CallScenario, { label: string; bg: string; text: string; dot: string }> = {
  booking:      { label: 'RDV',             bg: 'bg-teal-50',   text: 'text-teal-700',  dot: 'bg-teal-500' },
  cancellation: { label: 'Annulation',      bg: 'bg-amber-50',  text: 'text-amber-700', dot: 'bg-amber-500' },
  faq:          { label: 'FAQ',             bg: 'bg-stone-100', text: 'text-stone-700', dot: 'bg-stone-400' },
  out_of_scope: { label: 'Hors perimetre',  bg: 'bg-slate-50',  text: 'text-slate-600', dot: 'bg-slate-400' },
  error:        { label: 'Erreur',          bg: 'bg-rose-50',   text: 'text-rose-700',  dot: 'bg-rose-500' },
}

export function StatusBadge({ scenario }: { scenario: CallScenario }) {
  const config = SCENARIO_CONFIG[scenario] ?? SCENARIO_CONFIG.error
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-medium rounded-full ${config.bg} ${config.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}
