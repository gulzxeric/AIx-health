# RetinaEcho MVP Technical Design Specification

**Status:** Proposed for implementation

**Date:** 2026-09-04

**Product source:** `PRD/数字记忆相框（双端统一）PRD.md`

**Scope:** Patient Web, Family Web/H5, shared backend, asynchronous media/AI jobs, and MVP deployment

## 1. Purpose

This specification translates the unified PRD into an implementation-level design. It defines module boundaries, data ownership, authentication and authorization, consent enforcement, API contracts, state transitions, asynchronous processing, failure behavior, and verification strategy.

The implementation must preserve four product invariants:

1. A patient never needs an account or performs business consent.
2. A server-issued `patient_id` is the only identity used to associate devices, family members, memories, media, and summaries.
3. Every patient-scoped request is authorized on the server; hiding a button is never an authorization control.
4. Extraction confidence routes memory review only. It never represents a health or cognition confidence score.

## 2. Scope and Non-goals

### 2.1 In scope

- Phone OTP registration and login for family users.
- First-device binding and creation of a patient space.
- Invitation-based joining of additional family members.
- Administrator/member authorization and administrator transfer.
- Versioned product consent and per-asset voice/image authorization.
- Patient device enrollment, token rotation, unbinding, and replacement.
- Patient standby, chat, photo-persona, and soothing state flows.
- Text, voice, and photo memory ingestion with family confirmation.
- Public-era asset pack generation and caching.
- Daily reference summary generation from de-identified interaction features.
- Zero-shot voice cloning and pre-generated photo animation behind consent gates.
- Local demo mode for development and a real cross-device demonstration path.

### 2.2 Non-goals

- Medical diagnosis, screening, treatment advice, or automated clinical alerts.
- Doctor or institution administration portals.
- Microservice deployment.
- Automatic patient deduplication based on name, face, voice, phone, or government ID.
- Multiple administrators or multiple concurrently active frames for one patient.
- Real-time lip-sync avatars, fine-tuned voice cloning, and physical hardware production.
- Long-term public asset licensing workflows beyond recording source and license metadata.

## 3. Architectural Decision

### 3.1 Selected approach

Use two independently deployable Web clients backed by a modular FastAPI monolith:

```text
┌──────────────────────┐          ┌──────────────────────┐
│ Patient Web          │          │ Family Web/H5        │
│ full-screen PWA      │          │ mobile-first PWA     │
└──────────┬───────────┘          └──────────┬───────────┘
           │ HTTPS / WebSocket               │ HTTPS / WebSocket
           └────────────────┬────────────────┘
                            ▼
               ┌─────────────────────────┐
               │ FastAPI modular monolith│
               │ auth / patient / consent│
               │ memory / device / chat  │
               │ summary / media         │
               └───────┬─────────┬───────┘
                       │         │
             ┌─────────▼──┐   ┌──▼────────────────┐
             │ PostgreSQL │   │ Redis             │
             │ source data│   │ ephemeral state   │
             └─────────┬──┘   └──┬────────────────┘
                       │         │ job queue
             ┌─────────▼──┐   ┌──▼────────────────┐
             │ Object     │   │ Background worker│
             │ storage    │   │ AI/media/summary │
             └────────────┘   └───────────────────┘
```

### 3.2 Why a modular monolith

- Four developers can work against one contract and one local environment.
- Transactions across patient, care relation, consent, and device enrollment remain straightforward.
- Domain modules create clear ownership without introducing distributed-system failure modes.
- AI and media workloads remain isolated through asynchronous jobs and replaceable adapters.
- Modules may later be extracted if load or team ownership justifies it; the MVP does not pre-emptively split them.

### 3.3 Runtime components

| Component | Responsibility | Must not do |
| :--- | :--- | :--- |
| Patient Web | Device enrollment, local sensor processing, media playback, patient state machine | Family login, consent decisions, role management |
| Family Web | Login, patient selection, configuration, consent, memory management, summaries | Trust local role state for authorization |
| API process | Synchronous validation, authorization, transactional writes, query responses | Run long AI/media jobs in request threads |
| Worker process | Asset generation, extraction, voice clone, photo animation, daily summary | Accept unauthenticated user input directly |
| PostgreSQL | Authoritative relational data and audit history | Store access tokens or OTP plaintext |
| Redis | OTP attempts, binding sessions, invites, cache, rate limits, job coordination | Serve as authoritative consent or role storage |
| Object storage | Private original and derived media | Expose permanent public URLs |

