# Design: Admin UI Merge, Observability Dashboards & SSO

**Date:** 2026-02-06
**Status:** Approved

## Overview

Three interconnected improvements to BestBox's admin and operations experience:

1. Merge both admin areas under the localized route `/{locale}/admin` with full en/zh translation
2. Build three Grafana dashboards (Agent Performance, User Interaction, System Health) with backend metrics instrumentation
3. Integrate Authelia as OIDC identity provider for SSO across the admin app and Grafana

## 1. Admin UI Merge Under Localized Route

### Problem

Two separate admin areas exist:
- `/{locale}/admin` — old document upload page (localized)
- `/admin` — new full dashboard with sessions, documents, KB, users (non-localized, English-only)

The main page link at `/{locale}/` points to the old upload page.

### Solution

Move the full admin dashboard under `/{locale}/admin`, replacing the old upload-only page. Upload functionality becomes the Documents tab within the merged dashboard.

### File Changes

| Source | Destination |
|--------|-------------|
| `app/admin/page.tsx` | `app/[locale]/admin/page.tsx` (replaces old) |
| `app/admin/AdminSidebar.tsx` | `app/[locale]/admin/AdminSidebar.tsx` |
| `app/admin/layout.tsx` | `app/[locale]/admin/layout.tsx` |
| `app/admin/login/` | `app/[locale]/admin/login/` |
| `app/admin/users/` | `app/[locale]/admin/users/` |
| `app/admin/kb/` | `app/[locale]/admin/kb/` |

- Old `app/[locale]/admin/page.tsx` replaced by full dashboard
- `app/admin/` becomes a redirect to `/{defaultLocale}/admin`
- Layout wraps with `NextIntlClientProvider` for translation support

### URL Structure

```
/{locale}/admin          → Dashboard (sessions)
/{locale}/admin/login    → Login page
/{locale}/admin/documents → Document management + upload
/{locale}/admin/kb       → Knowledge base browse
/{locale}/admin/users    → User management
```

### Localization

Full en/zh translation for all admin UI text:
- Sidebar navigation labels (Sessions, Documents, Knowledge Base, Users)
- Login form (username, password, sign in, errors)
- All page headings, buttons, table headers, status labels, confirmation dialogs
- Existing upload form labels (already partially translated)
- Estimated ~80-100 new translation keys per language
- Added to `messages/en.json` and `messages/zh.json` under `Admin` namespace

## 2. Feedback UI Wiring

### Problem

Chat response cards render feedback buttons (thumbs up, thumbs down, mark as helpful, comments) but they are non-functional.

### Solution

Wire existing buttons to backend endpoints with visual state management.

### Frontend Changes

- Thumbs up/down: call `POST /api/feedback` on click
- Visual state: unselected → selected (filled icon, green for up, red for down)
- Mutually exclusive — clicking one deselects the other
- Comments: clicking opens a text input below the card, submits on Enter or blur
- Optimistic UI updates with error rollback
- Feedback state persists per message, fetched with session data on reload

### Backend Changes

- Verify existing feedback endpoints accept: `session_id`, `message_id`, `feedback_type` (thumbup/thumbdown), `comment`, `timestamp`
- Add `GET /api/feedback/{session_id}` to retrieve feedback for session reload
- Store in PostgreSQL for Grafana querying
- Emit Prometheus metrics: `bestbox_feedback_total{type="thumbup|thumbdown"}`, `bestbox_feedback_comments_total`

### Data Flow

```
User clicks thumbs up → POST /api/feedback → PostgreSQL insert + Prometheus counter
Grafana → PostgreSQL for trends + Prometheus for real-time counters
```

## 3. Grafana Dashboards

### Provisioning

JSON dashboard files in `config/grafana/dashboards/`, auto-loaded by existing Grafana provisioning (30s refresh).

### Dashboard 1: Agent Performance

| Panel | Type | Metric | Source |
|-------|------|--------|--------|
| Response Time | Time series | p50/p95/p99 per agent | `bestbox_agent_response_seconds` histogram |
| Token Usage | Stacked bar | prompt vs generation tokens per agent | `bestbox_tokens_total{phase}` counter |
| Router Confidence | Histogram | confidence score distribution | `bestbox_router_confidence` histogram |
| Tool Calls | Table | counts per agent, SLA compliance | `bestbox_tool_calls_total` counter |

### Dashboard 2: User Interaction

| Panel | Type | Metric | Source |
|-------|------|--------|--------|
| Active Sessions | Time series | sessions created over time | PostgreSQL sessions table |
| Messages Per Session | Stat | average/median per session | PostgreSQL |
| Feedback Ratio | Pie chart | thumbs up vs down | PostgreSQL feedback table |
| Feedback Trend | Time series | daily helpful ratio | PostgreSQL |
| Recent Comments | Table | latest comments with session links | PostgreSQL |

