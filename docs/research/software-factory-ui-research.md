# SDLC Platform UI Design Research

**Source:** Competitive AI-native SDLC platform documentation + product screenshots
**Date:** 2026-03-08
**Relevance:** Lintel UI design for REQ-022 through REQ-028, REQ-029 through REQ-034

---

## 1. Global Layout Architecture

### Top Navigation Bar
- **Left**: Logo + horizontal module tabs: Overview | Refinery | Foundry | Planner | Validator
- **Active tab**: Blue outline/highlight — this IS the primary navigation, not a sidebar
- **Right**: Project name dropdown ("Home Health Mileage Tracker"), Docs link, share button, user avatar
- Clean white background, minimal chrome

### Left Sidebar (context-dependent)
- **Overview module**: Overview, Artifacts, Codebase, API Keys, Settings
- **Refinery module**: Document tree (Product Overview, Feature Requirements, Technical Requirements) with nested docs
- **Foundry module**: Blueprint tree (Foundation Blueprints, System Diagrams, Feature Blueprints) with nested sections
- **Planner module**: Minimal — icon-only vertical toolbar (table view, timeline, comments, settings)
- Each sidebar item has an icon + label; active item has blue background highlight
- "+" buttons next to section headers for creating new items

### Right Panel — Agent Chat (persistent)
- **Always visible** in Refinery, Foundry, Planner, Validator — roughly 25-30% of viewport width
- **Header**: "{Module} Agent" title + collapse chevron + add/settings icons
- **Alert banners** at top: colored background (orange/yellow) with action buttons ("Sync All", "Update Work Orders", "Dismiss")
- **Chat messages**: Agent responses with markdown formatting, collapsible suggestion cards (+56/-48 diff counts)
- **Quick action buttons** at bottom: contextual pill buttons (e.g., "Quick Q&A", "Sync Blueprints with Code", "Review Current Blueprint", "Extract Work Orders from Blueprints", "Phase Planning")
- **Input area**: Text input with "Upload" and "Select" buttons, blue "Send" button
- **@ mentions**: "Use @ to mention artifacts or blueprints" placeholder text

### Three-Panel Pattern
```
┌──────────────────────────────────────────────────────────┐
│  Logo  │ Overview │ Refinery │ Foundry │ Planner │ Valid │ Project ▾ │ Docs │ Avatar │
├────────┼──────────────────────────────────┼───────────────┤
│        │                                  │               │
│  Left  │         Main Content             │  Agent Chat   │
│ Sidebar│         (editor/table/           │  Panel        │
│ (nav)  │          dashboard)              │  (~25-30%)    │
│        │                                  │               │
│        │                                  │  [Alerts]     │
│        │                                  │  [Messages]   │
│        │                                  │  [Actions]    │
│        │                                  │  [Input]      │
└────────┴──────────────────────────────────┴───────────────┘
```

---

## 2. Overview / Project Dashboard

### Module Summary Cards (top row, 4 cards)
- Horizontal row of equal-width cards with subtle borders
- Each card: **Module name** (top-left), **icon + external link icon** (top-right), **big number** (e.g., "6", "13", "0/0"), **label** (e.g., "Feature Nodes", "Blueprints Created", "Phases Completed", "Feedback Actions")
- Clickable — navigates to the module

### Codebase Indexing Card
- Repo name with git icon: "Melbourneandrew/mileage-calculator"
- Branch info: "Branch: main" + repo URL
- **"Completed" green badge** (top-right)
- Stats: "Files Indexed: **136**" (large number), "Last Updated: 2/1/2026"
- Action buttons: "Change Branch", "Reindex", "Unlink"
- Info banner: "Single Codebase Policy — Only one codebase can be indexed per project"

### Pending Work Orders
- Simple list view: WO ID + title, assignee, phase
- Status badges: "In Progress" (green), "Ready" (yellow outline)
- "View all" link top-right

### Flagged Comments
- Section with flag icon
- Empty state: icon + "No flagged comments"

---

## 3. Refinery UI (Requirements Editor)

