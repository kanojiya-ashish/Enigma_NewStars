import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, apiUrl } from '../api'
import type { Outcome, Role, Transfer } from '../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  Field,
  InfoNotice,
  Loading,
  PageHeader,
  dateTime,
  number,
  statusTone,
} from '../components/ui'
import { Icon } from '../components/icons'

const PATHWAYS = ['REUSE', 'REFURBISH', 'RECYCLE', 'RECOVER'] as const
type Pathway = (typeof PATHWAYS)[number]

function availablePathways(role: Role): Pathway[] {
  return role === 'RECYCLER' ? ['RECYCLE', 'RECOVER'] : ['REUSE', 'REFURBISH']
}

export function OutcomePage({
  transferId,
  role,
  onDone,
}: {
  transferId?: number
  role: Role
  onDone: () => void
}) {
  const [transfer, setTransfer] = useState<Transfer | null>(null)
  const [existing, setExisting] = useState<Outcome | null>(null)
  const [pathway, setPathway] = useState<Pathway>(availablePathways(role)[0])
  const [claimed, setClaimed] = useState('')
  const [narrative, setNarrative] = useState('')
  const [files, setFiles] = useState<Record<string, File | null>>({
    before: null,
    after: null,
    process: null,
    outcome: null,
  })
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState<Record<string, boolean>>({})
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    if (!transferId) {
      setLoading(false)
      return
    }

    setError('')
    try {
      const [transfers, outcome] = await Promise.all([
        api.transfers(),
        api.outcome(transferId),
      ])
      const selected = transfers.find((item) => item.id === transferId) ?? null
      setTransfer(selected)
      setExisting(outcome)
      if (selected) {
        setClaimed(String(selected.received_quantity ?? selected.quantity))
      }
      if (outcome) {
        setPathway(outcome.pathway as Pathway)
        setNarrative(outcome.narrative)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load outcome workspace')
    } finally {
      setLoading(false)
    }
  }, [transferId])

  useEffect(() => {
    void load()
  }, [load])

  const chooseFile = async (key: string, file: File | null) => {
    setFiles((current) => ({ ...current, [key]: file }))
    setSuccess('')
    if (!file) {
      setUrls((current) => {
        const next = { ...current }
        delete next[key]
        return next
      })
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      setError(`${key === 'after' ? 'After/deployment' : key === 'before' ? 'Before/original state' : key === 'process' ? 'Process record' : 'Outcome document'} must be 10 MB or smaller.`)
      setFiles((current) => ({ ...current, [key]: null }))
      return
    }

    setError('')
    setUploading((current) => ({ ...current, [key]: true }))
    try {
      const uploaded = await api.upload(file)
      setUrls((current) => ({ ...current, [key]: uploaded.url }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to upload evidence')
      setFiles((current) => ({ ...current, [key]: null }))
      setUrls((current) => {
        const next = { ...current }
        delete next[key]
        return next
      })
    } finally {
      setUploading((current) => ({ ...current, [key]: false }))
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSuccess('')
    setError('')
    if (!transfer) return

    if (Object.values(uploading).some(Boolean)) {
      setError('Please wait for all selected evidence files to finish uploading.')
      return
    }

    const selectedPathways = availablePathways(role)
    if (!selectedPathways.includes(pathway)) {
      setError('The selected circular pathway is not valid for this receiving organisation.')
      return
    }

    const quantity = Number(claimed)
    const received = Number(transfer.received_quantity ?? 0)
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setError('Enter a valid outcome quantity greater than zero.')
      return
    }
    if (received <= 0) {
      setError('This transfer has no recorded received quantity. Confirm physical receipt before submitting outcome evidence.')
      return
    }
    if (Math.abs(quantity - received) > 1e-9) {
      setError(`Outcome quantity must equal the physically received quantity (${number(received)}).`)
      return
    }

    if (narrative.trim().length < 20) {
      setError('Please provide at least 20 characters explaining what happened to the material and where it is now.')
      return
    }

    const evidenceChecks: Record<Pathway, boolean> = {
      REUSE: Boolean(urls.after || urls.outcome),
      REFURBISH: Boolean(urls.before && urls.after),
      RECYCLE: Boolean(urls.process && urls.outcome),
      RECOVER: Boolean(urls.process || urls.outcome),
    }
    if (!evidenceChecks[pathway]) {
      const message = pathway === 'REUSE'
        ? 'Attach an after/deployment photo or an outcome document before submission.'
        : pathway === 'REFURBISH'
          ? 'Attach both before/original and after/deployment evidence before submission.'
          : pathway === 'RECYCLE'
            ? 'Attach both a process record and an outcome certificate/document before submission.'
            : 'Attach a process record or outcome document before submission.'
      setError(message)
      return
    }

    setBusy(true)
    try {
      const submitted = await api.submitOutcome(transfer.id, {
        pathway,
        claimed_quantity: quantity,
        narrative: narrative.trim(),
        before_photo_url: urls.before || null,
        after_photo_url: urls.after || null,
        process_document_url: urls.process || null,
        outcome_document_url: urls.outcome || null,
      })
      setExisting(submitted)
      setSuccess('Outcome evidence submitted successfully. It is now waiting for Reloop platform verification. It will count toward impact only after an Admin verifies it.')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to submit outcome evidence')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Loading outcome verification workspace…" />
  if (!transfer) {
    return <ErrorNotice message={error || 'Transfer not found or is not accessible from this workspace.'} onRetry={() => void load()} />
  }

  const status = existing?.evidence_status ?? 'NOT_STARTED'
  const pathways = availablePathways(role)
  const receivedQuantity = transfer.received_quantity ?? 0

  return (
    <>
      <PageHeader
        eyebrow="CIRCULAR OUTCOME"
        title="Prove what happened to the material"
        description="Receipt proves handover. Outcome evidence proves the circular action. Only platform-verified evidence contributes to impact."
      />

      {error && <ErrorNotice message={error} onRetry={() => void load()} />}
      {success && <div className="notice notice-success"><Icon name="check" size={20} /><div><strong>Submitted successfully</strong><p>{success}</p></div></div>}

      <Card>
        <div className="outcome-status">
          <div>
            <span className="eyebrow">TRANSFER</span>
            <h2>RLP-{String(transfer.id).padStart(5, '0')}</h2>
            <p>
              {number(receivedQuantity || transfer.quantity)} {transfer.received_quantity ? 'received' : 'planned'}
              {' · '}
              {dateTime(transfer.received_at)}
            </p>
          </div>
          <Badge tone={statusTone(status)}>{status.replace(/_/g, ' ')}</Badge>
        </div>
      </Card>

      {status === 'VERIFIED' && existing ? (
        <Card className="verified-banner">
          <div className="verified-check"><Icon name="check" size={28} /></div>
          <div>
            <h2>Outcome verified</h2>
            <p>
              {number(existing.claimed_quantity)} units recorded as verified {existing.pathway.toLowerCase()} and included in platform impact.
            </p>
          </div>
          <Button onClick={onDone}>Back to transfers</Button>
        </Card>
      ) : (
        <>
          <InfoNotice>
            <strong>Proof standard:</strong> physical receipt confirms handover only. Reuse, refurbish,
            recycle and recover evidence is reviewed separately; only <strong>VERIFIED</strong> outcomes count toward impact.
          </InfoNotice>

          {status === 'SUBMITTED' || status === 'UNDER_REVIEW' ? (
            <Card className="verified-banner">
              <div className="verified-check"><Icon name="clock" size={28} /></div>
              <div>
                <h2>{status === 'UNDER_REVIEW' ? 'Evidence is under review' : 'Evidence submitted'}</h2>
                <p>Reloop has received the circular outcome evidence. An Admin must verify it before the transfer becomes completed impact.</p>
              </div>
              <Button onClick={onDone}>Back to transfers</Button>
            </Card>
          ) : null}
          {status !== 'SUBMITTED' && status !== 'UNDER_REVIEW' && <Card title={status === 'REJECTED' || status === 'CORRECTION_REQUESTED' ? 'Correct and resubmit outcome evidence' : 'Submit outcome evidence'}>
            <form onSubmit={submit} className="form-grid" noValidate>
              {(status === 'REJECTED' || status === 'CORRECTION_REQUESTED') && existing?.reviewer_note && (
                <div className="full-span">
                  <InfoNotice><strong>Reviewer note:</strong> {existing.reviewer_note}</InfoNotice>
                </div>
              )}

              <Field
                label="Verified outcome pathway"
                value={pathway}
                onChange={(value) => setPathway(value as Pathway)}
                options={pathways}
              />

              <Field
                label={`Outcome quantity (max ${number(receivedQuantity)})`}
                value={claimed}
                onChange={setClaimed}
                type="number"
                min="0.01"
                max={String(receivedQuantity)}
                step="0.01"
                required
              />

              <label className="field full-span">
                <span>Outcome narrative <em>*</em></span>
                <textarea
                  value={narrative}
                  onChange={(event) => setNarrative(event.target.value)}
                  rows={5}
                  minLength={20}
                  required
                  placeholder="Explain where the received material went, how it was reused/refurbished/recycled/recovered, and where it is now."
                />
              </label>

              <EvidenceUpload
                label="Before / original state"
                required={pathway === 'REFURBISH'}
                file={files.before}
                url={urls.before}
                onChange={(file) => void chooseFile('before', file)}
                uploading={Boolean(uploading.before)}
              />
              <EvidenceUpload
                label="After / deployment"
                required={pathway === 'REUSE' || pathway === 'REFURBISH'}
                file={files.after}
                url={urls.after}
                onChange={(file) => void chooseFile('after', file)}
                uploading={Boolean(uploading.after)}
                accept="image/*"
              />
              <EvidenceUpload
                label="Process record"
                required={pathway === 'RECYCLE' || pathway === 'RECOVER'}
                file={files.process}
                url={urls.process}
                onChange={(file) => void chooseFile('process', file)}
                uploading={Boolean(uploading.process)}
                accept=".pdf,.jpg,.jpeg,.png,.webp"
              />
              <EvidenceUpload
                label="Outcome document / certificate"
                required={pathway === 'RECYCLE'}
                file={files.outcome}
                url={urls.outcome}
                onChange={(file) => void chooseFile('outcome', file)}
                uploading={Boolean(uploading.outcome)}
                accept=".pdf,.jpg,.jpeg,.png,.webp"
              />

              <div className="full-span">
                <InfoNotice>
                  Evidence is stored against this transfer and reviewed by Reloop operations. AI may assist document checks,
                  but it does not self-certify recycling or reuse.
                </InfoNotice>
              </div>

              <div className="full-span form-actions">
                <Button type="button" variant="secondary" onClick={onDone}>Cancel</Button>
                <Button type="submit" disabled={busy || Object.values(uploading).some(Boolean) || !Number(claimed)} icon="send">
                  {busy ? 'Submitting…' : (status === 'REJECTED' || status === 'CORRECTION_REQUESTED') ? 'Resubmit for verification' : 'Submit for verification'}
                </Button>
              </div>
            </form>
          </Card>}
        </>
      )}
    </>
  )
}

function EvidenceUpload({
  label,
  required = false,
  file,
  url,
  onChange,
  accept = 'image/*,.pdf',
  uploading = false,
}: {
  label: string
  required?: boolean
  file: File | null
  url?: string
  onChange: (file: File | null) => void
  accept?: string
  uploading?: boolean
}) {
  return (
    <label className="upload-drop">
      <Icon name="file" size={21} />
      <span>
        <strong>{label}{required && <em>*</em>}</strong>
        <small>{uploading ? 'Uploading evidence…' : file ? file.name : url ? `Uploaded: ${url}` : 'Click to attach evidence'}</small>
      </span>
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </label>
  )
}

export function OutcomeReviewPage({ onOpenTracking }: { onOpenTracking: (id: number) => void }) {
  const [rows, setRows] = useState<Outcome[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reviewId, setReviewId] = useState<number | null>(null)
  const [decision, setDecision] = useState<'VERIFIED' | 'CORRECTION_REQUESTED' | 'REJECTED'>('VERIFIED')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      setRows(await api.outcomesPending())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load proof queue')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load])

  const review = async () => {
    if (!reviewId) return
    if ((decision === 'CORRECTION_REQUESTED' || decision === 'REJECTED') && note.trim().length < 10) {
      setError('Add a reviewer note with at least 10 characters so the partner knows what to correct.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api.reviewOutcome(reviewId, decision, note)
      setReviewId(null)
      setNote('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to review evidence')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Loading evidence review queue…" />

  return (
    <>
      <PageHeader
        eyebrow="PLATFORM VERIFICATION"
        title="Circular outcome review"
        description="Reloop Verification Admin reviews submitted evidence. Approve it to count verified impact, request a correction for missing or unclear proof, or reject it when the claim cannot be supported."
        actions={<Button variant="secondary" icon="refresh" onClick={() => void load()}>Refresh</Button>}
      />
      {error && <ErrorNotice message={error} onRetry={() => void load()} />}

      <Card>
        {rows.length === 0 ? (
          <EmptyState title="Verification queue is clear" message="No submitted outcome evidence is waiting for review." icon="shield" />
        ) : (
          <div className="review-list">
            {rows.map((row) => (
              <div className="review-item" key={row.id}>
                <div>
                  <div className="review-title">
                    <strong>Transfer RLP-{String(row.transfer_id).padStart(5, '0')}</strong>
                    <Badge tone={statusTone(row.evidence_status)}>{row.evidence_status}</Badge>
                  </div>
                  <p><strong>{row.pathway}</strong> · {number(row.claimed_quantity)} units</p>
                  <p>{row.narrative}</p>
                  <div className="evidence-links">
                    {[
                      ['Before', row.before_photo_url],
                      ['After', row.after_photo_url],
                      ['Process', row.process_document_url],
                      ['Outcome document', row.outcome_document_url],
                    ].filter(([, url]) => url).map(([label, url]) => (
                      <a key={label} href={apiUrl(url as string)} target="_blank" rel="noreferrer">
                        <Icon name="file" size={14} />{label}
                      </a>
                    ))}
                  </div>
                  <small>Submitted {dateTime(row.submitted_at)}</small>
                </div>
                <div className="review-actions">
                  <Button variant="ghost" icon="location" onClick={() => onOpenTracking(row.transfer_id)}>Track transfer</Button>
                  <Button
                    icon="check"
                    onClick={() => {
                      setReviewId(row.id)
                      setDecision('VERIFIED')
                      setNote('Evidence reviewed and consistent with the submitted circular outcome.')
                    }}
                  >Verify</Button>
                  <Button
                    variant="secondary"
                    icon="clipboard"
                    onClick={() => {
                      setReviewId(row.id)
                      setDecision('CORRECTION_REQUESTED')
                      setNote('Please provide the missing or clearer evidence described in this review note, then resubmit.')
                    }}
                  >Request correction</Button>
                  <Button
                    variant="danger"
                    icon="x"
                    onClick={() => {
                      setReviewId(row.id)
                      setDecision('REJECTED')
                      setNote('The submitted evidence does not sufficiently support the claimed circular outcome.')
                    }}
                  >Reject</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {reviewId && (
        <div className="modal-backdrop">
          <div className="modal">
            <div className="modal-head">
              <h2>{decision === 'VERIFIED' ? 'Verify outcome' : decision === 'CORRECTION_REQUESTED' ? 'Request evidence correction' : 'Reject outcome'}</h2>
              <button type="button" className="icon-btn" onClick={() => setReviewId(null)}>
                <Icon name="close" />
              </button>
            </div>
            <p>This decision changes whether the outcome contributes to Reloop's verified impact ledger.</p>
            <Field label="Reviewer note" value={note} onChange={setNote} placeholder="Add a concise review note" />
            <div className="modal-actions">
              <Button variant="ghost" onClick={() => setReviewId(null)}>Cancel</Button>
              <Button variant={decision === 'VERIFIED' ? 'success' : decision === 'CORRECTION_REQUESTED' ? 'secondary' : 'danger'} onClick={() => void review()} disabled={busy}>
                {busy ? 'Saving…' : decision === 'VERIFIED' ? 'Verify & count impact' : decision === 'CORRECTION_REQUESTED' ? 'Send correction request' : 'Reject & request revision'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
