# Admin Internationalization Migration

**Date:** 2026-02-08
**Status:** ✅ Completed

**Implementation Commits:**
- `eb6020e` - feat: migrate status and system pages to internationalized admin structure
- `bc3d76a` - chore: remove old non-internationalized admin directory

## Problem

The BestBox admin interface has two separate directory structures:
- Old structure: `app/admin/` (includes status and system pages, no i18n)
- New structure: `app/[locale]/admin/` (internationalized, missing status and system pages)

When users visit `http://localhost:3000/zh/admin`, they use the new internationalized structure which lacks the status page added in commit 731b033.

## Solution

Migrate all admin pages to the internationalized `app/[locale]/admin/` structure, ensuring consistent i18n support across all admin features.

## Scope

### Pages to Migrate

1. **Status Page** (`app/admin/status/page.tsx` → `app/[locale]/admin/status/page.tsx`)
   - Embeds Gatus dashboard (http://localhost:8086) in iframe
   - Loading and error states
   - Minimal text to internationalize

2. **System Page** (`app/admin/system/page.tsx` → `app/[locale]/admin/system/page.tsx`)
   - Service management UI (start/stop/restart)
   - Service health monitoring
   - Auto-refresh every 5 seconds
   - More extensive text internationalization needed

### Navigation Update

Update `app/[locale]/admin/AdminSidebar.tsx` to include:
- System page navigation item
- Status page navigation item

## Technical Approach

### 1. Translation Keys

Add to `messages/en.json` and `messages/zh.json` under `AdminNew`:

```json
{
  "status": {
    "title": "Status Page",
    "subtitle": "Real-time monitoring of all BestBox services",
    "openNewTab": "Open in New Tab",
    "unavailable": "Status Page Unavailable",
    "unavailableMsg": "Could not load the Gatus status dashboard.",
    "loadingMsg": "Loading status dashboard...",
    "makeRunning": "Make sure Gatus is running:",
    "retry": "Retry"
  },
  "system": {
    "title": "System",
    "subtitle": "Manage BestBox services and monitor health",
    "refresh": "Refresh",
    "totalServices": "Total Services",
    "running": "Running",
    "stopped": "Stopped",
    "errors": "Errors",
    "lastUpdated": "Last updated:",
    "autoRefresh": "Auto-refreshing every 5 seconds",
    "advancedMonitoring": "Advanced Monitoring",
    "advancedMonitoringDesc": "For detailed health checks, uptime history, response times, and alerting, visit the Gatus status page.",
    "openStatusPage": "Open Status Page",
    "externalService": "External service - managed externally",
    "accessDenied": "Access denied. Please log in with admin credentials."
  },
  "serviceStatus": {
    "running": "Running",
    "stopped": "Stopped",
    "error": "Error",
    "starting": "Starting",
    "stopping": "Stopping",
    "unknown": "Unknown"
  },
  "serviceActions": {
    "start": "Start",
    "stop": "Stop",
    "restart": "Restart"
  }
}
```

### 2. Status Page Migration

Changes:
- Already uses `"use client"` ✓
- Add `useTranslations("AdminNew")` hook
- Replace all hardcoded text with `t()` calls
- Keep iframe src as-is (localhost:8086)
- Keep loading/error state logic unchanged

### 3. System Page Migration

Changes:
- Add `useTranslations("AdminNew")` hook
- Internationalize all UI text (headers, buttons, labels)
- Keep service data from backend in English (API response)
- Keep API calls and business logic unchanged
- Maintain 5-second auto-refresh

### 4. Sidebar Navigation

Add two navigation items to `navItems` array:
- System page with gear icon (existing from old sidebar)
- Status page with bar chart icon (existing from old sidebar)

Both will use locale-aware routing: `/${locale}/admin/system` and `/${locale}/admin/status`

## Implementation Order

1. Add translation keys to both `en.json` and `zh.json`
2. Create `app/[locale]/admin/status/page.tsx`
3. Create `app/[locale]/admin/system/page.tsx`
4. Update `app/[locale]/admin/AdminSidebar.tsx`
5. Test all routes in both locales (`/zh/admin/*` and `/en/admin/*`)
6. Clean up old `app/admin/` directory

## Testing Checklist

- [ ] `/zh/admin/status` loads Gatus iframe with Chinese UI text
- [ ] `/en/admin/status` loads Gatus iframe with English UI text
- [ ] `/zh/admin/system` displays service cards with Chinese labels
- [ ] `/en/admin/system` displays service cards with English labels
- [ ] Navigation highlights active page correctly
- [ ] All service actions (start/stop/restart) work correctly
- [ ] Auto-refresh continues working on system page

## Post-Migration

After successful migration and testing:
- Delete old `app/admin/` directory
- All admin routes will be under `app/[locale]/admin/`
- Consistent i18n support across entire admin interface

## Notes

- Translations already exist for nav items (`nav.system`, `nav.status`)
- No changes needed to backend APIs
- Service names and descriptions from backend remain in English
- Gatus dashboard content is independent of Next.js i18n
