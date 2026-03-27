import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useCallback } from 'react'
import {
  getAppointments,
  getCabinets,
  createAppointment,
  updateAppointment,
  type Appointment,
  type AppointmentCreate,
  type AppointmentUpdate,
  type WeekSchedule,
} from '../api/client'

// ── Date helpers ──────────────────────────────────────────────────────────────

function getMonday(d: Date): Date {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}

function addDays(d: Date, n: number): Date {
  const date = new Date(d)
  date.setDate(date.getDate() + n)
  return date
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function formatISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function getFirstDayOfMonth(year: number, month: number): Date {
  return new Date(year, month, 1)
}

function getLastDayOfMonth(year: number, month: number): Date {
  return new Date(year, month + 1, 0)
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

const DAY_LABELS = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM'] as const
const DAY_LABELS_FULL = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'] as const
const MONTH_LABELS = [
  'janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre',
]

const SLOT_HEIGHT = 48 // px per 30-min slot
const HOUR_HEIGHT = SLOT_HEIGHT * 2 // 96px per hour

// ── Compute dynamic hours from cabinet config ────────────────────────────────

function computeWorkingHours(horaires?: WeekSchedule): { startHour: number; endHour: number } {
  if (!horaires) return { startHour: 8, endHour: 20 }
  let earliest = 24
  let latest = 0
  for (const sched of Object.values(horaires)) {
    if (sched.closed) continue
    const openH = parseInt(sched.open.split(':')[0], 10)
    const closeH = parseInt(sched.close.split(':')[0], 10)
    const closeM = parseInt(sched.close.split(':')[1], 10)
    if (openH < earliest) earliest = openH
    const effectiveClose = closeM > 0 ? closeH + 1 : closeH
    if (effectiveClose > latest) latest = effectiveClose
  }
  if (earliest >= latest) return { startHour: 8, endHour: 20 }
  return { startHour: earliest, endHour: latest }
}

// ── Overlap layout algorithm ─────────────────────────────────────────────────
// Groups overlapping appointments and assigns column index + total columns

const MAX_VISIBLE_COLS = 3

interface LayoutInfo {
  col: number
  totalCols: number  // capped at MAX_VISIBLE_COLS for positioning
  hidden: boolean    // true if this appt is beyond visible cols
  overflow: number   // how many hidden appts in this cluster (only set on visible ones)
}

interface OverflowBadge {
  count: number
  topPx: number
  heightPx: number
  allAppointments: Appointment[]  // every appt in the cluster (visible + hidden)
}

function computeOverlapLayout(
  appointments: Appointment[],
  startHour: number,
): { layouts: Map<string, LayoutInfo>; overflowBadges: OverflowBadge[] } {
  const layouts = new Map<string, LayoutInfo>()
  const overflowBadges: OverflowBadge[] = []
  if (appointments.length === 0) return { layouts, overflowBadges }

  const sorted = [...appointments].sort((a, b) =>
    new Date(a.date_heure).getTime() - new Date(b.date_heure).getTime()
  )

  // Group overlapping appointments into clusters
  const clusters: Appointment[][] = []
  let currentCluster: Appointment[] = [sorted[0]]
  let clusterEnd = new Date(sorted[0].date_heure).getTime() + sorted[0].duree_minutes * 60000

  for (let i = 1; i < sorted.length; i++) {
    const apptStart = new Date(sorted[i].date_heure).getTime()
    if (apptStart < clusterEnd) {
      currentCluster.push(sorted[i])
      const apptEnd = apptStart + sorted[i].duree_minutes * 60000
      if (apptEnd > clusterEnd) clusterEnd = apptEnd
    } else {
      clusters.push(currentCluster)
      currentCluster = [sorted[i]]
      clusterEnd = apptStart + sorted[i].duree_minutes * 60000
    }
  }
  clusters.push(currentCluster)

  // Assign columns within each cluster, cap visible at MAX_VISIBLE_COLS
  for (const cluster of clusters) {
    const columns: Appointment[][] = []
    for (const appt of cluster) {
      const apptStart = new Date(appt.date_heure).getTime()
      let placed = false
      for (let c = 0; c < columns.length; c++) {
        const lastInCol = columns[c][columns[c].length - 1]
        const lastEnd = new Date(lastInCol.date_heure).getTime() + lastInCol.duree_minutes * 60000
        if (apptStart >= lastEnd) {
          columns[c].push(appt)
          layouts.set(appt.id, { col: c, totalCols: 0, hidden: false, overflow: 0 })
          placed = true
          break
        }
      }
      if (!placed) {
        columns.push([appt])
        layouts.set(appt.id, { col: columns.length - 1, totalCols: 0, hidden: false, overflow: 0 })
      }
    }

    const actualCols = columns.length
    const visibleCols = Math.min(actualCols, MAX_VISIBLE_COLS)
    const hiddenCount = cluster.filter((a) => {
      const info = layouts.get(a.id)!
      return info.col >= MAX_VISIBLE_COLS
    }).length

    for (const appt of cluster) {
      const info = layouts.get(appt.id)!
      info.totalCols = visibleCols
      if (info.col >= MAX_VISIBLE_COLS) {
        info.hidden = true
      }
      // Store overflow count on col 0 items so we can render badge once
      if (info.col === MAX_VISIBLE_COLS - 1 && hiddenCount > 0) {
        info.overflow = hiddenCount
      }
    }

    // Create overflow badge for hidden appointments
    if (hiddenCount > 0) {
      // Position badge at the cluster's time range
      const clusterStartTime = Math.min(...cluster.map((a) => new Date(a.date_heure).getTime()))
      const clusterEndTime = Math.max(...cluster.map((a) => new Date(a.date_heure).getTime() + a.duree_minutes * 60000))
      const startMin = (new Date(clusterStartTime).getHours() * 60 + new Date(clusterStartTime).getMinutes()) - startHour * 60
      const endMin = (new Date(clusterEndTime).getHours() * 60 + new Date(clusterEndTime).getMinutes()) - startHour * 60
      overflowBadges.push({
        count: hiddenCount,
        topPx: (startMin / 60) * HOUR_HEIGHT,
        heightPx: ((endMin - startMin) / 60) * HOUR_HEIGHT,
        allAppointments: cluster,
      })
    }
  }

  return { layouts, overflowBadges }
}

// ── Components ────────────────────────────────────────────────────────────────

type ViewMode = 'week' | 'month'
type ModalMode = 'create' | 'edit' | 'duplicate' | 'reschedule'

function ViewToggle({
  viewMode,
  onChange,
}: {
  viewMode: ViewMode
  onChange: (mode: ViewMode) => void
}) {
  return (
    <div className="flex bg-stone-100 rounded-lg p-0.5">
      <button
        onClick={() => onChange('week')}
        className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
          viewMode === 'week'
            ? 'bg-white text-stone-900 shadow-sm'
            : 'text-stone-500 hover:text-stone-700'
        }`}
      >
        Semaine
      </button>
      <button
        onClick={() => onChange('month')}
        className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
          viewMode === 'month'
            ? 'bg-white text-stone-900 shadow-sm'
            : 'text-stone-500 hover:text-stone-700'
        }`}
      >
        Mois
      </button>
    </div>
  )
}

