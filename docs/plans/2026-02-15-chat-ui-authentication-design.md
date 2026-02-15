# Chat UI Authentication Design

**Date:** 2026-02-15
**Status:** Approved
**Author:** Claude Sonnet 4.5

## Overview

Add user authentication to the chat UI (`/[locale]/page.tsx`) so users can log in with admin/engineer/viewer roles and access protected tools based on their RBAC permissions. This enables proper access control for sensitive operations like viewing vendor data, financial reports, and procurement information.

## Requirements

### User Stories

1. **As a user**, I want to see a login prompt when accessing the chat so I know I can sign in for additional features
2. **As an authenticated user**, I want to see my username and role in the chat UI so I know who I'm logged in as
3. **As an authenticated user**, I want to access protected tools based on my role (admin/procurement/finance access vendor data)
4. **As an unauthenticated user**, I want to use basic chat features without login (viewer role, limited access)
5. **As a user**, I want to log out from the chat UI when I'm done

### Functional Requirements

- FR1: Dedicated login page at `/[locale]/login` for chat users
- FR2: Reuse existing admin authentication system (same users, roles, JWT)
- FR3: Allow unauthenticated chat access with viewer role (limited permissions)
- FR4: Show persistent banner for unauthenticated users prompting to sign in
- FR5: Show inline permission prompts when RBAC denies tool access
- FR6: Display user info (username, role) with logout button when authenticated
- FR7: Pass JWT token in Authorization header to Agent API
- FR8: Persist authentication across browser sessions (localStorage)

### Non-Functional Requirements

- NFR1: No backend changes required (reuse existing auth endpoints)
- NFR2: Login state syncs across multiple browser tabs
- NFR3: Graceful error handling for expired tokens, network failures
- NFR4: Maintain existing admin panel login flow (no breaking changes)

## Architecture

### High-Level Flow

```
User visits /en (chat)
  ↓
Check localStorage for JWT token
  ↓
No token? → Show banner "Sign in for full access"
  ↓
User clicks "Sign In" → Redirect to /en/login?returnUrl=/en
  ↓
User enters credentials → POST /admin/auth/login
  ↓
Success → Store token in localStorage → Redirect to returnUrl (/en)
  ↓
Chat UI passes token in Authorization header via CopilotKit
  ↓
Agent API validates token → Extracts roles → RBAC allows/denies tools
```

### Key Design Decisions

**1. Shared Login Page with Return URL (Approach 1)**

**Decision:** Create `/[locale]/login` that serves both chat and admin users, using `returnUrl` parameter to determine post-login redirect.

**Rationale:**
- DRY - No duplicate login UI code
- Consistent UX across chat and admin
- Easy to maintain (single source of truth)
- Reuses existing admin login logic (OIDC + username/password)

**Alternatives Considered:**
- Approach 2: Separate `/chat/login` page (rejected: code duplication)
- Approach 3: Modal-based login (rejected: doesn't handle OIDC redirects well)

**2. Allow Unauthenticated Access (Soft Auth)**

**Decision:** Unauthenticated users can access chat UI with viewer role (limited permissions).

**Rationale:**
- Better onboarding - users can try before signing in
- Non-disruptive - existing anonymous users continue working
- Clear feedback - permission prompts guide users to log in

**3. Token Passing via Custom Header**

**Decision:** Pass JWT via `Authorization: Bearer <token>` header through CopilotKit.

**Rationale:**
- Standard HTTP authentication pattern
- Agent API already expects this header
- Simpler than cookie-based auth for API calls

## Components

### 1. Shared Login Page (`/[locale]/login/page.tsx`)

**Changes to existing `/[locale]/admin/login/page.tsx`:**
- Move from `/admin/login` to `/login`
- Add `returnUrl` parameter handling
- Update page title/subtitle based on context

**Key Logic:**
```typescript
const searchParams = useSearchParams();
const returnUrl = searchParams.get('returnUrl') || `/${locale}/admin`;

// After successful login:
localStorage.setItem('admin_jwt_token', data.token);
localStorage.setItem('admin_role', data.user.role);
router.replace(returnUrl);
```

### 2. Auth Context Provider (`/contexts/AuthContext.tsx` - NEW)

**Provides:**
- `user: { username: string, role: string } | null`
- `token: string | null`
- `isAuthenticated: boolean`
- `login(username, password): Promise<void>`
- `logout(): void`
- `checkAuth(): void`

**Responsibilities:**
- Load token from localStorage on mount
- Decode JWT to extract username/role
- Provide auth state to all components
- Handle logout (clear localStorage)
- Sync auth state across tabs (storage event listener)

### 3. Chat Page UI Updates (`/[locale]/page.tsx`)

**A) Persistent Banner (unauthenticated)**
- Position: Top of chat UI
- Content: "Sign in to access all features (vendor data, financial reports, etc.)"
- CTA: "Sign In" button → redirects to `/login?returnUrl=/en`

