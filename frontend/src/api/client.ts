import { getAuthToken } from '../auth/AuthProvider'

// ── Types (frontend-friendly, used by forms) ────────────────────────────────

export interface DaySchedule {
  open: string   // "09:00"
  close: string  // "19:00"
  closed: boolean
}

export type DayKey = 'lundi' | 'mardi' | 'mercredi' | 'jeudi' | 'vendredi' | 'samedi' | 'dimanche'

export type WeekSchedule = Record<DayKey, DaySchedule>

export type PaymentMode = 'cb' | 'cheque' | 'especes'

export interface Cabinet {
  id: string
  nom_cabinet: string
  nom_praticien: string
  adresse: string
  telephone: string
  horaires: WeekSchedule
  tarifs: {
    seance_conventionnelle: number
    depassement: number
    modes_paiement: PaymentMode[]
  }
  google_calendar_id: string
  numero_sms_kine: string
  message_accueil: string
  faq: Record<string, string>
}

export type CabinetCreate = Omit<Cabinet, 'id'>
export type CabinetUpdate = Partial<CabinetCreate>

// ── API serialization ───────────────────────────────────────────────────────
// Backend expects: horaires = dict[str, list[str]], tarifs = dict[str, float]

const ALL_DAYS: DayKey[] = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

function toApiPayload(data: CabinetCreate | CabinetUpdate) {
  const out: Record<string, unknown> = { ...data }

  // horaires: {open, close, closed} → ["09:00-19:00"] or []
  if (data.horaires) {
    const h: Record<string, string[]> = {}
    for (const [day, sched] of Object.entries(data.horaires)) {
      h[day] = sched.closed ? [] : [`${sched.open}-${sched.close}`]
    }
    out.horaires = h
  }

  // tarifs: strip modes_paiement (not a float), store it in faq
  if (data.tarifs) {
    const { modes_paiement, ...numericTarifs } = data.tarifs
    out.tarifs = numericTarifs
    out.faq = { ...(data.faq || {}), modes_paiement: (modes_paiement ?? []).join(',') }
  }

  return out
}

function fromApiCabinet(raw: Record<string, unknown>): Cabinet {
  // horaires: ["09:00-12:00","14:00-18:00"] → {open, close, closed}
  const apiHoraires = (raw.horaires ?? {}) as Record<string, string[]>
  const horaires = {} as WeekSchedule
  for (const day of ALL_DAYS) {
    const slots = apiHoraires[day]
    if (!slots || slots.length === 0) {
      horaires[day] = { open: '09:00', close: '19:00', closed: true }
    } else {
      const firstOpen = slots[0].split('-')[0]
      const lastClose = slots[slots.length - 1].split('-')[1]
      horaires[day] = { open: firstOpen, close: lastClose, closed: false }
    }
  }

  // tarifs: flat dict → structured object + modes_paiement from faq
  const apiTarifs = (raw.tarifs ?? {}) as Record<string, number>
  const apiFaq = (raw.faq ?? {}) as Record<string, string>
  const modesPaiement: PaymentMode[] = apiFaq.modes_paiement
    ? apiFaq.modes_paiement.split(',').filter(Boolean) as PaymentMode[]
    : ['cb', 'especes']

  const { modes_paiement: _, ...restFaq } = apiFaq

  return {
    id: raw.id as string,
    nom_cabinet: (raw.nom_cabinet ?? '') as string,
    nom_praticien: (raw.nom_praticien ?? '') as string,
    adresse: (raw.adresse ?? '') as string,
    telephone: (raw.telephone ?? '') as string,
    horaires,
    tarifs: {
      seance_conventionnelle: apiTarifs.seance_conventionnelle ?? 0,
      depassement: apiTarifs.depassement ?? 0,
      modes_paiement: modesPaiement,
    },
    google_calendar_id: (raw.google_calendar_id ?? '') as string,
    numero_sms_kine: (raw.numero_sms_kine ?? '') as string,
    message_accueil: (raw.message_accueil ?? '') as string,
    faq: restFaq,
  }
}

export type CallScenario = 'booking' | 'cancellation' | 'faq' | 'out_of_scope' | 'error'

