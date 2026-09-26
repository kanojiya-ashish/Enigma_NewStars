import { useEffect, useState } from 'react'
import type { Page } from '../types'
import { api } from '../api'
import type { Notification } from '../types'
import { dateTime } from './ui'
import { Icon } from './icons'

export function Notifications({ onNavigate }: { onNavigate: (page: Page, transferId?: number) => void }) {
  const [count, setCount] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notification[]>([])
  const [busy, setBusy] = useState(false)

  const refresh = async () => {
    try { const next = await api.unreadNotifications(); setCount(next.count) } catch { /* auth handled globally */ }
  }
  useEffect(() => { refresh(); const id = window.setInterval(refresh, 5000); return () => window.clearInterval(id) }, [])
  useEffect(() => { if (open) api.notifications().then(setItems).catch(() => setItems([])) }, [open])

  const openNotification = async (item: Notification) => {
    if (!item.is_read) { try { await api.readNotification(item.id) } catch {} }
    if (item.type === 'MATCH_REQUEST' || item.type === 'MATCH_ACCEPTED') {
      onNavigate('requests', item.transfer_id ?? undefined)
    } else if (item.transfer_id) {
      if (item.type === 'OUTCOME_SUBMITTED' || item.type === 'OUTCOME_REJECTED' || item.type === 'OUTCOME_CORRECTION_REQUESTED') onNavigate('outcome-review', item.transfer_id)
      else if (['DRIVER_ASSIGNED', 'TRIP_STARTED', 'ARRIVAL'].includes(item.type)) onNavigate('tracking', item.transfer_id)
      else onNavigate('transfers', item.transfer_id)
    }
    setOpen(false); refresh()
  }

  return <div className="notification-wrap">
    <button className="notification-btn" onClick={() => setOpen(v => !v)} aria-label="Notifications"><Icon name="bell" size={20} />{count > 0 && <span className="notification-count">{count > 99 ? '99+' : count}</span>}</button>
    {open && <div className="notification-panel">
      <div className="notification-head"><strong>Notifications</strong><button className="text-btn" onClick={async () => { setBusy(true); try { await api.readAllNotifications(); await refresh(); setItems(await api.notifications()) } finally { setBusy(false) } }}>{busy ? 'Saving…' : 'Mark all read'}</button></div>
      <div className="notification-list">{items.length === 0 ? <div className="notification-empty">You're all caught up.</div> : items.map(item => <button className={`notification-item ${item.is_read ? '' : 'unread'}`} key={item.id} onClick={() => openNotification(item)}><div className="notification-dot" /><div><strong>{item.title}</strong><p>{item.message}</p><small>{dateTime(item.created_at)}</small></div></button>)}</div>
    </div>}
  </div>
}
