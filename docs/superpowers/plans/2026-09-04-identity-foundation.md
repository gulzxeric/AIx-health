# RetinaEcho Identity Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first secure vertical slice from family OTP login through atomic first binding, device enrollment, and the family patient list.

**Architecture:** Two React/TypeScript clients consume one FastAPI modular monolith. PostgreSQL owns durable identity and audit state, Redis owns expiring OTP and binding state, and all patient access passes through server-side relation or device authorization services. The local OTP adapter and Agnes smoke check are explicit non-production tools and never expose secrets through HTTP or logs.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL 16, Redis 7, PyJWT, cryptography, pytest, React, TypeScript, Vite, Vitest, pnpm, Docker Compose.

## Global Constraints

- Patients have no accounts and perform no business consent.
- Durable entity IDs use UUIDv7; public IDs are opaque prefixed strings.
- All API timestamps use UTC RFC 3339; local calendar logic uses an IANA timezone.
- Every patient-scoped query includes its patient boundary in SQL.
- Binding and other create operations use `Idempotency-Key`; mutable records use integer revisions.
- Logs never contain tokens, OTPs, codes, full phones, signed URLs, voice samples, or transcript bodies.
- `.env` is local-only and must remain untracked.
- Agnes is accessed through an adapter and is never required for identity endpoints.

---

### Task 1: Repository and Local Runtime Foundation

**Files:**
- Create: `.gitignore`
- Create: `.editorconfig`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `infra/compose.yaml`
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/__init__.py`
- Create: `services/api/app/main.py`
- Create: `services/api/app/core/config.py`
- Test: `services/api/tests/test_health.py`

**Interfaces:**
- Consumes: local environment variables without printing values.
- Produces: `create_app() -> FastAPI`, `GET /health/live`, PostgreSQL and Redis local services.

- [ ] **Step 1: Write the failing health test**

```python
def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test and verify import/application failure**

Run: `python -m pytest services/api/tests/test_health.py -v`

Expected: FAIL because the API package and dependencies do not exist.

- [ ] **Step 3: Add ignores, workspace metadata, Compose services, Python dependencies, settings, and app factory**

```python
def create_app() -> FastAPI:
    app = FastAPI(title="RetinaEcho API", version="0.1.0")
    app.get("/health/live")(lambda: {"status": "ok"})
    return app
```

- [ ] **Step 4: Install dependencies and verify the health test**

Run: `python -m pip install -e "services/api[test]"`

Run: `python -m pytest services/api/tests/test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .editorconfig package.json pnpm-workspace.yaml infra services/api
git commit -m "chore: scaffold RetinaEcho workspace"
```

### Task 2: Core Security, Errors, and Persistence

**Files:**
- Create: `services/api/app/core/database.py`
- Create: `services/api/app/core/redis.py`
- Create: `services/api/app/core/ids.py`
- Create: `services/api/app/core/security.py`
- Create: `services/api/app/core/errors.py`
- Create: `services/api/app/core/logging.py`
- Create: `services/api/app/models.py`
- Create: `services/api/alembic.ini`
- Create: `services/api/migrations/env.py`
- Create: `services/api/migrations/versions/20260904_0001_identity_foundation.py`
- Test: `services/api/tests/unit/test_ids.py`
- Test: `services/api/tests/unit/test_security.py`
- Test: `services/api/tests/unit/test_error_contract.py`

**Interfaces:**
- Consumes: `Settings.database_url`, `Settings.redis_url`, signing and encryption secrets.
- Produces: `new_external_id(prefix) -> str`, JWT helpers, keyed hashes, encrypted phone storage, async database/Redis dependencies, stable API errors.

- [ ] **Step 1: Write failing ID, token, keyed-hash, encryption, redaction, and error-envelope tests**

```python
def test_external_id_is_opaque_and_prefixed():
    value = new_external_id("fam")
    assert value.startswith("fam_")
    assert len(value) > 20
```

- [ ] **Step 2: Run the focused tests**

Run: `python -m pytest services/api/tests/unit/test_ids.py services/api/tests/unit/test_security.py services/api/tests/unit/test_error_contract.py -v`

Expected: FAIL because core modules do not exist.

- [ ] **Step 3: Implement the core helpers and identity schema migration**

```python
class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None): ...
```

Create family user/session, patient, care relation, device, consent, idempotency, audit, and outbox tables with the partial unique indexes defined by the approved design.

