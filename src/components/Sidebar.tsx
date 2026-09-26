import type { Page, Role } from '../types'
import { Icon, type IconName } from './icons'
import { useEffect, useState } from 'react'

interface NavItem { page: Page; label: string; icon: IconName }

const NAV: Record<Role, NavItem[]> = {
  ORGANIZATION: [
    { page: 'dashboard', label: 'Dashboard', icon: 'grid' }, { page: 'materials', label: 'My surplus', icon: 'box' }, { page: 'add-material', label: 'Add surplus', icon: 'plus' },
    { page: 'assessment', label: 'AI assessment', icon: 'brain' }, { page: 'matching', label: 'Find partners', icon: 'users' }, { page: 'requests', label: 'Requests', icon: 'send' }, { page: 'transfers', label: 'Transfers', icon: 'truck' }, { page: 'tracking', label: 'Live tracking', icon: 'location' }, { page: 'impact', label: 'Impact', icon: 'activity' }
  ],
  RECEIVER: [
    { page: 'dashboard', label: 'Dashboard', icon: 'grid' }, { page: 'needs', label: 'My needs', icon: 'clipboard' }, { page: 'materials', label: 'Find materials', icon: 'search' },
    { page: 'requests', label: 'Incoming requests', icon: 'send' }, { page: 'transfers', label: 'My receipts', icon: 'truck' }, { page: 'tracking', label: 'Live tracking', icon: 'location' }, { page: 'impact', label: 'Impact', icon: 'activity' }
  ],
  RECYCLER: [
    { page: 'dashboard', label: 'Dashboard', icon: 'grid' }, { page: 'materials', label: 'Opportunities', icon: 'layers' }, { page: 'requests', label: 'Recovery requests', icon: 'send' },
    { page: 'transfers', label: 'Recovery jobs', icon: 'truck' }, { page: 'tracking', label: 'Live tracking', icon: 'location' }, { page: 'impact', label: 'Recovery impact', icon: 'activity' }
  ],
  LOGISTICS: [
    { page: 'dashboard', label: 'Dashboard', icon: 'grid' }, { page: 'transfers', label: 'Dispatch queue', icon: 'truck' }, { page: 'drivers', label: 'Drivers & vehicles', icon: 'users' },
    { page: 'tracking', label: 'Live deliveries', icon: 'location' }, { page: 'impact', label: 'Transport impact', icon: 'activity' }
  ],
  DRIVER: [
    { page: 'dashboard', label: 'My dashboard', icon: 'grid' }, { page: 'transfers', label: 'My assignments', icon: 'truck' }, { page: 'tracking', label: 'Active trip', icon: 'navigation' }
  ],
  ADMIN: [
    { page: 'dashboard', label: 'Operations', icon: 'grid' }, { page: 'organizations', label: 'Partner verification', icon: 'shield' }, { page: 'transfers', label: 'All transfers', icon: 'truck' },
    { page: 'outcome-review', label: 'Proof review', icon: 'clipboard' }, { page: 'tracking', label: 'Tracking', icon: 'location' }, { page: 'impact', label: 'Platform impact', icon: 'activity' }
  ]
}

export function Sidebar({ role, current, onNavigate, collapsed, onToggle }: { role: Role; current: Page; onNavigate: (page: Page) => void; collapsed: boolean; onToggle: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  useEffect(() => { setMobileOpen(false) }, [current])
  const items = NAV[role]
  return <>
    <button className="mobile-menu" onClick={() => setMobileOpen(v => !v)} aria-label="Open navigation"><Icon name="menu" size={21} /></button>
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="brand"><div className="brand-mark">R</div>{!collapsed && <div><div className="brand-name">RELOOP</div><div className="brand-tag">Circular resource network</div></div>}</div>
      <div className="role-chip"><span className="role-dot" />{!collapsed && <>{role === 'ORGANIZATION' ? 'Organization' : role === 'RECEIVER' ? 'Receiver' : role === 'RECYCLER' ? 'Recycler / Recovery' : role === 'LOGISTICS' ? 'Logistics Partner' : role === 'DRIVER' ? 'Driver' : 'Platform Admin'}</>}</div>
      <nav className="side-nav">{items.map(item => <button className={current === item.page ? 'active' : ''} title={collapsed ? item.label : undefined} key={item.page} onClick={() => onNavigate(item.page)}><Icon name={item.icon} size={19} />{!collapsed && <span>{item.label}</span>}</button>)}</nav>
      <button className="collapse-btn" onClick={onToggle}><Icon name="chevron" size={18} />{!collapsed && 'Collapse'}</button>
    </aside>
  </>
}
