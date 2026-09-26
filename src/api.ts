import type {
  Assessment, Dashboard, Driver, Impact, Match, Need, Notification, Organization, Report, RouteOption, SessionData, Tracking, Transfer, Material, Outcome
} from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'
const SESSION_KEY = 'reloop_session_v8_final'

export function getSession(): SessionData | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) as SessionData : null
  } catch {
    return null
  }
}

export function saveSession(session: SessionData) { sessionStorage.setItem(SESSION_KEY, JSON.stringify(session)) }
export function clearSession() { sessionStorage.removeItem(SESSION_KEY) }
export function apiUrl(path: string) { return `${API_BASE}${path}` }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = getSession()
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (session?.token) headers.set('Authorization', `Bearer ${session.token}`)
  const response = await fetch(apiUrl(path), { ...init, headers, cache: 'no-store' })
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : payload?.detail || payload?.message || `Request failed (${response.status})`
    if (response.status === 401) {
      clearSession()
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('reloop-session-expired'))
    }
    throw new Error(message)
  }
  return payload as T
}

export function login(email: string, password: string, role?: string) {
  return request<{ access_token: string; user: SessionData['user']; organization: Organization | null }>('/api/auth/login', {
    method: 'POST', body: JSON.stringify({ email, password, role: role || undefined })
  }).then(data => {
    const session: SessionData = { token: data.access_token, user: data.user, organization: data.organization }
    saveSession(session)
    return session
  })
}

export function register(payload: Record<string, unknown>) {
  return request<{ access_token: string; user: SessionData['user']; organization: Organization | null }>('/api/auth/register', {
    method: 'POST', body: JSON.stringify(payload)
  }).then(data => {
    const session: SessionData = { token: data.access_token, user: data.user, organization: data.organization }
    saveSession(session)
    return session
  })
}