## 4. Proposed Repository Structure

The repository currently contains documentation only. Implementation should adopt the following structure:

```text
apps/
  patient-web/
    src/api/
    src/features/binding/
    src/features/standby/
    src/features/chat/
    src/features/soothing/
    src/features/sensors/
    src/state/
  family-web/
    src/api/
    src/features/auth/
    src/features/patients/
    src/features/memories/
    src/features/members/
    src/features/consents/
    src/features/summaries/
services/
  api/
    app/main.py
    app/core/
    app/modules/auth/
    app/modules/patients/
    app/modules/devices/
    app/modules/consents/
    app/modules/personas/
    app/modules/memories/
    app/modules/chat/
    app/modules/events/
    app/modules/summaries/
    app/modules/media/
    app/modules/audit/
    tests/
  worker/
    app/jobs/
    app/providers/
    tests/
packages/
  contracts/
    openapi/
    generated/
infra/
  compose.yaml
  migrations/
docs/
```

Rules:

- Each backend module owns its routes, service functions, repository queries, schemas, and tests.
- Cross-module writes go through service interfaces, not direct imports of another module's repository.
- OpenAPI is the source for generated TypeScript API types.
- Provider-specific AI, ASR, TTS, voice, and animation code lives behind worker adapters.

## 5. Domain Model

### 5.1 Identifier conventions

- All durable entities use UUIDv7 primary keys in storage.
- External IDs use opaque prefixed strings such as `pat_`, `fam_`, `dev_`, `mem_`, and `per_`.
- Display names are never identifiers.
- All timestamps are UTC in RFC 3339 over APIs and `timestamptz` in PostgreSQL.
- Records that require auditability use status transitions instead of destructive overwrites.

### 5.2 Core entities

#### `family_users`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `external_id` | text | unique, `fam_` prefix |
| `phone_e164` | text | unique, encrypted at application layer |
| `phone_lookup_hash` | bytes | unique keyed hash for lookup |
| `status` | enum | `active`, `locked`, `deleted` |
| `created_at`, `updated_at` | timestamptz | required |

#### `patients`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `external_id` | text | unique, `pat_` prefix |
| `display_name` | text | family-facing nickname, not identity evidence |
| `birth_era` | text | controlled value |
| `region` | jsonb | country/province/city codes and labels |
| `language` | enum | `mandarin`, `cantonese`, `english` |
| `resident_persona_name` | text | default `强叔` |
| `status` | enum | `provisioning`, `active`, `deletion_pending`, `deleted` |
| `created_at`, `updated_at` | timestamptz | required |

#### `care_relations`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `family_user_id` | UUID | foreign key |
| `patient_id` | UUID | foreign key |
| `role` | enum | `admin`, `member` |
| `relationship_label` | text | display only |
| `status` | enum | `active`, `removed` |
| `joined_at`, `removed_at` | timestamptz | removal timestamp nullable |

Constraints:

- Unique active relation on `(family_user_id, patient_id)`.
- Partial unique index allowing exactly one active administrator per patient.
- Administrator transfer updates old and new roles in one database transaction.

#### `patient_devices`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `external_id` | text | unique, `dev_` prefix |
| `patient_id` | UUID | foreign key |
| `token_version` | integer | increments on rotation/revocation |
| `status` | enum | `active`, `replaced`, `revoked` |
| `last_seen_at` | timestamptz | nullable |
| `created_at`, `revoked_at` | timestamptz | required/nullable |

Constraint: one active device per patient in MVP.

#### `consent_records`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `patient_id` | UUID | foreign key |
| `consent_type` | enum | defined in section 8 |
| `policy_version` | text | immutable document version |
| `state` | enum | `granted`, `denied`, `withdrawn` |
| `acted_by` | UUID | family user foreign key |
| `acted_at` | timestamptz | required |
| `supersedes_id` | UUID | previous record, nullable |

Consent is append-only. Current state is the latest record per `(patient_id, consent_type)`.

#### `personas`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `external_id` | text | unique, `per_` prefix |
| `patient_id` | UUID | foreign key |
| `display_name` | text | required |
| `relationship_label` | text | required |
| `status` | enum | `active`, `deleted` |
| `created_by` | UUID | family user foreign key |

Photos and voice samples reference `persona_id`; string name matching is prohibited.