export interface TranscriptMessage {
  role: 'assistant' | 'visitor'
  content: string
  timestamp: string
}

export interface CallRecord {
  id: string
  cabinet_id: string
  caller_phone: string
  duration_seconds: number
  scenario: CallScenario
  actions_taken: string[]
  summary: string
  stt_confidence_score: number
  transcript: TranscriptMessage[]
  created_at: string
  // Cost tracking
  total_cost_eur: number
  llm_cost_usd: number
  stt_cost_usd: number
  tts_cost_usd: number
  total_tokens: number
}

export interface ApiUsageEntry {
  id: string
  service: 'llm' | 'stt' | 'tts'
  turn_index: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  model: string
  tool_name: string | null
  chars: number
  duration_seconds: number
}

export interface Patient {
  id: string
  cabinet_id: string
  nom: string
  telephone: string
  email: string
  created_at: string
}

export interface PatientCreate {
  cabinet_id: string
  nom: string
  telephone?: string
  email?: string
}

export interface PatientUpdate {
  nom?: string
  telephone?: string
  email?: string
}

export interface Appointment {
  id: string
  cabinet_id: string
  patient_id: string | null
  patient_nom: string
  patient_telephone: string
  date_heure: string  // ISO datetime
  duree_minutes: number
  status: 'confirmed' | 'cancelled'
  source: string
  google_event_id: string
  created_at: string
}

export interface UsageSummary {
  total_calls: number
  total_cost_eur: number
  avg_cost_per_call_eur: number
  llm_cost_total_eur: number
  stt_cost_total_eur: number
  tts_cost_total_eur: number
  total_tokens: number
  avg_tokens_per_call: number
}

// Backend uses different field names — normalize here
const SCENARIO_MAP: Record<string, CallScenario> = {
  booking: 'booking',
  cancellation: 'cancellation',
  faq: 'faq',
  faq_tarifs: 'faq',
  faq_pratique: 'faq',
  out_of_scope: 'out_of_scope',
  hors_perimetre: 'out_of_scope',
  error: 'error',
}

function fromApiCall(raw: Record<string, unknown>): CallRecord {
  // actions_taken: backend sends JSON string or empty string
  let actions: string[] = []
  const rawActions = raw.actions_taken
  if (Array.isArray(rawActions)) {
    actions = rawActions as string[]
  } else if (typeof rawActions === 'string' && rawActions) {
    try { actions = JSON.parse(rawActions) } catch { actions = [] }
  }

  // transcript_json: backend sends JSON string
  let transcript: TranscriptMessage[] = []
  const rawTranscript = raw.transcript_json
  if (Array.isArray(rawTranscript)) {
    transcript = rawTranscript as TranscriptMessage[]
  } else if (typeof rawTranscript === 'string' && rawTranscript) {
    try { transcript = JSON.parse(rawTranscript) } catch { transcript = [] }
  }

  return {
    id: (raw.id ?? '') as string,
    cabinet_id: (raw.cabinet_id ?? '') as string,
    caller_phone: (raw.caller_number ?? raw.caller_phone ?? '') as string,
    duration_seconds: (raw.duration_seconds ?? 0) as number,
    scenario: SCENARIO_MAP[raw.scenario as string] ?? 'error',
    actions_taken: actions,
    summary: (raw.summary ?? '') as string,
    stt_confidence_score: (raw.stt_confidence ?? raw.stt_confidence_score ?? 0) as number,
    transcript,
    created_at: (raw.started_at ?? raw.created_at ?? '') as string,
    // Cost tracking
    total_cost_eur: (raw.total_cost_eur ?? 0) as number,
    llm_cost_usd: (raw.llm_cost_usd ?? 0) as number,
    stt_cost_usd: (raw.stt_cost_usd ?? 0) as number,
    tts_cost_usd: (raw.tts_cost_usd ?? 0) as number,
    total_tokens: (raw.total_tokens ?? 0) as number,
  }
}

