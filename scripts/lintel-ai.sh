#!/usr/bin/env bash
set -e

SESSION="lintel-ai"
ROOT="/Users/bamdad/projects/lintel"

# Require minimum terminal size for all panes to fit
MIN_COLS=120
MIN_ROWS=30
read ROWS COLS < <(stty size 2>/dev/null || echo "24 80")
if [ "$COLS" -lt "$MIN_COLS" ] || [ "$ROWS" -lt "$MIN_ROWS" ]; then
  echo "Terminal too small: ${COLS}x${ROWS} (need at least ${MIN_COLS}x${MIN_ROWS})"
  echo "Maximize your terminal or increase font size, then retry."
  exit 1
fi

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Helper: split pane with fallback (won't crash if too small)
safe_split() {
  tmux split-window "$@" 2>/dev/null || echo "Warning: skipped pane split (terminal too small)"
}

# ─── Orchestrator system prompt ──────────────────────────────────────
ORCH_PROMPT='You are Orchestrator ORCH_NUM of 3 in the lintel-ai tmux session.

Your role: coordinate and delegate — NEVER implement directly.

## Your windows
- **This window (orch-ORCH_NUM)**: You live here. Plan, decide, monitor.
- **Agent windows (orchORCH_NUM-agent1, orchORCH_NUM-agent2, orchORCH_NUM-agent3)**: Your 3 agent panes. Send claude commands to these via tmux send-keys to do actual work (coding, testing, research).
- **Services window**: Shared dev servers (API :8000, UI :5173, Ollama).
- **Tests window**: Pane PANE_IDX is yours for running tests.

## Lintel skills
- `/lintel-board-prioritise` — groom and prioritise board work items
- `/lintel-board-play` — fill WIP from board (triage failed, promote open)
- `/lintel-analyse` — pick next open work item and research it
- `/lintel-implement` — pick next in_progress item, implement in worktree, raise PR
- `/lintel-review` — review open PRs, run /rounds done, fix issues
- `/lintel-pr-land` — rebase PRs on main, fix tests/lint/types until green
- `/lintel-flow` — orchestrate the full AI dev flow end-to-end

## Rules
1. Delegate all implementation to your agent windows
2. Always `/clear` a tmux pane before sending a new command to it
3. Each agent should work in its own git worktree to avoid conflicts
4. Run `make test-affected` not `make test-unit` for fast feedback
5. Run `/rounds done` on completed work before raising PRs
6. Use `make lint && make typecheck` before every commit
7. Wait for user instructions before starting work

Ready for instructions.'

make_prompt() {
  echo "$ORCH_PROMPT" | sed "s/ORCH_NUM/$1/g; s/PANE_IDX/$2/g"
}

# ─── Windows 0-2: orchestrators ──────────────────────────────────────
tmux new-session -d -s "$SESSION" -c "$ROOT"
tmux rename-window -t "$SESSION:0" "orch-1"
tmux send-keys -t "$SESSION:orch-1" "claude --append-system-prompt '$(make_prompt 1 0)'" Enter

tmux new-window -t "$SESSION" -n "orch-2" -c "$ROOT"
tmux send-keys -t "$SESSION:orch-2" "claude --append-system-prompt '$(make_prompt 2 1)'" Enter

tmux new-window -t "$SESSION" -n "orch-3" -c "$ROOT"
tmux send-keys -t "$SESSION:orch-3" "claude --append-system-prompt '$(make_prompt 3 2)'" Enter

# ─── Windows 3-11: agents — 3 separate windows per orchestrator ─────
for i in 1 2 3; do
  for j in 1 2 3; do
    tmux new-window -t "$SESSION" -n "orch${i}-agent${j}" -c "$ROOT"
  done
done

# ─── Window 12: services — shared dev servers ────────────────────────
tmux new-window -t "$SESSION" -n "services" -c "$ROOT"
tmux send-keys -t "$SESSION:services" "make serve-db" Enter
safe_split -h -t "$SESSION:services" -c "$ROOT"
tmux send-keys -t "$SESSION:services" "make ui-dev" Enter
safe_split -h -t "$SESSION:services" -c "$ROOT"
tmux send-keys -t "$SESSION:services" "make ollama-serve" Enter
tmux select-layout -t "$SESSION:services" even-horizontal 2>/dev/null || true

# ─── Window 13: tests — 3 panes, one per stream ─────────────────────
tmux new-window -t "$SESSION" -n "tests" -c "$ROOT"
safe_split -h -t "$SESSION:tests" -c "$ROOT"
safe_split -h -t "$SESSION:tests" -c "$ROOT"
tmux select-layout -t "$SESSION:tests" even-horizontal 2>/dev/null || true

# ─── Window 14: git — monitoring PRs and branches ───────────────────
tmux new-window -t "$SESSION" -n "git" -c "$ROOT"

# Start on orchestrator 1
tmux select-window -t "$SESSION:orch-1"
tmux attach -t "$SESSION"