#### `media_assets`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `patient_id` | UUID | foreign key |
| `persona_id` | UUID | nullable foreign key |
| `kind` | enum | `photo`, `voice_sample`, `idle_video`, `tts_audio` |
| `storage_key` | text | private object key |
| `sha256` | bytes | integrity and duplicate upload detection |
| `mime_type`, `byte_size` | text/integer | required |
| `authorization_record_id` | UUID | required for voice/persona image processing |
| `status` | enum | `uploaded`, `processing`, `ready`, `failed`, `deleted` |

#### `memories`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `external_id` | text | unique, `mem_` prefix |
| `patient_id` | UUID | foreign key |
| `created_by` | UUID | family user foreign key |
| `raw_text` | text | encrypted |
| `entities` | jsonb | schema-validated structured fields |
| `extraction_confidence` | numeric(4,3) | 0 through 1 |
| `uncertain_fields` | text[] | valid entity field names only |
| `confirmation_status` | enum | `pending`, `confirmed`, `rejected` |
| `confirmed_by`, `confirmed_at` | UUID/timestamptz | nullable together |
| `revision` | integer | optimistic concurrency version |

Only `confirmed` memories are searchable by patient chat.

#### `interaction_events`

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `id` | UUIDv7 | primary key |
| `patient_id`, `device_id` | UUID | required foreign keys |
| `session_id` | UUIDv7 | groups one interaction session |
| `event_type` | enum | allowlisted event type |
| `occurred_at` | timestamptz | device event time |
| `received_at` | timestamptz | server receipt time |
| `payload` | jsonb | per-type validated and size limited |

Raw camera video and continuous ambient audio are not fields in this table or accepted API payloads.

#### `daily_summaries`

Unique on `(patient_id, local_date)` and stores versioned computed facts, family-facing labels, top topics, advice, source coverage, and generation status.

## 6. Authentication and Session Design

### 6.1 Family OTP flow

1. `POST /v1/auth/otp/request` accepts an E.164 phone number.
2. The API applies IP and phone rate limits, creates a cryptographically random six-digit OTP, stores only its keyed hash in Redis for five minutes, and sends the OTP through an adapter.
3. `POST /v1/auth/otp/verify` validates the OTP and increments an attempt counter atomically.
4. First successful verification creates `family_users`; later verifications reuse the same user through `phone_lookup_hash`.
5. Success issues a 15-minute access JWT and a 30-day opaque refresh token stored hashed in PostgreSQL.
6. Refresh rotation invalidates the consumed refresh token. Reuse of an already consumed token revokes that token family.

Limits:

- One OTP request per phone per 60 seconds.
- Maximum five failed attempts per OTP challenge.
- Fifteen-minute lock after five failures.
- API responses do not reveal whether a phone is already registered.

### 6.2 Family access token

JWT claims contain `sub` as `family_user.external_id`, `session_id`, `token_version`, `iat`, and `exp`. Patient roles are not embedded because they may change before token expiry. Every patient request loads the active `care_relation` from the database or a short-lived invalidatable cache.

### 6.3 Device token

After binding, the patient Web receives a device access token containing `sub=dev_*`, `patient_id`, `token_version`, `scope=device`, `iat`, and `exp`. A refresh secret is stored in IndexedDB using the most restrictive browser storage available.

- Device access token lifetime: 15 minutes.
- Device refresh lifetime: 90 days with rotation on use.
- Unbind or replacement increments `patient_devices.token_version` and revokes refresh secrets.
- Device endpoints verify both the token patient and the active device database record.

## 7. Binding, Invitation, and Patient Identity

### 7.1 Binding session

`POST /v1/device/binding-sessions` is unauthenticated but rate limited and returns:

```json
{
  "binding_session_id": "bnd_01...",
  "device_code": "482913",
  "qr_payload": "https://family.example/bind?session=bnd_01...",
  "expires_at": "2026-09-04T08:15:00Z",
  "poll_interval_seconds": 2
}
```

Redis stores the hashed device code, session status, device public key thumbprint, expiration, and failed-attempt count. A session expires after ten minutes and becomes unusable after successful consumption.

### 7.2 First binding transaction

`POST /v1/family/bindings` requires a family token, binding session, patient profile, required consents, and a client idempotency key.

In one transaction the service:

1. Locks and consumes the binding session.
2. Creates the patient in `provisioning` status.
3. Creates the caller's administrator care relation.
4. Creates the active device record.
5. Appends required consent records.
6. Creates an audit event.
7. Writes an outbox event for asset-pack generation.

