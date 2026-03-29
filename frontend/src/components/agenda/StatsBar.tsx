import { useMemo } from 'react'
import type { Appointment } from '../../api/client'
import { isSameDay, addDays, DAY_LABELS_FULL } from './agendaUtils'

export interface StatsBarProps {
  appointments: Appointment[]
  monday: Date
  startHour: number
  endHour: number
}

export function StatsBar({
  appointments,
  monday,
  startHour,
  endHour,
}: StatsBarProps) {
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
