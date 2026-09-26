export type Role = 'ORGANIZATION' | 'RECEIVER' | 'RECYCLER' | 'LOGISTICS' | 'DRIVER' | 'ADMIN'
export type Page =
  | 'dashboard'
  | 'materials'
  | 'add-material'
  | 'assessment'
  | 'matching'
  | 'needs'
  | 'requests'
  | 'route'
  | 'transfers'
  | 'tracking'
  | 'drivers'
  | 'outcome'
  | 'outcome-review'
  | 'impact'
  | 'organizations'

type Nullable<T> = T | null

export interface Organization {
  id: number
  name: string
  organization_type: string
  city: string
  state: string
  address: string
  latitude: number
  longitude: number
  contact_email: string
  verification_status: string
  materials_supported: string
  capacity: number
  service_area_km: number
  certifications: string
}

export interface User {
  id: number
  name: string
  email: string
  role: Role
  organization_id: Nullable<number>
}

export interface SessionData {
  token: string
  user: User
  organization: Nullable<Organization>
}

export interface Material {
  id: number
  owner_organization_id: number
  name: string
  category: string
  description: string
  quantity: number
  remaining_quantity: number
  unit: string
  condition: string
  age_years: number
  city: string
  state: string
  latitude: number
  longitude: number
  estimated_value: number
  available_from: string
  status: string
  created_at: string
}

export interface Assessment {
  id: number
  material_id: number
  condition_score: number
  recommendation: string
  confidence: number
  scores: Record<string, number>
  reasons: string[]
  factor_breakdown: Record<string, number>
  methodology: string
}

export interface Need {
  id: number
  organization_id: number
  material_name: string
  category: string
  quantity: number
  remaining_quantity: number
  unit: string
  acceptable_condition: string
  needed_by: Nullable<string>
  notes: string
  status: string
  created_at: string
}

export interface Match {
  id: Nullable<number>
  material_id: number
  need_id: Nullable<number>
  need_remaining_quantity: number | null
  need_unit: string | null
  partner: Organization
  source: Nullable<Organization>
  match_score: number
  distance_km: number
  reasons: string[]
  status: string
  factor_breakdown: Record<string, number>
}

export interface RouteOption {
  id: number
  material_id: number
  partner_organization_id: number
  vehicle_type: string
  distance_km: number
  estimated_time_min: number
  estimated_co2_kg: number
  route_score: number
  emission_factor_kg_per_km: number
  capacity_units: number
  source_lat: number
  source_lng: number
  destination_lat: number
  destination_lng: number
}

export interface Driver {
  id: number
  organization_id: number
  user_id: Nullable<number>
  driver_code: string
  name: string
  phone: string
  vehicle_type: string
  vehicle_number: string
  status: string
  current_lat: Nullable<number>
  current_lng: Nullable<number>
  last_seen_at: Nullable<string>
  is_active: boolean
}

export interface Outcome {
  id: number
  transfer_id: number
  pathway: string
  claimed_quantity: number
  narrative: string
  evidence_status: string
  before_photo_url: Nullable<string>
  after_photo_url: Nullable<string>
  process_document_url: Nullable<string>
  outcome_document_url: Nullable<string>
  submitted_at: string
  reviewed_at: Nullable<string>
  reviewer_note: string
}

export interface Transfer {
  id: number
  material_id: number
  source_organization_id: number
  receiver_organization_id: number
  logistics_partner_id: Nullable<number>
  driver_id: Nullable<number>
  driver_accepted_at: Nullable<string>
  driver_code: Nullable<string>
  driver_name: Nullable<string>
  driver_vehicle_type: Nullable<string>
  driver_vehicle_number: Nullable<string>
  route_id: Nullable<number>
  route_vehicle_type: Nullable<string>
  match_id: Nullable<number>
  need_id: Nullable<number>
  quantity: number
  status: string
  pickup_time: Nullable<string>
  delivery_time: Nullable<string>
  arrived_at: Nullable<string>
  received_at: Nullable<string>
  received_quantity: Nullable<number>
  received_condition: Nullable<string>
  receipt_notes: string
  receipt_photo_url: Nullable<string>
  cancelled_at: Nullable<string>
  created_at: string
  outcome: Nullable<Outcome>
}

export interface LocationPoint {
  latitude: number
  longitude: number
  accuracy_m: Nullable<number>
  speed_kmph: Nullable<number>
  recorded_at: string
}

export interface TransferEvent {
  event_type: string
  message: string
  created_at: string
}

export interface Tracking {
  transfer: Transfer
  driver: Nullable<Driver>
  source: Nullable<Organization>
  receiver: Nullable<Organization>
  logistics: Nullable<Organization>
  route: Nullable<RouteOption>
  latest_location: Nullable<LocationPoint>
  location_history: LocationPoint[]
  event_history: TransferEvent[]
  arrived: boolean
}

export interface Notification {
  id: number
  transfer_id: Nullable<number>
  type: string
  title: string
  message: string
  channel: string
  is_read: boolean
  created_at: string
}

export interface Impact {
  value_recovered: number
  waste_avoided_kg: number
  co2_avoided_kg: number
  verified_transfers: number
  verified_quantity: number
  by_pathway: Record<string, number>
  pathway_counts: Record<string, number>
  average_match_score: number
}

export interface Dashboard {
  role: Role
  organization: Nullable<Organization>
  metrics: Record<string, string | number>
  recent_transfers: Transfer[]
  notifications_unread: number
}

export interface Report {
  report: string
  generated_at: string
  transfer: Record<string, unknown>
  material: Record<string, unknown> | null
  source: Organization | null
  receiver: Organization | null
  logistics: Organization | null
  driver: Driver | null
  decision: Record<string, unknown> | null
  route: Record<string, unknown> | null
  tracking: Record<string, unknown>
  receipt: Record<string, unknown> | null
  outcome: Outcome | null
  impact: Record<string, unknown> | null
  methodology: string
}