The binding session is then marked completed with an encrypted one-time device credential response. Retrying the same idempotency key returns the original result; consuming the session with a different key returns `409 BINDING_SESSION_USED`.

### 7.3 Invitations

An administrator creates an invite with `POST /v1/patients/{patient_id}/invites`. The API returns a single-use code that expires in 30 minutes. Redis stores a hash of the code plus `patient_id`, inviter, role=`member`, expiration, and state.

The recipient must authenticate, preview the invitation, and explicitly accept it. Acceptance creates an active care relation in one transaction. Existing relations return the existing patient membership without creating duplicates.

The preview exposes only patient display name, relationship label, and masked administrator phone. It does not expose memories, media, summaries, or legal name.

### 7.4 Device replacement

Only the administrator may replace a device. Replacement revokes the old device before activating the new one in the same transaction. If the new enrollment fails before activation, the old device remains active. The API must not leave two active devices.

## 8. Authorization and Consent Enforcement

### 8.1 Authorization policy

Each patient-scoped service method requires an authorization context:

```text
authorize_family(user_id, patient_id, required_capability)
authorize_device(device_id, patient_id, required_scope)
```

Capabilities are mapped server-side:

| Capability | Admin | Member |
| :--- | :---: | :---: |
| `patient.read` | yes | yes |
| `memory.create` | yes | yes |
| `memory.confirm_own` | yes | yes |
| `memory.confirm_any` | yes | no |
| `media.upload_basic` | yes | yes |
| `voice.upload` | yes | only when admin enabled voice clone |
| `summary.read` | yes | yes |
| `patient.configure` | yes | no |
| `consent.manage` | yes | no |
| `member.manage` | yes | no |
| `device.manage` | yes | no |
| `patient.delete` | yes | no |

Removed relations fail immediately with `403 RELATION_INACTIVE`.

### 8.2 Product consent types

```text
ai_companion
non_medical_acknowledgement
private_memory_storage
gaze_feature_collection
acoustic_feature_collection
conversation_history_storage
voice_cloning
photo_animation
```

`ai_companion`, `non_medical_acknowledgement`, and `private_memory_storage` must be granted to finish binding. Optional consents default to denied.

### 8.3 Enforcement points

| Operation | Required current consent |
| :--- | :--- |
| Run LLM conversation | `ai_companion` |
| Store confirmed memory | `private_memory_storage` |
| Initialize gaze processing | `gaze_feature_collection` |
| Upload gaze events | `gaze_feature_collection` |
| Compute acoustic reference features | `acoustic_feature_collection` |
| Store conversation transcript | `conversation_history_storage` |
| Upload/process voice sample | `voice_cloning` plus asset authorization |
| Generate photo animation | `photo_animation` plus asset authorization |

Consent is checked when work is accepted and again when an asynchronous job starts. Withdrawal therefore prevents queued jobs from processing stale authorization.

### 8.4 Withdrawal effects

- Gaze/acoustic withdrawal updates device configuration revision and publishes a refresh signal. Patient Web stops the sensor within one minute and no later than the next config poll.
- Conversation-history withdrawal stops new transcript storage. Existing history remains until separately deleted.
- Voice-cloning withdrawal cancels queued jobs, disables cloned voices, and enqueues deletion of derived clone artifacts.
- Photo-animation withdrawal cancels queued jobs, disables animations, and enqueues deletion of derived videos.
- Required consent withdrawal deactivates the dependent feature; it does not silently re-grant consent.

### 8.5 Browser permission exception

Browser camera and microphone permission is a device-local technical grant. The family administrator first enables the associated business capability. Patient Web then exposes a one-time caregiver setup action that calls the browser permission API.

Application behavior always follows current server consent. A browser-level permission remaining granted does not authorize the application to access the sensor after family consent is withdrawn.

## 9. Patient Web State Machine

### 9.1 States

```text
UNENROLLED → COLD_START → CAREGIVER_SETUP → STANDBY
                                           ↕
                                          CHAT
                                           ↓
                                        SOOTHING
```

`ERROR_RECOVERY` is an internal transient state; it must resolve to `COLD_START` or `STANDBY`, never a permanent error screen.

### 9.2 Transition table