- [ ] **Step 4: Start dependencies, migrate, and rerun tests**

Run: `docker compose -f infra/compose.yaml up -d postgres redis`

Run: `python -m alembic -c services/api/alembic.ini upgrade head`

Run: `python -m pytest services/api/tests/unit -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api
git commit -m "feat: add identity persistence foundation"
```

### Task 3: Family OTP and Rotating Sessions

**Files:**
- Create: `services/api/app/modules/auth/models.py`
- Create: `services/api/app/modules/auth/schemas.py`
- Create: `services/api/app/modules/auth/otp.py`
- Create: `services/api/app/modules/auth/repository.py`
- Create: `services/api/app/modules/auth/service.py`
- Create: `services/api/app/modules/auth/routes.py`
- Test: `services/api/tests/unit/auth/test_otp.py`
- Test: `services/api/tests/integration/test_auth_api.py`

**Interfaces:**
- Consumes: Redis challenge store, family user/session repository, `OtpSender`.
- Produces: `request_otp(phone, request_context)`, `verify_otp(phone, code) -> TokenPair`, refresh, logout, and `/v1/auth/*` routes.

- [ ] **Step 1: Write failing OTP expiry, cooldown, lockout, non-enumeration, rotation, and reuse tests**

```python
async def test_fifth_invalid_attempt_locks_challenge(auth_client):
    for _ in range(5):
        await auth_client.verify("+8613800000000", "000000")
    assert await auth_client.verify("+8613800000000", "000000") == "OTP_LOCKED"
```

- [ ] **Step 2: Run the auth tests and confirm failure**

Run: `python -m pytest services/api/tests/unit/auth services/api/tests/integration/test_auth_api.py -v`

Expected: FAIL because auth services/routes do not exist.

- [ ] **Step 3: Implement the adapter, Redis challenge state, tokens, refresh rotation, and routes**

```python
class OtpSender(Protocol):
    async def send(self, phone_e164: str, code: str) -> None: ...

class TestOtpSender:
    async def send(self, phone_e164: str, code: str) -> None:
        self.deliveries[phone_e164] = code
```

The test sender is injectable only and no API response or log contains the code.

- [ ] **Step 4: Run auth tests**

Run: `python -m pytest services/api/tests/unit/auth services/api/tests/integration/test_auth_api.py -v`

Expected: PASS, including provider-failure behavior.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/modules/auth services/api/tests
git commit -m "feat: add family otp authentication"
```

### Task 4: Device Binding Sessions

**Files:**
- Create: `services/api/app/modules/devices/models.py`
- Create: `services/api/app/modules/devices/schemas.py`
- Create: `services/api/app/modules/devices/repository.py`
- Create: `services/api/app/modules/devices/service.py`
- Create: `services/api/app/modules/devices/routes.py`
- Test: `services/api/tests/unit/devices/test_binding_sessions.py`
- Test: `services/api/tests/integration/test_binding_session_api.py`

**Interfaces:**
- Consumes: Redis and rate-limit context.
- Produces: `create_binding_session(public_key_thumbprint)`, `poll_binding_session(session_id, secret)`, and anonymous `/v1/device/binding-sessions` routes.

- [ ] **Step 1: Write failing session TTL, code hashing, polling secret, expiry, and one-time delivery tests**

```python
async def test_expired_binding_session_cannot_be_polled(binding_store, clock):
    session = await binding_store.create("thumbprint")
    clock.advance(minutes=10, seconds=1)
    assert await binding_store.poll(session.id, session.secret) == "BINDING_SESSION_EXPIRED"
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest services/api/tests/unit/devices services/api/tests/integration/test_binding_session_api.py -v`

- [ ] **Step 3: Implement binding session creation and polling**

Store only hashes for human codes and polling secrets. Return the raw values only in the creation response over HTTPS.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest services/api/tests/unit/devices services/api/tests/integration/test_binding_session_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/modules/devices services/api/tests
git commit -m "feat: add device binding sessions"
```

### Task 5: Atomic First Binding and Authorization

