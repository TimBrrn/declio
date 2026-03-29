import type { ViewMode } from './agendaUtils'

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

export interface AgendaHeaderProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  label: string
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onNewAppointment: () => void
}

export function AgendaHeader({
  viewMode,
  onViewModeChange,
  label,
  onPrev,
  onNext,
  onToday,
  onNewAppointment,
}: AgendaHeaderProps) {
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
