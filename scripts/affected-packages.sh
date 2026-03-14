#!/usr/bin/env bash
# Determine which workspace packages are affected by changes since a given git ref.
# Usage: ./scripts/affected-packages.sh [BASE_REF]
# Default BASE_REF: origin/main
#
# Outputs space-separated package names (e.g., "lintel-contracts lintel")

set -euo pipefail

BASE_REF="${1:-origin/main}"

# Map directory prefixes to package names
declare -A PKG_MAP=(
  [packages/contracts]=lintel-contracts
  [packages/agents]=lintel-agents
  [packages/infrastructure]=lintel-infrastructure
  [packages/workflows]=lintel-workflows
  [packages/app]=lintel
  [packages/event-store]=lintel-event-store
  [packages/event-bus]=lintel-event-bus
  [packages/persistence]=lintel-persistence
  [packages/sandbox]=lintel-sandbox
  [packages/pii]=lintel-pii
  [packages/observability]=lintel-observability
  [packages/models]=lintel-models
  [packages/slack]=lintel-slack
  [packages/repos]=lintel-repos
  [packages/coordination]=lintel-coordination
  [packages/projections]=lintel-projections
)

# Dependency graph: package -> dependents (transitive closure)
declare -A DEPENDENTS=(
  [lintel-contracts]="lintel-agents lintel-infrastructure lintel-workflows lintel lintel-event-store lintel-event-bus lintel-persistence lintel-sandbox lintel-pii lintel-observability lintel-models lintel-slack lintel-repos lintel-projections"
  [lintel-agents]="lintel-workflows lintel"
  [lintel-infrastructure]="lintel"
  [lintel-workflows]="lintel"
  [lintel]=""
  [lintel-event-store]="lintel-projections lintel"
  [lintel-event-bus]="lintel-projections lintel"
  [lintel-persistence]="lintel"
  [lintel-sandbox]="lintel"
  [lintel-pii]="lintel"
  [lintel-observability]="lintel"
  [lintel-models]="lintel"
  [lintel-slack]="lintel"
  [lintel-repos]="lintel"
  [lintel-coordination]="lintel"
  [lintel-projections]="lintel"
)

changed_files=$(git diff --name-only "$BASE_REF"...HEAD 2>/dev/null || git diff --name-only "$BASE_REF" HEAD)

affected=()

for prefix in "${!PKG_MAP[@]}"; do
  pkg="${PKG_MAP[$prefix]}"
  if echo "$changed_files" | grep -q "^${prefix}/"; then
    affected+=("$pkg")
    # Add transitive dependents
    for dep in ${DEPENDENTS[$pkg]}; do
      affected+=("$dep")
    done
  fi
done

# Changes outside packages/ (root configs, CI, tests/) affect everything
if echo "$changed_files" | grep -qvE "^packages/"; then
  for pkg in "${PKG_MAP[@]}"; do
    affected+=("$pkg")
  done
fi

# Deduplicate and output
printf '%s\n' "${affected[@]}" | sort -u | tr '\n' ' '
echo
