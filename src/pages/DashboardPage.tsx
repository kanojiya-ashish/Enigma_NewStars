import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Dashboard, Page, Role } from '../types'
import type { IconName } from '../components/icons'
import { Button, Card, EmptyState, ErrorNotice, Loading, PageHeader, StatCard, Badge, dateTime, statusTone, number } from '../components/ui'
import { Icon } from '../components/icons'

const roleLabel: Record<Role, string> = { ORGANIZATION: 'Organization', RECEIVER: 'Receiver', RECYCLER: 'Recycler / Recovery Partner', LOGISTICS: 'Logistics Partner', DRIVER: 'Driver', ADMIN: 'Platform Operations' }

export function DashboardPage({ role, onNavigate }: { role: Role; onNavigate: (page: Page, transferId?: number) => void }) {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = () => { setError(''); setLoading(true); api.dashboard().then(setData).catch(e => setError(e instanceof Error ? e.message : 'Unable to load dashboard')).finally(() => setLoading(false)) }
  useEffect(() => { void load() }, [])
  if (loading && !data) return <Loading label="Loading your workspace…" />
  if (error && !data) return <ErrorNotice message={error} onRetry={load} />
  const metrics = Object.entries(data?.metrics || {})
  const actionMap: Record<Role, { label: string; page: Page; icon: IconName }[]> = {
    ORGANIZATION: [{ label: 'Add surplus', page: 'add-material', icon: 'plus' }, { label: 'Run AI assessment', page: 'assessment', icon: 'brain' }, { label: 'Find partners', page: 'matching', icon: 'users' }, { label: 'Arrange transport', page: 'requests', icon: 'truck' }],
    RECEIVER: [{ label: 'Create material need', page: 'needs', icon: 'plus' }, { label: 'Incoming requests', page: 'requests', icon: 'clipboard' }, { label: 'Find materials', page: 'materials', icon: 'users' }, { label: 'Track delivery', page: 'tracking', icon: 'location' }],
    RECYCLER: [{ label: 'Recovery opportunities', page: 'materials', icon: 'box' }, { label: 'Recovery requests', page: 'requests', icon: 'clipboard' }, { label: 'Track jobs', page: 'tracking', icon: 'location' }, { label: 'Impact', page: 'impact', icon: 'brain' }],
    LOGISTICS: [{ label: 'Dispatch queue', page: 'transfers', icon: 'truck' }, { label: 'Drivers & vehicles', page: 'drivers', icon: 'users' }, { label: 'Live deliveries', page: 'tracking', icon: 'location' }, { label: 'Transport impact', page: 'impact', icon: 'brain' }],
    DRIVER: [{ label: 'My assignments', page: 'transfers', icon: 'truck' }, { label: 'Active trip', page: 'tracking', icon: 'location' }],
    ADMIN: [{ label: 'Verification queue', page: 'outcome-review', icon: 'clipboard' }, { label: 'Partner verification', page: 'organizations', icon: 'users' }, { label: 'All transfers', page: 'transfers', icon: 'truck' }, { label: 'Platform impact', page: 'impact', icon: 'brain' }],
  }
  return <>
    <PageHeader eyebrow="WORKSPACE" title={`Good to see you, ${roleLabel[role]}`} description={data?.organization ? `${data.organization.name} · ${data.organization.city}` : 'Reloop platform operations'} actions={<Button variant="secondary" icon="refresh" onClick={load}>Refresh</Button>} />
    {error && <ErrorNotice message={error} onRetry={load} />}
    <div className="stats-grid">{metrics.map(([key, value], index) => <StatCard key={key} label={key.split('_').join(' ')} value={typeof value === 'number' ? number(value) : value} tone={(['teal','violet','navy','amber'] as const)[index % 4]} />)}</div>
    <div className="action-grid">{(actionMap[role] || []).map(action => <button key={action.label} className="action-card" onClick={() => onNavigate(action.page)}><span className="action-icon"><Icon name={action.icon} size={21} /></span><span><strong>{action.label}</strong><small>Open workflow</small></span><Icon name="arrow" size={18} /></button>)}</div>
    <Card title="Recent activity" action={<Button variant="ghost" icon="activity" onClick={() => onNavigate('transfers')}>View all</Button>}>
      {(data?.recent_transfers || []).length === 0 ? <EmptyState title="No transfers yet" message="Your operational activity will appear here once a request is created." /> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Transfer</th><th>Quantity</th><th>Status</th><th>Last update</th><th /></tr></thead><tbody>{data!.recent_transfers.map(t => <tr key={t.id}><td><strong>RLP-{String(t.id).padStart(5,'0')}</strong><span className="table-sub">Material #{t.material_id}</span></td><td>{number(t.quantity)}</td><td><Badge tone={statusTone(t.status)}>{t.status.split('_').join(' ')}</Badge></td><td>{dateTime(t.arrived_at || t.received_at || t.pickup_time || t.created_at)}</td><td><button className="table-link" onClick={() => onNavigate('tracking', t.id)}>Open</button></td></tr>)}</tbody></table></div>}
    </Card>
    <Card className="integrity-card"><div className="integrity-row"><span className="integrity-icon"><Icon name="shield" size={22} /></span><div><strong>Verified impact policy</strong><p>Delivery completion does not automatically become circular impact. Outcome evidence must be submitted and verified first.</p></div><Badge tone="green">Active</Badge></div></Card>
  </>
}