**B) User Info Header (authenticated)**
- Position: Top of chat UI
- Content: Avatar (first letter), username, role badge
- CTA: "Sign Out" button → calls `logout()`

**C) Inline Permission Prompts**
- Trigger: Agent response contains permission denial message
- Content: "Sign in with admin/procurement role to access vendor data"
- CTA: Link to login page

### 4. CopilotKit Integration (`/app/api/copilotkit/route.ts`)

**Pass auth token to Agent API:**
```typescript
// Read token from frontend (passed via CopilotKit headers)
const authToken = req.headers.get('authorization')?.replace('Bearer ', '');

const openai = new OpenAI({
  baseURL,
  defaultHeaders: {
    "X-BBX-Session": uiSessionId,
    ...(authToken && { "Authorization": `Bearer ${authToken}` }),
  },
});
```

**Frontend (Chat Page):**
```typescript
const { token } = useAuth();

<CopilotKit
  runtimeUrl="/api/copilotkit"
  headers={{
    'Authorization': token ? `Bearer ${token}` : undefined
  }}
>
  {/* Chat UI */}
</CopilotKit>
```

## Data Flow

### Login Flow

1. User visits `/en` (chat)
2. AuthContext checks localStorage for `admin_jwt_token`
3. No token → `isAuthenticated = false` → Shows banner
4. User clicks "Sign In" → Redirect to `/en/login?returnUrl=/en`
5. User submits credentials → POST `/admin/auth/login`
6. Success → Store token + role in localStorage
7. Redirect to `returnUrl` (`/en`)
8. Chat page loads → AuthContext reads token → `isAuthenticated = true`
9. Shows user info header instead of banner

### Authenticated Chat Request

1. User sends message: "who are our top vendors"
2. CopilotKit sends request with `Authorization: Bearer <token>` header
3. Agent API receives request
4. `build_user_context()` decodes JWT → `roles = ["admin"]`
5. Router → ERP Agent → `get_top_vendors` tool
6. RBAC check: `"admin" in {"admin", "procurement", "finance"}` ✅
7. Tool executes → Returns vendor data

### Unauthenticated Chat Request

1. User sends message: "who are our top vendors"
2. CopilotKit sends request WITHOUT Authorization header
3. Agent API `build_user_context()` → `roles = ["viewer"]` (default)
4. Router → ERP Agent → `get_top_vendors` tool
5. RBAC check: `"viewer" in {"admin", "procurement", "finance"}` ❌
6. Tool denied → Agent responds with permission error
7. Frontend detects denial → Shows inline prompt to sign in

### Logout Flow

1. User clicks "Sign Out"
2. `AuthContext.logout()` called
3. Clear localStorage (`admin_jwt_token`, `admin_role`)
4. Update state: `setUser(null)`, `setToken(null)`
5. UI updates: User info → Banner
6. Next chat request has no auth → viewer role

## Error Handling

### Expired Token

**Scenario:** User has token but it expired

**Handling:**
```typescript
// In API error handler
if (response.status === 401) {
  localStorage.removeItem('admin_jwt_token');
  localStorage.removeItem('admin_role');
  window.dispatchEvent(new Event('auth-expired'));
  // Show banner: "Session expired. Please sign in again."
}
```

### Invalid Credentials

**Scenario:** User enters wrong password

**Handling:**
- Show error: "Invalid username or password"
- Don't redirect, allow retry
- Don't clear existing session

### Network Failure

**Scenario:** Agent API is down

**Handling:**
- Show error: "Unable to connect. Please try again."
- Don't clear session (might be temporary)

### Permission Denied After Login

**Scenario:** User logs in as "viewer" but tries protected tool

**Handling:**
- Show inline message: "Your role (viewer) cannot access this data."
- Suggest contacting admin for role upgrade
- Keep user logged in (can use other features)

### OIDC Failure

**Scenario:** Authelia unavailable

**Handling:**
- Show fallback: "SSO unavailable. Use username/password below."
- Allow username/password login

## Edge Cases

### Multiple Tabs

**Behavior:**
- Login in tab 1 → Tab 2 auto-updates to authenticated
- Logout in tab 2 → Tab 1 auto-updates to unauthenticated

