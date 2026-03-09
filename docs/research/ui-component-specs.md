# UI Component Specs

**Date:** 2026-03-08
**Source:** Competitive SDLC platform screenshots + analysis
**Purpose:** Reusable component specs for Lintel UI implementation

---

## 1. Global App Shell

### Description
Three-panel layout that wraps every module. Provides consistent navigation, content area, and persistent agent chat.

### Structure
```
┌─────────────────────────────────────────────────────────────────┐
│  Logo │ Overview │ Refinery │ Foundry │ Planner │ Validator     │
├───────┼─────────────────────────────────────┼───────────────────┤
│       │                                     │                   │
│ Left  │          Main Content               │   Agent Panel     │
│ Sidebar                                     │   (~300px)        │
│ (~200px)                                    │                   │
│       │                                     │                   │
└───────┴─────────────────────────────────────┴───────────────────┘
```

### Props
```typescript
interface AppShellProps {
  activeModule: 'overview' | 'specs' | 'architecture' | 'planner' | 'feedback'
  projectName: string
  sidebar: React.ReactNode       // module-specific sidebar content
  children: React.ReactNode      // main content area
  agentPanel?: React.ReactNode   // agent chat panel (default: AgentPanel)
}
```

### Behavior
- Top nav: horizontal module tabs, active tab has blue outline
- Right side of top nav: project name dropdown, docs link, share button, user avatar
- Left sidebar width: ~200px, collapsible
- Agent panel width: ~300px, collapsible via chevron
- Agent panel persists across page navigations within a module
- Responsive: agent panel collapses to a floating button on small screens

### Lintel Mapping
- Overview → Project Dashboard
- Refinery → Spec Workshop (REQ-022)
- Foundry → Architecture Decisions (REQ-023)
- Planner → Task Board (REQ-015) / Work Items
- Validator → Feedback Ingestion (REQ-025)

---

## 2. Agent Chat Panel

### Description
Persistent right-side panel for conversing with the module's AI agent. Shows alerts, chat messages, suggestions, and contextual quick actions.

### Structure
```
┌─────────────────────────┐
│ ▸ Module Agent    [+][⚙]│  ← Header (collapsible)
├─────────────────────────┤
│ ┌─────────────────────┐ │
│ │ ⚠ Alert Banner      │ │  ← Drift/sync alerts
│ │ [Action] [Dismiss]  │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│                         │
│  Chat messages          │  ← Scrollable message area
│  - Agent responses      │
│  - Suggestion cards     │
│  - Read/action logs     │
│                         │
├─────────────────────────┤
│ [Quick Q&A] [Sync] [..] │  ← Quick action pills
├─────────────────────────┤
│ Use @ to mention...     │  ← Input with @ mentions
│ [Upload] [Select] [Send]│
└─────────────────────────┘
```

### Props
```typescript
interface AgentPanelProps {
  agentName: string                    // e.g. "Spec Agent", "Architecture Agent"
  alerts: AgentAlert[]                 // drift/sync alert banners
  messages: AgentMessage[]             // chat history
  quickActions: QuickAction[]          // contextual action pills
  onSendMessage: (text: string, attachments?: string[]) => void
  onAlertAction: (alertId: string, action: 'primary' | 'dismiss') => void
  onQuickAction: (actionId: string) => void
}

interface AgentAlert {
  id: string
  severity: 'warning' | 'info' | 'error'
  title: string                        // e.g. "Sync Blueprints with Code"
  description: string                  // e.g. "7 blueprints may be out of sync"
  primaryAction: { label: string }     // e.g. "Sync All", "Update Work Orders"
  count?: number                       // badge count
}

interface AgentMessage {
  id: string
  role: 'agent' | 'user'
  content: string                      // markdown
  suggestions?: AgentSuggestion[]      // collapsible edit suggestions
  readActions?: ReadAction[]           // "Read Document (33 lines)" cards
  timestamp: string
}

interface AgentSuggestion {
  id: string
  additions: number                    // +56
  deletions: number                    // -48
  targetDocument: string
  diff: string                         // unified diff
  status: 'pending' | 'accepted' | 'rejected'
}

interface QuickAction {
  id: string
  label: string                        // e.g. "Extract Work Orders"
  icon?: string                        // optional icon name
}
```

### Behavior
- Alert banners: orange/amber background, stack at top, dismissible
- Alert badge: "Hide Alerts N" button top-right of panel header
- Suggestion cards: collapsed by default showing "+N -N", expand to show diff
- Quick action pills: horizontal scrollable row, icon + label, click sends as agent command
- Input: text area with @ mention autocomplete, Upload button for files, Select button for existing artifacts
- Messages: markdown rendered, code blocks with syntax highlighting

