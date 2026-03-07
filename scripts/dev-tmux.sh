#!/usr/bin/env bash
set -euo pipefail

SESSION="lintel"

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null || true

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

# Right: UI dev server
tmux split-window -h -t "$SESSION:services"
tmux send-keys -t "$SESSION:services" "make ui-dev" Enter

# Start on the prompts window
tmux select-window -t "$SESSION:prompts"

# Attach
tmux attach-session -t "$SESSION"
