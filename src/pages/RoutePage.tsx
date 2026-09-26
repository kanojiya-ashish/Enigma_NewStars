import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { Match, Material, Organization, RouteOption } from '../types'
import { Badge, Button, Card, EmptyState, ErrorNotice, Field, InfoNotice, Loading, PageHeader, currency, number } from '../components/ui'
import { Icon } from '../components/icons'

interface RoutePageProps {
  match: Match
  onCreated: (transferId: number) => void
  onBack: () => void
}

export function RoutePage({ match, onCreated, onBack }: RoutePageProps) {
  const [material, setMaterial] = useState<Material | null>(null)
  const [routes, setRoutes] = useState<RouteOption[]>([])
  const [logistics, setLogistics] = useState<Organization[]>([])
  const [quantity, setQuantity] = useState('')
  const [routeId, setRouteId] = useState(0)
  const [logisticsId, setLogisticsId] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [routesBusy, setRoutesBusy] = useState(false)

  const loadRoutes = useCallback(async (q: number) => {
    if (!Number.isFinite(q) || q <= 0) {
      setRoutes([])
      setRouteId(0)
      return
    }
    setRoutesBusy(true)
    try {
      const rows = await api.routeOptions(match.material_id, match.partner.id, q)
      setRoutes(rows)
      setRouteId(previous => rows.some(row => row.id === previous) ? previous : (rows[0]?.id ?? 0))
      setError('')
    } catch (e) {
      setRoutes([])
      setRouteId(0)
      setError(e instanceof Error ? e.message : 'Unable to calculate route options')
    } finally {
      setRoutesBusy(false)
    }
  }, [match.material_id, match.partner.id])

  useEffect(() => {
    let cancelled = false
    const loadContext = async () => {
      setLoading(true)
      setError('')
      const [materialResult, logisticsResult] = await Promise.allSettled([
        api.material(match.material_id),
        api.logistics(),
      ])
      if (cancelled) return

      if (materialResult.status === 'fulfilled') {
        const m = materialResult.value
        setMaterial(m)
        const materialLimit = m.remaining_quantity
        const needLimit = match.need_remaining_quantity ?? materialLimit
        setQuantity(String(Math.max(0.01, Math.min(materialLimit, needLimit))))
      } else {
        setError(materialResult.reason instanceof Error ? materialResult.reason.message : 'Unable to load material')
      }

      if (logisticsResult.status === 'fulfilled') {
        const available = logisticsResult.value
        setLogistics(available)
        setLogisticsId(previous => previous && available.some(item => item.id === previous) ? previous : (available[0]?.id ?? 0))
      } else {
        setLogistics([])
        setError(prev => prev || (logisticsResult.reason instanceof Error ? logisticsResult.reason.message : 'Unable to load logistics partners'))
      }
      setLoading(false)
    }
    void loadContext()
    return () => { cancelled = true }
  }, [match.material_id, match.need_remaining_quantity])

  useEffect(() => {
    if (material) void loadRoutes(Number(quantity))
  }, [material, quantity, loadRoutes])

  const selectedRoute = useMemo(
    () => routes.find(route => route.id === routeId) ?? routes[0],
    [routes, routeId],
  )

  const selectedLogistics = logistics.find(item => item.id === logisticsId)
  const maximumQuantity = match.need_remaining_quantity ?? material?.remaining_quantity ?? 0

  const submit = async () => {
    const q = Number(quantity)
    if (!material || !selectedRoute || !selectedLogistics || q <= 0 || q > maximumQuantity) {
      setError('Select a valid quantity, route and verified logistics partner before confirming transport.')
      return
    }

    setBusy(true)
    setError('')
    try {
      const created = await api.createTransfer({
        material_id: match.material_id,
        receiver_organization_id: match.partner.id,
        logistics_partner_id: selectedLogistics.id,
        route_id: selectedRoute.id,
        quantity: q,
        need_id: match.need_id,
      })
      onCreated(created.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to create transport request')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Preparing carbon-aware transport plan…" />

  return (
    <>
      <PageHeader
        eyebrow="SMART ROUTE"
        title="Arrange transport"
        description="Choose a feasible route and verified logistics partner. Driver assignment happens after the transport request is created."
        actions={<Button variant="ghost" onClick={onBack}>Back</Button>}
      />
      {error && <ErrorNotice message={error} />}

      <div className="two-col transport-layout">
        <Card title="Shipment details">
          <div className="route-summary">
            <div><small>Material</small><strong>{material?.name ?? '—'}</strong></div>
            <div><small>Destination</small><strong>{match.partner.name}</strong><span>{match.partner.city}</span></div>
            <div><small>Partner match</small><strong>{Math.round(match.match_score)}%</strong></div>
          </div>

          <Field
            label={`Quantity (${material?.unit ?? match.need_unit ?? 'units'})`}
            value={quantity}
            onChange={setQuantity}
            type="number"
            min="0.01"
            max={String(maximumQuantity)}
            step="0.01"
            required
          />
          <div className="button-row">
            <Button variant="secondary" onClick={() => void loadRoutes(Number(quantity))} disabled={routesBusy || !Number(quantity)}>
              {routesBusy ? 'Calculating…' : 'Recalculate routes'}
            </Button>
          </div>

          <label className="field">
            <span>Logistics partner</span>
            <select value={logisticsId} onChange={event => setLogisticsId(Number(event.target.value))}>
              <option value={0}>Select verified logistics partner</option>
              {logistics.map(item => <option key={item.id} value={item.id}>{item.name} · Verified · {item.service_area_km} km area</option>)}
            </select>
          </label>

          {selectedLogistics && (
            <div className="logistics-choice">
              <div className="choice-logo"><Icon name="truck" /></div>
              <div><strong>{selectedLogistics.name}</strong><span>Verified · {selectedLogistics.service_area_km} km service area</span></div>
              <Badge tone="green">Verified</Badge>
            </div>
          )}
        </Card>

        <Card title="Route alternatives" action={selectedRoute && <Badge tone="teal">Lowest estimated CO₂</Badge>}>
          {routes.length === 0 ? (
            <EmptyState icon="route" title="No feasible route" message="Try a smaller quantity or confirm that a suitable logistics route can carry the shipment." />
          ) : (
            <div className="route-list">
              {routes.map(route => (
                <button
                  type="button"
                  className={`route-option ${selectedRoute?.id === route.id ? 'selected' : ''}`}
                  key={route.id}
                  onClick={() => setRouteId(route.id)}
                >
                  <div className="route-radio"><span /></div>
                  <div className="route-data">
                    <strong>{route.vehicle_type}</strong>
                    <div><span>{route.distance_km.toFixed(1)} km</span><span>{Math.round(route.estimated_time_min)} min</span><span>{route.capacity_units} capacity</span></div>
                  </div>
                  <div className="route-carbon"><strong>{route.estimated_co2_kg.toFixed(1)} kg</strong><span>CO₂</span></div>
                  <div className="route-score"><strong>{Math.round(route.route_score)}</strong><span>score</span></div>
                </button>
              ))}
            </div>
          )}
          <InfoNotice>CO₂ estimate = route distance × vehicle emission factor. Reloop compares only vehicle types that can carry the selected quantity.</InfoNotice>
        </Card>
      </div>

      {selectedRoute && (
        <Card className="transport-confirm">
          <div>
            <div className="eyebrow">READY TO DISPATCH</div>
            <h2>{selectedRoute.vehicle_type} · {selectedRoute.estimated_co2_kg.toFixed(1)} kg CO₂</h2>
            <p>{number(Number(quantity))} {material?.unit} · {match.partner.name} · {currency(material?.estimated_value ?? 0)} estimated material value</p>
          </div>
          <Button onClick={() => void submit()} disabled={busy || !selectedLogistics} icon="truck">
            {busy ? 'Creating request…' : 'Confirm transport request'}
          </Button>
        </Card>
      )}
    </>
  )
}
