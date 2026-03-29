import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useCallback } from 'react'
import {
  getAppointments,
  getCabinets,
  updateAppointment,
  type Appointment,
} from '../api/client'
import type { ViewMode, ModalMode, LayoutInfo, OverflowBadge } from '../components/agenda/agendaUtils'
import {
  getMonday,
  addDays,
  isSameDay,
  formatISODate,
  getFirstDayOfMonth,
  getLastDayOfMonth,
  MONTH_LABELS,
  HOUR_HEIGHT,
  computeWorkingHours,
  computeOverlapLayout,
} from '../components/agenda/agendaUtils'
import { AgendaHeader } from '../components/agenda/AgendaHeader'
import { StatsBar } from '../components/agenda/StatsBar'
import { WeekGrid } from '../components/agenda/WeekGrid'
import { MonthGrid } from '../components/agenda/MonthGrid'
import { DayAppointmentList } from '../components/agenda/DayAppointmentList'
import { DetailPanel } from '../components/agenda/DetailPanel'
import { AppointmentModal } from '../components/agenda/AppointmentModal'

// ── Slot popover (for "+N" overflow click) ──────────────────────────────────

function SlotPopover({
  appointments,
  anchorRect,
  onClose,
  onSelect,
}: {
  appointments: Appointment[]
  anchorRect: DOMRect
  onClose: () => void
  onSelect: (appt: Appointment) => void
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-30"
        onClick={onClose}
      />
      <div
        className="fixed z-40 bg-white rounded-xl shadow-2xl border border-stone-200 w-72 max-h-80 overflow-auto"
        style={{
          top: Math.min(anchorRect.bottom + 4, window.innerHeight - 340),
          left: Math.max(8, Math.min(anchorRect.left - 240, window.innerWidth - 296)),
        }}
      >
        <div className="px-4 py-3 border-b border-stone-100 sticky top-0 bg-white rounded-t-xl">
          <p className="text-sm font-semibold text-stone-900">
            {appointments.length} rendez-vous
          </p>
          <p className="text-xs text-stone-500">
            {(() => {
              const t = new Date(appointments[0].date_heure)
              return `${String(t.getHours()).padStart(2, '0')}h${String(t.getMinutes()).padStart(2, '0')}`
            })()}
          </p>
        </div>
        <div className="divide-y divide-stone-100">
          {appointments.map((appt) => {
            const start = new Date(appt.date_heure)
            const h = String(start.getHours()).padStart(2, '0')
            const m = String(start.getMinutes()).padStart(2, '0')
            const isCancelled = appt.status === 'cancelled'
            return (
              <button
                key={appt.id}
                onClick={() => onSelect(appt)}
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
        <WeekGrid
          monday={monday}
          startHour={startHour}
          endHour={endHour}
          byDay={byDay}
          overlapLayouts={overlapLayouts}
          dayOverflowBadges={dayOverflowBadges}
          isCurrentWeek={isCurrentWeek}
          mobileDay={mobileDay}
          onMobileDayChange={setMobileDay}
          onSelectAppointment={setSelected}
          onGridClick={handleGridClick}
          onOverflowClick={(appointments, anchorRect) =>
            setSlotPopover({ appointments, anchorRect })
          }
          onPrev={handlePrev}
          onNext={handleNext}
        />
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
        <SlotPopover
          appointments={slotPopover.appointments}
          anchorRect={slotPopover.anchorRect}
          onClose={() => setSlotPopover(null)}
          onSelect={(appt) => {
            setSlotPopover(null)
            setSelected(appt)
          }}
        />
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