**Implementation:**
```typescript
useEffect(() => {
  const handleStorageChange = (e: StorageEvent) => {
    if (e.key === 'admin_jwt_token') {
      checkAuth(); // Reload auth state
    }
  };
  window.addEventListener('storage', handleStorageChange);
  return () => window.removeEventListener('storage', handleStorageChange);
}, []);
```

### Browser Back Button After Logout

**Behavior:**
- Browser shows cached chat page
- localStorage is empty → AuthContext loads as unauthenticated
- UI correctly shows login banner

### Direct Link with returnUrl

**Example:** User clicks `/en/login?returnUrl=/en/voice`

**Behavior:**
- After login, redirects to voice page
- Works for any valid path

### Admin Panel + Chat Both Logged In

**Behavior:**
- Both share same token from localStorage
- Logout from either logs out both
- Seamless shared authentication state

## Testing Strategy

### Manual Testing Checklist

**Login Flow:**
- [ ] Visit `/en` → See banner
- [ ] Click "Sign In" → Redirects to `/en/login?returnUrl=/en`
- [ ] Login with valid credentials → Returns to chat
- [ ] User info header shows username/role

**Authentication Persistence:**
- [ ] Login → Refresh → Still authenticated
- [ ] Login → Close/reopen tab → Still authenticated
- [ ] Login → New tab → Authenticated in new tab

**RBAC Integration:**
- [ ] As admin: Access vendor data ✅
- [ ] As viewer: Get permission error ❌
- [ ] Permission error shows inline prompt

**Logout:**
- [ ] Click "Sign Out" → User info disappears
- [ ] Banner reappears
- [ ] Next request uses viewer role

**Multi-Tab:**
- [ ] Login tab 1 → Tab 2 updates
- [ ] Logout tab 2 → Tab 1 updates

**Error Handling:**
- [ ] Wrong password → Shows error
- [ ] Expired token → Clears token, shows banner
- [ ] Network failure → Shows error

### Automated Tests (Future)

**Unit Tests:**
- AuthContext login/logout/token validation
- Token parsing utilities

**Integration Tests:**
- Login form submission
- CopilotKit auth header passing
- RBAC enforcement

**E2E Tests:**
```typescript
test('user can login and access protected tools', async () => {
  await page.goto('/en');
  await page.click('text=Sign In');
  await page.fill('[name=username]', 'admin');
  await page.fill('[name=password]', 'bestbox-admin');
  await page.click('button[type=submit]');
  await expect(page).toHaveURL('/en');
  await page.fill('[placeholder="Ask"]', 'who are our top vendors');
  await page.keyboard.press('Enter');
  await expect(page.locator('text=permission')).not.toBeVisible();
});
```

## Security Considerations

### Token Storage

- JWT stored in localStorage (persists across sessions)
- localStorage is vulnerable to XSS but:
  - Next.js sanitizes user input by default
  - No user-generated content in chat UI
  - Future: Consider httpOnly cookies for production

### Token Validation

- Backend validates JWT signature (not tampered)
- Backend checks expiration (`exp` claim)
- Frontend role display is cosmetic - backend enforces permissions

### CSRF Protection

- Login uses POST (not GET)
- Token in localStorage (not cookies) - no CSRF risk
- Agent API validates origin

### Role Tampering

- User can modify `admin_role` in localStorage
- **Not a security issue:** Backend extracts roles from signed JWT
- Frontend role display is for UI only

## Migration Path

### Phase 1: Core Authentication (MVP)
- Shared login page with returnUrl
- AuthContext provider
- Persistent banner + user info header
- Token passing via CopilotKit

### Phase 2: Enhanced UX
- Inline permission prompts
- Multi-tab sync
- Loading states during login

### Phase 3: Security Hardening (Production)
- Token refresh mechanism
- httpOnly cookies (if needed)
- Rate limiting on login endpoint
- Audit logging

## Dependencies

### Frontend
- Existing: `next-intl`, `@copilotkit/react-core`, `@copilotkit/react-ui`
- New: None (reuse existing libraries)

### Backend
- No changes required
- Existing: `/admin/auth/login` endpoint
- Existing: JWT validation in `build_user_context()`

## Success Metrics

- Users can log in from chat UI
- Authenticated users can access protected tools based on role
- Unauthenticated users see clear prompts to sign in
- No backend changes required
- Authentication state syncs across tabs

## Future Enhancements

- Token refresh (auto-refresh before expiration)
- Remember me checkbox (extend token expiration)
- Password reset from login page
- Social login (Google, GitHub) via OIDC
- Two-factor authentication (2FA)

---

**Next Steps:** Proceed to implementation planning (writing-plans skill).
