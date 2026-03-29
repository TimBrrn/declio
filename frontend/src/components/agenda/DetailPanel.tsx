import type { Appointment } from '../../api/client'

export interface DetailPanelProps {
  appointment: Appointment
  onClose: () => void
  onEdit: () => void
  onDuplicate: () => void
  onReschedule: () => void
  onCancel: () => void
}

export function DetailPanel({
  appointment,
  onClose,
  onEdit,
  onDuplicate,
  onReschedule,
  onCancel,
}: DetailPanelProps) {
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