**Files:**
- Create: `services/api/app/modules/patients/models.py`
- Create: `services/api/app/modules/patients/schemas.py`
- Create: `services/api/app/modules/patients/repository.py`
- Create: `services/api/app/modules/patients/authorization.py`
- Create: `services/api/app/modules/patients/service.py`
- Create: `services/api/app/modules/patients/routes.py`
- Create: `services/api/app/modules/consents/service.py`
- Create: `services/api/app/modules/audit/service.py`
- Test: `services/api/tests/integration/test_first_binding.py`
- Test: `services/api/tests/integration/test_patient_isolation.py`

**Interfaces:**
- Consumes: authenticated family user, binding session, required consent bundle, idempotency key.
- Produces: `bind_first_patient(command) -> BindingResult`, `authorize_family`, `authorize_device`, `/v1/family/bindings`, `/v1/patients`, `/v1/device/me`.

- [ ] **Step 1: Write failing atomicity, concurrency, idempotency, role, token-confusion, and two-patient isolation tests**

```python
async def test_family_cannot_list_unrelated_patient(api, family_a, family_b_patient):
    response = await api.get("/v1/patients", token=family_a.access_token)
    assert family_b_patient.external_id not in response.text
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest services/api/tests/integration/test_first_binding.py services/api/tests/integration/test_patient_isolation.py -v`

- [ ] **Step 3: Implement required consent validation and the single binding transaction**

```python
REQUIRED_BINDING_POLICIES = {
    "ai_companion": "ai-companion-2026-09-04",
    "non_medical_acknowledgement": "non-medical-2026-09-04",
    "private_memory_storage": "private-memory-2026-09-04",
}
```

Create patient, administrator relation, active device, consent records, audit row, outbox row, and replayable idempotency result together.

- [ ] **Step 4: Run focused and full API suites**

Run: `python -m pytest services/api/tests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api
git commit -m "feat: add atomic first patient binding"
```

### Task 6: OpenAPI Contract and Generated Client

**Files:**
- Create: `packages/contracts/openapi/retinaecho-v1.json`
- Create: `packages/contracts/package.json`
- Create: `packages/contracts/generated/client.ts`
- Create: `packages/contracts/generated/schema.ts`
- Create: `scripts/export-openapi.py`
- Test: `services/api/tests/contract/test_openapi.py`

**Interfaces:**
- Consumes: FastAPI app schema.
- Produces: deterministic OpenAPI artifact and TypeScript client types used by both Web apps.

- [ ] **Step 1: Write failing contract tests for routes, security schemes, idempotency header, and stable errors**

```python
def test_binding_declares_idempotency_header(openapi_schema):
    operation = openapi_schema["paths"]["/v1/family/bindings"]["post"]
    assert any(p["name"] == "Idempotency-Key" for p in operation["parameters"])
```

- [ ] **Step 2: Run contract test and confirm failure**

Run: `python -m pytest services/api/tests/contract/test_openapi.py -v`

- [ ] **Step 3: Export OpenAPI and generate TypeScript**

Run: `python scripts/export-openapi.py`

Run: `pnpm --filter @retinaecho/contracts generate`

- [ ] **Step 4: Verify deterministic generation and TypeScript compilation**

Run: `python -m pytest services/api/tests/contract -v`

Run: `pnpm --filter @retinaecho/contracts typecheck`

Expected: PASS and no generated diff on a second run.

- [ ] **Step 5: Commit**

```bash
git add packages scripts services/api/tests/contract
git commit -m "feat: publish identity api contract"
```

### Task 7: Patient Web Enrollment UI

**Files:**
- Create: `apps/patient-web/package.json`
- Create: `apps/patient-web/index.html`
- Create: `apps/patient-web/src/main.tsx`
- Create: `apps/patient-web/src/app.tsx`
- Create: `apps/patient-web/src/api/client.ts`
- Create: `apps/patient-web/src/features/binding/machine.ts`
- Create: `apps/patient-web/src/features/binding/binding-screen.tsx`
- Create: `apps/patient-web/src/styles.css`
- Test: `apps/patient-web/src/features/binding/binding-screen.test.tsx`

**Interfaces:**
- Consumes: generated contract and device binding endpoints.
- Produces: `UNENROLLED`, `COLD_START`, and `ENROLLED_PENDING_EXPERIENCE` client states.

- [ ] **Step 1: Write failing state and rendering tests**

```tsx
it("renews an expired binding session without showing a technical error", async () => {
  render(<BindingScreen api={expiredThenFreshApi} />)
  expect(await screen.findByText("请家人扫码设置")).toBeVisible()
  expect(await screen.findByText("482913")).toBeVisible()
})
```

