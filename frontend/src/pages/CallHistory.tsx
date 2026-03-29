import { useQuery } from '@tanstack/react-query'
import { useState, useMemo, useCallback } from 'react'
import { getCalls, getCallUsage, type CallRecord, type CallScenario, type TranscriptMessage } from '../api/client'
import { formatDate, formatDuration, SCENARIO_LABELS } from '../utils/format'

type DateFilter = '' | 'today' | 'week' | 'month'

const PAGE_SIZES = [10, 20, 50] as const

const SCENARIO_ICONS: Record<CallScenario | 'all', React.ReactNode> = {
  all: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
    </svg>
  ),
  booking: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  ),
  cancellation: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z" />
    </svg>
  ),
  faq: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
    </svg>
  ),
  out_of_scope: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
    </svg>
  ),
  error: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  ),
}

const DATE_FILTERS: { value: DateFilter; label: string }[] = [
  { value: '',      label: 'Toutes les dates' },
  { value: 'today', label: "Aujourd'hui" },
  { value: 'week',  label: 'Cette semaine' },
  { value: 'month', label: 'Ce mois' },
]

const READ_CALLS_KEY = 'declio_read_calls'

function getReadCalls(): Set<string> {
  try {
    const raw = localStorage.getItem(READ_CALLS_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw) as string[])
  } catch {
    return new Set()
  }
}

function markCallAsRead(callId: string) {
  const readSet = getReadCalls()
  readSet.add(callId)
  localStorage.setItem(READ_CALLS_KEY, JSON.stringify([...readSet]))
}

function getDateThreshold(filter: DateFilter): Date | null {
  if (!filter) return null
  const now = new Date()
  if (filter === 'today') {
    return new Date(now.getFullYear(), now.getMonth(), now.getDate())
  }
  if (filter === 'week') {
    const d = new Date(now)
    d.setDate(d.getDate() - d.getDay() + 1)
    d.setHours(0, 0, 0, 0)
    return d
  }
  return new Date(now.getFullYear(), now.getMonth(), 1)
}