### Quick Actions per Module
| Module | Actions |
|---|---|
| Spec Workshop | Quick Q&A, Organize Features, Create Features, Review Document, Review Across Documents |
| Architecture | Quick Q&A, Sync with Code, Review Current, Generate Diagram |
| Planner | Phase Planning, Extract Work Items, Implementation Plan, Review Phase, Duplicate Check, Generate Plan |
| Feedback | Generate Work Items, Refresh, Categorize All |

---

## 3. Document Tree Sidebar

### Description
Hierarchical tree navigation for documents with collapsible sections, nested items, and create actions. Used in Spec Workshop and Architecture Decisions modules.

### Structure
```
▾ Section Header                    [+]
    Document Item
    Document Item
  ▾ Document Item (expanded)
      Sub-section
      Sub-section
        Leaf item
        Leaf item
    Document Item
▾ Section Header                    [+]
    Document Item
```

### Props
```typescript
interface DocumentTreeProps {
  sections: TreeSection[]
  activeItemId: string | null
  onSelectItem: (itemId: string) => void
  onCreateItem: (sectionId: string) => void
}

interface TreeSection {
  id: string
  label: string                       // e.g. "Product Overview", "Foundation Blueprints"
  icon?: string
  canCreate: boolean                  // shows [+] button
  items: TreeItem[]
}

interface TreeItem {
  id: string
  label: string
  icon?: string                       // page icon, diagram icon, etc.
  children?: TreeItem[]               // nested items
  badge?: string                      // optional status indicator
}
```

### Behavior
- Sections: bold header with [+] button, collapsible
- Items: click to navigate, active item gets blue background highlight
- Nesting: unlimited depth, indent per level (~16px)
- Icons: page icon for documents, diagram icon for system diagrams, folder icon for groups
- Overflow: horizontal text truncation with ellipsis
- Keyboard: arrow keys to navigate, Enter to select, left/right to collapse/expand

### Spec Workshop Tree Structure
```
▾ Product Overview               [+]
    Business Problem
    Current State
    Product Description
    Personas
    Success Metrics
    Technical Constraints
▾ Feature Specs                  [+]
    {feature-name}
      Overview
      Terminology
      Requirements
        REQ-{PREFIX}-001: {title}
        REQ-{PREFIX}-002: {title}
      Behavior & Rules
```

### Architecture Decisions Tree Structure
```
▾ Foundation Decisions           [+]
    Backend
    Frontend
    Data Layer
▾ System Diagrams                [+]
    System Architecture
    Entity Relationship Diagram
    Sequence Diagram
▾ Feature Plans                  [+]
    {feature-name}
      Solution Design
      Key Design Decisions
      Data Model
      API Implementation
        {endpoint}
      UI Implementation
```

---

## 4. Rich Markdown Editor

### Description
Full-featured document editor shared across Spec Workshop and Architecture Decisions. Supports rich text, code blocks, tables, and AI-assisted editing.

### Structure
```
┌─────────────────────────────────────────┐
│ Document Title                          │  ← Editable heading
│                              Last saved │  ← Auto-save indicator
├─────────────────────────────────────────┤
│ B I U S 🔗 │ H▾ │ ≡ 1. │ ⊞ — │ </> ✨ │  ← Formatting toolbar
├─────────────────────────────────────────┤
│                                         │
│  Document content                       │  ← Editable area
│  - Headings (H1-H6)                    │
│  - Paragraphs                           │
│  - Bullet/numbered lists                │
│  - Code blocks (monospace, grey bg)     │
│  - Inline code (backticks)              │
│  - Tables                               │
│  - Dividers                             │
│  - Mermaid diagrams (rendered)          │
│                                         │
└─────────────────────────────────────────┘
```

### Props
```typescript
interface MarkdownEditorProps {
  documentId: string
  title: string
  content: string                      // markdown content
  lastSaved?: string                   // "Last saved 4h ago"
  readOnly?: boolean
  onTitleChange: (title: string) => void
  onContentChange: (content: string) => void
  onAIAssist?: () => void              // sparkle button handler
  collaborators?: User[]               // for real-time presence
}
```

### Toolbar Actions
| Button | Function |
|---|---|
| **B** | Bold |
| *I* | Italic |
| U̲ | Underline |
| ~~S~~ | Strikethrough |
| 🔗 | Insert link |
| H▾ | Heading level dropdown (H1–H6, Paragraph) |
| ≡ | Bullet list |
| 1. | Numbered list |
| ⊞ | Table |
| — | Horizontal divider |
| </> | Code block |
| ✨ | AI assist (generate/rewrite with agent) |