### Left Sidebar — Document Tree
```
▾ Product Overview                    [+]
    Business Problem
    Current State
    Product Description
    Personas
    Success Metrics
    Technical Requirements
▾ Feature Requirements                [+]
    User Authentication
    File Upload & Parsing
    Distance Calculation
    Results Display & Export
    Calculation History
  ▾ Admin Dashboard                   (active, expanded)
      Overview
      Terminology
      Requirements
        REQ-ADMIN-001: Admin Access Control
        REQ-ADMIN-002: Email Allowlist Manag..
        REQ-ADMIN-003: User Management
        REQ-ADMIN-004: Usage Dashboard
        REQ-ADMIN-005: System Configuration
        REQ-ADMIN-006: Audit Log
      Feature Behavior & Rules
```
- Hierarchical tree with collapsible sections
- Active document highlighted in blue
- Nested down to individual requirements (REQ-ADMIN-001, etc.)
- Document icons (page icon) next to each item
- Section headers ("Product Overview", "Feature Requirements") in bold with [+] create button

### Center — Rich Text Editor
- **Document title**: Large heading ("Admin Dashboard")
- **Last saved**: "Last saved 4h ago" (top-right)
- **Formatting toolbar**: B, I, U, S (strikethrough), link, Heading dropdown, bullet list, numbered list, table, divider, code block, AI sparkle icon
- **Content structure**: Overview → Terminology → Requirements with User Stories and Acceptance Criteria
- **Acceptance Criteria formatting**: Bold "AC-ADMIN-001.1:" prefix, indented under requirements, with colored highlight on some items (yellow highlight on one AC)
- **Code references**: Inline code blocks for field names (e.g., `is_admin`, `deleted_at`)

### Right Panel — Refinery Agent
- Agent chat showing document population workflow
- **Collapsible "Read" cards**: "Read Results Display & Export (33 lines)" — shows agent reading documents
- **"Suggestion" cards**: "+56 -48" diff stats, collapsible to see proposed changes
- **Completion summary**: "Feature Requirements Documents - Complete ✅" with table of all features
- **Quick action pills**: "Quick Q&A", "Organize Features", "Create Features", "Review Document", "Review Across Documents"
- Input: "Use @ to mention artifacts, or ask questions about requirements..."

---

## 4. Foundry UI (Blueprint Editor)

### Left Sidebar — Blueprint Tree
```
▾ Foundation Blueprints               [+]
    Backend
    Frontend
    Data Layer
▾ System Diagrams                     [+]
    System Architecture
    Entity Relationship Diagram
    Sequence Diagram
    Feature Relationship Diagram
▾ Feature Blueprints                  [+]
    User Authentication
    File Upload & Parsing
    Distance Calculation
  ▾ Results Display & Export
      Calculation History             (active, orange highlight)
        Solution Design
        Key Design Decisions
        Data Model
        API Implementation
          GET /api/calculations
          DELETE /api/calculations...
          GET /api/calculations/{id}
        UI Implementation
        Background Cleanup Task
    Admin Dashboard
```
- Three sections: Foundation, System Diagrams, Feature Blueprints
- Feature Blueprints have deep nesting: Feature → Sections → Sub-sections → Endpoints
- Active item: orange/amber text highlight
- Icons on left sidebar rail: document, clock, chat, settings, git, home

### Center — Blueprint Document Editor
- Same rich text editor as Refinery
- **Document title**: "Calculation History"
- Sections: Solution Design, Key Design Decisions, Data Model
- **Code blocks**: Schema definitions with monospace font, grey background
- **Inline code**: `calculations` table references in backticks
- **Key Design Decisions**: Bullet list with bold decision name + explanation

### Right Panel — Foundry Agent
- **Drift alert banner** (orange): "Sync Blueprints with Code — 7 blueprints may be out of sync with the codebase" with "Sync All" (blue button) and "Dismiss"
- **"Hide Alerts 1"** badge showing alert count
- **Suggestion cards**: Collapsible "+1" suggestions for blueprint updates
- Agent shows "Summary of Changes" with formatted markdown — what was changed in which blueprints
- **Quick action pills**: "Quick Q&A", "Sync Blueprints with Code", "Review Current Blueprint"
- Input: "Use @ to mention artifacts or blueprints"

