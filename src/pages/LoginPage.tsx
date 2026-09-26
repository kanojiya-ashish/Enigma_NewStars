import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import type { Role } from '../types'
import { Button, Field, InfoNotice } from '../components/ui'
import { Icon } from '../components/icons'

const DEMOS: { role: Role; label: string; email: string; note: string; icon: 'box' | 'users' | 'layers' | 'truck' | 'navigation' }[] = [
  { role: 'ORGANIZATION', label: 'Organization', email: 'org@reloop.demo', note: 'List surplus, decide next life and arrange transfers.', icon: 'box' },
  { role: 'RECEIVER', label: 'Receiver', email: 'receiver@reloop.demo', note: 'Create needs, accept offers and verify receipt.', icon: 'users' },
  { role: 'RECYCLER', label: 'Recycler / Recovery', email: 'recycler@reloop.demo', note: 'Accept recovery jobs and submit process proof.', icon: 'layers' },
  { role: 'LOGISTICS', label: 'Logistics Partner', email: 'logistics@reloop.demo', note: 'Dispatch vehicles, assign drivers and monitor trips.', icon: 'truck' },
  { role: 'DRIVER', label: 'Driver', email: 'driver2@reloop.demo', note: 'Receive assignments, start trips and share GPS.', icon: 'navigation' },
]

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('org@reloop.demo')
  const [password, setPassword] = useState('demo123')
  const [selectedRole, setSelectedRole] = useState<Role>('ORGANIZATION')
  const [showInternal, setShowInternal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try { await login(email.trim(), password, selectedRole) }
    catch (err) { setError(err instanceof Error ? err.message : 'Login failed') }
    finally { setBusy(false) }
  }

  const useDemo = (demo: typeof DEMOS[number]) => { setSelectedRole(demo.role); setEmail(demo.email); setPassword('demo123'); setError('') }

  return <div className="login-page">
    <div className="login-visual"><div className="visual-grid" /><div className="visual-content"><div className="brand large"><div className="brand-mark">R</div><div><div className="brand-name">RELOOP</div><div className="brand-tag">AI-powered circular resource network</div></div></div><div className="visual-copy"><span className="eyebrow">DECIDE · MATCH · ROUTE · MEASURE</span><h1>Give surplus material a verified next life.</h1><p>Reloop connects organizations, receivers, recyclers and logistics partners through explainable decisions, trusted transfers and evidence-backed circular outcomes.</p></div><div className="visual-flow">{['Surplus', 'AI decision', 'Partner', 'Transport', 'Verified impact'].map((x, i) => <div className="flow-item" key={x}><span>{String(i + 1).padStart(2, '0')}</span>{x}</div>)}</div></div></div>
    <div className="login-panel"><div className="login-card">
      <div className="login-heading"><div className="eyebrow">SIGN IN</div><h2>Choose your Reloop workspace</h2><p>Every role has a dedicated workflow and permissions.</p></div>
      <div className="role-picker">{DEMOS.map(demo => <button key={demo.role} className={`role-option ${selectedRole === demo.role ? 'selected' : ''}`} onClick={() => useDemo(demo)}><span className="role-option-icon"><Icon name={demo.icon} size={20} /></span><span><strong>{demo.label}</strong><small>{demo.note}</small></span></button>)}</div>
      {showInternal && <button className={`role-option internal ${selectedRole === 'ADMIN' ? 'selected' : ''}`} onClick={() => { setSelectedRole('ADMIN'); setEmail('admin@reloop.demo'); setPassword('demo123') }}><span className="role-option-icon"><Icon name="shield" size={20} /></span><span><strong>Platform Admin</strong><small>Internal verification and operations.</small></span></button>}
      {error && <InfoNotice><strong className="error-text">{error}</strong></InfoNotice>}
      <form onSubmit={submit} className="auth-form"><Field label="Work email" value={email} onChange={setEmail} type="email" required placeholder="name@company.com" /><label className="field"><span>Password</span><div className="password-field"><input value={password} onChange={e => setPassword(e.target.value)} type="password" required /><button type="button" className="password-toggle" onClick={e => { const input = e.currentTarget.previousElementSibling as HTMLInputElement | null; if (input) input.type = input.type === 'password' ? 'text' : 'password' }}>Show</button></div></label><Button type="submit" disabled={busy} className="full-btn">{busy ? 'Signing in…' : 'Sign in to Reloop'}</Button></form>
      <div className="demo-box"><div><strong>Fast demo access</strong><span>All demo passwords: <b>demo123</b></span></div><div className="demo-email">{DEMOS.find(d => d.role === selectedRole)?.email || 'admin@reloop.demo'}</div></div>
      <button className="internal-link" onClick={() => setShowInternal(v => !v)}>{showInternal ? 'Hide platform access' : 'Platform operations sign-in'}</button>
    </div></div>
  </div>
}
