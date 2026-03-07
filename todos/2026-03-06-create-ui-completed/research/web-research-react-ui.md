# Web Research - react-ui

## Research Scope

**Tech Area:** react-ui
**Task Context:** Build a React 18 + TypeScript admin dashboard (Lintel UI) for an AI agent orchestration control plane, using Mantine v7, TanStack Query v5, React Flow, Recharts, Vite, and React Router v7.
**Research Date:** 2026-03-06

---

## Executive Summary

Mantine v7 represents a major architectural shift with a rewritten AppShell using compound components, built-in color scheme management (including `auto` for system preference), and a powerful `useForm` hook that integrates cleanly with Stepper for wizard flows. TanStack Query v5 provides first-class polling via `refetchInterval` and a simplified optimistic updates pattern. React Flow is production-ready for workflow editors with Zustand-based state management and dagre.js for auto-layout. Vite's proxy config eliminates CORS in dev for FastAPI backends. React Router v7's nested layouts with `Outlet` and `createBrowserRouter` are the current standard for large SPAs.

---

## Findings by Topic

### 1. Mantine v7: AppShell, Theming, Dark Mode, Forms, Stepper, Notifications

**Confidence:** 0.92

- AppShell uses compound component pattern (`AppShell.Navbar`, `AppShell.Header`, etc.)
- `colorScheme: 'auto'` uses OS preference with no extra wrapper component
- `useForm` hook's `form.validate().hasErrors` guards Stepper `nextStep()` calls
- Notifications system (`notifications.show()`) supports multiple positions; works globally
- `createFormActions` (v7.2.0+) allows updating form state from outside the component tree

