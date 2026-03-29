import type { Appointment } from '../../api/client'
import type { LayoutInfo } from './agendaUtils'
import { HOUR_HEIGHT } from './agendaUtils'

export interface AppointmentBlockProps {
  appointment: Appointment
  layout: LayoutInfo
  startHour: number
  onClick: () => void
}

export function AppointmentBlock({
  appointment,
  layout,
  startHour,
  onClick,
}: AppointmentBlockProps) {
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