| Current | Event/guard | Next | Side effect |
| :--- | :--- | :--- | :--- |
| UNENROLLED | app initialized | COLD_START | create binding session |
| COLD_START | binding completed | CAREGIVER_SETUP | persist rotating device credential |
| CAREGIVER_SETUP | required local prompts completed/skipped | STANDBY | fetch config/assets |
| STANDBY | touch or speech intent | CHAT | open session |
| STANDBY | gaze >5s on labeled persona and gaze enabled | CHAT | open persona session |
| CHAT | silence >=90s | STANDBY | close session |
| CHAT/STANDBY | 17:00–19:30 and negative signal | SOOTHING | start soothing playlist |
| SOOTHING | stable >=20m or local time >19:30 | STANDBY | close soothing event |
| any enrolled state | device revoked | COLD_START | clear local credentials |

Time-window evaluation uses the patient's configured IANA timezone, defaulting to `Asia/Shanghai` for Chinese regions. Device clock drift over five minutes uses server time offset.

### 9.3 Sensor lifecycle

- Sensors are lazy-initialized only when server consent is granted.
- Video frames remain in browser memory and are discarded after feature extraction.
- Acoustic analysis uses an in-memory rolling window and uploads numeric aggregates only.
- Chat audio sent to ASR is a separate short-lived input path and is not treated as ambient feature collection.
- Missing, denied, or failed sensor permissions disable the corresponding trigger while touch and ordinary chat remain usable.

## 10. Memory Ingestion Pipeline

### 10.1 Create request

`POST /v1/patients/{patient_id}/memories` accepts one text field, one short voice upload reference, one photo reference, or an allowed combination. At least one source is required.

Validation limits:

- Text: 1–500 Unicode characters.
- Voice: 1–30 seconds, maximum 10 MiB, allowlisted codecs.
- Photo: maximum 15 MiB, JPEG/PNG/WebP after signature validation.
- One photo per memory in MVP.

The synchronous response creates a pending memory and job:

```json
{
  "memory_id": "mem_01...",
  "status": "processing",
  "job_id": "job_01..."
}
```

### 10.2 Processing stages

1. Verify authorization and `private_memory_storage` consent.
2. Validate uploads by file signature, scan, strip metadata, and create private object keys.
3. Transcribe short voice input through the ASR adapter.
4. Combine normalized text, patient era/region/language context, and optional photo input.
5. Call the extraction adapter with a strict JSON Schema.
6. Validate output, clamp confidence to 0–1, and reject unknown fields.
7. Store entities, confidence, uncertain fields, and processing provenance.
8. Publish `memory.extraction_ready` to the family client.

### 10.3 Extraction contract

```json
{
  "era": "1970s-1980s",
  "locations": ["海珠桥"],
  "event": "修自行车",
  "preferences": ["铁观音"],
  "suggested_person_labels": [],
  "confidence": 0.95,
  "uncertain_fields": []
}
```

The model may suggest labels but may not create a persona or attach a real identity. A family user performs that action explicitly.

### 10.4 Confirmation policy

- Confidence below `0.600`: state remains `pending`; explicit family confirmation or edit is required.
- Confidence at or above `0.600`: Family Web starts a three-second undo countdown after rendering the completed card, then calls confirm.
- The server never auto-confirms based on elapsed wall time alone. The family client makes an authenticated confirm call so confirmation has an actor and audit trail.
- A member may confirm only their own submission; an administrator may confirm any submission.
- Confirm requires the current `revision`; stale revisions return `409 MEMORY_REVISION_CONFLICT`.

### 10.5 Chat indexing

Confirmation writes an outbox event. The worker generates an embedding and marks the memory searchable. Chat retrieval filters by `patient_id`, `confirmation_status=confirmed`, and `searchable=true`. Search results never cross patient partitions.

Target: confirmed text memory becomes searchable within three seconds under normal load and within one minute under degraded provider conditions.

## 11. Persona and Media Processing

### 11.1 Persona creation

A family user creates a persona with display name and relationship. The service returns `persona_id`. Photos and voice samples may then be attached to that ID. Duplicate display names are allowed because identity is based on ID.

### 11.2 Asset authorization

Each voice sample or person-photo processing request includes a checked attestation:

```json
{
  "attestation": "I_HAVE_SUBJECT_OR_GUARDIAN_PERMISSION",
  "policy_version": "persona-media-2026-09-04"
}
```

The API writes an immutable asset authorization record. Omitting or falsifying the enum fails validation; current product consent is independently checked.

### 11.3 Voice clone job

```text
uploaded → validating → processing → ready
                    ↘ failed
any non-deleted state → deletion_pending → deleted
```

Patient chat resolves voice in this order:

