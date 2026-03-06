# Framework Documentation Research - react-ui

## Research Scope

**Tech Area:** react-ui
**Frameworks:** Mantine v7, TanStack Query v5, React Flow v11, React Router v7, Vite v5
**Task Context:** Build a React 18 + TypeScript SPA dashboard for Lintel
**Research Date:** 2026-03-06

---

## Framework: Mantine v7

### AppShell Responsive Layout
```tsx
import { AppShell, Burger, Group } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';

export function Layout({ children }: { children: React.ReactNode }) {
  const [opened, { toggle }] = useDisclosure();
  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md">{/* sidebar links */}</AppShell.Navbar>
      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}
```
**Evidence:** [MANTINE-01]

### Stepper Multi-Step Form
Controlled via `active` prop (0-indexed). `Stepper.Completed` renders when `active` equals step count. `allowStepSelect` lets users navigate back.
**Evidence:** [MANTINE-02]

### @mantine/form with Zod Validation
```tsx
import { useForm } from '@mantine/form';
import { zodResolver } from 'mantine-form-zod-resolver';

const form = useForm({
  mode: 'uncontrolled',
  initialValues: { dsn: '' },
  validate: zodResolver(schema),
});
// form.getInputProps('dsn') returns { value, onChange, onBlur, error }
```
**Evidence:** [MANTINE-03]

### Notifications -- Loading to Success/Error
```tsx
const id = notifications.show({ loading: true, title: 'Testing...', autoClose: false });
// after await:
notifications.update({ id, color: 'green', title: 'Connected', loading: false, autoClose: 3000 });
```
**Evidence:** [MANTINE-04]

### Dark Mode / Theming
- `createTheme()` customises colors (10-element tuples), font, radius
- `defaultColorScheme="auto"` respects system preference
- `<ColorSchemeScript />` in `<head>` prevents FOUC
- `useMantineColorScheme()` provides `{ colorScheme, toggleColorScheme }`
**Evidence:** [MANTINE-05]

### @mantine/charts
`AreaChart`, `BarChart`, `PieChart`, `DonutChart` accept `data`, `dataKey`, `series`. Colors use Mantine tokens (`'indigo.6'`).
**Evidence:** [MANTINE-06]

### Best Practices
- **CSS Import Order:** Import `@mantine/core/styles.css` first, then per-package stylesheets. Missing imports leave all components unstyled. [MANTINE-07]
- **Forms:** Use `mode: 'uncontrolled'` to avoid per-keystroke re-renders. [MANTINE-03]
- **Responsive:** Use `hiddenFrom="sm"` / `visibleFrom="sm"` props. [MANTINE-09]
- **Command Palette:** `@mantine/spotlight` is a drop-in `Cmd+K` palette. [MANTINE-10]

---

## Framework: TanStack Query v5

### QueryClient Setup
```tsx
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: true },
  },
});
```
**Evidence:** [TANSTACK-01]

### useQuery
v5 requires options object (no positional arguments). `isLoading` is true only on first fetch with no cached data. `placeholderData: (prev) => prev` replaces `keepPreviousData`.
**Evidence:** [TANSTACK-02]

### Polling with refetchInterval
```tsx
refetchInterval: (query) => {
  const terminal = ['closed', 'failed'];
  return terminal.includes(query.state.data?.phase) ? false : 3_000;
},
```
**Evidence:** [TANSTACK-03]

### useMutation with Cache Invalidation
```tsx
onSuccess: () => {
  queryClient.invalidateQueries({ queryKey: queryKeys.repositories.all });
},
```
**Evidence:** [TANSTACK-04]

### Centralised Query Key Factory
```ts
export const queryKeys = {
  threads: {
    all: ['threads'] as const,
    detail: (id: string) => ['threads', id] as const,
  },
  // ... per domain
};
```
**Evidence:** [TANSTACK-05]

### v5 Breaking Changes
- `onSuccess`/`onError`/`onSettled` removed from `useQuery`
- `keepPreviousData` -> `placeholderData`
- `cacheTime` -> `gcTime`
**Evidence:** [TANSTACK-06]

---

## Framework: React Flow v11

### Canvas Setup
Container `div` must have explicit height. `nodeTypes` must be defined outside component.
```tsx
const nodeTypes = { agentStep: AgentStepNode, approvalGate: ApprovalGateNode };

export function WorkflowEditor() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  return (
    <div style={{ height: '100%', width: '100%' }}>
      <ReactFlow nodes={nodes} edges={edges}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes} fitView>
        <Background /><Controls /><MiniMap />
      </ReactFlow>
    </div>
  );
}
```
**Evidence:** [REACTFLOW-01]

### Custom Node Types
```tsx
export function AgentStepNode({ data, selected }: NodeProps<AgentStepData>) {
  return (
    <div style={{ padding: 10, borderRadius: 8, border: `2px solid ${selected ? '#6366f1' : '#e2e8f0'}` }}>
      <Handle type="target" position={Position.Top} />
      <div>{data.label}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```
