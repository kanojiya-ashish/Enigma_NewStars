import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { Role, Tracking, Transfer } from '../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  InfoNotice,
  Loading,
  PageHeader,
  dateTime,
  number,
  statusTone,
} from '../components/ui'
import { Icon } from '../components/icons'

interface TrackingPageProps {
  role: Role
  transferId?: number
  onOpenOutcome: (id: number) => void
  onOpenTransfers: () => void
}

const ARRIVAL_RADIUS_METERS = 250

function distanceMeters(lat1: number, lng1: number, lat2: number, lng2: number) {
  const toRad = (value: number) => (value * Math.PI) / 180
  const earthRadius = 6371000
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return 2 * earthRadius * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))))
}

export function TrackingPage({
  role,
  transferId,
  onOpenOutcome,
  onOpenTransfers,
}: TrackingPageProps) {
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [selected, setSelected] = useState<number>(transferId ?? 0)
  const [data, setData] = useState<Tracking | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [gpsBusy, setGpsBusy] = useState(false)
  const [deviceGps, setDeviceGps] = useState<{ latitude: number; longitude: number; accuracy_m: number; distance_m: number } | null>(null)

  const loadTransfers = useCallback(async () => {
    try {
      const rows = await api.transfers()
      setTransfers(rows)
      if (transferId && rows.some((row) => row.id === transferId)) {
        setSelected(transferId)
      } else if (!selected && rows[0]) {
        setSelected(rows[0].id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load transfers')
    } finally {
      setLoading(false)
    }
  }, [selected, transferId])

  const loadTracking = useCallback(async (id: number) => {
    try {
      const next = await api.tracking(id)
      setData(next)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load live tracking')
    }
  }, [])

  useEffect(() => {
    void loadTransfers()
  }, [loadTransfers])

  useEffect(() => {
    if (!selected) {
      setData(null)
      return
    }

    void loadTracking(selected)
    const timer = window.setInterval(() => {
      void loadTracking(selected)
    }, 2500)

    return () => window.clearInterval(timer)
  }, [selected, loadTracking])

  const percent = useMemo(() => {
    if (!data?.route || !data.latest_location) return 0

    const route = data.route
    const latDelta = route.destination_lat - route.source_lat
    const lngDelta = route.destination_lng - route.source_lng
    const latProgress = Math.abs(latDelta) < 0.00001
      ? 0
      : (data.latest_location.latitude - route.source_lat) / latDelta
    const lngProgress = Math.abs(lngDelta) < 0.00001
      ? 0
      : (data.latest_location.longitude - route.source_lng) / lngDelta

    return Math.max(0, Math.min(100, ((latProgress + lngProgress) / 2) * 100))
  }, [data])

  const readCurrentGps = async () => {
    if (!selected || !data?.route) throw new Error('Select a transfer with an active route first.')
    if (!navigator.geolocation) {
      throw new Error('Browser GPS is not available. Use the demo arrival control for the hackathon.')
    }

    const position = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      })
    })

    const latitude = position.coords.latitude
    const longitude = position.coords.longitude
    const accuracy_m = position.coords.accuracy
    const distance_m = distanceMeters(latitude, longitude, data.route!.destination_lat, data.route!.destination_lng)
    setDeviceGps({ latitude, longitude, accuracy_m, distance_m })
    return {
      latitude,
      longitude,
      accuracy_m,
      speed_kmph: position.coords.speed == null ? undefined : position.coords.speed * 3.6,
      distance_m,
    }
  }

  const sendCurrentLocation = async (markArrived = false) => {
    if (!selected) return

    setGpsBusy(true)
    setError('')

    try {
      const payload = await readCurrentGps()

      if (markArrived && payload.distance_m > ARRIVAL_RADIUS_METERS) {
        throw new Error(`GPS check passed, but you are ${Math.round(payload.distance_m)} m from the destination. Arrival requires you to be within ${ARRIVAL_RADIUS_METERS} m.`)
      }

      if (markArrived) {
        await api.markArrived(selected, payload)
      } else {
        await api.sendLocation(selected, payload)
      }

      await loadTracking(selected)
    } catch (e) {
      const code = e && typeof e === 'object' && 'code' in e ? Number((e as { code?: number }).code) : 0
      if (code === 1) {
        setError('Location permission was denied. Allow location access for localhost:5173, then try GPS again.')
      } else if (code === 2) {
        setError('Your device could not determine a GPS position. Try again outdoors or on a phone with location enabled.')
      } else if (code === 3) {
        setError('GPS timed out. Try again, or use Demo arrival for the hackathon presentation.')
      } else {
        setError(e instanceof Error ? e.message : 'Unable to send GPS location')
      }
    } finally {
      setGpsBusy(false)
    }
  }

  const simulate = async (progress: number) => {
    if (!selected) return
    setError('')
    try {
      await api.simulateLocation(selected, progress)
      await loadTracking(selected)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Demo movement failed')
    }
  }

  if (loading) {
    return <Loading label="Connecting to live tracking…" />
  }

  return (
    <>
      <PageHeader
        eyebrow="LIVE OPERATIONS"
        title="Track delivery"
        description="Every location ping is tied to a driver, transfer and timestamp. Drivers must accept the assigned ride before starting the trip; arrival is GPS-verified within 250 metres of the destination."
        actions={
          <Button
            variant="secondary"
            icon="refresh"
            onClick={() => {
              void loadTransfers()
              if (selected) void loadTracking(selected)
            }}
          >
            Refresh
          </Button>
        }
      />

      {error && <ErrorNotice message={error} onRetry={() => selected && void loadTracking(selected)} />}

      <Card>
        <div className="selector-row">
          <label className="field">
            <span>Transfer</span>
            <select
              value={selected}
              onChange={(event) => {
                setSelected(Number(event.target.value))
                setError('')
              }}
            >
              {transfers.map((transfer) => (
                <option key={transfer.id} value={transfer.id}>
                  RLP-{String(transfer.id).padStart(5, '0')} · {transfer.status.replace(/_/g, ' ')} · Material #{transfer.material_id}
                </option>
              ))}
            </select>
          </label>
          <Badge tone={data ? statusTone(data.transfer.status) : 'neutral'}>
            {data?.transfer.status?.replace(/_/g, ' ') || '—'}
          </Badge>
        </div>
      </Card>

      {!data ? (
        <EmptyState
          icon="location"
          title="Select a transfer"
          message="Choose a transfer to see its driver, route, location history and event timeline."
        />
      ) : (
        <>
          <div className="tracking-layout">
            <Card className="tracking-map" title="Live trip">
              <div className="map-surface">
                <div className="map-grid" />

                <div className="map-source">
                  <span className="map-pin source" />
                  <strong>{data.source?.name || 'Source'}</strong>
                  <small>{data.source?.city || '—'}</small>
                </div>

                <div className="map-dest">
                  <span className="map-pin dest" />
                  <strong>{data.receiver?.name || 'Destination'}</strong>
                  <small>{data.receiver?.city || '—'}</small>
                </div>

                <div
                  className="map-driver"
                  style={{
                    left: `${Math.max(8, Math.min(88, percent))}%`,
                    top: `${42 - Math.sin(percent / 15) * 12}%`,
                  }}
                >
                  <div className="driver-pulse">
                    <Icon name="truck" size={18} />
                  </div>
                  <span>{data.driver?.driver_code || 'Driver'}</span>
                </div>

                <div className="map-route-line">
                  <span style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
                </div>
              </div>

              <div className="map-meta">
                <span>
                  <Icon name="location" size={15} />
                  {data.latest_location
                    ? `${data.latest_location.latitude.toFixed(5)}, ${data.latest_location.longitude.toFixed(5)}`
                    : 'Awaiting GPS'}
                </span>
                <span>{data.latest_location ? dateTime(data.latest_location.recorded_at) : '—'}</span>
              </div>
            </Card>

            <div className="tracking-side">
              <Card title="Driver">
                <div className="driver-card">
                  {data.driver ? (
                    <>
                      <div className="driver-avatar">{data.driver.name.slice(0, 1)}</div>
                      <div>
                        <strong>{data.driver.name}</strong>
                        <span>{data.driver.driver_code} · {data.driver.vehicle_number}</span>
                        <span>{data.driver.vehicle_type} · {data.driver.status}</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <Icon name="users" size={24} />
                      <div>
                        <strong>Not assigned</strong>
                        <span>Logistics partner must assign a driver.</span>
                      </div>
                    </>
                  )}
                </div>
              </Card>

              <Card title="Trip details">
                <div className="detail-list">
                  <div>
                    <small>Shipment</small>
                    <strong>{number(data.transfer.quantity)} units</strong>
                  </div>
                  <div>
                    <small>Distance</small>
                    <strong>{data.route ? data.route.distance_km.toFixed(1) : '—'} km</strong>
                  </div>
                  <div>
                    <small>Estimated CO₂</small>
                    <strong>{data.route ? data.route.estimated_co2_kg.toFixed(1) : '—'} kg</strong>
                  </div>
                  <div>
                    <small>Arrival radius</small>
                    <strong>250 m</strong>
                  </div>
                  <div>
                    <small>Progress</small>
                    <strong>{Math.round(percent)}%</strong>
                  </div>
                </div>
              </Card>

              {role === 'DRIVER' && data.transfer.status === 'IN_TRANSIT' && (
                <Card title="GPS arrival check">
                  <div className="detail-list">
                    <div>
                      <small>Device GPS</small>
                      <strong>{deviceGps ? 'Location acquired' : 'Not checked yet'}</strong>
                    </div>
                    <div>
                      <small>Distance to destination</small>
                      <strong>{deviceGps ? `${Math.round(deviceGps.distance_m)} m` : '—'}</strong>
                    </div>
                    <div>
                      <small>Required radius</small>
                      <strong>{ARRIVAL_RADIUS_METERS} m</strong>
                    </div>
                  </div>
                  <p className="muted" style={{ marginTop: 10 }}>
                    Real arrival is accepted only when the driver's current GPS is within {ARRIVAL_RADIUS_METERS} m of the receiver.
                  </p>
                  {deviceGps && deviceGps.distance_m <= ARRIVAL_RADIUS_METERS && (
                    <Badge tone="green">Within arrival radius</Badge>
                  )}
                  {deviceGps && deviceGps.distance_m > ARRIVAL_RADIUS_METERS && (
                    <Badge tone="amber">Still {Math.round(deviceGps.distance_m)} m away</Badge>
                  )}
                </Card>
              )}

              {role === 'DRIVER' && (
                <Card title="Driver controls">
                  <div className="button-stack">
                    {role === 'DRIVER' && data.transfer.status === 'PICKUP_SCHEDULED' && (
                      data.transfer.driver_accepted_at ? (
                        <Button
                          icon="navigation"
                          onClick={async () => {
                            try {
                              await api.startTrip(data.transfer.id)
                              await loadTracking(data.transfer.id)
                            } catch (e) {
                              setError(e instanceof Error ? e.message : 'Unable to start trip')
                            }
                          }}
                        >
                          Start trip
                        </Button>
                      ) : (
                        <Button
                          variant="success"
                          icon="check"
                          onClick={async () => {
                            try {
                              await api.acceptAssignment(data.transfer.id)
                              await loadTracking(data.transfer.id)
                            } catch (e) {
                              setError(e instanceof Error ? e.message : 'Unable to accept ride')
                            }
                          }}
                        >
                          Accept ride
                        </Button>
                      )
                    )}

                    {data.transfer.status === 'IN_TRANSIT' && (
                      <>
                        <Button
                          variant="secondary"
                          icon="location"
                          disabled={gpsBusy}
                          onClick={() => {
                            setGpsBusy(true)
                            setError('')
                            void readCurrentGps().catch((e) => {
                              setError(e instanceof Error ? e.message : 'Unable to read device GPS')
                            }).finally(() => setGpsBusy(false))
                          }}
                        >
                          {gpsBusy ? 'Reading GPS…' : 'Check my GPS'}
                        </Button>

                        <Button
                          icon="location"
                          disabled={gpsBusy}
                          onClick={() => void sendCurrentLocation(false)}
                        >
                          {gpsBusy ? 'Sending GPS…' : 'Send current GPS'}
                        </Button>

                        <Button
                          variant="success"
                          icon="check"
                          disabled={gpsBusy}
                          onClick={() => void sendCurrentLocation(true)}
                        >
                          Mark arrived with GPS
                        </Button>

                        <div className="demo-controls">
                          <strong>Hackathon demo movement</strong>
                          <div>
                            <Button variant="ghost" onClick={() => void simulate(0.25)}>25%</Button>
                            <Button variant="ghost" onClick={() => void simulate(0.5)}>50%</Button>
                            <Button variant="ghost" onClick={() => void simulate(0.75)}>75%</Button>
                            <Button variant="success" onClick={() => void simulate(1)}>Demo: mark arrived</Button>
                          </div>
                          <small className="muted">Use this only for demonstration. Production arrival uses the driver's real GPS.</small>
                        </div>
                      </>
                    )}

                    {data.transfer.status === 'DELIVERED' && (
                      <InfoNotice>
                        Arrival is complete. The receiver now needs to verify the physical handover.
                      </InfoNotice>
                    )}
                  </div>
                </Card>
              )}
            </div>
          </div>

          <Card title="Transfer event history">
            {data.event_history.length === 0 ? (
              <EmptyState title="No events yet" message="Operational events will appear here as the shipment progresses." />
            ) : (
              <div className="timeline">
                {data.event_history.map((event, index) => (
                  <div className="timeline-item" key={`${event.created_at}-${index}`}>
                    <div className="timeline-dot" />
                    <div>
                      <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                      <p>{event.message}</p>
                      <small>{dateTime(event.created_at)}</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {data.transfer.status === 'DELIVERED' && (role === 'RECEIVER' || role === 'RECYCLER') && (
            <Card className="next-step-card">
              <div>
                <div className="eyebrow">RECEIPT REQUIRED</div>
                <h2>Verify physical delivery</h2>
                <p>Confirm quantity, observed condition and optional handover photo.</p>
              </div>
              <Button onClick={onOpenTransfers} icon="check">
                Open receipt workflow
              </Button>
            </Card>
          )}

          {data.transfer.status === 'RECEIVED' &&
            data.transfer.outcome?.evidence_status !== 'VERIFIED' &&
            (role === 'RECEIVER' || role === 'RECYCLER') && (
              <Card className="next-step-card">
                <div>
                  <div className="eyebrow">NEXT STEP</div>
                  <h2>Submit circular outcome evidence</h2>
                  <p>
                    Physical receipt is verified. Tell Reloop what happened to the material and attach the appropriate proof.
                  </p>
                </div>
                <Button onClick={() => onOpenOutcome(data.transfer.id)} icon="file">
                  Submit evidence
                </Button>
              </Card>
            )}
        </>
      )}
    </>
  )
}