**Sources:** [Mantine v7.0.0 Changelog](https://mantine.dev/changelog/7-0-0/) | [Mantine Stepper](https://mantine.dev/core/stepper/) | [jotyy/Mantine-Admin](https://github.com/jotyy/Mantine-Admin)

### 2. TanStack Query v5: Polling, Cache Invalidation, Optimistic Updates

**Confidence:** 0.93

- `refetchInterval: (query) => condition ? ms : false` for conditional polling
- `refetchIntervalInBackground: true` keeps polling in backgrounded tabs
- v5 simplifies optimistic updates via mutation `variables` -- no manual cache writes
- `isFetching` (separate from `isLoading`) indicates background refetch -- use for connection status spinners
- `useMutationState` hook gives cross-component visibility into in-flight mutations

**Sources:** [TanStack Query v5 useQuery](https://tanstack.com/query/v5/docs/framework/react/reference/useQuery) | [Optimistic Updates Guide](https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates)

### 3. React Flow: Workflow/Graph Editor Production Patterns

**Confidence:** 0.88

- React Flow + Zustand for editor state + dagre.js for auto-layout is the recommended stack
- Custom node types must be defined outside the component render function
- Built-in virtualization renders only visible nodes/edges
- The [AI Workflow Editor template](https://reactflow.dev/ui/templates/ai-workflow-editor) is a starting point

**Sources:** [React Flow Workflow Editor Template](https://reactflow.dev/ui/templates/workflow-editor) | [Synergy Codes](https://www.synergycodes.com/blog/react-flow-everything-you-need-to-know)

### 4. Vite: React SPA + FastAPI Backend Integration

**Confidence:** 0.95

- `server.proxy` in `vite.config.ts` proxies `/api` to FastAPI, eliminating CORS in dev
- Add `/ws` proxy target with `ws: true` for WebSocket connections
- Production: FastAPI mounts `dist/` as `StaticFiles` with SPA catch-all
- Run two dev processes: `bun run dev` (Vite on :5173) and `uvicorn` (FastAPI on :8000)

**Sources:** [FastAPI and React in 2025](https://www.joshfinnie.com/blog/fastapi-and-react-in-2025/) | [TestDriven.io](https://testdriven.io/blog/fastapi-react/)

### 5. React Router v7: Nested Layouts, Protected Routes, Breadcrumbs

**Confidence:** 0.90

- `createBrowserRouter` with nested `children` arrays is the current standard
- `ProtectedRoute` wraps `<Outlet>` and redirects if unauthenticated
- Breadcrumbs: `handle: { crumb: 'Threads' }` + `useMatches()` to build breadcrumb trail
- `lazy: () => import('./features/threads/ThreadsPage')` for per-page code splitting

**Sources:** [React Router v7 Guide](https://dev.to/utkvishwas/react-router-v7-a-comprehensive-guide-migration-from-v6-7d1) | [Protected Routes](https://dev.to/ra1nbow1/building-reliable-protected-routes-with-react-router-v7-1ka0)

### 6. Admin Dashboard UX: Command Palette, Connection Status, Setup Wizards

**Confidence:** 0.87

- `@mantine/spotlight` is the first-party command palette for Mantine apps
- Trigger: `useHotkeys([['mod+k', openSpotlight]])` from `@mantine/hooks`
- Connection status: `Indicator` component; color driven by `isFetching` or WebSocket `readyState`
- Setup wizard: Mantine `Stepper` + `useForm` + `localStorage` persistence for resume

**Sources:** [cmdk](https://cmdk.paco.me/) | [@mantine/spotlight](https://mantine.dev/)

### 7. Large React SPA Architecture

**Confidence:** 0.90

- Feature-based (domain-driven) folder structure is the 2025 consensus
- Group by domain, not by file type
- TanStack Query handles server state; `useState`/`useReducer` handles local UI state
- Zustand for shared in-memory editor state (React Flow graph)
- Route-level code splitting via React Router v7's `lazy:` option

**Sources:** [How to Structure a React App in 2025](https://ramonprata.medium.com/how-to-structure-a-react-app-in-2025-spa-ssr-or-native-10d8de7a245a)

---

## Best Practices Summary

### Strongly Recommended (0.85+ confidence)
1. Mantine AppShell compound components for shell layout
2. TanStack Query conditional polling: `refetchInterval: (query) => condition ? ms : false`
3. Vite proxy for FastAPI dev: single `server.proxy` block
4. Route-level code splitting: React Router v7's `lazy:` route option
5. Feature-based folder structure: group by domain
6. React Router v7 `createBrowserRouter` with nested routes
7. React Flow node types defined outside component

### Consider (0.7-0.85 confidence)
8. `@mantine/spotlight` for command palette
9. Zustand alongside TanStack Query for React Flow editor state
10. `createFormActions` for wizard state from outside components

---

## Evidence Index

| ID | Topic | Source | Confidence |
|----|-------|--------|------------|
| WEB-01 | Mantine AppShell | Mantine Changelog v7.0.0 | 0.95 |
| WEB-02 | Mantine Dark Mode | Mantine Changelog v7.0.0 | 0.95 |
| WEB-03 | Mantine Forms + Stepper | Mantine Docs | 0.92 |
| WEB-04 | Mantine Notifications | Mantine v7 Docs | 0.92 |
| WEB-05 | TanStack Query Polling | TanStack Docs | 0.93 |
| WEB-06 | TanStack Optimistic Updates | TanStack Docs | 0.93 |
| WEB-07 | TanStack isFetching | TanStack Docs | 0.90 |
| WEB-08 | React Flow + Zustand | Synergy Codes | 0.88 |
| WEB-09 | React Flow Custom Nodes | Velt Blog | 0.88 |
| WEB-10 | Vite FastAPI Proxy | Josh Finnie | 0.95 |
| WEB-11 | Vite FastAPI Production | TestDriven.io | 0.92 |
| WEB-12 | RR v7 Protected Routes | DEV Community | 0.90 |
| WEB-13 | RR v7 Breadcrumbs | DEV Community | 0.88 |
| WEB-14 | Command Palette cmdk | cmdk | 0.87 |
| WEB-15 | Command Palette Mantine | Mantine | 0.87 |
| WEB-16 | SPA Folder Structure | Medium | 0.90 |
| WEB-17 | Code Splitting | React Docs | 0.92 |
| WEB-18 | TanStack DB | InfoQ | 0.70 |