---

## 5. Planner UI (Work Order Management)

### Left Sidebar — Minimal Icon Rail
- Vertical icon-only toolbar (no labels): table, clock, comments, settings, git, home
- Very narrow (~40px)

### Center — Work Order Table + Detail Drawer
**Table view (left portion):**
- Search bar: "Search by title..."
- Filter bar: "Filters ▾", "My work", "MCP Connection" (red dot indicator)
- **Table columns**: Work Order (ID + title + blueprint), Status, Assignee, Phase
- **Phase grouping**: "▾ No Phase" as collapsible section header
- Status badges: "Backlog" (grey), "In Progress" (green with sparkle icon), "Ready" (yellow)
- Assignee: "AM Andr..." (avatar + truncated name), "? Unas..." for unassigned
- Phase: "No Ph..." dropdown
- **Delete icon** (trash) per row
- Rows are compact, ~40px height

**Detail drawer (center-right, overlay):**
- Slides open when clicking a work order
- **Header**: "Work Order #1 WO-1" with edit and close icons
- **Title**: Editable text field ("Example Work Order")
- **Metadata row**: Status dropdown (Backlog), Assignee (AM Andrew Melbourne), Phase (No Phase) — all as pill buttons with dropdowns
- **Tab bar**: Details | Blueprint | Requirements
- **Details tab**:
  - "This is an example of a work order description!"
  - **Implementation section**: "Update with AI" button, "+ Add File" button
  - File list: `src/controllers/user_controller.py` → "Create", `src/app.py` → "Modify"
  - Each file shows path + description of what to do
- **Activity section**: "Show logs / Hide logs" toggle
  - Comment input: avatar + "Enter your comment..." + Upload/Select + "Send Comment" (blue button)

### Right Panel — Planner Agent
- **Alert banner** (orange): "Blueprint Sections Updated — 11 Blueprints have been updated since last work order extraction" with "Update Work Orders" (blue) and "Dismiss"
- Shows agent creating work orders: "Creating Work Orders for Backend Blueprint"
  - "+ Create Work Order" with "Success" green badge (×2)
- **Created work orders summary**: Numbered list with bullet points per WO
- Agent explains dependencies: "The Celery Task Server Setup work order should be implemented first as it provides the foundation that the Hard Delete Cleanup Task depends on"
- **Quick action pills**: "Phase Planning", "Extract Work Orders from Blueprints", "Implementation Plan Next Phase", "Review Current Phase", "Duplicate Check", "Generate Implementation Plan", "More"

---

## 6. Validator UI (Feedback Inbox)

### Layout — Two Panel (no left sidebar)
- **Sub-header**: "Validator: Home Health Mileage Tracker"
- **View toggle**: "Inbox" (active, blue) | "Advanced ▾" dropdown
- **Action buttons**: "Generate Work Orders" (sparkle icon), "Refresh"

### Inbox View
- **Header**: "Inbox 0 items"
- **Filter bar**: Search input ("Search feedback..."), "All Types ▾", "All Priorities ▾"
- **Empty state**: "No Feedback Collected Yet" + "Click here to set up your Validator Integration" (blue link)
- Clean, minimal design

### Right Panel — Validator Agent
- Same agent chat pattern
- Input placeholder: "Ask questions about submitted feedback or create work orders..."
- Upload + Select + Send buttons

---

## 7. Key Design Patterns for Lintel

### Pattern 1: Consistent Three-Panel Layout
Every module uses the same shell:
- **Left**: Navigation (document tree or icon rail)
- **Center**: Content (editor, table, dashboard)
- **Right**: Agent chat (always present, ~25-30% width)

**Lintel action**: Adopt this as the standard layout. The agent panel should be a global shell component, not per-page.

### Pattern 2: Agent Alert Banners
Orange/yellow banners at the top of the agent panel with:
- Clear description of what needs attention
- Primary action button (blue: "Sync All", "Update Work Orders")
- "Dismiss" secondary action
- Badge count ("Hide Alerts 1")