1. Ready authorized clone for the active persona.
2. Language-appropriate default voice.

A clone error must never fail the chat response.

### 11.4 Photo animation job

Animation is pre-generated after upload. Patient Web plays only a ready derived asset and otherwise renders the still image with a CSS breathing effect. The original photo is never modified.

### 11.5 Private media delivery

- Clients receive signed URLs valid for at most five minutes.
- Object keys include patient partitioning but not names or phone numbers.
- Download endpoints verify authorization before signing.
- Derived files inherit the source patient's access boundary and deletion policy.

## 12. Asset Pack Generation

Binding emits `asset_pack.requested` with region, era, and language. The worker:

1. Checks the exact cache key `{region_code}:{era}:{language}:{generator_version}`.
2. Generates structured topics, photo search references, song metadata, and prompt anchors.
3. Applies content safety and source/license validation.
4. Stores the versioned pack and links it to the patient.

Fallback order:

1. Exact cached regional pack.
2. Newly generated exact pack within 30 seconds.
3. Cached era/language generic pack.
4. Bundled demo-safe generic pack.

The patient becomes active once any valid pack is linked. A later successful exact generation may replace only the public pack; private memories are untouched.

## 13. Chat and Validation-Therapy Guardrails

### 13.1 Chat request context

The API constructs context from:

- Patient language and public asset pack.
- Confirmed patient-scoped memories.
- Active persona facts when persona mode is selected.
- Short session history when conversation storage is permitted; otherwise in-memory session history only.
- Hard system rules for non-diagnostic and non-confrontational language.

### 13.2 Output policy

- Chinese responses are at most 40 Han characters excluding punctuation; English uses a 30-word maximum.
- Disallowed correction patterns include direct statements that the patient remembered wrongly or is already retired.
- The assistant must not claim to be a human when directly asked.
- It must not invent a shared event for a persona when the event is absent from confirmed memory.
- Medical questions receive a short supportive boundary and a suggestion to ask a family member or professional.

### 13.3 Failure fallback

If the LLM times out or fails safety validation twice, use a language-specific local response template. If TTS fails, show the large subtitle and retry with the default voice once. The session remains usable.

## 14. Interaction Events and Daily Summary

### 14.1 Accepted events

Allowlisted event types include:

```text
session.started
session.ended
state.entered
photo.view_aggregate
chat.turn_aggregate
topic.mentioned
persona.activated
soothing.started
soothing.ended
device.heartbeat
```

Each payload has its own Pydantic schema. Unknown event types, raw blobs, and oversized payloads are rejected.

### 14.2 Idempotent ingestion

Events include a device-generated `event_id`. A unique constraint on `(device_id, event_id)` makes retries safe. The server records receipt time and rejects events whose patient does not match the authenticated device.

### 14.3 Summary computation

A daily job runs after local midnight and may be manually recomputed by version. It:

1. Loads valid events for the local date.
2. Computes coverage and refuses trend claims when fewer than three valid historical days exist.
3. Compares current features with the patient's latest seven valid days.
4. Computes internal sub-scores: interaction/gaze 40%, response timing 30%, speech continuity 30%.
5. Converts the result into non-medical family-facing status text.
6. Scores topics as `gaze_seconds + dialogue_turns*10 + active_mentions*5` and selects the top three.
7. Generates one or two validation-therapy communication suggestions from confirmed facts.

The family response omits internal extraction confidence and avoids diagnostic labels.

### 14.4 Insufficient and missing data

- Fewer than three baseline days: “正在了解日常状态”, with no percentage trend.
- No events that day: “今天暂无足够互动数据”, with no score.
- One feature unavailable: reweight available sub-scores proportionally and label source coverage.
- All features unavailable: no activity status is inferred.

## 15. API Conventions

### 15.1 Response envelope

Successful single-resource responses return the resource directly. Errors use:

```json
{
  "error": {
    "code": "RELATION_INACTIVE",
    "message": "You no longer have access to this patient.",
    "request_id": "req_01...",
    "details": {}
  }
}
```

Stable error codes are part of the client contract. Messages may be localized and must not be parsed by clients.

### 15.2 Concurrency and idempotency

- Create/bind/invite acceptance/upload initiation endpoints accept `Idempotency-Key`.
- Mutable resources expose integer `revision` and require `If-Match` or request revision.
- Conflicts return `409`, not last-write-wins.
- List endpoints use opaque cursor pagination.

### 15.3 Real-time updates