export function CallHistory() {
  const [scenarioFilter, setScenarioFilter] = useState<'' | CallScenario>('')
  const [dateFilter, setDateFilter] = useState<DateFilter>('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState<number>(20)
  const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null)
  const [readCalls, setReadCalls] = useState<Set<string>>(getReadCalls)

  const { data: calls, isLoading, isError } = useQuery({
    queryKey: ['calls'],
    queryFn: () => getCalls(),
    retry: false,
  })

  const threshold = getDateThreshold(dateFilter)
  const searchLower = search.toLowerCase().trim()

  const filtered = useMemo(() =>
    (calls ?? [])
      .filter(c => !scenarioFilter || c.scenario === scenarioFilter)
      .filter(c => !threshold || new Date(c.created_at) >= threshold)
      .filter(c => {
        if (!searchLower) return true
        return (
          c.caller_phone.toLowerCase().includes(searchLower) ||
          c.summary.toLowerCase().includes(searchLower)
        )
      })
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [calls, scenarioFilter, threshold, searchLower],
  )

  const scenarioCounts = useMemo(() => {
    const all = calls ?? []
    const counts: Record<string, number> = { all: all.length }
    for (const c of all) {
      counts[c.scenario] = (counts[c.scenario] ?? 0) + 1
    }
    return counts
  }, [calls])

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, totalPages - 1)
  const paged = filtered.slice(safePage * pageSize, (safePage + 1) * pageSize)

  function setFilterAndReset<T>(setter: (v: T) => void, value: T) {
    setter(value)
    setPage(0)
  }

  const handleOpenDetail = useCallback((call: CallRecord) => {
    markCallAsRead(call.id)
    setReadCalls(getReadCalls())
    setSelectedCall(call)
  }, [])

  function exportCsv() {
    const header = 'Date,Appelant,Duree (s),Scenario,Resume,Cout EUR'
    const rows = filtered.map(c =>
      [
        formatDate(c.created_at),
        c.caller_phone,
        c.duration_seconds,
        SCENARIO_LABELS[c.scenario] ?? c.scenario,
        `"${(c.summary ?? '').replace(/"/g, '""')}"`,
        c.total_cost_eur.toFixed(4),
      ].join(',')
    )
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `declio-appels-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-stone-900">Historique des appels</h1>
          <p className="mt-1 text-sm text-stone-500">
            {calls
              ? `${calls.length} appel${calls.length !== 1 ? 's' : ''} au total`
              : 'Chargement...'}
          </p>
        </div>
        {calls && filtered.length > 0 && (
          <button
            onClick={exportCsv}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-stone-600 bg-white rounded-xl border border-stone-200/60 hover:bg-stone-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Exporter CSV
          </button>
        )}
      </div>

      {/* Stat cards (scenario filters) */}
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatFilterCard
          label="Tous"
          count={scenarioCounts['all'] ?? 0}
          icon={SCENARIO_ICONS['all']}
          active={scenarioFilter === ''}
          onClick={() => setFilterAndReset(setScenarioFilter, '' as '' | CallScenario)}
        />
        {(['booking', 'cancellation', 'faq', 'out_of_scope', 'error'] as CallScenario[]).map(s => (
          <StatFilterCard
            key={s}
            label={SCENARIO_LABELS[s]}
            count={scenarioCounts[s] ?? 0}
            icon={SCENARIO_ICONS[s]}
            active={scenarioFilter === s}
            onClick={() => setFilterAndReset(setScenarioFilter, s)}
          />
        ))}
      </div>

      {/* Search + date filter */}
      <div className="mt-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={e => setFilterAndReset(setSearch, e.target.value)}
            placeholder="Rechercher par numero ou resume..."
            className="block w-full pl-10 pr-3 py-2.5 border border-stone-200 rounded-xl text-sm bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none transition-colors"
          />
        </div>
        <select
          value={dateFilter}
          onChange={e => setFilterAndReset(setDateFilter, e.target.value as DateFilter)}
          className="px-3 py-2.5 border border-stone-200 rounded-xl text-sm bg-white text-stone-700 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none transition-colors sm:w-48"
        >
          {DATE_FILTERS.map(f => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      {isLoading ? (
        <TableSkeleton />
      ) : isError ? (
        <div className="mt-8 text-center py-12">
          <p className="text-sm text-stone-500">Impossible de joindre le serveur. Verifiez que le backend est lance.</p>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState hasFilter={!!(scenarioFilter || dateFilter || search)} />
      ) : (
        <>
          {/* Results count + per page selector */}
          <div className="mt-6 flex items-center justify-between">
            <p className="text-sm text-stone-500">
              {filtered.length} resultat{filtered.length !== 1 ? 's' : ''}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm text-stone-400">Par page</span>
              <select
                value={pageSize}
                onChange={e => {
                  setPageSize(Number(e.target.value))
                  setPage(0)
                }}
                className="px-2 py-1 border border-stone-200 rounded-lg text-sm bg-white text-stone-700 focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none"
              >
                {PAGE_SIZES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Table card */}
          <div className="mt-3 bg-white rounded-2xl border border-stone-200/60 overflow-hidden">
            {/* Desktop table */}
            <div className="hidden md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-100">
                    <th className="px-5 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-stone-400">Date</th>
                    <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-stone-400">Appelant</th>
                    <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-stone-400">Duree</th>
                    <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-stone-400">Type</th>
                    <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-stone-400">Resume</th>
                    <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-stone-400">Cout</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100/80">
                  {paged.map(call => {
                    const isRead = readCalls.has(call.id)
                    return (
                      <tr
                        key={call.id}
                        onClick={() => handleOpenDetail(call)}
                        className={`cursor-pointer transition-colors hover:bg-stone-50 ${isRead ? '' : 'bg-primary-50/30'}`}
                      >
                        <td className="px-5 py-3.5 whitespace-nowrap text-stone-900">
                          {formatDate(call.created_at)}
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap text-stone-500 font-mono text-xs">
                          {call.caller_phone}
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap text-stone-500">
                          {formatDuration(call.duration_seconds)}
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap text-stone-500 text-xs">
                          {SCENARIO_LABELS[call.scenario]}
                        </td>
                        <td className="px-4 py-3.5 max-w-xs">
                          <span className={`truncate block ${isRead ? 'text-stone-500' : 'text-stone-700 font-medium'}`}>
                            {call.summary || 'Aucun resume'}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-right whitespace-nowrap font-mono text-xs text-stone-500">
                          {call.total_cost_eur > 0 ? `${call.total_cost_eur.toFixed(3)} EUR` : '--'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-stone-100/80">
              {paged.map(call => {
                const isRead = readCalls.has(call.id)
                return (
                  <div
                    key={call.id}
                    onClick={() => handleOpenDetail(call)}
                    className={`p-4 cursor-pointer transition-colors hover:bg-stone-50 ${isRead ? '' : 'bg-primary-50/30'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-stone-900">{formatDate(call.created_at)}</span>
                      <span className="text-xs text-stone-400">{SCENARIO_LABELS[call.scenario]}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-sm text-stone-500">
                      <span className="font-mono text-xs">{call.caller_phone}</span>
                      <span>{formatDuration(call.duration_seconds)}</span>
                      {call.total_cost_eur > 0 && (
                        <span className="font-mono text-xs">{call.total_cost_eur.toFixed(3)} EUR</span>
                      )}
                    </div>
                    <p className={`mt-1.5 text-sm truncate ${isRead ? 'text-stone-500' : 'text-stone-700 font-medium'}`}>
                      {call.summary || 'Aucun resume'}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-stone-400">
              Page {safePage + 1}/{totalPages}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={safePage === 0}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-white border border-stone-200/60 text-stone-600 hover:bg-stone-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Precedent
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={safePage >= totalPages - 1}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-white border border-stone-200/60 text-stone-600 hover:bg-stone-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Suivant
              </button>
            </div>
          </div>
        </>
      )}

      {/* Detail panel */}
      {selectedCall && (
        <CallDetailPanel call={selectedCall} onClose={() => setSelectedCall(null)} />
      )}
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatFilterCard({ label, count, icon, active, onClick }: {
  label: string
  count: number
  icon: React.ReactNode
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all ${
        active
          ? 'bg-white border-2 border-primary-500'
          : 'bg-white border border-stone-200/60 hover:border-stone-300'
      }`}
    >
      <div className={`shrink-0 ${active ? 'text-primary-600' : 'text-stone-400'}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className={`text-lg font-semibold leading-tight ${active ? 'text-primary-700' : 'text-stone-900'}`}>
          {count}
        </div>
        <div className="text-xs text-stone-500 truncate">{label}</div>
      </div>
    </button>
  )
}

