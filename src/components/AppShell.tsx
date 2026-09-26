import { useState, type ReactNode } from 'react'
import type { Page, Role } from '../types'
import { useAuth } from '../auth/AuthContext'
import { Icon } from './icons'
import { Notifications } from './Notifications'
import { Sidebar } from './Sidebar'

export function AppShell({ role, page, onNavigate, children }: { role: Role; page: Page; onNavigate: (page: Page, transferId?: number) => void; children: ReactNode }) {
  const { session, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const roleName = role === 'ORGANIZATION' ? 'Organization' : role === 'RECEIVER' ? 'Receiver' : role === 'RECYCLER' ? 'Recycler / Recovery' : role === 'LOGISTICS' ? 'Logistics Partner' : role === 'DRIVER' ? 'Driver' : 'Platform Admin'
  return <div className="app-shell">
    <Sidebar role={role} current={page} onNavigate={onNavigate} collapsed={collapsed} onToggle={() => setCollapsed(v => !v)} />
    <main className="main-shell">
      <header className="topbar">
        <div className="topbar-context"><span className="topbar-dot" />Operational workspace <span className="slash">/</span> {roleName}</div>
        <div className="topbar-actions">
          <Notifications onNavigate={onNavigate} />
          <div className="account-menu"><div className="avatar">{(session?.user.name || 'R').slice(0,1).toUpperCase()}</div><div className="account-copy"><strong>{session?.user.name}</strong><span>{session?.organization?.name || 'Reloop Platform'}</span></div><button className="icon-btn logout-btn" title="Sign out" onClick={logout}><Icon name="logout" size={18} /></button></div>
        </div>
      </header>
      <div className="content-area">{children}</div>
    </main>
  </div>
}