Family and patient clients use authenticated WebSocket channels for job and sync events. Channels are scoped to a patient only after authorization. Clients fall back to exponential polling starting at two seconds and capping at thirty seconds.

Event payloads contain resource IDs and status, not private media or full transcripts.

## 16. Asynchronous Jobs and Reliability

### 16.1 Job types

```text
asset_pack.generate
memory.extract
memory.embed
voice_clone.generate
photo_animation.generate
daily_summary.generate
media.delete
patient.delete
```

### 16.2 Transactional outbox

Database state changes and job requests are committed in one transaction through an outbox table. A dispatcher publishes outbox rows to the Redis-backed queue. Workers record `job_id`, attempt, provider request ID, status, and sanitized error category.

### 16.3 Retry policy

- Provider timeout/429/5xx: exponential backoff with jitter, maximum three attempts.
- Validation or unsupported-media failure: no automatic retry.
- Consent withdrawn: mark cancelled, never retry.
- Deletion jobs retry until confirmed or moved to an operations-visible dead-letter state.

All handlers are idempotent and verify the latest entity status before writing results.

## 17. Data Deletion and Retention

### 17.1 Asset deletion

Deleting a source photo or voice sample immediately hides it from APIs, disables derived use, and enqueues physical deletion. Derived clone/audio/video artifacts are deleted in the same deletion graph.

### 17.2 Patient deletion

Administrator confirmation changes the patient to `deletion_pending`, revokes device and family access, and schedules deletion of:

- Memories and embeddings.
- Media originals and derivatives.
- Conversation history and daily summaries.
- Device refresh tokens and active invites.
- Patient-specific cache entries.

Audit rows retain only the minimum non-content evidence required to demonstrate that deletion occurred: actor ID, patient opaque ID, action, timestamp, and result.

### 17.3 MVP retention defaults

- OTP challenge data: five minutes.
- Binding session: ten minutes plus 24-hour security metadata without codes.
- Invite: 30 minutes plus audit result.
- TTS response audio cache: 24 hours.
- Failed temporary uploads: 24 hours.
- Confirmed memories/media: until family deletion or patient deletion.
- De-identified interaction aggregates and summaries: until patient deletion.

## 18. Security and Privacy Controls

- HTTPS and secure WebSocket only.
- CORS allowlist contains only the two product origins.
- Refresh tokens, OTP hashes, and invite hashes are never logged.
- Private media is encrypted at rest and delivered only by short signed URL.
- Phone numbers and raw memory text are encrypted with application-managed keys; searchable phone lookup uses a keyed hash.
- File type is determined by signature, not client MIME header.
- Uploads are malware-scanned and image metadata is stripped before processing.
- Provider requests use patient opaque IDs and minimum required content.
- Every write and privileged read creates a structured audit event with request ID.
- Logs redact authorization headers, cookies, phone numbers, signed URLs, and transcript bodies.
- Rate limits apply to OTP, binding code checks, invite previews, uploads, chat, and extraction jobs.

## 19. Observability

### 19.1 Metrics

- API latency/error rate by route and error code.
- OTP request, success, failure, and lock counts.
- Binding completion and expiration rates.
- Authorization-denial counts by capability.
- Job queue depth, duration, retry, cancellation, and failure by job type/provider.
- Confirmed-memory-to-searchable latency.
- Device heartbeat freshness and config revision lag.
- Chat LLM/ASR/TTS latency and fallback rate.
- Consent-withdrawal-to-device-stop latency.

### 19.2 Tracing and correlation

Every API request has `request_id`; async work propagates `correlation_id`, `patient_id` opaque identifier, and originating request. Traces never contain raw transcript or media content.

### 19.3 Alerts

Alert on sustained authentication failures, binding completion collapse, queue backlog, patient isolation test failure, deletion dead letters, and elevated chat fallback rate. Daily-summary absence is an operational warning, not a health alert.

## 20. Failure Modes

| Failure | Required behavior |
| :--- | :--- |
| OTP provider unavailable | Return retryable error; do not create a session or reveal account existence |
| Binding code expired | Patient creates a new session; no patient record is created |
| Duplicate binding request | Idempotent replay returns original result |
| Invitation already used | Return existing relation to same user, otherwise conflict |
| Asset generation timeout | Activate patient with generic cached pack and retry exact pack later |
| Extraction provider failure | Preserve draft; family sees retry action; nothing syncs to patient |
| Low extraction confidence | Require family action; do not index memory |
| Clone/animation failure | Use default voice/still photo; keep base experience working |
| WebSocket unavailable | Fall back to bounded polling |
| Sensor permission denied | Disable that sensor; keep touch/chat/standby usable |
| Consent withdrawn during job | Cancel before provider call or discard result and delete artifact |
| Device offline | Queue config revision and sync when heartbeat resumes |
| LLM unavailable | Use local validation-therapy response library |
| Summary lacks data | State insufficient data; do not infer deterioration |

