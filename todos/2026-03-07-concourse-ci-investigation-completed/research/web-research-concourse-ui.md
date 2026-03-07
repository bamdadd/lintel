# Web Research - Concourse CI UI/UX

## Executive Summary

Concourse's web UI is an Elm SPA rendering pipeline DAGs via D3.js + SVG and streaming build logs via SSE on `/api/v1/builds/:id/events`. Build events are richly typed (`initialize-task`, `start-task`, `finish-task`, `log`, `status`, `end`) with per-line timestamps. Prometheus exposes `concourse_builds_duration_seconds` but lacks per-step execution duration — an identified gap. For Lintel, the SSE + typed event model is directly applicable; key extensions: prompt/input as first-class event metadata, and per-step duration metrics.

## Web UI Architecture

- Elm SPA for all application logic
- D3.js v3.5.5 + SVG for pipeline graph rendering via custom `graph.js` layout
- SSE bridged into Elm via ports
- ATC (Go monolith) serves both web UI and API

## Build Output Streaming

- **Protocol**: SSE (`text/event-stream`), HTTP/1.1 chunked encoding, unidirectional
- **Endpoint**: `GET /api/v1/builds/:build_id/events`
- Terminal `end` event signals completion; client must call `eventSource.close()`
- Per-line timestamps rendered in browser timezone
- ANSI color codes work but progress bars cause performance degradation
- `fly watch` uses the same SSE endpoint

## Event Stream API - Event Types

| Type | Meaning |
|------|---------|
| `log` | Line of stdout/stderr; includes `origin` (step name), `payload` (text), `time` |
| `status` | Build-level status change: started/succeeded/failed/errored/aborted |
| `initialize-task` | Task step: inputs fetched, image fetch starting |
| `start-task` | Container ready; execution starting |
| `finish-task` | Task complete; includes `exit_status` |
| `initialize-get` | Get step starting |
| `finish-get` | Get done; includes fetched version metadata |
| `initialize-put` | Put step starting |
| `finish-put` | Put done; includes output version metadata |
| `error` | Error in a step; includes `message` |
| `end` | Terminal event; close EventSource |

- Each event type carries a `version` field for backwards compatibility

## Build Step Visualization

- Each step (`get`/`put`/`task`) is a collapsible panel updating in real-time
- Color coding: yellow animated halo = running; green = succeeded; red = failed
- On failure: auto-scroll to first failing log line
- Resource metadata (version hash, input chain) shown inline in get/put sections
- Per-line timestamps on left margin
- Build history as horizontal scrollable tabs

## Build Metadata

- `Build.StartTime`, `Build.EndTime`: Unix int64; duration = EndTime - StartTime
- `Build.Status`: started | pending | succeeded | failed | errored | aborted
- Per-step durations NOT available in API — only aggregate build duration

## Pipeline Visualization

- D3 + SVG; custom `graph.js` DAG layout
- Job box fill encodes status: green/red/blue (paused)/brown (cancelled)/grey
- Yellow animated halo = currently running
- Solid lines = `trigger: true` (auto-trigger); dotted = `trigger: false` (dependency only)
- Clicks navigate to job's latest build page
- Auto-refreshes via polling every ~5 seconds

## Real-Time Updates

- **Hybrid approach**: HTTP polling (~5s) for pipeline/dashboard; persistent SSE for active build logs
- No WebSockets in standard UI
- Known "pile-on" problem under many concurrent dashboard viewers

## Metrics

### Build-Level (Prometheus)
| Metric | Type | Description |
|--------|------|-------------|
| `concourse_builds_duration_seconds` | Histogram | Build wall-clock duration (team/pipeline/job labels) |
| `concourse_builds_started_total` | Counter | Cumulative builds started |
| `concourse_builds_running` | Gauge | Currently active builds |

### Step-Level
| Metric | Type | Description |
|--------|------|-------------|
| `concourse_tasks_waiting` | Gauge | Tasks queued, not yet executing |
| `concourse_tasks_wait_duration` | Histogram | Time waiting for container slot (NOT execution time) |

**Key gap**: No per-step execution duration metric exists. Community recommends OpenTelemetry with Jaeger for sub-build timing.

## Recommendations for Lintel

1. **Typed SSE event stream**: `GET /api/v1/runs/:run_id/events` with types: `initialize-step`, `start-step`, `finish-step`, `log`, `tool-call`, `tool-result`, `status`, `end`
2. **Prompt/input as first-class event fields**: `tool-call` event with `prompt_preview`, `model_id`, `input_tokens`, `tool_name`, `tool_input_json` — not ANSI log text
3. **Per-step Prometheus histograms**: `lintel_step_duration_seconds{workflow, step_type, tool_name, status}` — filling Concourse's gap
4. **Hybrid polling + SSE**: Poll workflow list at 5s; SSE only on active run detail page
5. **OTel spans per LangGraph node**: Extend existing observability for waterfall timing views

## Sources

- https://medium.com/concourse-ci/concourse-build-page-explained-4f92824c98f1
- https://medium.com/concourse-ci/concourse-pipeline-ui-explained-87dfeea83553
- https://concourse-ci.org/docs/operation/metrics/
- https://github.com/concourse/concourse/discussions/5671
- https://ops.tips/notes/tracing-builds-concourse/
- https://deepwiki.com/concourse/concourse/3-web-ui
