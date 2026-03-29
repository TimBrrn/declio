import type { Appointment } from '../../api/client'
import type { LayoutInfo, OverflowBadge } from './agendaUtils'
import {
  DAY_LABELS,
  MONTH_LABELS,
  SLOT_HEIGHT,
  HOUR_HEIGHT,
  addDays,
  isSameDay,
} from './agendaUtils'
import { AppointmentBlock } from './AppointmentBlock'

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

// ── WeekGrid props ────────────────────────────────────────────────────────────

export interface WeekGridProps {
  monday: Date
  startHour: number
  endHour: number
  byDay: Record<number, Appointment[]>
  overlapLayouts: Map<string, LayoutInfo>
  dayOverflowBadges: Record<number, OverflowBadge[]>
  isCurrentWeek: boolean
  mobileDay: number
  onMobileDayChange: (day: number) => void
  onSelectAppointment: (appt: Appointment) => void
  onGridClick: (dayIdx: number, e: React.MouseEvent<HTMLDivElement>) => void
  onOverflowClick: (appointments: Appointment[], anchorRect: DOMRect) => void
  onPrev: () => void
  onNext: () => void
}

export function WeekGrid({
  monday,
  startHour,
  endHour,
  byDay,
  overlapLayouts,
  dayOverflowBadges,
  isCurrentWeek,
  mobileDay,
  onMobileDayChange,
  onSelectAppointment,
  onGridClick,
  onOverflowClick,
  onPrev,
  onNext,
}: WeekGridProps) {
  const today = new Date()
  const totalHours = endHour - startHour

  return (
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
                  onClick={(e) => onGridClick(dayIdx, e)}
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
                        onClick={() => onSelectAppointment(appt)}
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
                        onOverflowClick(badge.allAppointments, rect)
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
          <button onClick={onPrev} className="p-2 text-stone-500">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <span className="text-sm font-medium text-stone-600">
            {monday.getDate()} — {addDays(monday, 5).getDate()} {MONTH_LABELS[monday.getMonth()]}
          </span>
          <button onClick={onNext} className="p-2 text-stone-500">
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
                onClick={() => onMobileDayChange(i)}
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
                  onClick={() => onSelectAppointment(appt)}
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
  )
}
