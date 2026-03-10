#!/usr/bin/env bash
set -euo pipefail

SESSION="lintel"

# If session already exists, switch to it
if tmux has-session -t "$SESSION" 2>/dev/null; then
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

# Attach or switch
if [ -n "$ORIG_TMUX" ]; then
  export TMUX="$ORIG_TMUX"
  tmux switch-client -t "$SESSION"
else
  tmux attach-session -t "$SESSION"
fi