### Behavior
- Auto-save with "Last saved X ago" indicator
- Title is inline editable (large heading)
- Content supports all standard markdown
- Code blocks: syntax highlighted, grey background, monospace
- Mermaid diagrams: rendered inline as SVG
- AI sparkle button: opens agent panel with context of current selection/cursor position
- Collaborative: show other users' cursors (future)

### Recommended Library
ProseMirror-based editors support all required features and are extensible with good React integration.

---

## 5. Work Item Detail Drawer

### Description
Slide-over drawer showing full work item details when clicked from the table/board. Includes metadata, implementation plan, activity feed, and upstream document links.

### Structure
```
┌───────────────────────────────────┐
│ Work Item #N  WI-{id}    [✏][✕] │  ← Header with edit/close
├───────────────────────────────────┤
│ {Title}                      [🗑] │  ← Editable title
├───────────────────────────────────┤
│ (Status▾) (Assignee▾) (Phase▾)  │  ← Metadata pill dropdowns
├───────────────────────────────────┤
│ [Details] [Specs] [Architecture] │  ← Tab navigation
├───────────────────────────────────┤
│                                   │
│  Details tab:                     │
│    Description text               │
│                                   │
│    Implementation                 │
│    [Update with AI] [+ Add File]  │
│    ┌────────────────────────────┐ │
│    │ src/path/file.py   Create  │ │
│    │ description of change      │ │
│    ├────────────────────────────┤ │
│    │ src/path/other.py  Modify  │ │
│    │ description of change      │ │
│    └────────────────────────────┘ │
│                                   │
├───────────────────────────────────┤
│  Activity          [Show/Hide logs]│
│  ┌────────────────────────────┐   │
│  │ 👤 Enter your comment...   │   │
│  │ [Upload] [Select] [Send]   │   │
│  └────────────────────────────┘   │
└───────────────────────────────────┘
```

### Props
```typescript
interface WorkItemDrawerProps {
  workItem: WorkItem
  isOpen: boolean
  onClose: () => void
  onUpdate: (updates: Partial<WorkItem>) => void
  onComment: (text: string, attachments?: string[]) => void
  onAIUpdate: () => void              // "Update with AI" button
}

interface WorkItem {
  id: string
  sequenceNumber: number              // WI-1, WI-2, etc.
  title: string
  description: string
  status: WorkItemStatus
  assignee?: { id: string; name: string; avatar: string }
  phase?: string
  implementationPlan?: ImplementationFile[]
  upstreamSpecs?: DocReference[]      // linked spec documents
  upstreamArchitecture?: DocReference[] // linked architecture decisions
  activity: ActivityEntry[]
}

interface ImplementationFile {
  filePath: string                    // e.g. "src/controllers/user_controller.py"
  action: 'create' | 'modify' | 'delete'
  description: string                 // what to do with this file
}

interface ActivityEntry {
  id: string
  type: 'comment' | 'status_change' | 'assignment' | 'log'
  author: { name: string; avatar: string }
  content: string
  timestamp: string
}
```

