# RetinaEcho Identity Foundation Design

**Status:** Approved for implementation planning

**Date:** 2026-09-04

**Parent requirements:**

- `PRD/数字记忆相框（双端统一）PRD.md`
- `spec/2026-09-04-retinaecho-mvp-design.md`
- `AGENTS.md`

## 1. Goal

Deliver the first independently testable RetinaEcho MVP slice: a family user can complete a test-adapter OTP login, a patient device can create a short-lived binding session, the first family user can atomically create one patient space and become its administrator, the device receives patient-scoped credentials, and the family user can see the new patient in their patient list.

This slice establishes the identity and isolation boundaries required by every later feature. It does not implement patient-facing standby, consent management after binding, memories, chat, media processing, summaries, invitations, or administrator transfer.

## 2. Product Invariants

1. The patient has no account and never logs in.
2. A server-created `patient_id` is the only patient business identity. Display name, phone number, face, and voice are never used to merge or associate patients.
3. Every patient-scoped family request loads an active `care_relation` on the server.
4. Every device request verifies both the token claims and the current active device row.
5. One patient has exactly one active administrator and at most one active device in the MVP.
6. Required binding consents are recorded as immutable, versioned records even though the full consent center is delivered in the next slice.
7. Tokens, OTP values and hashes, binding codes and hashes, full phone numbers, signed URLs, and private content are never logged.
8. Agnes is an optional LLM provider and cannot affect identity, authorization, or binding availability.

## 3. Selected Architecture

Use the repository layout from the formal technical specification:

```text
apps/
  patient-web/     React + TypeScript full-screen client
  family-web/      React + TypeScript mobile-first client
services/
  api/             FastAPI modular monolith
  worker/          asynchronous worker boundary
packages/
  contracts/       checked OpenAPI plus generated TypeScript types
infra/
  compose.yaml     PostgreSQL and Redis for local development
  migrations/      Alembic migrations
```

The identity slice implements the `auth`, `patients`, `devices`, `consents`, and `audit` backend modules. The worker exists as a runnable boundary but does not process identity requests. Binding writes an `asset_pack.requested` outbox row so the later cold-start slice can attach a dispatcher without changing the binding transaction.

PostgreSQL is authoritative for durable users, patients, relationships, devices, sessions, consents, audit events, idempotency results, and outbox rows. Redis holds expiring OTP challenges and binding sessions. Neither browser stores family roles. The patient browser stores only rotating device credentials after successful enrollment.

## 4. Backend Module Boundaries

### 4.1 `auth`

Owns phone normalization and protected lookup, OTP challenge state, family access tokens, rotating refresh tokens, logout, and refresh-token reuse detection.

It exposes authenticated family identity only. It does not decide patient permissions.

### 4.2 `patients`

Owns patients and care relations. It provides a single authorization service:

```python
authorize_family(user_id, patient_id, required_capability) -> AuthorizationContext
```

The patient list is produced by joining through active care relations; it never starts from a global patient query and filters in application code.

### 4.3 `devices`

Owns expiring binding sessions, device enrollment, device token issuance and rotation, current device validation, and last-seen updates. It provides:

```python
authorize_device(device_id, patient_id, required_scope) -> DeviceAuthorizationContext
```

### 4.4 `consents`

In this slice, the module validates and appends only the three binding-required consent types:

```text
ai_companion
non_medical_acknowledgement
private_memory_storage
```

All must be `granted` under the current policy version for binding to complete. Optional consents and later withdrawal are part of the governance slice.

The binding policy versions are fixed for this slice:

```text
ai_companion: ai-companion-2026-09-04
non_medical_acknowledgement: non-medical-2026-09-04
private_memory_storage: private-memory-2026-09-04
```

Clients obtain this versioned disclosure bundle from the API and submit the same identifiers during binding; they do not hard-code or invent policy versions.

### 4.5 `audit`

Writes structured, sanitized events for OTP outcomes, session refresh/revocation, binding success/failure, and privileged patient reads. Audit payloads contain opaque identifiers and result categories, never secrets or request bodies.

## 5. Durable Data

All durable primary keys are UUIDv7. External identifiers are opaque prefixed values.

### 5.1 Identity tables

- `family_users`: `fam_` external ID, encrypted E.164 phone, keyed lookup hash, status, token version, timestamps.
- `family_sessions`: hashed refresh token, token family, rotation lineage, expiration, consumed/revoked timestamps.
- `patients`: `pat_` external ID, display profile, IANA timezone, resident persona name, `provisioning` status, timestamps.
- `care_relations`: family, patient, role, relationship label, active/removed status, joined/removed timestamps.
- `patient_devices`: `dev_` external ID, patient, device public-key thumbprint, token version, active/replaced/revoked status, last seen, timestamps.
- `consent_records`: patient, type, policy version, granted state, actor, action time, superseded record reference.
- `idempotency_records`: authenticated actor, operation, key hash, canonical request hash, response status/body, expiration.
- `outbox_events`: event type, opaque aggregate ID, schema version, sanitized payload, state, timestamps.
- `audit_events`: request ID, actor type and opaque ID, patient opaque ID when applicable, action, target opaque ID, outcome, timestamp, sanitized metadata.