## 21. Testing Strategy

### 21.1 Unit tests

- Role-to-capability mapping and inactive relation rejection.
- Required and optional consent resolution.
- Consent supersession and withdrawal effects.
- OTP lock and expiry logic.
- Binding and invitation state transitions.
- Confidence boundary at `0.599` and `0.600`.
- Memory revision conflicts and confirmation actor rules.
- Patient Web transition guards, silence timer, and soothing time window.
- Topic scoring, baseline eligibility, missing-data reweighting.
- Provider fallback selection.

### 21.2 Database integration tests

- Exactly one active administrator per patient under concurrent updates.
- Exactly one active device under concurrent replacement.
- Unique care relation and idempotent invite acceptance.
- Transactional binding rollback on any failed insert.
- Outbox row committed with entity change.
- Cross-patient query filters cannot return another patient's memory, media, event, or summary.

### 21.3 API contract tests

- Generated TypeScript clients compile against OpenAPI.
- All patient-scoped routes reject missing relation and wrong patient ID.
- Member receives `403` on administrator actions.
- Device token cannot call family routes.
- Family token cannot call device event ingestion.
- Signed media URLs are short-lived and not returned without authorization.
- Error codes remain stable and responses do not leak sensitive state.

### 21.4 Worker tests

- Job retry classification and maximum attempts.
- Consent re-check immediately before processing.
- Duplicate delivery remains idempotent.
- Extraction schema rejects extra keys and invalid confidence.
- Clone and animation errors produce usable fallbacks.
- Source deletion removes derived artifacts.

### 21.5 End-to-end tests

1. New family login → first binding → required consent → patient standby.
2. Admin invite → second account acceptance → both see same `patient_id`.
3. Member cannot change consent or unbind.
4. High-confidence memory confirmation → patient chat retrieval.
5. Low-confidence memory remains invisible until explicit confirmation.
6. Persona photo/voice upload with authorization → persona chat; clone failure falls back.
7. Gaze consent withdrawn → device config refresh → sensor stops within one minute.
8. Browser sensor permission denied → degraded patient experience remains usable.
9. Time-dislocation phrase receives non-corrective response.
10. Patient deletion revokes access and removes content/derived media.

### 21.6 Security tests

- Horizontal access attempts across two patients and two families.
- Replay of used binding and invite codes.
- Refresh token reuse detection.
- Malicious file extension/MIME mismatch.
- Oversized event payload and unknown event type rejection.
- Log-redaction assertions for tokens, phones, signed URLs, and content.

## 22. Delivery Slices

The system is implemented as one product but should be delivered in independently testable vertical slices:

1. **Identity foundation:** OTP, patient, care relation, first binding, device token, patient list.
2. **Governance:** role enforcement, consent center, device configuration revision, audit log.
3. **Cold-start experience:** asset-pack fallback, patient state machine, standby carousel.
4. **Memory loop:** text ingestion, extraction, confidence routing, confirmation, chat retrieval.
5. **Media persona:** photo/persona management, asset authorization, voice/animation fallbacks.
6. **Conversation and soothing:** validation guardrails, multilingual ASR/TTS adapters, soothing transitions.
7. **Reference summary:** event ingestion, personal baseline, top topics, family advice.
8. **Hardening and demo:** deletion, offline recovery, security tests, full two-account demonstration.

Each slice must include migrations, API tests, client states, failure behavior, and observability before the next slice begins.

## 23. Acceptance of This Specification

This design is ready for implementation planning when review confirms:

- The modular monolith and selected storage components are acceptable for the MVP.
- `patient_id`, `persona_id`, roles, and device-token boundaries match product intent.
- All business consent remains in Family Web, with only the browser permission click performed on the patient device by a caregiver.
- Low-confidence memories cannot reach patient chat without family confirmation.
- Daily summaries remain non-diagnostic and handle insufficient data explicitly.
- The eight delivery slices match the expected four-person team scope and demonstration deadline.
