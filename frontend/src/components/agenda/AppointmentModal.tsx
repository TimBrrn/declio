import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  createAppointment,
  updateAppointment,
  type Appointment,
  type AppointmentCreate,
  type AppointmentUpdate,
} from '../../api/client'
import type { ModalMode } from './agendaUtils'
import { formatISODate } from './agendaUtils'

export interface AppointmentModalProps {
  mode: ModalMode
  appointment?: Appointment
  cabinetId: string
  prefillDate?: Date
  onClose: () => void
  onSaved: () => void
}

export function AppointmentModal({
  mode,
  appointment,
  cabinetId,
  prefillDate,
  onClose,
  onSaved,
}: AppointmentModalProps) {
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