### 5.2 Database constraints

- Unique `family_users.phone_lookup_hash`.
- Unique active `(family_user_id, patient_id)` care relation.
- Partial unique index for one active administrator per patient.
- Partial unique index for one active device per patient.
- Unique refresh token hash.
- Unique `(actor_id, operation, idempotency_key_hash)`.
- Unique outbox event ID.

All tables that can contain patient data include an explicit `patient_id` or are reachable only through a patient-scoped foreign key.

## 6. API Contract

All routes use `/v1`. Successful single-resource responses return the resource directly. Errors use the formal stable envelope with `code`, localized `message`, `request_id`, and `details`.

### 6.1 Family authentication

```text
POST /v1/auth/otp/request
POST /v1/auth/otp/verify
POST /v1/auth/refresh
POST /v1/auth/logout
```

OTP request accepts an E.164 phone number. Responses are indistinguishable for new and existing accounts. Verification returns a 15-minute access token, a 30-day rotating refresh token, and the opaque family user ID. Refresh-token reuse revokes the entire token family.

### 6.2 Device binding

```text
POST /v1/device/binding-sessions
GET  /v1/device/binding-sessions/{binding_session_id}
POST /v1/family/bindings
POST /v1/device/token/refresh
GET  /v1/device/me
```

Creating a binding session is anonymous, rate limited, and accepts a browser-generated public-key thumbprint. It returns a ten-minute session ID, six-digit code, QR payload, expiration, and two-second polling interval.

The polling route requires the binding-session secret returned only to the device. Before completion it returns `pending`. After binding it returns a one-time encrypted device credential package and atomically marks that package delivered. Repeated delivery attempts return `410 DEVICE_CREDENTIAL_ALREADY_DELIVERED`. An expired session returns `410 BINDING_SESSION_EXPIRED`, allowing the patient client to create a replacement session.

First binding requires a family access token and `Idempotency-Key`. The request contains the binding session reference or device code, patient display profile, relationship label, and three required consent grants with their exact policy versions.

### 6.3 Patient list

```text
GET /v1/patients?cursor={opaque_cursor}&limit={1..50}
```

The response includes only patients reached through the caller's active care relations. Each item contains patient external ID, display name, relationship label, current role, provisioning status, active device status, and last synchronization time. Pagination uses an opaque signed cursor.

## 7. Critical Flows

### 7.1 OTP login

1. Normalize the phone number to E.164.
2. Apply IP and phone request limits.
3. Generate a cryptographically random six-digit OTP in non-test environments.
4. Store only a keyed challenge hash in Redis for five minutes.
5. Deliver through the configured `OtpSender` adapter.
6. On verification, atomically increment failed attempts; lock for fifteen minutes at five failures.
7. On success, create or load the family user by phone lookup hash and issue rotating session credentials.

### 7.2 First binding transaction

1. Authenticate the family user and reserve the idempotency key.
2. Lock and validate the binding session without exposing the stored code.
3. Reject missing, denied, or wrong-version required consent.
4. In one PostgreSQL transaction, create the patient, administrator care relation, active device, three consent records, audit event, outbox event, and idempotency response.
5. Commit before marking the Redis binding session completed.
6. Store the encrypted one-time device credential package in the binding session.
7. A replay using the same idempotency key and same canonical body returns the original response.
8. The same key with a different body returns `409 IDEMPOTENCY_KEY_REUSED`.
9. A different key against a consumed binding session returns `409 BINDING_SESSION_USED`.

If PostgreSQL commits but the Redis completion update fails, a recovery path reconstructs the completion package from the durable device enrollment record without creating another patient. The operation remains idempotent.

### 7.3 Device authorization

Device access JWT claims contain device external ID, patient external ID, token version, `scope=device`, issue time, and expiration. Every device request loads the active device and confirms patient and token version. A revoked, replaced, or mismatched device returns a stable authorization error and the patient client clears local credentials.

## 8. Client States

### 8.1 Patient Web

This slice implements only the enrollment portion of the formal state machine:

```text
UNENROLLED -> COLD_START -> ENROLLED_PENDING_EXPERIENCE
```

- `UNENROLLED`: no valid device credentials exist.
- `COLD_START`: create or restore a binding session, render QR and device code within three seconds, and poll at the server-provided interval.
- `ENROLLED_PENDING_EXPERIENCE`: credentials are stored and device identity is validated; render a gentle “家人已完成设置，正在准备回忆内容” holding screen until the cold-start experience slice adds caregiver setup and standby.
- Expiry creates a new binding session without a permanent error screen.
- Revocation clears credentials and returns to `COLD_START`.

No family login, consent choice, or technical error details appear in Patient Web.

### 8.2 Family Web

This slice implements:

- Phone and OTP login.
- “我照护的人” patient list with empty state.
- QR deep-link or six-digit-code binding entry.
- Patient display profile and relationship fields.
- Required disclosure and three explicit required consent controls.
- Binding progress, retryable failure, idempotent retry, and success states.

