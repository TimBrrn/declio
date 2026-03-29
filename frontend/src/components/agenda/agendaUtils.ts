import type { WeekSchedule, Appointment } from '../../api/client'

// ── Types ────────────────────────────────────────────────────────────────────

export type ViewMode = 'week' | 'month'
export type ModalMode = 'create' | 'edit' | 'duplicate' | 'reschedule'

export interface LayoutInfo {
  col: number
  totalCols: number  // capped at MAX_VISIBLE_COLS for positioning
  hidden: boolean    // true if this appt is beyond visible cols
  overflow: number   // how many hidden appts in this cluster (only set on visible ones)
}

export interface OverflowBadge {
  count: number
  topPx: number
  heightPx: number
  allAppointments: Appointment[]  // every appt in the cluster (visible + hidden)
}

// ── Constants ────────────────────────────────────────────────────────────────

export const DAY_LABELS = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM'] as const
export const DAY_LABELS_FULL = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'] as const
export const MONTH_LABELS = [
  'janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre',
]

export const SLOT_HEIGHT = 48 // px per 30-min slot
export const HOUR_HEIGHT = SLOT_HEIGHT * 2 // 96px per hour
export const MAX_VISIBLE_COLS = 3

// ── Date helpers ─────────────────────────────────────────────────────────────

export function getMonday(d: Date): Date {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}

export function addDays(d: Date, n: number): Date {
  const date = new Date(d)
  date.setDate(date.getDate() + n)
  return date
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

export function formatISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function getFirstDayOfMonth(year: number, month: number): Date {
  return new Date(year, month, 1)
}

export function getLastDayOfMonth(year: number, month: number): Date {
  return new Date(year, month + 1, 0)
}

export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

// ── Compute dynamic hours from cabinet config ────────────────────────────────

export function computeWorkingHours(horaires?: WeekSchedule): { startHour: number; endHour: number } {
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

export function computeOverlapLayout(
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
