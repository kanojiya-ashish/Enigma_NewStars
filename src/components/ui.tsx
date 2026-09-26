import type { ReactNode } from 'react'
import { Icon, type IconName } from './icons'

export function Button({ children, variant = 'primary', icon, disabled, onClick, type = 'button', className = '' }: {
  children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'; icon?: IconName; disabled?: boolean; onClick?: () => void; type?: 'button' | 'submit'; className?: string
}) {
  return <button type={type} className={`btn btn-${variant} ${className}`} disabled={disabled} onClick={onClick}>{icon && <Icon name={icon} size={17} />}{children}</button>
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'blue' | 'teal' | 'green' | 'amber' | 'red' | 'violet' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function Card({ children, className = '', title, action }: { children: ReactNode; className?: string; title?: string; action?: ReactNode }) {
  return <section className={`card ${className}`}>{(title || action) && <div className="card-head"><div>{title && <h2>{title}</h2>}</div>{action}</div>}{children}</section>
}

export function StatCard({ label, value, hint, icon, tone = 'teal' }: { label: string; value: ReactNode; hint?: string; icon?: IconName; tone?: 'teal' | 'violet' | 'navy' | 'amber' }) {
  return <div className={`stat-card tone-${tone}`}><div className="stat-icon">{icon && <Icon name={icon} size={21} />}</div><div><div className="stat-label">{label}</div><div className="stat-value">{value}</div>{hint && <div className="stat-hint">{hint}</div>}</div></div>
}

export function EmptyState({ icon = 'box', title, message, action }: { icon?: IconName; title: string; message: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Icon name={icon} size={30} /></div><h3>{title}</h3><p>{message}</p>{action}</div>
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="notice notice-error"><Icon name="warning" size={20} /><div><strong>Something went wrong</strong><p>{message}</p>{onRetry && <button className="inline-link" onClick={onRetry}>Try again</button>}</div></div>
}

export function InfoNotice({ children }: { children: ReactNode }) {
  return <div className="notice notice-info"><Icon name="info" size={19} /><div>{children}</div></div>
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="header-actions">{actions}</div>}</div>
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading"><span className="spinner" />{label}</div>
}

export function ConfirmModal({ title, message, confirmLabel, onConfirm, onCancel, danger = false, children }: { title: string; message?: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void; danger?: boolean; children?: ReactNode }) {
  return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><h2>{title}</h2><button className="icon-btn" onClick={onCancel}><Icon name="close" /></button></div>{message && <p>{message}</p>}{children}<div className="modal-actions"><Button variant="ghost" onClick={onCancel}>Cancel</Button><Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>{confirmLabel}</Button></div></div></div>
}

export function Field({ label, value, onChange, placeholder, type = 'text', options, min, max, step, required = false, disabled = false }: {
  label: string; value: string | number; onChange: (value: string) => void; placeholder?: string; type?: string; options?: string[]; min?: string; max?: string; step?: string; required?: boolean; disabled?: boolean
}) {
  return <label className="field"><span>{label}{required && <em>*</em>}</span>{options ? <select value={value} onChange={e => onChange(e.target.value)} disabled={disabled}>{options.map(option => <option key={option} value={option}>{option}</option>)}</select> : <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} type={type} min={min} max={max} step={step} required={required} disabled={disabled} />}</label>
}

export const currency = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0)
export const number = (value: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value || 0)
export const dateTime = (value?: string | null) => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
export const shortDate = (value?: string | null) => value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'

export function statusTone(status: string): 'neutral' | 'blue' | 'teal' | 'green' | 'amber' | 'red' | 'violet' {
  if (['COMPLETED', 'VERIFIED', 'ACCEPTED', 'RECEIVED', 'FULFILLED'].includes(status)) return 'green'
  if (['IN_TRANSIT', 'DELIVERED', 'PICKUP_SCHEDULED'].includes(status)) return 'blue'
  if (['REQUESTED', 'SUBMITTED', 'UNDER_REVIEW', 'CORRECTION_REQUESTED', 'MATCHED'].includes(status)) return 'amber'
  if (['REJECTED', 'CANCELLED', 'SUSPENDED'].includes(status)) return 'red'
  if (['REUSE', 'REFURBISH'].includes(status)) return 'teal'
  if (['RECYCLE', 'RECOVER'].includes(status)) return 'violet'
  return 'neutral'
}
