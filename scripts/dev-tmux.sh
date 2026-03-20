#!/usr/bin/env bash
set -euo pipefail

SESSION="lintel"
SESSION2="lintel2"
LINTEL2_DIR="$(cd "$(dirname "$0")/../.." && pwd)/lintel2"

# Helper: set up lintel2 session if directory exists and session doesn't
setup_lintel2() {
  if [ -d "$LINTEL2_DIR" ] && ! tmux has-session -t "$SESSION2" 2>/dev/null; then
    local saved_tmux="${TMUX:-}"
    unset TMUX

    tmux new-session -d -s "$SESSION2" -n prompts -x 200 -y 50 -c "$LINTEL2_DIR"

    # Ensure lintel2 is on main and up to date
    tmux send-keys -t "$SESSION2:prompts" "git checkout main && git pull" Enter
    sleep 2

    # 3 claude code panes
    tmux send-keys -t "$SESSION2:prompts" "claude" Enter
    tmux split-window -h -t "$SESSION2:prompts" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:prompts" "claude" Enter
    tmux split-window -h -t "$SESSION2:prompts" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:prompts" "claude" Enter
    tmux select-layout -t "$SESSION2:prompts" even-horizontal

    # Services window
    tmux new-window -t "$SESSION2" -n services -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:services" "make serve-db" Enter
    tmux split-window -h -t "$SESSION2:services" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:services" "make ui-dev" Enter
    tmux split-window -h -t "$SESSION2:services" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:services" "make ollama-serve" Enter

    # Editor window
    tmux new-window -t "$SESSION2" -n editor -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:editor" "nvim" Enter
    tmux split-window -v -t "$SESSION2:editor" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:editor" "ulimit -n 4096" Enter
    tmux split-window -h -t "$SESSION2:editor" -c "$LINTEL2_DIR"
    tmux send-keys -t "$SESSION2:editor" "ulimit -n 4096" Enter

    tmux select-window -t "$SESSION2:prompts"

    if [ -n "$saved_tmux" ]; then
      export TMUX="$saved_tmux"
    fi
  fi
}

# If session already exists, ensure lintel2 is up, then switch
if tmux has-session -t "$SESSION" 2>/dev/null; then
  setup_lintel2
  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$SESSION"
  else
    tmux attach-session -t "$SESSION"
  fi
  exit 0
fi

# Detach from current session if inside tmux, so we can create a new one
ORIG_TMUX="${TMUX:-}"
unset TMUX

# Create session with first window: "prompts" (3 claude code panes)
tmux new-session -d -s "$SESSION" -n prompts -x 200 -y 50

# Split into 3 vertical panes for claude code sessions
tmux send-keys -t "$SESSION:prompts" "claude" Enter
tmux split-window -h -t "$SESSION:prompts"
tmux send-keys -t "$SESSION:prompts" "claude" Enter
tmux split-window -h -t "$SESSION:prompts"
tmux send-keys -t "$SESSION:prompts" "claude" Enter

# Even out the 3 panes
tmux select-layout -t "$SESSION:prompts" even-horizontal

# Create second window: "services" (API server, UI dev, DB)
tmux new-window -t "$SESSION" -n services

# Left: API server with DB
tmux send-keys -t "$SESSION:services" "make serve-db" Enter

# Middle: UI dev server
tmux split-window -h -t "$SESSION:services"
tmux send-keys -t "$SESSION:services" "make ui-dev" Enter

# Right: Ollama server
tmux split-window -h -t "$SESSION:services"
tmux send-keys -t "$SESSION:services" "make ollama-serve" Enter

# Create third window: "editor" (nvim + terminal)
tmux new-window -t "$SESSION" -n editor
tmux send-keys -t "$SESSION:editor" "nvim" Enter
tmux split-window -v -t "$SESSION:editor"
tmux send-keys -t "$SESSION:editor" "ulimit -n 4096" Enter
tmux split-window -h -t "$SESSION:editor"
tmux send-keys -t "$SESSION:editor" "ulimit -n 4096" Enter

# Start on the prompts window
tmux select-window -t "$SESSION:prompts"

# Set up lintel2 if not already running
setup_lintel2

# Attach or switch to primary session
if [ -n "$ORIG_TMUX" ]; then
  export TMUX="$ORIG_TMUX"
  tmux switch-client -t "$SESSION"
else
  tmux attach-session -t "$SESSION"
fi
