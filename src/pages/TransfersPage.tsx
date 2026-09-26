import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { Role, Transfer, Driver } from '../types'
import { Badge, Button, Card, EmptyState, ErrorNotice, Field, Loading, PageHeader, statusTone, number, dateTime, ConfirmModal, InfoNotice } from '../components/ui'
import { Icon } from '../components/icons'

export function TransfersPage({ role, onTrack, onOutcome }: { role: Role; onTrack: (id:number)=>void; onOutcome: (id:number)=>void }) {
  const [rows,setRows]=useState<Transfer[]>([]); const [drivers,setDrivers]=useState<Driver[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState(''); const [assignId,setAssignId]=useState<number|null>(null); const [selectedDriver,setSelectedDriver]=useState(''); const [assignBusy,setAssignBusy]=useState(false); const [confirmId,setConfirmId]=useState<number|null>(null); const [receivedQty,setReceivedQty]=useState(''); const [receivedCondition,setReceivedCondition]=useState('GOOD'); const [receiptNotes,setReceiptNotes]=useState(''); const [receiptPhoto,setReceiptPhoto]=useState<File|null>(null); const [receiptBusy,setReceiptBusy]=useState(false)
  const load=useCallback(async()=>{setError('');try{const t=await api.transfers();setRows(t);if(role==='LOGISTICS')setDrivers(await api.drivers())}catch(e){setError(e instanceof Error?e.message:'Unable to load transfers')}finally{setLoading(false)}},[role])
  useEffect(()=>{load();const timer=window.setInterval(load,5000);return()=>window.clearInterval(timer)},[load])
  const compatibleDrivers = useMemo(() => {
    const transfer = assignId ? rows.find(x => x.id === assignId) : undefined
    if (!transfer) return []
    return drivers.filter(d => d.status === 'AVAILABLE' && ['BIKE','EV VAN','MINI TRUCK','TRUCK'].includes(d.vehicle_type) && (
      d.vehicle_type === 'BIKE' ? transfer.quantity <= 20 :
      d.vehicle_type === 'EV VAN' ? transfer.quantity <= 80 :
      d.vehicle_type === 'MINI TRUCK' ? transfer.quantity <= 250 :
      transfer.quantity <= 800
    ))
  }, [assignId, drivers, rows])
  useEffect(() => {
    if (!assignId) return
    const transfer = rows.find(x => x.id === assignId)
    if (!transfer) return
    let cancelled = false
    void api.eligibleDrivers(transfer.quantity).then(items => {
      if (cancelled) return
      setDrivers(previous => {
        const ids = new Set(items.map(item => item.id))
        return [...previous.filter(item => !ids.has(item.id)), ...items]
      })
    }).catch(() => {
      // The main driver list remains available as a fallback; assignment will show the backend error if eligibility changed.
    })
    return () => { cancelled = true }
  }, [assignId, rows])

  useEffect(() => {
    if (!assignId) return
    const first = compatibleDrivers[0]
    setSelectedDriver(first ? `${first.id} — ${first.driver_code} · ${first.name} · ${first.vehicle_number} · ${first.vehicle_type}` : '')
  }, [assignId, compatibleDrivers])
  const assign=async()=>{if(!assignId||!selectedDriver){setError('Select an available driver before assigning the transport.');return}const driverId=Number(selectedDriver.split(' — ')[0]);if(!driverId){setError('Select a valid driver.');return}setAssignBusy(true);setError('');try{await api.assignDriver(assignId,driverId);setAssignId(null);setSelectedDriver('');await load()}catch(e){setError(e instanceof Error?e.message:'Unable to assign driver')}finally{setAssignBusy(false)}}
  const confirmReceipt=async()=>{if(!confirmId)return;const q=Number(receivedQty);const transfer=rows.find(x=>x.id===confirmId);if(!transfer||q<=0){setError('Enter a valid received quantity.');return}setReceiptBusy(true);setError('');try{let receipt_photo_url: string|undefined;if(receiptPhoto){const upload=await api.upload(receiptPhoto);receipt_photo_url=upload.url}await api.confirmReceipt(confirmId,{received_quantity:q,received_condition:receivedCondition,notes:receiptNotes,receipt_photo_url});setConfirmId(null);setReceiptPhoto(null);setReceiptNotes('');await load()}catch(e){setError(e instanceof Error?e.message:'Unable to confirm receipt')}finally{setReceiptBusy(false)}}
  const title = role==='LOGISTICS'?'Dispatch queue':role==='DRIVER'?'My assignments':role==='RECEIVER'?'My receipts':role==='RECYCLER'?'Recovery jobs':'Transfers'
  const desc = role==='LOGISTICS'?'Accept transport requests, assign a vehicle and driver, and hand off to live tracking.':role==='DRIVER'?'Only trips assigned to your driver profile appear here.':role==='RECEIVER'?'Track incoming material and verify physical receipt before outcome proof.':role==='RECYCLER'?'Track collection, physical receipt and subsequent recovery proof.':'Monitor every transport you have initiated.'
  if(loading)return <Loading label="Loading transfer operations…"/>
  return <><PageHeader eyebrow="TRANSFER OPERATIONS" title={title} description={desc} actions={<Button variant="secondary" icon="refresh" onClick={load}>Refresh</Button>}/>{error&&<ErrorNotice message={error} onRetry={load}/>}<Card>{rows.length===0?<EmptyState icon="truck" title="No transfers in this workspace" message="Transfers will appear here as soon as a material exchange enters transport planning."/>:<div className="table-wrap"><table className="data-table"><thead><tr><th>Transfer</th><th>Shipment</th><th>Status</th><th>Driver / logistics</th><th>Updated</th><th>Actions</th></tr></thead><tbody>{rows.map(t=><tr key={t.id}><td><strong>RLP-{String(t.id).padStart(5,'0')}</strong><span className="table-sub">Route #{t.route_id || '—'}</span></td><td><strong>{number(t.quantity)} units</strong><span className="table-sub">Material #{t.material_id}</span></td><td><Badge tone={statusTone(t.status)}>{t.status.split('_').join(' ')}</Badge>{t.outcome&&<span className="table-sub">Outcome: {t.outcome.evidence_status}</span>}</td><td>{t.driver_name?<><strong>{t.driver_code}</strong><span className="table-sub">{t.driver_name} · {t.driver_vehicle_number}</span></>:<span className="table-sub">Unassigned · planned {t.route_vehicle_type || 'vehicle'}</span>}</td><td>{dateTime(t.arrived_at||t.received_at||t.pickup_time||t.created_at)}</td><td><div className="table-actions"><Button variant="ghost" onClick={()=>onTrack(t.id)} icon="location">Track</Button>{role==='LOGISTICS'&&t.status==='REQUESTED'&&<Button onClick={()=>{setAssignId(t.id);setSelectedDriver('')}} icon="users">Assign driver</Button>}{role==='DRIVER'&&t.status==='PICKUP_SCHEDULED'&&(t.driver_accepted_at?<Button onClick={async()=>{try{await api.startTrip(t.id);await load()}catch(e){setError(e instanceof Error?e.message:'Unable to start trip')}}} icon="navigation">Start trip</Button>:<Button variant="success" onClick={async()=>{try{await api.acceptAssignment(t.id);await load()}catch(e){setError(e instanceof Error?e.message:'Unable to accept ride')}}} icon="check">Accept ride</Button>)}{(role==='RECEIVER'||role==='RECYCLER')&&t.status==='DELIVERED'&&<Button onClick={()=>{setConfirmId(t.id);setReceivedQty(String(t.quantity))}} icon="check">Verify receipt</Button>}{(role==='RECEIVER'||role==='RECYCLER')&&t.status==='RECEIVED'&&<Button variant="success" onClick={()=>onOutcome(t.id)} icon="file">Submit outcome proof</Button>}{t.status==='COMPLETED'&&<Badge tone="green">Impact verified</Badge>}</div></td></tr>)}</tbody></table></div>}</Card><InfoNotice>Reloop treats <strong>transport completion</strong> and <strong>circular outcome verification</strong> as separate states. A delivered shipment does not count toward verified impact until evidence is reviewed.</InfoNotice>{assignId&&<ConfirmModal title="Assign a driver" message={`Choose an available driver for transfer RLP-${String(assignId).padStart(5,'0')}. Reloop will automatically re-plan the route to the driver's vehicle when needed, then notify the driver.`} confirmLabel={assignBusy?'Assigning…':'Assign driver'} onConfirm={assign} onCancel={()=>setAssignId(null)}><Field label="Available driver" value={selectedDriver} onChange={setSelectedDriver} options={compatibleDrivers.length ? compatibleDrivers.map(d=>`${d.id} — ${d.driver_code} · ${d.name} · ${d.vehicle_number} · ${d.vehicle_type}`) : ['No available driver can carry this shipment']}/>{compatibleDrivers.length===0&&<p className="muted">Add/activate a driver whose vehicle capacity can carry this shipment, then refresh.</p>}</ConfirmModal>}
      {confirmId&&(()=>{const transfer=rows.find(x=>x.id===confirmId); if(!transfer) return null; return <ConfirmModal title={`Verify receipt · RLP-${String(transfer.id).padStart(5,'0')}`} message="Confirm the quantity and condition that physically arrived. This changes the shipment to RECEIVED; circular outcome evidence is submitted separately." confirmLabel={receiptBusy?'Confirming…':'Confirm physical receipt'} onConfirm={confirmReceipt} onCancel={()=>{if(!receiptBusy){setConfirmId(null);setReceiptPhoto(null);setReceiptNotes('')}}}>
        <div className="form-grid compact modal-form">
          <Field label={`Received quantity (${number(transfer.quantity)} planned)`} value={receivedQty} onChange={setReceivedQty} type="number" min="0.01" max={String(transfer.quantity)} step="0.01" required disabled={receiptBusy}/>
          <Field label="Observed condition" value={receivedCondition} onChange={setReceivedCondition} options={['EXCELLENT','GOOD','FAIR','POOR']} disabled={receiptBusy}/>
          <label className="field full-span"><span>Receipt notes</span><textarea value={receiptNotes} onChange={e=>setReceiptNotes(e.target.value)} rows={3} placeholder="Quantity discrepancy, condition, packaging or handover note…" disabled={receiptBusy}/></label>
          <label className="upload-drop full-span"><Icon name="camera"/><span><strong>Receipt photo</strong><small>{receiptPhoto?receiptPhoto.name:'Optional handover photo'}</small></span><input type="file" accept="image/*" disabled={receiptBusy} onChange={e=>setReceiptPhoto(e.target.files?.[0]||null)}/></label>
          <div className="full-span"><InfoNotice><strong>Important:</strong> receipt verification proves physical handover only. Reuse/recycle/refurbish/recover evidence is a separate step.</InfoNotice></div>
        </div>
      </ConfirmModal>})()}</>
}

export function ReceiptPanel({ transfer, onDone }: { transfer: Transfer; onDone:()=>void }) {
  const [qty,setQty]=useState(String(transfer.quantity)); const [condition,setCondition]=useState('GOOD'); const [notes,setNotes]=useState(''); const [photo,setPhoto]=useState<File|null>(null); const [busy,setBusy]=useState(false);const [error,setError]=useState('')
  const submit=async()=>{setBusy(true);setError('');try{let url: string|undefined;if(photo)url=(await api.upload(photo)).url;await api.confirmReceipt(transfer.id,{received_quantity:Number(qty),received_condition:condition,notes,receipt_photo_url:url});onDone()}catch(e){setError(e instanceof Error?e.message:'Unable to confirm receipt')}finally{setBusy(false)}}
  return <Card title="Physical receipt verification"><InfoNotice>Confirm what physically arrived. This verifies handover only; the circular outcome still needs separate evidence.</InfoNotice>{error&&<ErrorNotice message={error}/>}<div className="form-grid compact"><Field label={`Received quantity (${transfer.quantity} planned)`} value={qty} onChange={setQty} type="number" min="0.01" step="0.01"/><Field label="Observed condition" value={condition} onChange={setCondition} options={['EXCELLENT','GOOD','FAIR','POOR']}/><label className="field full-span"><span>Receipt notes</span><textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} placeholder="Any quantity/condition discrepancy, packaging issue or handover note…"/></label><label className="upload-drop full-span"><Icon name="camera"/><span><strong>Receipt photo</strong><small>{photo?photo.name:'Optional handover photo'}</small></span><input type="file" accept="image/*" onChange={e=>setPhoto(e.target.files?.[0]||null)}/></label><div className="full-span form-actions"><Button onClick={submit} disabled={busy}>{busy?'Confirming…':'Confirm physical receipt'}</Button></div></div></Card>
}
