import type { Appointment } from '../../api/client'
import { isSameDay } from './agendaUtils'

export interface DayAppointmentListProps {
  day: Date
  appointments: Appointment[]
  onSelect: (a: Appointment) => void
}

export function DayAppointmentList({
  day,
  appointments,
  onSelect,
}: DayAppointmentListProps) {
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
