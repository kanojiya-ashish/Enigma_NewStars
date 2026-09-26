# Reloop — Final Full Stack V8.5.1

Reloop is an AI-powered circular resource exchange prototype built around one accountable workflow:

**DECIDE → MATCH → ROUTE → TRANSPORT → RECEIVE → PROVE → VERIFY → MEASURE**

The project is intentionally structured like a real product: role-based workspaces, backend authorization, lifecycle state transitions, notifications, driver assignment, GPS tracking, receipt verification, outcome evidence, reviewer verification and verified-only impact.

## Roles

Visible business workspaces:

1. Organization — lists surplus, runs assessment, selects partner, arranges transport.
2. Receiver — creates material needs, accepts offers, verifies receipt, submits reuse/refurbish proof.
3. Recycler / Recovery Partner — receives recovery jobs and submits recycle/recovery evidence.
4. Logistics Partner — receives transport requests, assigns drivers, manages dispatch.
5. Driver — sees assigned jobs, starts trips, sends GPS, marks verified arrival.

Internal platform role:

- Admin — partner verification and circular-outcome evidence review. Admin is intentionally not presented as a normal marketplace role.

## Demo credentials

All demo passwords are `demo123`.

- Organization: `org@reloop.demo`
- Receiver: `receiver@reloop.demo`
- Recycler: `recycler@reloop.demo`
- Logistics: `logistics@reloop.demo`
- Driver: `driver2@reloop.demo` (EV Van)
- Driver (additional): `driver@reloop.demo`, `driver3@reloop.demo`, `driver4@reloop.demo`
- Internal Admin: `admin@reloop.demo`

## Run on Windows

1. Extract the ZIP into a new folder.
2. Run `start.bat`.
3. Open `http://localhost:5173`.
4. Backend API docs: `http://localhost:8000/docs`.

For the fastest demo, use the Organization and Receiver accounts in two different browser tabs/windows. Driver and Logistics can be opened in additional tabs/windows.

## Driver assignment

A logistics partner can assign any active, available driver whose vehicle can carry the shipment. If the assigned driver uses a different vehicle from the original planning option, Reloop automatically recalculates the route for the assigned vehicle and records the route-change event in the audit trail.

## Verification model

Transport completion and circular outcome are separate. A driver reaching the destination proves delivery arrival; it does not prove reuse, refurbishment, recycling or recovery.

The receiving partner submits pathway-specific evidence. The internal **Reloop Verification Admin** is the accountable reviewer. The reviewer can `VERIFY`, `REQUEST_CORRECTION`, or `REJECT`. Only `VERIFIED` outcomes contribute to the impact ledger and close the circular-outcome stage; correction/rejection returns the case to the receiving partner for action and resubmission.

## Local data

SQLite is the default so no database server is required. The backend seeds realistic demo data on first run and preserves business state across restarts. `reset_demo.bat` deletes the local SQLite database so you can restart with a clean demonstration dataset.

## Developer verification

`verify_release.py` creates an isolated temporary SQLite database and checks authentication, AI assessment, matching, receiver acceptance, transport planning, logistics assignment, driver trip, GPS/arrival, receipt verification, outcome submission, reviewer verification and verified-only impact. It does not mutate the demo database.

## Final workflow

**Material → AI Decision → Match → Request → Accept → Transport → Driver Assignment → Trip → GPS → Arrival → Physical Receipt → Outcome Evidence → Platform Verification → Verified Impact**

Transport proof and circular-outcome proof are intentionally separate. A GPS-verified arrival proves handover at the destination; it does not, by itself, prove reuse, refurbishment, recycling or recovery. Only evidence that has passed the platform verification stage enters the verified impact ledger.

## Operational safeguards

- One material cannot have multiple accepted partner matches at the same time.
- Driver assignment is limited to the selected logistics partner and capacity-compatible vehicle.
- Drivers can only publish GPS for their own assigned transfer.
- Receiver/recycler proof submission is blocked until physical receipt is confirmed.
- Outcome quantities must equal the physically received quantity before verification.
- Cancelled/in-flight/completed materials and transfers follow explicit state-transition rules.
- Uploads are limited to 10 MB and supported image/PDF MIME types.
- Demo verification uses an isolated temporary database and never resets the live demo data.

## Production notes

The included prototype uses SQLite, in-app notifications, browser GPS, and deterministic geodesic routing so the project runs without paid services or API keys. For a production deployment, use PostgreSQL, HTTPS, object storage, a road-routing provider (for example OSRM/Mapbox/Google), and a push/SMS/WhatsApp provider. Browser GPS requires the driver device to grant location permission; production deployments should be HTTPS. These substitutions do not change the Reloop lifecycle or role/permission model.


## GPS arrival behavior

The Driver Portal has two clearly separated paths: `Mark arrived with GPS` for real deployments and `Demo: mark arrived` for hackathon demonstration. Real GPS arrival is accepted only when the device is within 250 metres of the route destination. The page shows the live measured distance so drivers know why an arrival was accepted or rejected. Browser GPS works on localhost when permission is granted; production deployments should use HTTPS.

## Driver assignment acceptance

A driver assignment now has an explicit acceptance step. After the logistics partner assigns a driver, the driver receives a notification and can open it to see **Accept ride**. The driver cannot start the trip until the assignment is accepted.


## V8.5.1.1 outcome submission fix
The receiver/recycler outcome form uses explicit validation (`noValidate`) so the browser cannot silently block submission. Evidence uploads show an uploading state, the submit button waits for uploads, and successful submission displays a clear “Submitted successfully” state. The server still enforces physical receipt, full received quantity, role permissions, pathway rules, and required evidence.

To test the real evidence flow locally after backend dependencies are installed:
`python test_outcome_submission.py`


## Final circular outcome verification

The receiving partner never self-completes the circular outcome. After physical receipt, the Receiver or Recycler/Recovery Partner submits pathway-specific evidence. An internal **Reloop Verification Admin** receives a persistent review notification and reviews the evidence in `Proof review`. The reviewer can:

- `VERIFY`: evidence is accepted; the outcome becomes `VERIFIED`, verified impact is created, and the transfer moves from `RECEIVED` to `COMPLETED`.
- `REQUEST_CORRECTION`: the case stays open in `RECEIVED`, the partner gets a correction notification and can resubmit.
- `REJECT`: the case stays open in `RECEIVED`, the partner gets a rejection notification and can resubmit.

Only verified quantities enter the platform impact ledger. `SUBMITTED`, `CORRECTION_REQUESTED`, `REJECTED` and `UNDER_REVIEW` outcomes do not count as verified impact.