function AgendaHeader({
  viewMode,
  onViewModeChange,
  label,
  onPrev,
  onNext,
  onToday,
  onNewAppointment,
}: {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  label: string
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onNewAppointment: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Agenda</h1>
        <div className="hidden sm:flex items-center bg-white rounded-lg shadow-sm border border-stone-200">
          <button
            onClick={onPrev}
            className="p-2 text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded-l-lg transition-colors"
            title="Precedent"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div className="w-px h-6 bg-stone-200" />
          <button
            onClick={onNext}
            className="p-2 text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded-r-lg transition-colors"
            title="Suivant"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
          </button>
        </div>
        <span className="hidden sm:block text-sm font-medium text-stone-600">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <ViewToggle viewMode={viewMode} onChange={onViewModeChange} />
        <button
          onClick={onToday}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 shadow-sm transition-colors"
        >
          Aujourd'hui
        </button>
        <button
          onClick={onNewAppointment}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 shadow-sm transition-colors flex items-center gap-1.5"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Nouveau
        </button>
      </div>
    </div>
  )
}

function StatsBar({
  appointments,
  monday,
  startHour,
  endHour,
}: {
  appointments: Appointment[]
  monday: Date
  startHour: number
  endHour: number
}) {
  const today = new Date()
  const confirmed = appointments.filter((a) => a.status === 'confirmed')
  const weekCount = confirmed.length
  const todayCount = confirmed.filter((a) =>
    isSameDay(new Date(a.date_heure), today)
  ).length

  const nextDispo = useMemo(() => {
    if (confirmed.length === 0) return 'Toute la semaine'
    const now = new Date()
    for (let d = 0; d < 6; d++) {
      const day = addDays(monday, d)
      if (day < addDays(now, -1)) continue
      for (let h = startHour; h < endHour; h++) {
        for (const m of [0, 30]) {
          const slotStart = new Date(day)
          slotStart.setHours(h, m, 0, 0)
          if (slotStart < now) continue
          const hasConflict = confirmed.some((a) => {
            const aStart = new Date(a.date_heure)
            const aEnd = new Date(aStart.getTime() + a.duree_minutes * 60000)
            return slotStart >= aStart && slotStart < aEnd
          })
          if (!hasConflict) {
            return `${DAY_LABELS_FULL[d]} ${String(h).padStart(2, '0')}h${String(m).padStart(2, '0')}`
          }
        }
      }
    }
    return 'Aucune'
  }, [confirmed, monday, startHour, endHour])

  const stats = [
    {
      label: 'Cette semaine',
      value: String(weekCount),
      sub: 'rendez-vous',
      color: 'text-stone-900',
      icon: (
        <svg className="w-5 h-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
        </svg>
      ),
    },
    {
      label: "Aujourd'hui",
      value: String(todayCount),
      sub: 'rendez-vous',
      color: todayCount > 0 ? 'text-primary-700' : 'text-stone-900',
      icon: (
        <svg className="w-5 h-5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      label: 'Prochaine dispo',
      value: nextDispo,
      sub: '',
      color: 'text-primary-600',
      icon: (
        <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-white rounded-xl px-4 py-3.5 shadow-sm border border-stone-100 flex items-start gap-3">
          <div className="p-2 bg-stone-50 rounded-lg shrink-0">{s.icon}</div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">{s.label}</p>
            <p className={`text-xl font-bold ${s.color} mt-0.5 truncate`}>{s.value}</p>
            {s.sub && <p className="text-xs text-stone-400">{s.sub}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

function AppointmentBlock({
  appointment,
  layout,
  startHour,
  onClick,
}: {
  appointment: Appointment
  layout: LayoutInfo
  startHour: number
  onClick: () => void
}) {
  const start = new Date(appointment.date_heure)
  const startMinutes = start.getHours() * 60 + start.getMinutes()
  const offsetMinutes = startMinutes - startHour * 60
  const topPx = (offsetMinutes / 60) * HOUR_HEIGHT
  const heightPx = (appointment.duree_minutes / 60) * HOUR_HEIGHT

  const isCancelled = appointment.status === 'cancelled'

  const hour = String(start.getHours()).padStart(2, '0')
  const min = String(start.getMinutes()).padStart(2, '0')

  // Overlap positioning
  const colWidth = 100 / layout.totalCols
  const leftPct = layout.col * colWidth
  const widthPct = colWidth

  return (
    <button
      onClick={onClick}
      className={`absolute rounded-lg text-left cursor-pointer transition-all overflow-hidden group ${
        isCancelled
          ? 'bg-stone-50 border border-stone-200 hover:border-stone-300'
          : 'bg-primary-50 border border-primary-200 hover:border-primary-300 hover:shadow-sm'
      }`}
      style={{
        top: `${topPx + 1}px`,
        height: `${Math.max(heightPx - 2, 28)}px`,
        left: `calc(${leftPct}% + 2px)`,
        width: `calc(${widthPct}% - 4px)`,
      }}
    >
      {/* Left accent bar */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-lg ${
          isCancelled ? 'bg-stone-300' : 'bg-primary-500'
        }`}
      />
      <div className="pl-2.5 pr-1.5 py-1">
        <span
          className={`text-xs font-semibold block truncate leading-tight ${
            isCancelled ? 'text-stone-400 line-through' : 'text-primary-900'
          }`}
        >
          {appointment.patient_nom}
        </span>
        <span
          className={`text-[11px] block leading-tight mt-0.5 ${
            isCancelled ? 'text-stone-400' : 'text-primary-600/70'
          }`}
        >
          {hour}:{min}
        </span>
      </div>
    </button>
  )
}

function DetailPanel({
  appointment,
  onClose,
  onEdit,
  onDuplicate,
  onReschedule,
  onCancel,
}: {
  appointment: Appointment
  onClose: () => void
  onEdit: () => void
  onDuplicate: () => void
  onReschedule: () => void
  onCancel: () => void
}) {
  const start = new Date(appointment.date_heure)
  const end = new Date(start.getTime() + appointment.duree_minutes * 60000)
  const dayStr = start.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const startStr = `${String(start.getHours()).padStart(2, '0')}h${String(start.getMinutes()).padStart(2, '0')}`
  const endStr = `${String(end.getHours()).padStart(2, '0')}h${String(end.getMinutes()).padStart(2, '0')}`
  const isCancelled = appointment.status === 'cancelled'

  const initials = appointment.patient_nom
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-2xl z-40 flex flex-col border-l border-stone-200">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100">
        <h3 className="text-base font-semibold text-stone-900">Rendez-vous</h3>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-stone-400 hover:text-stone-600 hover:bg-stone-100 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {/* Patient card */}
        <div className="px-6 py-5 border-b border-stone-100">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
              isCancelled ? 'bg-stone-100 text-stone-400' : 'bg-primary-100 text-primary-700'
            }`}>
              {initials}
            </div>
            <div className="min-w-0">
              <p className={`text-base font-semibold truncate ${isCancelled ? 'text-stone-400 line-through' : 'text-stone-900'}`}>
                {appointment.patient_nom}
              </p>
              {appointment.patient_telephone && (
                <p className="text-sm text-stone-500">{appointment.patient_telephone}</p>
              )}
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="px-6 py-5 space-y-5">
          {/* Date & time row */}
          <div className="flex items-start gap-3">
            <div className="p-2 bg-stone-50 rounded-lg shrink-0 mt-0.5">
              <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-stone-900 capitalize">{dayStr}</p>
              <p className="text-sm text-stone-500 mt-0.5">{startStr} — {endStr}</p>
            </div>
          </div>

          {/* Duration */}
          <div className="flex items-start gap-3">
            <div className="p-2 bg-stone-50 rounded-lg shrink-0 mt-0.5">
              <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-stone-900">{appointment.duree_minutes} minutes</p>
              <p className="text-sm text-stone-500 mt-0.5">Seance de kinesitherapie</p>
            </div>
          </div>

          {/* Phone */}
          {appointment.patient_telephone && (
            <div className="flex items-start gap-3">
              <div className="p-2 bg-stone-50 rounded-lg shrink-0 mt-0.5">
                <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-stone-900">{appointment.patient_telephone}</p>
                <p className="text-sm text-stone-500 mt-0.5">Telephone</p>
              </div>
            </div>
          )}

          {/* Status */}
          <div className="flex items-start gap-3">
            <div className="p-2 bg-stone-50 rounded-lg shrink-0 mt-0.5">
              {isCancelled ? (
                <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
              ) : (
                <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </div>
            <div>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                  isCancelled
                    ? 'bg-red-50 text-red-600'
                    : 'bg-emerald-50 text-emerald-700'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isCancelled ? 'bg-red-400' : 'bg-emerald-400'}`} />
                {isCancelled ? 'Annule' : 'Confirme'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="px-6 py-4 border-t border-stone-100 bg-stone-50/50">
        {isCancelled ? (
          <p className="text-xs text-stone-400 text-center">Ce rendez-vous a ete annule</p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={onEdit}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
            >
              Modifier
            </button>
            <button
              onClick={onDuplicate}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
            >
              Dupliquer
            </button>
            <button
              onClick={onReschedule}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
            >
              Reporter
            </button>
            <button
              onClick={onCancel}
              className="px-3 py-2 text-sm font-medium rounded-lg border border-red-200 bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
            >
              Annuler RDV
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Current time indicator ────────────────────────────────────────────────────

function NowIndicator({ startHour, endHour }: { startHour: number; endHour: number }) {
  const now = new Date()
  const minutes = now.getHours() * 60 + now.getMinutes()
  const offset = minutes - startHour * 60
  const totalMinutes = (endHour - startHour) * 60
  if (offset < 0 || offset > totalMinutes) return null
  const topPx = (offset / 60) * HOUR_HEIGHT

  return (
    <div className="absolute left-0 right-0 z-10 pointer-events-none" style={{ top: `${topPx}px` }}>
      <div className="flex items-center">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500 -ml-[5px] shrink-0" />
        <div className="flex-1 h-[2px] bg-red-500" />
      </div>
    </div>
  )
}

// ── Appointment Modal ─────────────────────────────────────────────────────────

function AppointmentModal({
  mode,
  appointment,
  cabinetId,
  prefillDate,
  onClose,
  onSaved,
}: {
  mode: ModalMode
  appointment?: Appointment
  cabinetId: string
  prefillDate?: Date
  onClose: () => void
  onSaved: () => void
}) {
  const queryClient = useQueryClient()

  const isReadOnlyPatient = mode === 'reschedule'
  const isNewRecord = mode === 'create' || mode === 'duplicate'

  // Compute default date/time
  const defaultDate = (() => {
    if (mode === 'edit' && appointment) return formatISODate(new Date(appointment.date_heure))
    if (mode === 'reschedule' && appointment) return ''
    if (mode === 'duplicate' && appointment) return ''
    if (prefillDate) return formatISODate(prefillDate)
    return formatISODate(new Date())
  })()

  const defaultTime = (() => {
    if (mode === 'edit' && appointment) {
      const d = new Date(appointment.date_heure)
      return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    }
    if (mode === 'reschedule') return ''
    if (mode === 'duplicate') return ''
    if (prefillDate) {
      return `${String(prefillDate.getHours()).padStart(2, '0')}:${String(prefillDate.getMinutes()).padStart(2, '0')}`
    }
    return '09:00'
  })()

  const [patientNom, setPatientNom] = useState(
    (mode !== 'create' && appointment) ? appointment.patient_nom : ''
  )
  const [patientTel, setPatientTel] = useState(
    (mode !== 'create' && appointment) ? appointment.patient_telephone : ''
  )
  const [date, setDate] = useState(defaultDate)
  const [time, setTime] = useState(defaultTime)
  const [duree, setDuree] = useState(
    appointment ? appointment.duree_minutes : 30
  )
  const [repeatWeeks, setRepeatWeeks] = useState(1)

  const title = {
    create: 'Nouveau rendez-vous',
    edit: 'Modifier le rendez-vous',
    duplicate: 'Dupliquer le rendez-vous',
    reschedule: 'Reporter le rendez-vous',
  }[mode]

  const createMutation = useMutation({
    mutationFn: (data: AppointmentCreate) => createAppointment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      onSaved()
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: AppointmentUpdate) =>
      updateAppointment(appointment!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      onSaved()
    },
  })

  const isSubmitting = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!patientNom.trim() || !date || !time) return

    const dateHeure = `${date}T${time}:00`

    if (isNewRecord) {
      createMutation.mutate({
        cabinet_id: cabinetId,
        patient_nom: patientNom.trim(),
        patient_telephone: patientTel.trim(),
        date_heure: dateHeure,
        duree_minutes: duree,
        repeat_weeks: repeatWeeks,
      })
    } else {
      // edit or reschedule
      const data: AppointmentUpdate = {}
      if (mode === 'edit') {
        data.patient_nom = patientNom.trim()
        data.patient_telephone = patientTel.trim()
        data.duree_minutes = duree
      }
      data.date_heure = dateHeure
      updateMutation.mutate(data)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100">
          <h3 className="text-base font-semibold text-stone-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-600 hover:bg-stone-100 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          {/* Patient */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              Patient <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={patientNom}
              onChange={(e) => setPatientNom(e.target.value)}
              disabled={isReadOnlyPatient}
              placeholder="Nom du patient"
              className={`w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                isReadOnlyPatient ? 'bg-stone-50 text-stone-500' : 'bg-white'
              }`}
              required
            />
          </div>

          {/* Telephone */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              Telephone
            </label>
            <input
              type="tel"
              value={patientTel}
              onChange={(e) => setPatientTel(e.target.value)}
              disabled={isReadOnlyPatient}
              placeholder="06 12 34 56 78"
              className={`w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                isReadOnlyPatient ? 'bg-stone-50 text-stone-500' : 'bg-white'
              }`}
            />
          </div>

          {/* Date + Time */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5">
                Date <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5">
                Heure <span className="text-red-500">*</span>
              </label>
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                step="1800"
                className="w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                required
              />
            </div>
          </div>

          {/* Duree */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              Duree
            </label>
            <select
              value={duree}
              onChange={(e) => setDuree(Number(e.target.value))}
              disabled={mode === 'reschedule'}
              className="w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value={15}>15 minutes</option>
              <option value={30}>30 minutes</option>
              <option value={45}>45 minutes</option>
              <option value={60}>1 heure</option>
              <option value={90}>1h30</option>
              <option value={120}>2 heures</option>
            </select>
          </div>

          {/* Recurrence (only for create/duplicate) */}
          {isNewRecord && (
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5">
                Recurrence
              </label>
              <select
                value={repeatWeeks}
                onChange={(e) => setRepeatWeeks(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 rounded-lg border border-stone-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value={1}>Une seule fois</option>
                <option value={2}>Chaque semaine pendant 2 semaines</option>
                <option value={3}>Chaque semaine pendant 3 semaines</option>
                <option value={4}>Chaque semaine pendant 4 semaines</option>
                <option value={5}>Chaque semaine pendant 5 semaines</option>
                <option value={6}>Chaque semaine pendant 6 semaines</option>
                <option value={8}>Chaque semaine pendant 8 semaines</option>
                <option value={10}>Chaque semaine pendant 10 semaines</option>
                <option value={12}>Chaque semaine pendant 12 semaines</option>
              </select>
              {repeatWeeks > 1 && (
                <p className="mt-1.5 text-xs text-stone-500">
                  {repeatWeeks} rendez-vous seront crees (meme jour/heure chaque semaine)
                </p>
              )}
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
              {error.message}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-stone-100 bg-stone-50/50">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !patientNom.trim() || !date || !time}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isSubmitting && (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            )}
            Enregistrer
          </button>
        </div>
      </form>
    </div>
  )
}

// ── Month view ────────────────────────────────────────────────────────────────

function MonthGrid({
  year,
  month,
  appointments,
  selectedDay,
  onSelectDay,
}: {
  year: number
  month: number
  appointments: Appointment[]
  selectedDay: Date | null
  onSelectDay: (d: Date) => void
}) {
  const today = new Date()
  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfMonth(year, month)
  // Monday = 0, Sunday = 6
  const startDow = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1

  // Build grid cells (6 rows x 7 cols, Mon-Sun, but we only show Mon-Sat = 6 cols)
  // We need to compute which days fall on Mon-Sat
  const cells: (number | null)[] = []
  // Fill leading nulls
  for (let i = 0; i < startDow && i < 6; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(year, month, d)
    const dow = date.getDay() // 0=Sun, 1=Mon...6=Sat
    if (dow === 0) continue // Skip Sundays
    cells.push(d)
  }

  // Group appointments by day number
  const apptsByDay = useMemo(() => {
    const map: Record<number, Appointment[]> = {}
    for (const a of appointments) {
      const d = new Date(a.date_heure)
      if (d.getFullYear() === year && d.getMonth() === month) {
        const day = d.getDate()
        if (!map[day]) map[day] = []
        map[day].push(a)
      }
    }
    return map
  }, [appointments, year, month])

  // Split cells into rows of 6 (Mon-Sat)
  const rows: (number | null)[][] = []
  for (let i = 0; i < cells.length; i += 6) {
    rows.push(cells.slice(i, i + 6))
  }
  // Pad last row
  if (rows.length > 0) {
    const lastRow = rows[rows.length - 1]
    while (lastRow.length < 6) lastRow.push(null)
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-stone-200 overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-6 border-b border-stone-200">
        {DAY_LABELS.map((label) => (
          <div key={label} className="py-2.5 text-center border-r border-stone-100 last:border-r-0">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Grid */}
      {rows.map((row, ri) => (
        <div key={ri} className="grid grid-cols-6 border-b border-stone-100 last:border-b-0">
          {row.map((day, ci) => {
            if (day === null) {
              return (
                <div
                  key={`empty-${ri}-${ci}`}
                  className="min-h-[80px] sm:min-h-[100px] border-r border-stone-100 last:border-r-0 bg-stone-50/50"
                />
              )
            }
            const dateObj = new Date(year, month, day)
            const isToday = isSameDay(dateObj, today)
            const isSelected = selectedDay && isSameDay(dateObj, selectedDay)
            const dayAppts = (apptsByDay[day] || []).filter((a) => a.status === 'confirmed')
            const displayMax = 3
            const extra = dayAppts.length - displayMax

            return (
              <button
                key={day}
                onClick={() => onSelectDay(dateObj)}
                className={`min-h-[80px] sm:min-h-[100px] border-r border-stone-100 last:border-r-0 p-1.5 text-left transition-colors cursor-pointer ${
                  isSelected ? 'bg-primary-50' : 'hover:bg-stone-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <span
                    className={`inline-flex items-center justify-center text-sm font-semibold ${
                      isToday
                        ? 'w-7 h-7 rounded-full bg-primary-600 text-white'
                        : isSelected
                          ? 'text-primary-700'
                          : 'text-stone-700'
                    }`}
                  >
                    {day}
                  </span>
                  {dayAppts.length > 0 && (
                    <span className="text-[10px] font-medium text-stone-400 mt-1">
                      {dayAppts.length}
                    </span>
                  )}
                </div>
                <div className="mt-1 space-y-0.5">
                  {dayAppts.slice(0, displayMax).map((a) => {
                    const t = new Date(a.date_heure)
                    const hh = String(t.getHours()).padStart(2, '0')
                    const mm = String(t.getMinutes()).padStart(2, '0')
                    return (
                      <div
                        key={a.id}
                        className="flex items-center gap-1 px-1 py-0.5 bg-primary-50 rounded text-[10px] truncate"
                      >
                        <span className="w-1 h-1 rounded-full bg-primary-500 shrink-0" />
                        <span className="text-primary-700 font-medium truncate">
                          {hh}:{mm} {a.patient_nom.split(' ')[0]}
                        </span>
                      </div>
                    )
                  })}
                  {extra > 0 && (
                    <span className="text-[10px] text-stone-400 pl-1">
                      +{extra} autre{extra > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}

function DayAppointmentList({
  day,
  appointments,
  onSelect,
}: {
  day: Date
  appointments: Appointment[]
  onSelect: (a: Appointment) => void
}) {
  const dayAppts = appointments
    .filter((a) => isSameDay(new Date(a.date_heure), day))
    .sort((a, b) => new Date(a.date_heure).getTime() - new Date(b.date_heure).getTime())

  const dayStr = day.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="bg-white rounded-xl shadow-sm border border-stone-200 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-stone-100">
        <h3 className="text-sm font-semibold text-stone-900 capitalize">{dayStr}</h3>
        <p className="text-xs text-stone-500 mt-0.5">
          {dayAppts.length === 0
            ? 'Aucun rendez-vous'
            : `${dayAppts.length} rendez-vous`}
        </p>
      </div>
      {dayAppts.length === 0 ? (
        <div className="p-8 text-center">
          <p className="text-sm text-stone-400">Aucun rendez-vous ce jour</p>
        </div>
      ) : (
        <div className="divide-y divide-stone-100">
          {dayAppts.map((appt) => {
            const start = new Date(appt.date_heure)
            const h = String(start.getHours()).padStart(2, '0')
            const m = String(start.getMinutes()).padStart(2, '0')
            const isCancelled = appt.status === 'cancelled'
            return (
              <button
                key={appt.id}
                onClick={() => onSelect(appt)}
                className="w-full text-left px-5 py-3 flex items-center gap-3 hover:bg-stone-50 transition-colors"
              >
                <div className={`w-1 self-stretch rounded-full shrink-0 ${
                  isCancelled ? 'bg-stone-300' : 'bg-primary-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-semibold ${
                      isCancelled ? 'text-stone-400 line-through' : 'text-stone-900'
                    }`}>
                      {appt.patient_nom}
                    </span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      isCancelled
                        ? 'bg-red-50 text-red-500'
                        : 'bg-emerald-50 text-emerald-600'
                    }`}>
                      {isCancelled ? 'Annule' : 'Confirme'}
                    </span>
                  </div>
                  <p className={`text-xs mt-0.5 ${isCancelled ? 'text-stone-400' : 'text-stone-500'}`}>
                    {h}:{m} — {appt.duree_minutes} min
                  </p>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Agenda() {
  const queryClient = useQueryClient()
  const today = new Date()
  const [viewMode, setViewMode] = useState<ViewMode>('week')
  const [monday, setMonday] = useState(() => getMonday(today))
  const [selected, setSelected] = useState<Appointment | null>(null)
  const [mobileDay, setMobileDay] = useState(() => today.getDay() === 0 ? 5 : Math.min(today.getDay() - 1, 5))

  // Month view state
  const [currentMonth, setCurrentMonth] = useState({ year: today.getFullYear(), month: today.getMonth() })
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)

  // Modal state
  const [modalState, setModalState] = useState<{
    open: boolean
    mode: ModalMode
    appointment?: Appointment
    prefillDate?: Date
  }>({ open: false, mode: 'create' })

  // Slot popover state (for overflow "+N" badge click)
  const [slotPopover, setSlotPopover] = useState<{
    appointments: Appointment[]
    anchorRect: DOMRect
  } | null>(null)

  // Fetch cabinet for dynamic hours
  const { data: cabinets } = useQuery({
    queryKey: ['cabinets'],
    queryFn: getCabinets,
  })
  const cabinet = cabinets?.[0]
  const { startHour, endHour } = useMemo(
    () => computeWorkingHours(cabinet?.horaires),
    [cabinet?.horaires]
  )
  const totalHours = endHour - startHour

  // Week data
  const saturday = addDays(monday, 5)
  const dateFrom = formatISODate(monday)
  const dateTo = formatISODate(addDays(saturday, 1))

  const { data: weekAppointments = [], isLoading: weekLoading } = useQuery({
    queryKey: ['appointments', 'week', dateFrom, dateTo],
    queryFn: () => getAppointments(dateFrom, dateTo),
    enabled: viewMode === 'week',
  })

  // Month data
  const monthStart = formatISODate(getFirstDayOfMonth(currentMonth.year, currentMonth.month))
  const monthEnd = formatISODate(addDays(getLastDayOfMonth(currentMonth.year, currentMonth.month), 1))

  const { data: monthAppointments = [], isLoading: monthLoading } = useQuery({
    queryKey: ['appointments', 'month', currentMonth.year, currentMonth.month],
    queryFn: () => getAppointments(monthStart, monthEnd),
    enabled: viewMode === 'month',
  })

  const isLoading = viewMode === 'week' ? weekLoading : monthLoading

  const byDay = useMemo(() => {
    const map: Record<number, Appointment[]> = {}
    for (let i = 0; i < 6; i++) map[i] = []
    for (const appt of weekAppointments) {
      const d = new Date(appt.date_heure)
      const dayOfWeek = d.getDay()
      const idx = dayOfWeek === 0 ? 6 : dayOfWeek - 1
      if (idx >= 0 && idx < 6) {
        map[idx].push(appt)
      }
    }
    return map
  }, [weekAppointments])

  // Overlap layouts per day
  const { overlapLayouts, dayOverflowBadges } = useMemo(() => {
    const layouts = new Map<string, LayoutInfo>()
    const badges: Record<number, OverflowBadge[]> = {}
    for (let i = 0; i < 6; i++) {
      const { layouts: dayLayouts, overflowBadges } = computeOverlapLayout(byDay[i] || [], startHour)
      dayLayouts.forEach((v, k) => layouts.set(k, v))
      badges[i] = overflowBadges
    }
    return { overlapLayouts: layouts, dayOverflowBadges: badges }
  }, [byDay, startHour])

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (id: string) => updateAppointment(id, { status: 'cancelled' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      setSelected(null)
    },
  })

  // Navigation
  function handlePrev() {
    if (viewMode === 'week') {
      setMonday((m) => addDays(m, -7))
    } else {
      setCurrentMonth((cm) => {
        const d = new Date(cm.year, cm.month - 1, 1)
        return { year: d.getFullYear(), month: d.getMonth() }
      })
      setSelectedDay(null)
    }
    setSelected(null)
  }

  function handleNext() {
    if (viewMode === 'week') {
      setMonday((m) => addDays(m, 7))
    } else {
      setCurrentMonth((cm) => {
        const d = new Date(cm.year, cm.month + 1, 1)
        return { year: d.getFullYear(), month: d.getMonth() }
      })
      setSelectedDay(null)
    }
    setSelected(null)
  }

  function handleToday() {
    const now = new Date()
    if (viewMode === 'week') {
      setMonday(getMonday(now))
      setMobileDay(now.getDay() === 0 ? 5 : Math.min(now.getDay() - 1, 5))
    } else {
      setCurrentMonth({ year: now.getFullYear(), month: now.getMonth() })
      setSelectedDay(now)
    }
    setSelected(null)
  }

  const headerLabel = viewMode === 'week'
    ? (() => {
        const endOfWeek = addDays(monday, 5)
        const sameMonth = monday.getMonth() === endOfWeek.getMonth()
        return sameMonth
          ? `${monday.getDate()} — ${endOfWeek.getDate()} ${MONTH_LABELS[monday.getMonth()]} ${monday.getFullYear()}`
          : `${monday.getDate()} ${MONTH_LABELS[monday.getMonth()]} — ${endOfWeek.getDate()} ${MONTH_LABELS[endOfWeek.getMonth()]} ${monday.getFullYear()}`
      })()
    : `${MONTH_LABELS[currentMonth.month]} ${currentMonth.year}`

  const isCurrentWeek = isSameDay(monday, getMonday(today))

  // Click on empty grid area to create appointment
  const handleGridClick = useCallback((dayIdx: number, e: React.MouseEvent<HTMLDivElement>) => {
    // Only trigger on the grid div itself, not on appointment blocks
    if (e.target !== e.currentTarget) return
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top
    const totalMinutes = (y / HOUR_HEIGHT) * 60
    // Snap to 30min
    const snappedMinutes = Math.floor(totalMinutes / 30) * 30
    const hours = Math.floor(snappedMinutes / 60) + startHour
    const mins = snappedMinutes % 60

    const dayDate = addDays(monday, dayIdx)
    dayDate.setHours(hours, mins, 0, 0)

    setModalState({
      open: true,
      mode: 'create',
      prefillDate: dayDate,
    })
  }, [monday, startHour])

  function openModal(mode: ModalMode, appointment?: Appointment, prefillDate?: Date) {
    setModalState({ open: true, mode, appointment, prefillDate })
    setSelected(null)
  }

  function closeModal() {
    setModalState({ open: false, mode: 'create' })
  }

  return (
    <div className="space-y-5">
      <AgendaHeader
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        label={headerLabel}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewAppointment={() => openModal('create')}
      />

      {viewMode === 'week' && (
        <StatsBar appointments={weekAppointments} monday={monday} startHour={startHour} endHour={endHour} />
      )}

      {isLoading ? (
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-16 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-primary-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : viewMode === 'week' ? (
        <>
          {/* ── Desktop week grid ─────────────────────────────────── */}
          <div className="hidden sm:block bg-white rounded-xl shadow-sm border border-stone-200 overflow-hidden">
            {/* Day header row */}
            <div
              className="grid border-b border-stone-200"
              style={{ gridTemplateColumns: '64px repeat(6, 1fr)' }}
            >
              <div className="border-r border-stone-200" />
              {DAY_LABELS.map((label, i) => {
                const dayDate = addDays(monday, i)
                const isToday = isSameDay(dayDate, today)
                return (
                  <div
                    key={label}
                    className={`py-3 text-center border-r border-stone-100 last:border-r-0 ${
                      isToday ? 'bg-primary-50/50' : ''
                    }`}
                  >
                    <p className={`text-[11px] font-semibold uppercase tracking-wider ${
                      isToday ? 'text-primary-600' : 'text-stone-400'
                    }`}>
                      {label}
                    </p>
                    <div className={`mt-1 inline-flex items-center justify-center ${
                      isToday
                        ? 'w-8 h-8 rounded-full bg-primary-600 text-white'
                        : ''
                    }`}>
                      <span className={`text-lg font-bold ${
                        isToday ? 'text-white' : 'text-stone-800'
                      }`}>
                        {dayDate.getDate()}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Time grid body - scrollable with pt-3 to prevent first label clipping */}
            <div className="overflow-y-auto" style={{ maxHeight: '640px' }}>
              <div
                className="grid relative pt-3"
                style={{ gridTemplateColumns: '64px repeat(6, 1fr)' }}
              >
                {/* Time labels column */}
                <div className="border-r border-stone-200">
                  {Array.from({ length: totalHours }).map((_, i) => {
                    const h = startHour + i
                    return (
                      <div key={h} className="relative" style={{ height: `${HOUR_HEIGHT}px` }}>
                        <span className="absolute -top-[9px] right-3 text-[11px] font-medium text-stone-400">
                          {String(h).padStart(2, '0')}:00
                        </span>
                      </div>
                    )
                  })}
                </div>

                {/* Day columns */}
                {Array.from({ length: 6 }).map((_, dayIdx) => {
                  const dayDate = addDays(monday, dayIdx)
                  const isToday = isSameDay(dayDate, today)
                  const dayAppts = byDay[dayIdx] || []

                  return (
                    <div
                      key={dayIdx}
                      className={`relative border-r border-stone-100 last:border-r-0 ${
                        isToday ? 'bg-primary-50/20' : ''
                      }`}
                      style={{ height: `${totalHours * HOUR_HEIGHT}px` }}
                      onClick={(e) => handleGridClick(dayIdx, e)}
                    >
                      {/* Hour grid lines */}
                      {Array.from({ length: totalHours }).map((_, hIdx) => (
                        <div key={hIdx}>
                          <div
                            className="absolute left-0 right-0 border-t border-stone-200 pointer-events-none"
                            style={{ top: `${hIdx * HOUR_HEIGHT}px` }}
                          />
                          <div
                            className="absolute left-0 right-0 border-t border-stone-100 border-dashed pointer-events-none"
                            style={{ top: `${hIdx * HOUR_HEIGHT + SLOT_HEIGHT}px` }}
                          />
                        </div>
                      ))}

                      {/* Now indicator */}
                      {isToday && isCurrentWeek && <NowIndicator startHour={startHour} endHour={endHour} />}

                      {/* Appointment blocks (skip hidden ones) */}
                      {dayAppts.map((appt) => {
                        const layout = overlapLayouts.get(appt.id) || { col: 0, totalCols: 1, hidden: false, overflow: 0 }
                        if (layout.hidden) return null
                        return (
                          <AppointmentBlock
                            key={appt.id}
                            appointment={appt}
                            layout={layout}
                            startHour={startHour}
                            onClick={() => setSelected(appt)}
                          />
                        )
                      })}

                      {/* Overflow badges for hidden appointments */}
                      {(dayOverflowBadges[dayIdx] || []).map((badge, bi) => (
                        <button
                          key={`overflow-${bi}`}
                          className="absolute right-0.5 z-20 flex items-center justify-center cursor-pointer"
                          style={{
                            top: `${badge.topPx + 1}px`,
                            height: `${Math.max(badge.heightPx - 2, 24)}px`,
                          }}
                          onClick={(e) => {
                            e.stopPropagation()
                            const rect = e.currentTarget.getBoundingClientRect()
                            setSlotPopover({ appointments: badge.allAppointments, anchorRect: rect })
                          }}
                        >
                          <span className="bg-primary-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shadow-sm hover:bg-primary-700 transition-colors">
                            +{badge.count}
                          </span>
                        </button>
                      ))}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* ── Mobile: single day view ───────────────────────────── */}
          <div className="sm:hidden space-y-3">
            {/* Mobile nav arrows */}
            <div className="flex items-center justify-between">
              <button onClick={handlePrev} className="p-2 text-stone-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
              </button>
              <span className="text-sm font-medium text-stone-600">
                {monday.getDate()} — {addDays(monday, 5).getDate()} {MONTH_LABELS[monday.getMonth()]}
              </span>
              <button onClick={handleNext} className="p-2 text-stone-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </button>
            </div>

            {/* Day tabs */}
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {DAY_LABELS.map((label, i) => {
                const dayDate = addDays(monday, i)
                const isToday = isSameDay(dayDate, today)
                const isActive = mobileDay === i
                const dayApptCount = (byDay[i] || []).filter((a) => a.status === 'confirmed').length
                return (
                  <button
                    key={label}
                    onClick={() => setMobileDay(i)}
                    className={`flex-shrink-0 w-12 py-2 rounded-xl text-center transition-all ${
                      isActive
                        ? 'bg-primary-600 text-white shadow-md shadow-primary-600/25'
                        : isToday
                          ? 'bg-primary-50 text-primary-700 border border-primary-200'
                          : 'bg-white text-stone-600 border border-stone-200 hover:bg-stone-50'
                    }`}
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wider">{label}</p>
                    <p className="text-base font-bold mt-0.5">{dayDate.getDate()}</p>
                    {dayApptCount > 0 && (
                      <div className={`mx-auto mt-1 w-1.5 h-1.5 rounded-full ${
                        isActive ? 'bg-white/70' : 'bg-primary-400'
                      }`} />
                    )}
                  </button>
                )
              })}
            </div>

            {/* Day appointments */}
            {(byDay[mobileDay] || []).length === 0 ? (
              <div className="bg-white rounded-xl p-8 text-center shadow-sm border border-stone-200">
                <p className="text-stone-400 text-sm">Aucun rendez-vous ce jour</p>
              </div>
            ) : (
              <div className="space-y-2">
                {(byDay[mobileDay] || []).map((appt) => {
                  const start = new Date(appt.date_heure)
                  const h = String(start.getHours()).padStart(2, '0')
                  const m = String(start.getMinutes()).padStart(2, '0')
                  const isCancelled = appt.status === 'cancelled'
                  return (
                    <button
                      key={appt.id}
                      onClick={() => setSelected(appt)}
                      className={`w-full text-left bg-white rounded-xl p-4 shadow-sm border transition-colors hover:bg-stone-50 ${
                        isCancelled ? 'border-stone-200' : 'border-stone-200'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-1 self-stretch rounded-full shrink-0 ${
                          isCancelled ? 'bg-stone-300' : 'bg-primary-500'
                        }`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className={`text-sm font-semibold ${
                              isCancelled ? 'text-stone-400 line-through' : 'text-stone-900'
                            }`}>
                              {appt.patient_nom}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                              isCancelled
                                ? 'bg-red-50 text-red-500'
                                : 'bg-emerald-50 text-emerald-600'
                            }`}>
                              {isCancelled ? 'Annule' : 'Confirme'}
                            </span>
                          </div>
                          <p className={`text-xs mt-1 ${isCancelled ? 'text-stone-400' : 'text-stone-500'}`}>
                            {h}:{m} — {appt.duree_minutes} min
                          </p>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </>
      ) : (
        /* ── Month view ─────────────────────────────────────────── */
        <div className="space-y-4">
          <MonthGrid
            year={currentMonth.year}
            month={currentMonth.month}
            appointments={monthAppointments}
            selectedDay={selectedDay}
            onSelectDay={setSelectedDay}
          />
          {selectedDay && (
            <DayAppointmentList
              day={selectedDay}
              appointments={monthAppointments}
              onSelect={setSelected}
            />
          )}
        </div>
      )}

      {/* Slot popover (for "+N" overflow click) */}
      {slotPopover && (
        <>
          <div
            className="fixed inset-0 z-30"
            onClick={() => setSlotPopover(null)}
          />
          <div
            className="fixed z-40 bg-white rounded-xl shadow-2xl border border-stone-200 w-72 max-h-80 overflow-auto"
            style={{
              top: Math.min(slotPopover.anchorRect.bottom + 4, window.innerHeight - 340),
              left: Math.max(8, Math.min(slotPopover.anchorRect.left - 240, window.innerWidth - 296)),
            }}
          >
            <div className="px-4 py-3 border-b border-stone-100 sticky top-0 bg-white rounded-t-xl">
              <p className="text-sm font-semibold text-stone-900">
                {slotPopover.appointments.length} rendez-vous
              </p>
              <p className="text-xs text-stone-500">
                {(() => {
                  const t = new Date(slotPopover.appointments[0].date_heure)
                  return `${String(t.getHours()).padStart(2, '0')}h${String(t.getMinutes()).padStart(2, '0')}`
                })()}
              </p>
            </div>
            <div className="divide-y divide-stone-100">
              {slotPopover.appointments.map((appt) => {
                const start = new Date(appt.date_heure)
                const h = String(start.getHours()).padStart(2, '0')
                const m = String(start.getMinutes()).padStart(2, '0')
                const isCancelled = appt.status === 'cancelled'
                return (
                  <button
                    key={appt.id}
                    onClick={() => {
                      setSlotPopover(null)
                      setSelected(appt)
                    }}
                    className="w-full text-left px-4 py-2.5 flex items-center gap-2.5 hover:bg-stone-50 transition-colors"
                  >
                    <div className={`w-1 h-8 rounded-full shrink-0 ${
                      isCancelled ? 'bg-stone-300' : 'bg-primary-500'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <span className={`text-sm font-medium block truncate ${
                        isCancelled ? 'text-stone-400 line-through' : 'text-stone-900'
                      }`}>
                        {appt.patient_nom}
                      </span>
                      <span className="text-xs text-stone-500">
                        {h}:{m} — {appt.duree_minutes} min
                      </span>
                    </div>
                    <svg className="w-4 h-4 text-stone-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </button>
                )
              })}
            </div>
          </div>
        </>
      )}

      {/* Detail slide-in panel */}
      {selected && (
        <>
          <div
            className="fixed inset-0 bg-black/20 backdrop-blur-[2px] z-30 transition-opacity"
            onClick={() => setSelected(null)}
          />
          <DetailPanel
            appointment={selected}
            onClose={() => setSelected(null)}
            onEdit={() => openModal('edit', selected)}
            onDuplicate={() => openModal('duplicate', selected)}
            onReschedule={() => openModal('reschedule', selected)}
            onCancel={() => {
              if (window.confirm(`Annuler le rendez-vous de ${selected.patient_nom} ?`)) {
                cancelMutation.mutate(selected.id)
              }
            }}
          />
        </>
      )}

      {/* Appointment modal */}
      {modalState.open && cabinet && (
        <AppointmentModal
          mode={modalState.mode}
          appointment={modalState.appointment}
          cabinetId={cabinet.id}
          prefillDate={modalState.prefillDate}
          onClose={closeModal}
          onSaved={closeModal}
        />
      )}
    </div>
  )
}
