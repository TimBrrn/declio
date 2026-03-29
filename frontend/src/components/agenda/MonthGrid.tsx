import { useMemo } from 'react'
import type { Appointment } from '../../api/client'
import { DAY_LABELS, isSameDay, getDaysInMonth, getFirstDayOfMonth } from './agendaUtils'

export interface MonthGridProps {
  year: number
  month: number
  appointments: Appointment[]
  selectedDay: Date | null
  onSelectDay: (d: Date) => void
}

export function MonthGrid({
  year,
  month,
  appointments,
  selectedDay,
  onSelectDay,
}: MonthGridProps) {
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