// ── HTTP helpers ─────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {}
  if (init?.body) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...init,
  })
  if (res.status === 401) {
    localStorage.removeItem('declio_auth_token')
    localStorage.removeItem('declio_auth_user')
    window.location.href = '/login'
    throw new Error('Session expiree')
  }
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...init,
  })
  if (res.status === 401) {
    localStorage.removeItem('declio_auth_token')
    localStorage.removeItem('declio_auth_user')
    window.location.href = '/login'
    throw new Error('Session expiree')
  }
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`)
  }
}

// ── Cabinet ──────────────────────────────────────────────────────────────────

export async function getCabinets(): Promise<Cabinet[]> {
  const raw = await request<Record<string, unknown>[]>('/cabinets')
  return raw.map(fromApiCabinet)
}

export async function getCabinet(id: string): Promise<Cabinet> {
  const raw = await request<Record<string, unknown>>(`/cabinets/${id}`)
  return fromApiCabinet(raw)
}

export async function createCabinet(data: CabinetCreate): Promise<Cabinet> {
  const raw = await request<Record<string, unknown>>('/cabinets', {
    method: 'POST',
    body: JSON.stringify(toApiPayload(data)),
  })
  return fromApiCabinet(raw)
}

export async function updateCabinet(id: string, data: CabinetUpdate): Promise<Cabinet> {
  const raw = await request<Record<string, unknown>>(`/cabinets/${id}`, {
    method: 'PUT',
    body: JSON.stringify(toApiPayload(data)),
  })
  return fromApiCabinet(raw)
}

// ── Calls ────────────────────────────────────────────────────────────────────

export async function getCalls(cabinetId?: string): Promise<CallRecord[]> {
  const params = cabinetId ? `?cabinet_id=${cabinetId}` : ''
  const raw = await request<Record<string, unknown>[]>(`/calls${params}`)
  return raw.map(fromApiCall)
}

export async function getCallUsage(callId: string): Promise<ApiUsageEntry[]> {
  return request<ApiUsageEntry[]>(`/calls/${callId}/usage`)
}

export async function getUsageSummary(dateFrom?: string, dateTo?: string): Promise<UsageSummary> {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const qs = params.toString()
  return request<UsageSummary>(`/usage/summary${qs ? `?${qs}` : ''}`)
}

// ── Appointments ──────────────────────────────────────────────────────────────

export interface AppointmentCreate {
  cabinet_id: string
  patient_nom: string
  patient_telephone?: string
  date_heure: string  // ISO "2026-03-27T09:00:00"
  duree_minutes?: number
  status?: string
  repeat_weeks?: number  // 1 = single, 2+ = recurrence
}

export interface AppointmentUpdate {
  patient_nom?: string
  patient_telephone?: string
  date_heure?: string
  duree_minutes?: number
  status?: string
}

export async function getAppointments(
  dateFrom?: string,
  dateTo?: string,
  status?: string,
): Promise<Appointment[]> {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  if (status) params.set('status', status)
  const qs = params.toString()
  return request<Appointment[]>(`/appointments${qs ? `?${qs}` : ''}`)
}

export async function createAppointment(data: AppointmentCreate): Promise<Appointment[]> {
  return request<Appointment[]>('/appointments', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAppointment(id: string, data: AppointmentUpdate): Promise<Appointment> {
  return request<Appointment>(`/appointments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteAppointment(id: string): Promise<void> {
  return requestVoid(`/appointments/${id}`, { method: 'DELETE' })
}

// ── Patients ──────────────────────────────────────────────────────────────────

export async function getPatients(cabinetId?: string): Promise<Patient[]> {
  const params = cabinetId ? `?cabinet_id=${cabinetId}` : ''
  return request<Patient[]>(`/patients${params}`)
}

export async function getPatient(id: string): Promise<Patient> {
  return request<Patient>(`/patients/${id}`)
}

export async function createPatient(data: PatientCreate): Promise<Patient> {
  return request<Patient>('/patients', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updatePatient(id: string, data: PatientUpdate): Promise<Patient> {
  return request<Patient>(`/patients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deletePatient(id: string): Promise<void> {
  return requestVoid(`/patients/${id}`, { method: 'DELETE' })
}