- [ ] **Step 2: Run patient tests and confirm failure**

Run: `pnpm --filter @retinaecho/patient-web test`

- [ ] **Step 3: Implement the explicit state reducer, polling, credential store, and accessible screen**

Use at least 32pt core text, at least 7:1 contrast, large touch targets, no login or consent UI, and recoverable copy only.

- [ ] **Step 4: Run tests, typecheck, and production build**

Run: `pnpm --filter @retinaecho/patient-web test && pnpm --filter @retinaecho/patient-web typecheck && pnpm --filter @retinaecho/patient-web build`

- [ ] **Step 5: Commit**

```bash
git add apps/patient-web
git commit -m "feat: add patient enrollment experience"
```

### Task 8: Family Web Login, Binding, and Patient List

**Files:**
- Create: `apps/family-web/package.json`
- Create: `apps/family-web/index.html`
- Create: `apps/family-web/src/main.tsx`
- Create: `apps/family-web/src/app.tsx`
- Create: `apps/family-web/src/api/client.ts`
- Create: `apps/family-web/src/features/auth/login-screen.tsx`
- Create: `apps/family-web/src/features/patients/patient-list.tsx`
- Create: `apps/family-web/src/features/patients/binding-flow.tsx`
- Create: `apps/family-web/src/copy/zh-CN.ts`
- Create: `apps/family-web/src/styles.css`
- Test: `apps/family-web/src/app.test.tsx`

**Interfaces:**
- Consumes: generated family auth, binding, and patient-list API types.
- Produces: mobile-first login, explicit required disclosure, idempotent binding flow, and “我照护的人”.

- [ ] **Step 1: Write failing login, empty-state, disclosure, retry, and successful list-refresh tests**

```tsx
it("does not submit binding until all required disclosures are granted", async () => {
  render(<BindingFlow api={api} />)
  await user.click(screen.getByRole("button", { name: "完成绑定" }))
  expect(api.bind).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run family tests and confirm failure**

Run: `pnpm --filter @retinaecho/family-web test`

- [ ] **Step 3: Implement typed API calls and explicit UI states**

Keep all Chinese copy centralized. Never expose raw error codes, secret values, or medical claims to users.

- [ ] **Step 4: Run tests, typecheck, and production build**

Run: `pnpm --filter @retinaecho/family-web test && pnpm --filter @retinaecho/family-web typecheck && pnpm --filter @retinaecho/family-web build`

- [ ] **Step 5: Commit**

```bash
git add apps/family-web
git commit -m "feat: add family identity flow"
```

### Task 9: Agnes Smoke Check and Slice Verification

**Files:**
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/app/providers/agnes.py`
- Create: `services/worker/scripts/check_agnes.py`
- Test: `services/worker/tests/test_agnes_adapter.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `AGNES_API_KEY`, configurable Agnes base URL/model, synthetic smoke input.
- Produces: provider adapter and explicit smoke command that prints only status, latency, model, and sanitized error category.

- [ ] **Step 1: Write failing adapter tests with mocked HTTP success, timeout, 429, 5xx, and malformed response**

```python
async def test_timeout_is_sanitized(http_mock):
    http_mock.timeout()
    with pytest.raises(ProviderUnavailable) as exc:
        await adapter.complete_synthetic_check()
    assert "key" not in str(exc.value).lower()
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest services/worker/tests -v`

- [ ] **Step 3: Implement the OpenAI-compatible Agnes adapter and smoke CLI**

Use `https://apihub.agnes-ai.com/v1`, model `agnes-2.5-flash`, a bounded timeout, no retries in the manual check, and synthetic text only.

- [ ] **Step 4: Run all automated verification and the explicitly requested smoke check**

Run: `python -m pytest services/api/tests services/worker/tests -v`

Run: `pnpm -r test && pnpm -r typecheck && pnpm -r build`

Run: `python services/worker/scripts/check_agnes.py`

Expected: all automated tests pass; the smoke command reports success or a sanitized provider failure without exposing credentials.

- [ ] **Step 5: Check repository hygiene and commit**

Run: `git diff --check`

Run: `git status --short`

Expected: only intentional source changes are tracked; `.env` remains untracked.

```bash
git add README.md services/worker
git commit -m "feat: add Agnes provider smoke check"
```