Optional consent switches and post-binding consent management are not shown until the governance slice.

## 9. Provider Adapters

### 9.1 OTP

`OtpSender` has a real-provider boundary and a deterministic test implementation.

The local/test adapter accepts a test-owned OTP value through dependency injection. Automated tests retrieve it from their fixture rather than an HTTP response or logs. Local interactive development requires an explicit non-production setting and a developer-provided value; startup fails if the test adapter is enabled in a production environment.

Provider failure returns `503 OTP_DELIVERY_UNAVAILABLE`, creates no family session, and reveals nothing about account existence.

### 9.2 Agnes

Agnes uses the OpenAI-compatible base URL `https://apihub.agnes-ai.com/v1` and the `AGNES_API_KEY` environment variable. The default model for this MVP is `agnes-2.5-flash`, supplied through configuration rather than product code.

This slice adds only a provider adapter contract and a manual smoke check that sends synthetic, non-patient text and validates a small structured response. The smoke check reads `.env` locally, redacts credentials and response headers, has a bounded timeout, and is excluded from the default test suite. Missing or invalid Agnes configuration does not stop the API, clients, OTP, binding, or patient list.

Memory extraction and chat begin consuming the Agnes adapter in their later delivery slices.

## 10. Error and Recovery Behavior

Stable errors required in this slice include:

```text
OTP_RATE_LIMITED
OTP_EXPIRED
OTP_INVALID
OTP_LOCKED
OTP_DELIVERY_UNAVAILABLE
REFRESH_TOKEN_INVALID
REFRESH_TOKEN_REUSED
BINDING_SESSION_EXPIRED
BINDING_SESSION_USED
DEVICE_CREDENTIAL_ALREADY_DELIVERED
REQUIRED_CONSENT_MISSING
CONSENT_POLICY_VERSION_INVALID
IDEMPOTENCY_KEY_REUSED
RELATION_INACTIVE
DEVICE_REVOKED
DEVICE_PATIENT_MISMATCH
```

The family client maps codes to localized, recoverable states. The patient client maps expiry to session renewal and device revocation to cold start. Neither client parses error messages.

## 11. Verification

### 11.1 Unit tests

- OTP expiry, cooldown, five-attempt lock, and non-enumerating responses.
- Refresh rotation and token-family reuse revocation.
- Required consent type and policy-version validation.
- Family and device authorization context construction.
- Opaque cursor validation.

### 11.2 PostgreSQL integration tests

- First binding creates patient, administrator relation, device, consents, audit, idempotency result, and outbox row atomically.
- Failure at each binding write rolls back the entire transaction.
- Concurrent binding cannot create two patients from one session.
- Database constraints prevent two active administrators or two active devices.
- Same idempotency key returns the original response and a changed body conflicts.
- Two families with two patients cannot read one another's patient rows.
- A removed relation cannot access its patient.

### 11.3 Redis integration tests

- OTP and binding TTLs are exact and expiration is handled.
- OTP attempt increments and binding consumption are atomic.
- A used binding code cannot be replayed.
- PostgreSQL-committed binding can recover from a failed Redis completion update.

### 11.4 API and contract tests

- OpenAPI contains every route, schema, error, header, and security scheme in this slice.
- Generated TypeScript clients compile for both Web apps.
- Device tokens cannot call family routes.
- Family tokens cannot call device routes.
- Patient-list pagination never crosses the active care relation.
- Logs redact phones, OTPs, tokens, binding codes, and request authorization headers.

### 11.5 Client tests

- Patient Web renders a code within three seconds, renews expired sessions, consumes credentials once, and returns to cold start when revoked.
- Family Web covers login, empty patient list, binding validation, retryable provider failure, idempotent retry, and successful patient list refresh.
- Both clients render a recoverable state when the API or Redis is unavailable.

### 11.6 Agnes smoke check

- Requires explicit invocation and `AGNES_API_KEY`.
- Sends only a synthetic instruction such as extracting a place and event from a fictional sentence.
- Verifies HTTP success, configured model access, non-empty content, and response parseability.
- Prints only pass/fail, latency, model name, and sanitized error category.

## 12. Acceptance Criteria

The slice is complete only when:

1. A fresh patient browser displays a QR code and six-digit code within three seconds.
2. A family user can log in through the test OTP adapter and submit the binding flow.
3. Binding atomically creates one patient, one administrator relation, one active device, three required consent records, one audit event, and one outbox event.
4. The patient browser receives patient-scoped rotating credentials once and reaches the enrolled holding state.
5. Refreshing Family Web shows the same opaque `patient_id` in “我照护的人”.
6. Idempotent retry cannot create a duplicate patient, administrator, or device.
7. Cross-patient access, member-only access without an active relation, and token-type confusion are rejected by the server.
8. OTP delivery failure leaves login recoverable and does not reveal whether the phone exists.
9. Agnes smoke checking succeeds with the locally configured key or reports a sanitized provider failure without affecting product services.
10. Relevant unit, database, Redis, API contract, and client suites pass; `git diff --check` passes; `.env` remains untracked and unmodified.
