import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { getCalls, getUsageSummary, type CallScenario } from '../api/client'
import { formatDuration, SCENARIO_LABELS, SCENARIO_COLORS } from '../utils/format'

const ALL_SCENARIOS: CallScenario[] = ['booking', 'cancellation', 'faq', 'out_of_scope', 'error']

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function formatDayLabel(d: Date) {
  return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric' })
}

export function Dashboard() {
  const { data: calls, isLoading, isError } = useQuery({
    queryKey: ['calls'],
    queryFn: () => getCalls(),
    retry: false,
  })

  const { data: usageSummary } = useQuery({
    queryKey: ['usage-summary'],
    queryFn: () => getUsageSummary(),
    retry: false,
  })

  if (isLoading) return <DashboardSkeleton />
  if (isError) {
    return (
      <div className="text-center py-16">
        <p className="text-sm text-stone-500">Impossible de joindre le serveur. Verifiez que le backend est lance.</p>
      </div>
    )
  }

  const allCalls = calls ?? []

  if (allCalls.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-stone-900">Dashboard</h1>
        <p className="mt-1 text-sm text-stone-500">Vue d'ensemble de l'activite de votre assistant vocal.</p>
        <div className="mt-16 text-center py-16">
          <svg className="mx-auto w-14 h-14 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
          </svg>
          <h3 className="mt-4 text-base font-medium text-stone-900">Aucun appel traite</h3>
          <p className="mt-2 text-sm text-stone-500 max-w-sm mx-auto">
            L'assistant vocal n'a pas encore recu d'appels. Les statistiques apparaitront ici des les premiers appels.
          </p>
        </div>
      </div>
    )
  }

  const now = new Date()
  const today = startOfDay(now)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const todayCalls = allCalls.filter(c => new Date(c.created_at) >= today)
  const yesterdayCalls = allCalls.filter(c => {
    const d = new Date(c.created_at)
    return d >= yesterday && d < today
  })

  const callsToday = todayCalls.length
  const callsYesterday = yesterdayCalls.length
  const trendPct = callsYesterday > 0
    ? Math.round(((callsToday - callsYesterday) / callsYesterday) * 100)
    : callsToday > 0 ? 100 : 0

  const avgDuration = allCalls.length > 0
    ? Math.round(allCalls.reduce((s, c) => s + c.duration_seconds, 0) / allCalls.length)
    : 0
  const avgMin = Math.floor(avgDuration / 60)
  const avgSec = avgDuration % 60

  const resolved = allCalls.filter(c => c.scenario !== 'error' && c.scenario !== 'out_of_scope')
  const resolutionRate = allCalls.length > 0 ? Math.round((resolved.length / allCalls.length) * 100) : 0

  // Chart: last 7 days
  const days: Date[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    days.push(d)
  }

  const chartData = days.map(day => {
    const dayCalls = allCalls.filter(c => isSameDay(new Date(c.created_at), day))
    const byScenario: Record<CallScenario, number> = {
      booking: 0, cancellation: 0, faq: 0, out_of_scope: 0, error: 0,
    }
    dayCalls.forEach(c => { byScenario[c.scenario]++ })
    return { day, total: dayCalls.length, byScenario }
  })

  const maxTotal = Math.max(...chartData.map(d => d.total), 1)

  // Scenario breakdown
  const scenarioCounts = ALL_SCENARIOS.map(s => ({
    scenario: s,
    count: allCalls.filter(c => c.scenario === s).length,
  })).filter(s => s.count > 0)

  // Top callers (unique phone numbers, sorted by call count)
  const callerMap = new Map<string, { count: number; lastScenario: CallScenario; totalDuration: number }>()
  for (const c of allCalls) {
    const entry = callerMap.get(c.caller_phone)
    if (entry) {
      entry.count++
      entry.totalDuration += c.duration_seconds
      entry.lastScenario = c.scenario
    } else {
      callerMap.set(c.caller_phone, { count: 1, lastScenario: c.scenario, totalDuration: c.duration_seconds })
    }
  }
  const topCallers = [...callerMap.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5)

  return (
    <div>
      <h1 className="text-2xl font-semibold text-stone-900">Dashboard</h1>
      <p className="mt-1 text-sm text-stone-500">Vue d'ensemble de l'activite de votre assistant vocal.</p>

      {/* Stats cards */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Appels aujourd'hui"
          value={String(callsToday)}
          trend={trendPct}
        />
        <StatCard
          label="Duree moyenne"
          value={`${avgMin}:${String(avgSec).padStart(2, '0')}`}
          subtitle="min:sec"
        />
        <StatCard
          label="Taux de resolution"
          value={`${resolutionRate}%`}
          subtitle={`${resolved.length}/${allCalls.length}`}
        />
        <StatCard
          label="Cout total"
          value={usageSummary ? `${usageSummary.total_cost_eur.toFixed(2)} EUR` : '--'}
        />
      </div>

      {/* Activity chart */}
      <div className="mt-8 bg-white rounded-2xl border border-stone-200/60 p-6">
        <h2 className="text-base font-semibold text-stone-900">Activite — 7 derniers jours</h2>
        <div className="mt-4 flex items-end gap-2 sm:gap-3 h-48">
          {chartData.map((d, i) => (
            <BarColumn key={i} data={d} maxTotal={maxTotal} />
          ))}
        </div>
        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1">
          {ALL_SCENARIOS.map(s => (
            <div key={s} className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${SCENARIO_COLORS[s]}`} />
              <span className="text-xs text-stone-500">{SCENARIO_LABELS[s]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom row: Scenario breakdown + Top callers */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scenario breakdown */}
        <div className="bg-white rounded-2xl border border-stone-200/60 p-6">
          <h2 className="text-base font-semibold text-stone-900">Repartition par type</h2>
          <div className="mt-5 space-y-3">
            {scenarioCounts.map(({ scenario, count }) => {
              const pct = Math.round((count / allCalls.length) * 100)
              return (
                <div key={scenario}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-stone-600">{SCENARIO_LABELS[scenario]}</span>
                    <span className="text-sm text-stone-400">{count} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${SCENARIO_COLORS[scenario]}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          {scenarioCounts.length === 0 && (
            <p className="mt-4 text-sm text-stone-400">Aucune donnee.</p>
          )}
        </div>

        {/* Top callers */}
        <div className="bg-white rounded-2xl border border-stone-200/60 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-stone-900">Appelants frequents</h2>
            <Link to="/calls" className="text-sm text-primary-600 hover:text-primary-700 no-underline font-medium">
              Voir tout
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {topCallers.map(([phone, data]) => (
              <div key={phone} className="flex items-center justify-between py-2">
                <div className="min-w-0">
                  <span className="text-sm font-mono text-stone-900">{phone}</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-stone-400">
                      {data.count} appel{data.count > 1 ? 's' : ''}
                    </span>
                    <span className="text-xs text-stone-300">·</span>
                    <span className="text-xs text-stone-400">{formatDuration(data.totalDuration)}</span>
                  </div>
                </div>
                <span className="text-xs text-stone-400 shrink-0">{SCENARIO_LABELS[data.lastScenario]}</span>
              </div>
            ))}
            {topCallers.length === 0 && (
              <p className="text-sm text-stone-400">Aucun appelant.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, trend, subtitle }: {
  label: string
  value: string
  trend?: number
  subtitle?: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-stone-200/60 p-5">
      <span className="text-sm text-stone-500">{label}</span>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-stone-900">{value}</span>
        {trend !== undefined && trend !== 0 && (
          <span className={`text-xs font-medium ${trend > 0 ? 'text-primary-600' : 'text-rose-600'}`}>
            {trend > 0 ? '+' : ''}{trend}%
          </span>
        )}
        {subtitle && <span className="text-xs text-stone-400">{subtitle}</span>}
      </div>
    </div>
  )
}

function BarColumn({ data, maxTotal }: {
  data: { day: Date; total: number; byScenario: Record<CallScenario, number> }
  maxTotal: number
}) {
  const [hovered, setHovered] = useState(false)
  const heightPct = maxTotal > 0 ? (data.total / maxTotal) * 100 : 0

  return (
    <div
      className="flex-1 flex flex-col items-center gap-1 relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Tooltip */}
      {hovered && data.total > 0 && (
        <div className="absolute bottom-full mb-2 bg-stone-800 text-white text-xs rounded-lg px-3 py-2 whitespace-nowrap z-10 shadow-lg animate-fade-in">
          <div className="font-medium mb-1">{formatDayLabel(data.day)} — {data.total} appel{data.total > 1 ? 's' : ''}</div>
          {ALL_SCENARIOS.map(s => data.byScenario[s] > 0 && (
            <div key={s} className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${SCENARIO_COLORS[s]}`} />
              <span>{SCENARIO_LABELS[s]}: {data.byScenario[s]}</span>
            </div>
          ))}
        </div>
      )}
      {/* Bar */}
      <div className="w-full flex flex-col justify-end rounded-t-md overflow-hidden" style={{ height: '10rem' }}>
        {data.total === 0 ? (
          <div className="w-full bg-stone-100 rounded-t-md" style={{ height: '2px' }} />
        ) : (
          <div className="w-full flex flex-col justify-end" style={{ height: `${heightPct}%` }}>
            {ALL_SCENARIOS.map(s => {
              const count = data.byScenario[s]
              if (count === 0) return null
              const segPct = (count / data.total) * 100
              return (
                <div
                  key={s}
                  className={`w-full ${SCENARIO_COLORS[s]} first:rounded-t-md`}
                  style={{ height: `${segPct}%`, minHeight: '2px' }}
                />
              )
            })}
          </div>
        )}
      </div>
      <span className="text-xs text-stone-400 mt-1">{formatDayLabel(data.day)}</span>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-8 w-48 bg-stone-200 rounded" />
      <div className="h-4 w-72 bg-stone-100 rounded" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-stone-100 rounded-2xl" />
        ))}
      </div>
      <div className="h-64 bg-stone-100 rounded-2xl" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-48 bg-stone-100 rounded-2xl" />
        <div className="h-48 bg-stone-100 rounded-2xl" />
      </div>
    </div>
  )
}