/** Parse "Assistant: ...\nPatient: ..." plain text into TranscriptMessage[] */
function parseSummaryToMessages(summary: string): TranscriptMessage[] {
  if (!summary) return []
  const messages: TranscriptMessage[] = []
  const lines = summary.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const assistantMatch = trimmed.match(/^Assistant\s*:\s*(.+)/i)
    if (assistantMatch) {
      messages.push({ role: 'assistant', content: assistantMatch[1], timestamp: '' })
      continue
    }
    const patientMatch = trimmed.match(/^Patient\s*:\s*(.+)/i)
    if (patientMatch) {
      messages.push({ role: 'visitor', content: patientMatch[1], timestamp: '' })
      continue
    }
    if (messages.length > 0) {
      messages[messages.length - 1].content += ' ' + trimmed
    }
  }
  return messages
}

function CallDetailPanel({ call, onClose }: { call: CallRecord; onClose: () => void }) {
  const { data: usageRows } = useQuery({
    queryKey: ['call-usage', call.id],
    queryFn: () => getCallUsage(call.id),
    retry: false,
  })

  const messages = call.transcript.length > 0
    ? call.transcript
    : parseSummaryToMessages(call.summary)

  return (
    <>
      <div className="fixed inset-0 bg-black/15 backdrop-blur-sm z-40 animate-fade-in" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white shadow-xl overflow-y-auto animate-slide-in-right border-l border-stone-200/60">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-stone-900">Detail de l'appel</h2>
            <button onClick={onClose} className="p-1 text-stone-400 hover:text-stone-600 transition-colors">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Meta */}
          <div className="space-y-3">
            <DetailRow label="Date" value={formatDate(call.created_at)} />
            <DetailRow label="Appelant" value={call.caller_phone} mono />
            <DetailRow label="Duree" value={formatDuration(call.duration_seconds)} />
            <DetailRow label="Type" value={SCENARIO_LABELS[call.scenario]} />
          </div>

          {/* Conversation */}
          {messages.length > 0 ? (
            <div className="mt-6 pt-6 border-t border-stone-100">
              <h3 className="text-sm font-medium text-stone-900 mb-4">Conversation</h3>
              <div className="space-y-3">
                {messages.map((msg, i) => (
                  <ChatBubble key={i} message={msg} />
                ))}
              </div>
            </div>
          ) : call.summary ? (
            <div className="mt-6 pt-6 border-t border-stone-100">
              <h3 className="text-sm font-medium text-stone-900 mb-2">Resume</h3>
              <p className="text-sm text-stone-600 leading-relaxed whitespace-pre-wrap">
                {call.summary}
              </p>
            </div>
          ) : null}

          {/* Actions taken */}
          {call.actions_taken.length > 0 && (
            <div className="mt-6 pt-6 border-t border-stone-100">
              <h3 className="text-sm font-medium text-stone-900 mb-2">Actions effectuees</h3>
              <ul className="space-y-1.5">
                {call.actions_taken.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-stone-600">
                    <svg className="w-4 h-4 text-primary-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Cost breakdown */}
          {(call.total_cost_eur > 0 || (usageRows && usageRows.length > 0)) && (
            <div className="mt-6 pt-6 border-t border-stone-100">
              <h3 className="text-sm font-medium text-stone-900 mb-3">Cout de l'appel</h3>

              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-stone-50 rounded-xl p-3 text-center">
                  <div className="text-xs text-stone-400">LLM</div>
                  <div className="text-sm font-semibold text-stone-900">${call.llm_cost_usd.toFixed(4)}</div>
                </div>
                <div className="bg-stone-50 rounded-xl p-3 text-center">
                  <div className="text-xs text-stone-400">STT</div>
                  <div className="text-sm font-semibold text-stone-900">${call.stt_cost_usd.toFixed(4)}</div>
                </div>
                <div className="bg-stone-50 rounded-xl p-3 text-center">
                  <div className="text-xs text-stone-400">TTS</div>
                  <div className="text-sm font-semibold text-stone-900">${call.tts_cost_usd.toFixed(4)}</div>
                </div>
              </div>
              <div className="flex items-center justify-between py-2.5 bg-primary-50 rounded-xl px-4">
                <span className="text-sm font-medium text-stone-700">Total</span>
                <span className="text-sm font-bold text-primary-700">{call.total_cost_eur.toFixed(3)} EUR</span>
              </div>

              {/* Per-turn detail */}
              {usageRows && usageRows.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-medium text-stone-400 uppercase tracking-wider mb-2">Detail par tour</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-stone-200">
                          <th className="py-1.5 text-left text-stone-400 font-medium">Service</th>
                          <th className="py-1.5 text-left text-stone-400 font-medium">Tour</th>
                          <th className="py-1.5 text-right text-stone-400 font-medium">Tokens</th>
                          <th className="py-1.5 text-right text-stone-400 font-medium">Cout</th>
                          <th className="py-1.5 text-left text-stone-400 font-medium">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-50">
                        {usageRows.map((row, i) => (
                          <tr key={i}>
                            <td className="py-1.5 text-stone-600 text-xs uppercase">
                              {row.service}
                            </td>
                            <td className="py-1.5 text-stone-500">
                              {row.service === 'llm' ? `#${row.turn_index + 1}` : '\u2014'}
                            </td>
                            <td className="py-1.5 text-right font-mono text-stone-500">
                              {row.service === 'llm' ? row.total_tokens.toLocaleString() : '\u2014'}
                            </td>
                            <td className="py-1.5 text-right font-mono text-stone-900">
                              ${row.cost_usd.toFixed(5)}
                            </td>
                            <td className="py-1.5 text-stone-400">
                              {row.service === 'llm' && row.tool_name ? `tool: ${row.tool_name}` : ''}
                              {row.service === 'stt' ? `${row.duration_seconds}s` : ''}
                              {row.service === 'tts' ? `${row.chars} chars` : ''}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-stone-400">{label}</span>
      <span className={`text-sm text-stone-900 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

function ChatBubble({ message }: { message: TranscriptMessage }) {
  const isAssistant = message.role === 'assistant'

  if (isAssistant) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%]">
          <div className="bg-primary-50 rounded-2xl rounded-tr-sm px-4 py-2.5">
            <span className="text-xs font-medium text-primary-700 block mb-1">Assistant</span>
            <p className="text-sm text-stone-700 leading-relaxed">{message.content}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%]">
        <div className="bg-stone-50 border border-stone-200/60 rounded-2xl rounded-tl-sm px-4 py-2.5">
          <span className="text-xs font-medium text-stone-600 block mb-1">Patient</span>
          <p className="text-sm text-stone-700 leading-relaxed">{message.content}</p>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <div className="mt-8 text-center py-16">
      <svg className="mx-auto w-12 h-12 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
      </svg>
      <h3 className="mt-4 text-sm font-medium text-stone-900">
        {hasFilter ? 'Aucun appel pour ces filtres' : 'Aucun appel traite pour le moment'}
      </h3>
      <p className="mt-1 text-sm text-stone-500">
        {hasFilter
          ? 'Essayez d\'autres filtres ou revenez plus tard.'
          : "Les appels apparaitront ici des que l'assistant vocal sera actif."}
      </p>
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="mt-6 animate-pulse space-y-2">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-12 bg-stone-100 rounded-xl" />
      ))}
    </div>
  )
}