**Evidence:** [REACTFLOW-02]

### Drag-and-Drop from External Palette
Palette items use `dataTransfer.setData`. `onDrop` uses `reactFlowInstance.screenToFlowPosition` for coordinates.
**Evidence:** [REACTFLOW-03]

### Best Practices
- **Module-Level nodeTypes:** Mandatory. Inline definitions remount all nodes every render. [REACTFLOW-04]
- **Serialisation:** `{ nodes, edges }` maps directly to workflow_definitions API payload. [REACTFLOW-05]

---

## Framework: React Router v7

### createBrowserRouter with Nested Layouts
```tsx
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,   // renders <Outlet /> in AppShell.Main
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'threads', element: <ThreadList /> },
      { path: 'threads/:streamId', element: <ThreadDetail /> },
      // ... all pages
    ],
  },
  { path: '/setup', element: <SetupWizard /> },  // full-screen, no sidebar
]);
```
**Evidence:** [ROUTER-01]

### NavLink for Active Sidebar
`NavLink` provides `isActive` prop for automatic active-link highlighting.
**Evidence:** [ROUTER-02]

### Best Practices
- Import from `'react-router'` not `'react-router-dom'` in v7. [ROUTER-04]
- Use `lazy:` on route objects for per-page code splitting. [ROUTER-03]

---

## Framework: Vite v5

### Dev Proxy to FastAPI
```ts
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://localhost:8000', changeOrigin: true },
    '/healthz': { target: 'http://localhost:8000', changeOrigin: true },
  },
},
```
**Evidence:** [VITE-02]

### Production Build
```ts
build: {
  outDir: '../src/lintel/api/static',
  emptyOutDir: true,
  rollupOptions: {
    output: {
      manualChunks: {
        vendor: ['react', 'react-dom', 'react-router'],
        mantine: ['@mantine/core', '@mantine/hooks', '@mantine/form'],
        tanstack: ['@tanstack/react-query'],
        reactflow: ['reactflow'],
      },
    },
  },
},
```
**Evidence:** [VITE-03]

---

## Anti-Patterns

1. **Inline nodeTypes in ReactFlow** -- Remounts all nodes every render [REACTFLOW-04]
2. **useQuery onSuccess/onError** -- Removed in v5; use `useEffect` or `useMutation` callbacks [TANSTACK-06]
3. **Missing Mantine CSS imports** -- All components unstyled without explicit imports [MANTINE-07]
4. **Importing from 'react-router-dom'** -- Use `'react-router'` in v7 [ROUTER-04]
5. **StaticFiles without html=True** -- Deep links return 404 [VITE-03]

---

## Evidence Index

[MANTINE-01] Official Docs - AppShell Component (Mantine, v7)
[MANTINE-02] Official Docs - Stepper Component (Mantine, v7)
[MANTINE-03] Official Docs - useForm / @mantine/form (Mantine, v7)
[MANTINE-04] Official Docs - @mantine/notifications (Mantine, v7)
[MANTINE-05] Official Docs - MantineProvider / Dark Mode (Mantine, v7)
[MANTINE-06] Official Docs - @mantine/charts (Mantine, v7)
[MANTINE-07] Official Docs - CSS Import Order (Mantine, v7)
[MANTINE-08] Official Docs - v6 to v7 Migration Guide (Mantine, v7)
[MANTINE-09] Official Docs - Responsive Styles (Mantine, v7)
[MANTINE-10] Official Docs - @mantine/spotlight (Mantine, v7)
[TANSTACK-01] Official Docs - QueryClient (TanStack Query, v5)
[TANSTACK-02] Official Docs - useQuery (TanStack Query, v5)
[TANSTACK-03] Official Docs - Polling / refetchInterval (TanStack Query, v5)
[TANSTACK-04] Official Docs - useMutation (TanStack Query, v5)
[TANSTACK-05] Official Docs - Query Keys (TanStack Query, v5)
[TANSTACK-06] Official Docs - v4 to v5 Migration (TanStack Query, v5)
[REACTFLOW-01] Official Docs - Getting Started (React Flow, v11)
[REACTFLOW-02] Official Docs - Custom Nodes (React Flow, v11)
[REACTFLOW-03] Official Docs - Drag and Drop (React Flow, v11)
[REACTFLOW-04] Official Docs - nodeTypes Pitfall (React Flow, v11)
[REACTFLOW-05] Official Docs - Save and Restore (React Flow, v11)
[ROUTER-01] Official Docs - createBrowserRouter (React Router, v7)
[ROUTER-02] Official Docs - NavLink (React Router, v7)
[ROUTER-03] Official Docs - loader / lazy (React Router, v7)
[ROUTER-04] Official Docs - v6 to v7 Migration (React Router, v7)
[VITE-01] Official Docs - Getting Started (Vite, v5)
[VITE-02] Official Docs - server.proxy (Vite, v5)
[VITE-03] Official Docs - Building for Production (Vite, v5)
[VITE-04] Official Docs - Env Variables (Vite, v5)