### Dashboard 3: System Health

| Panel | Type | Metric | Source |
|-------|------|--------|--------|
| LLM Server | Gauge + time series | latency, throughput | Prometheus scrape :8001 |
| Embeddings | Time series | request rate, latency | Prometheus scrape :8004 |
| Qdrant | Time series | query times, collection sizes | Agent API proxy metrics |
| Error Rates | Time series | HTTP 4xx/5xx per service | `bestbox_http_errors_total` counter |

### Backend Instrumentation

The Agent API (`services/agent_api.py`) needs Prometheus metrics added to key code paths:

- **Agent execution:** `bestbox_agent_response_seconds` histogram (labeled by agent)
- **Token usage:** `bestbox_tokens_total` counter (labeled by agent, phase)
- **Routing:** `bestbox_router_confidence` histogram
- **Tool calls:** `bestbox_tool_calls_total` counter (labeled by agent, tool)
- **HTTP errors:** `bestbox_http_errors_total` counter (labeled by service, status_code)
- **Feedback:** `bestbox_feedback_total` counter (labeled by type)

## 4. SSO with Authelia

### Architecture

```
Browser → Authelia (:9091) → OIDC tokens → Admin App + Grafana
```

Authelia acts as the single OIDC identity provider. Users log in once and get tokens accepted by both services.

### Deployment

- New service in `docker-compose.yml`: `bestbox-authelia` on port 9091
- Config files in `config/authelia/` (configuration.yml, users_database.yml)
- Local file-based user store (no external LDAP needed)
- Session storage via existing Redis instance

### User Database

- Authelia manages `users_database.yml` with argon2id password hashes
- Replaces `admin_users` PostgreSQL table for authentication (table kept for RBAC role mapping)
- Default users: `admin` (admin role), `engineer` (engineer role), `viewer` (viewer role)
- Role mapping: Authelia groups → BestBox roles via OIDC claims

### Admin App Integration

- Replace JWT login flow with OIDC Authorization Code flow
- Frontend: login button → Authelia → authenticate → redirect back with auth code → exchange for token
- Backend: `admin_auth.py` updated with `verify_oidc_token()` replacing `verify_jwt_token()`
- Role extracted from OIDC claims
- Fallback: `ADMIN_DEV_MODE=true` still bypasses auth for development

### Grafana Integration

- Configure `[auth.generic_oauth]` in Grafana to use Authelia as OAuth provider
- Role mapping: Authelia `admin` → Grafana Admin, `engineer` → Editor, `viewer` → Viewer
- Disable Grafana built-in login form
- Anonymous access preserved for embedded dashboard panels

### Login Flow

1. User visits `/{locale}/admin` → not authenticated → redirect to Authelia
2. User enters credentials → authenticated → redirect back with OIDC token
3. User opens Grafana from admin sidebar → same OIDC session → auto-login

## 5. Implementation Phases

### Phase 1: Authelia SSO (foundation)

1. Add Authelia service to `docker-compose.yml`
2. Create `config/authelia/configuration.yml` with OIDC provider config
3. Create `config/authelia/users_database.yml` with default users
4. Update `services/admin_auth.py` — add `verify_oidc_token()`, keep JWT as fallback
5. Configure Grafana `[auth.generic_oauth]` section
6. Test: single login grants access to both admin app and Grafana

### Phase 2: Admin UI Merge + Localization

1. Move `app/admin/` components to `app/[locale]/admin/`
2. Wrap layout with `NextIntlClientProvider`
3. Replace JWT login page with OIDC redirect flow
4. Merge old upload page into Documents tab
5. Add ~80-100 translation keys to `en.json` and `zh.json`
6. Set up `/admin` → `/{defaultLocale}/admin` redirect
7. Update main page admin link (already points to `/{locale}/admin`)
8. Test: full admin workflow in both en and zh

### Phase 3: Feedback Wiring + Metrics Instrumentation

1. Wire thumbs up/down buttons to `POST /api/feedback`
2. Wire comments input to backend
3. Add `GET /api/feedback/{session_id}` endpoint
4. Add Prometheus instrumentation to Agent API (histograms, counters)
5. Create/verify PostgreSQL feedback table schema
6. Test: feedback persists and metrics appear at `/metrics`

### Phase 4: Grafana Dashboards

1. Create `config/grafana/dashboards/agent-performance.json`
2. Create `config/grafana/dashboards/user-interaction.json`
3. Create `config/grafana/dashboards/system-health.json`
4. Add Grafana link to admin sidebar navigation
5. Optionally embed key panels in admin UI via iframe
6. Test: dashboards load with data from Phase 3 instrumentation

Each phase is independently shippable.