### Behavior
- Opens as slide-over from right (overlays content, doesn't push)
- Metadata (status, assignee, phase): inline pill dropdowns, click to change
- Tabs: Details (default), Specs (linked spec docs), Architecture (linked arch decisions)
- Implementation plan: file path + action badge (Create/Modify) + description per file
- "Update with AI": triggers agent to regenerate implementation plan based on current specs/architecture
- "+ Add File": manual file path entry
- Activity: chronological feed, comment input with Upload/Select/Send
- "Show logs / Hide logs": toggle to show/hide system events

---

## 6. Project Dashboard

### Description
Overview page showing module health metrics, codebase status, pending work items, and flagged issues.

### Structure
```
┌─────────────────────────────────────────────────┐
│  Project Name                                    │
│  Track your progress across all modules          │
├───────────┬───────────┬───────────┬─────────────┤
│ Specs     │ Arch      │ Planner   │ Feedback    │  ← Module summary cards
│ 6         │ 13        │ 0/0       │ 0           │
│ Features  │ Decisions │ Phases    │ Actions     │
├───────────┴───────────┴───────────┴─────────────┤
│ Codebase Index                    [Completed ✓]  │
│ repo/name  Branch: main                          │
│ Files: 136              Last Updated: date       │
│ [Change Branch] [Reindex] [Unlink]               │
├─────────────────────────────────────────────────┤
│ Pending Work Items                    [View all] │
│ WI-5: Celery Task Setup       [In Progress]     │
│ WI-6: Hard Delete Cleanup     [Ready]            │
├─────────────────────────────────────────────────┤
│ 🚩 Flagged Comments                              │
│ Open comments flagged across all modules         │
│             No flagged comments                  │
└─────────────────────────────────────────────────┘
```

### Props
```typescript
interface ProjectDashboardProps {
  project: Project
  moduleStats: ModuleStats[]
  codebaseIndex?: CodebaseIndex
  pendingWorkItems: WorkItem[]
  flaggedComments: FlaggedComment[]
}

interface ModuleStats {
  module: string
  label: string                       // "Features", "Decisions", "Phases", "Actions"
  count: number | string              // "6", "13", "0/0", "0"
  icon: string
  linkTo: string                      // route to module
}

interface CodebaseIndex {
  repoName: string
  repoUrl: string
  branch: string
  status: 'indexing' | 'completed' | 'error'
  filesIndexed: number
  lastUpdated: string
}
```

---

## 7. Feedback Inbox

### Description
Filterable list view for user/product feedback with search, type/priority filtering, and agent integration.

### Structure
```
┌─────────────────────────────────────────────┐
│ Feedback: {Project}       [Inbox] [Advanced▾]│
├─────────────────────────────────────────────┤
│ Inbox  N items    [Generate Work Items] [↻] │
├─────────────────────────────────────────────┤
│ 🔍 Search...  │ All Types ▾ │ All Priority ▾│
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ feedback item                        │   │
│  │ type badge │ priority │ timestamp    │   │
│  │ description preview                  │   │
│  │ technical context (collapsed)        │   │
│  │ [Create Work Item] [Dismiss]         │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Empty state:                               │
│  "No Feedback Collected Yet"                │
│  Click here to set up integration           │
│                                             │
└─────────────────────────────────────────────┘
```

### Props
```typescript
interface FeedbackInboxProps {
  items: FeedbackItem[]
  filters: FeedbackFilters
  onFilterChange: (filters: FeedbackFilters) => void
  onCreateWorkItem: (feedbackId: string) => void
  onDismiss: (feedbackId: string) => void
  onGenerateWorkItems: () => void     // batch generate from agent
}

interface FeedbackItem {
  id: string
  type: 'bug' | 'feature_request' | 'performance' | 'ux'
  priority: 'critical' | 'high' | 'medium' | 'low'
  description: string
  technicalContext?: {
    browser?: string
    device?: string
    session?: string
    recentCodeChanges?: string[]
  }
  status: 'new' | 'reviewed' | 'work_item_created' | 'dismissed'
  linkedWorkItemId?: string
  createdAt: string
}

interface FeedbackFilters {
  search: string
  type: string | null                 // null = all types
  priority: string | null             // null = all priorities
}
```

---

## 8. Status Badge Component

### Description
Consistent colored status badges used across all modules.

### Variants
```typescript
interface StatusBadgeProps {
  status: string
  variant?: 'default' | 'outline'
}
```

| Status | Color | Style | Icon |
|---|---|---|---|
| Backlog | Grey | Filled | Circle |
| Open | Grey | Outline | Circle |
| Ready | Yellow | Outline | Play triangle |
| In Progress | Green | Filled | Sparkle ✨ |
| In Review | Blue | Filled | Eye |
| Completed | Green | Filled | Checkmark ✓ |
| Blocked | Red | Filled | X |
| Dismissed | Grey | Filled | Minus |

---

## 9. Alert Banner Component

### Description
Contextual notification banner shown at the top of the agent panel for drift detection, sync issues, and actionable notifications.

### Props
```typescript
interface AlertBannerProps {
  id: string
  severity: 'warning' | 'info' | 'error' | 'success'
  title: string
  description: string
  primaryAction: { label: string; onClick: () => void }
  onDismiss: () => void
}
```

### Visual
- **Warning**: Orange/amber background, dark text
- **Info**: Blue background, white text
- **Error**: Red background, white text
- **Success**: Green background, white text
- Primary action: Solid button matching severity color
- Dismiss: Text button "Dismiss"
- Compact: max 2 lines of text

---

## 10. @ Mention Picker

### Description
Autocomplete dropdown triggered by typing "@" in agent chat input. Allows referencing specs, architecture decisions, work items, and attachments.

### Props
```typescript
interface MentionPickerProps {
  query: string                        // text after @
  onSelect: (item: MentionItem) => void
  onDismiss: () => void
}

interface MentionItem {
  id: string
  type: 'spec' | 'architecture' | 'work_item' | 'attachment' | 'agent'
  label: string
  description?: string
  icon: string                         // type-specific icon
}
```

### Behavior
- Triggered on "@" keystroke in input
- Dropdown appears below cursor position
- Fuzzy search across all mentionable items
- Grouped by type (Specs, Architecture, Work Items, Attachments)
- Type-specific icons for visual distinction
- Insert as styled chip in input on selection
- Escape or click-outside to dismiss
