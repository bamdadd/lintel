# Risks & Troubleshooting

Consolidated risks from all research agents across react-ui and python-api tech areas.

---

## Risk Analysis

### Risk 1: No CORS Middleware -- Hard Blocker
**Likelihood:** Certain
**Impact:** High (blocks all UI development)
**Detection:** First browser fetch call fails with CORS error
**Mitigation:** Add `CORSMiddleware` to `app.py` gated on `ENV=development` (XS effort)
**Fallback:** Use Vite dev proxy for `/api` to bypass CORS entirely
**Evidence:** [CLEAN-04, DOCS-2, WEB-04]

### Risk 2: No Typed Response Models -- TypeScript Client Unusable
**Likelihood:** Certain
**Impact:** High (OpenAPI schema is empty objects; generated client has no types)
**Detection:** Run `openapi-typescript` on `/openapi.json` -- all response types are `Record<string, unknown>`
**Mitigation:** Define ~20-25 Pydantic response models mirroring domain dataclasses (M effort)
**Fallback:** Hand-write TypeScript types mirroring `contracts/types.py` (higher drift risk)
**Evidence:** [CLEAN-01, DOCS-6, DOCS-10]

### Risk 3: In-Memory Stores Reset on Restart
**Likelihood:** Certain
**Impact:** Medium (frustrates iterative UI development; all data lost on backend restart)
**Detection:** Backend restart empties all lists
**Mitigation:** Create `scripts/seed_dev.py` that POSTs sample data to running server (S effort)
**Fallback:** Use MSW (Mock Service Worker) in the React dev build for frontend-only iteration
**Evidence:** [REPO-02]

### Risk 4: React Flow Performance with Inline nodeTypes
**Likelihood:** High (common mistake)
**Impact:** Medium (all nodes unmount/remount on every render; visual flicker, lost state)
**Detection:** Workflow editor flickers or loses node selection on any state change
**Mitigation:** Define `nodeTypes` at module scope, never inside a component
**Evidence:** [REACTFLOW-04, WEB-09]

### Risk 5: Mantine v7 CSS Not Imported
**Likelihood:** Medium (most common v7 setup mistake)
**Impact:** High (all components unstyled -- no borders, no layout, no colors)
**Detection:** Components render but look broken
**Mitigation:** Import CSS files in order at top of `main.tsx`
**Evidence:** [MANTINE-07]

### Risk 6: TanStack Query v5 API Drift
**Likelihood:** Medium (teams copying v4 examples)
**Impact:** Medium (silent failures: `onSuccess` callbacks on `useQuery` don't fire)
**Detection:** TypeScript errors for v4-style API; callbacks silently ignored
**Mitigation:** Use only v5 API: `useMutation` callbacks, `placeholderData`, `gcTime`
**Evidence:** [TANSTACK-06]

### Risk 7: Stub Endpoints Return 200 with Empty Data
**Likelihood:** Certain
**Impact:** Medium (UI silently shows empty event timelines with no error indicator)
**Detection:** Event stream and correlation views appear to load but show nothing
**Mitigation:** Change stubs to return 501 with descriptive message; UI shows "not yet available" banner
**Evidence:** [CLEAN-07]

### Risk 8: HTTP/1.1 SSE Connection Limit
**Likelihood:** Medium (only if multiple SSE streams opened simultaneously)
**Impact:** Medium (browser limits 6 SSE connections per domain under HTTP/1.1)
**Detection:** 7th SSE connection hangs indefinitely
**Mitigation:** Use single `/events` SSE stream with query-param filtering, or ensure HTTP/2
**Evidence:** [WEB-08 python-api]

---

## Common Issues & Solutions

### Issue: Vite Dev Server Gets CORS Errors
**Symptom:** `Access-Control-Allow-Origin` missing from FastAPI responses
**Cause:** No `CORSMiddleware` in `app.py`
**Solution:** Either add `CORSMiddleware` or use Vite `server.proxy` to route `/api` through Vite
**Evidence:** [CLEAN-04, VITE-02]

### Issue: React Router Deep Links Return 404 in Production
**Symptom:** Navigating to `/threads/abc123` directly returns 404
**Cause:** FastAPI `StaticFiles` without `html=True` or missing SPA catch-all
**Solution:** Add `StaticFiles(html=True)` + `/{full_path:path}` catch-all route registered AFTER API routers
**Evidence:** [DOCS-1, DOCS-17, DOCS-18]

### Issue: SPA Catch-All Swallows API Routes
**Symptom:** All API calls return `index.html` content
**Cause:** `/{full_path:path}` registered BEFORE API routers
**Solution:** Always `include_router()` all API routers before the catch-all
**Evidence:** [DOCS-18]

### Issue: OpenAPI Client Has No Types
**Symptom:** Generated TypeScript client uses `Record<string, unknown>` everywhere
**Cause:** All FastAPI endpoints return `dict[str, Any]` with no `response_model`
**Solution:** Add Pydantic response models with `response_model=` on each endpoint
**Evidence:** [CLEAN-01, DOCS-6]

### Issue: React Flow Nodes Flicker on State Change
**Symptom:** All nodes unmount and remount; selection lost
**Cause:** `nodeTypes` object defined inside component (new reference each render)
**Solution:** Move `const nodeTypes = {...}` to module scope
**Evidence:** [REACTFLOW-04]

### Issue: Mantine Components Render Without Styles
**Symptom:** Components visible but no borders, colors, or spacing
**Cause:** Missing CSS imports
**Solution:** Add to top of `main.tsx`: `import '@mantine/core/styles.css'` + per-package imports
**Evidence:** [MANTINE-07]

---

## Testing Considerations

### What Needs Testing
- API client layer: response transforms (snake_case to camelCase), error handling
- TanStack Query hooks: cache key correctness, invalidation after mutations
- Mantine form validation: Zod schema integration, server error injection
- React Flow: node creation, edge connection, drag-and-drop from palette
- Route guards: setup wizard redirect on first run, protected routes
- Empty states: every list view with zero data

### Testing Strategy
- **Vitest + React Testing Library** for component tests
- **MSW (Mock Service Worker)** for API mocking in tests and standalone UI dev
- Presentational components tested with props (no network)
- Container components tested with MSW handlers
- E2E with Playwright for critical flows (setup wizard, repo registration)

### Edge Cases to Cover
- Backend returns 501 for stub endpoints
- Backend unreachable (connection error banner)
- All lists empty (empty state with CTA)
- Dark mode / light mode transitions
- Mobile responsive layout (sidebar collapse)
- Workflow graph with 50+ nodes (React Flow performance)