**Lintel action**: Use for drift detection alerts (REQ-024), blueprint sync notifications, and CoS agent recommendations.

### Pattern 3: Agent Suggestion Cards
Collapsible cards showing:
- "+56 -48" diff statistics
- Expandable to see full proposed changes
- Accept/dismiss actions

**Lintel action**: Use for agent-proposed edits to specs and architecture docs.

### Pattern 4: Quick Action Pills
Contextual action buttons at the bottom of agent chat:
- Module-specific (Refinery: "Create Features", "Review Document"; Planner: "Phase Planning", "Extract Work Orders")
- Horizontally scrollable row
- Icon + label format

**Lintel action**: Define quick actions per workspace. These are the most important UX affordance — they tell users what the agent can do.

### Pattern 5: Work Order Detail Drawer
Slide-over drawer (not a new page) for work order details:
- Metadata as inline pill dropdowns
- Tab navigation (Details, Blueprint, Requirements)
- Implementation plan with file paths and actions (Create/Modify)
- Activity feed with comments

**Lintel action**: Already have a work item drawer (REQ-015). Enhance with: implementation plan section, Blueprint/Requirements tabs linking to upstream docs.

### Pattern 6: Document Tree with Deep Nesting
- Three-level hierarchy: Category → Document → Sections → Sub-sections
- Collapsible at every level
- "+" create buttons on section headers
- Active item highlighted

**Lintel action**: Build a reusable tree component for both Spec Workshop (REQ-022) and Architecture Decisions (REQ-023).

### Pattern 7: Rich Text Editor with Formatting Toolbar
Consistent across Refinery and Foundry:
- Standard formatting: B, I, U, S, link, heading dropdown
- Structural: bullet list, numbered list, table, divider
- Code: code block, inline code
- AI: sparkle icon for AI-assisted editing
- "Last saved X ago" indicator

**Lintel action**: Use a single ProseMirror-based rich markdown editor component for all document workspaces.

### Pattern 8: @ Mentions for Context
- Agent input supports "@" to reference artifacts, blueprints, requirements
- Shows in placeholder text as a hint
- Enables cross-document context in agent conversations

**Lintel action**: Implement @ mention picker for work items, specs, architecture decisions, and attachments.

### Pattern 9: Status Badge System
Consistent colored badges across all modules:
- **Backlog**: Grey
- **Ready**: Yellow outline
- **In Progress**: Green with sparkle icon
- **Completed**: Green solid
- Status is always a dropdown, inline editable

### Pattern 10: Implementation Plan with File Paths
Work orders include a file-level implementation plan:
- File path (e.g., `src/controllers/user_controller.py`)
- Action type: "Create" or "Modify"
- Description of what to do
- "Update with AI" button to regenerate
- "+ Add File" to manually add files

**Lintel action**: Add to work item detail — this is where codebase awareness (REQ-026) meets the planner. Agent generates implementation plans that reference real files.

---

## 8. Visual Design Language

- **Colors**: Mostly white/grey with blue accents for active states and primary actions
- **Alert colors**: Orange/amber for drift/sync alerts
- **Status colors**: Grey (backlog), yellow (ready), green (in progress/completed)
- **Typography**: Clean sans-serif, large headings for document titles, monospace for code
- **Spacing**: Generous whitespace, cards with subtle borders and shadows
- **Icons**: Minimal line icons, consistent style
- **Overall feel**: Clean, professional, enterprise-ready — modern productivity app aesthetic

---

## 9. What Lintel Should Prioritize (UI Build Order)

1. **Global shell with agent panel** — three-panel layout as the foundation
2. **Rich markdown editor** — shared component for specs + architecture docs
3. **Document tree sidebar** — reusable for both Spec Workshop and Architecture Decisions
4. **Agent alert banners** — for drift detection and sync notifications
5. **Quick action pills** — contextual agent actions per workspace
6. **Work item detail drawer enhancements** — implementation plan, upstream doc tabs
7. **@ mention picker** — cross-reference system for agent chat
8. **Suggestion cards with diffs** — agent-proposed edits