export const api = {
  dashboard: () => request<Dashboard>('/api/dashboard'),
  materials: () => request<Material[]>('/api/materials'),
  marketplace: () => request<Material[]>('/api/materials/all'),
  material: (id: number) => request<Material>(`/api/materials/${id}`),
  createMaterial: (payload: Record<string, unknown>) => request<Material>('/api/materials', { method: 'POST', body: JSON.stringify(payload) }),
  updateMaterial: (id: number, payload: Record<string, unknown>) => request<Material>(`/api/materials/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  closeMaterial: (id: number) => request<Material>(`/api/materials/${id}/close`, { method: 'POST' }),
  upload: (file: File) => { const form = new FormData(); form.append('file', file); return request<{ url: string; filename: string }>('/api/materials/uploads', { method: 'POST', body: form }) },
  uploadMaterialImage: (id: number, file: File) => { const form = new FormData(); form.append('file', file); return request<{ url: string; filename: string }>(`/api/materials/${id}/images`, { method: 'POST', body: form }) },
  assessment: (id: number) => request<Assessment>(`/api/assessment/${id}`),
  runAssessment: (id: number) => request<Assessment>(`/api/assessment/${id}`, { method: 'POST' }),
  methodology: () => request<Record<string, unknown>>('/api/assessment/methodology/overview'),
  needs: () => request<Need[]>('/api/needs'),
  createNeed: (payload: Record<string, unknown>) => request<Need>('/api/needs', { method: 'POST', body: JSON.stringify(payload) }),
  organizations: (kind?: string) => request<Organization[]>(`/api/organizations${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`),
  manageOrganizations: (status?: string) => request<Organization[]>(`/api/organizations/manage${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  verifyOrganization: (id: number, status: string) => request<Organization>(`/api/organizations/${id}/verification`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  matches: (materialId: number) => request<Match[]>(`/api/matching/material/${materialId}`),
  sentMatches: () => request<Match[]>('/api/matching/sent'),
  incomingMatches: () => request<Match[]>('/api/matching/incoming'),
  incomingCount: () => request<{ count: number }>('/api/matching/incoming/count'),
  requestMatch: (payload: { material_id: number; partner_organization_id: number; need_id?: number | null }) => request<Match>('/api/matching/request', { method: 'POST', body: JSON.stringify(payload) }),
  decideMatch: (id: number, decision: 'ACCEPTED' | 'REJECTED') => request<Match>(`/api/matching/${id}`, { method: 'PATCH', body: JSON.stringify({ decision }) }),
  routeOptions: (materialId: number, partnerId: number, quantity: number) => request<RouteOption[]>(`/api/routes/options/${materialId}/${partnerId}?quantity=${quantity}`),
  calculateRoute: (payload: { material_id: number; partner_organization_id: number; vehicle_type: string; quantity: number }) => request<RouteOption>('/api/routes/calculate', { method: 'POST', body: JSON.stringify(payload) }),
  logistics: () => request<Organization[]>('/api/organizations?kind=LOGISTICS'),
  drivers: () => request<Driver[]>('/api/logistics/drivers'),
  eligibleDrivers: (quantity: number, vehicleType?: string) => request<Driver[]>(`/api/logistics/drivers/eligible?quantity=${encodeURIComponent(quantity)}${vehicleType ? `&vehicle_type=${encodeURIComponent(vehicleType)}` : ''}`),
  myDriver: () => request<Driver>('/api/logistics/drivers/me'),
  createDriver: (payload: Record<string, unknown>) => request<Driver>('/api/logistics/drivers', { method: 'POST', body: JSON.stringify(payload) }),
  logisticsJobs: () => request<Record<string, unknown>[]>('/api/logistics/jobs'),
  transfers: () => request<Transfer[]>('/api/transfers'),
  createTransfer: (payload: Record<string, unknown>) => request<Transfer>('/api/transfers', { method: 'POST', body: JSON.stringify(payload) }),
  assignDriver: (transferId: number, driverId: number) => request<Transfer>(`/api/transfers/${transferId}/assign-driver`, { method: 'POST', body: JSON.stringify({ driver_id: driverId }) }),
  acceptAssignment: (transferId: number) => request<Transfer>(`/api/transfers/${transferId}/accept-assignment`, { method: 'POST' }),
  startTrip: (transferId: number) => request<Transfer>(`/api/transfers/${transferId}/start-trip`, { method: 'POST' }),
  sendLocation: (transferId: number, payload: { latitude: number; longitude: number; accuracy_m?: number; speed_kmph?: number }) => request<Transfer>(`/api/transfers/${transferId}/location`, { method: 'POST', body: JSON.stringify(payload) }),
  markArrived: (transferId: number, payload: { latitude: number; longitude: number; accuracy_m?: number; speed_kmph?: number }) => request<Transfer>(`/api/transfers/${transferId}/mark-arrived`, { method: 'POST', body: JSON.stringify(payload) }),
  simulateLocation: (transferId: number, progress: number) => request<Transfer>(`/api/transfers/${transferId}/simulate-location?progress=${progress}`, { method: 'POST' }),
  confirmReceipt: (transferId: number, payload: { received_quantity: number; received_condition: string; notes: string; receipt_photo_url?: string | null }) => request<Transfer>(`/api/transfers/${transferId}/confirm-receipt`, { method: 'POST', body: JSON.stringify(payload) }),
  cancelTransfer: (transferId: number) => request<Transfer>(`/api/transfers/${transferId}/cancel`, { method: 'POST' }),
  tracking: (transferId: number) => request<Tracking>(`/api/transfers/${transferId}/tracking`),
  notifications: (limit = 30) => request<Notification[]>(`/api/notifications?limit=${limit}`),
  unreadNotifications: () => request<{ count: number }>('/api/notifications/unread-count'),
  readNotification: (id: number) => request<Notification>(`/api/notifications/${id}/read`, { method: 'PATCH' }),
  readAllNotifications: () => request<{ success: boolean }>('/api/notifications/read-all', { method: 'POST' }),
  outcomesPending: () => request<Outcome[]>('/api/outcomes/pending'),
  outcome: (transferId: number) => request<Outcome | null>(`/api/outcomes/transfer/${transferId}`),
  submitOutcome: (transferId: number, payload: Record<string, unknown>) => request<Outcome>(`/api/outcomes/transfer/${transferId}/submit`, { method: 'POST', body: JSON.stringify(payload) }),
  reviewOutcome: (outcomeId: number, decision: 'VERIFIED' | 'CORRECTION_REQUESTED' | 'REJECTED', reviewer_note: string) => request<Outcome>(`/api/outcomes/${outcomeId}/review`, { method: 'POST', body: JSON.stringify({ decision, reviewer_note }) }),
  impact: () => request<Impact>('/api/impact/dashboard'),
  report: (transferId: number) => request<Report>(`/api/reports/transfer/${transferId}`),
  meta: () => request<Record<string, unknown>>('/api/meta'),
  health: () => request<Record<string, unknown>>('/api/health')
}
