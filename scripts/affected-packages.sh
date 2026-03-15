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
  [packages/domain]=lintel-domain
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
  [lintel-contracts]="lintel-domain lintel-agents lintel-infrastructure lintel-workflows lintel lintel-event-store lintel-event-bus lintel-persistence lintel-sandbox lintel-pii lintel-observability lintel-models lintel-slack lintel-repos lintel-projections"
  [lintel-domain]="lintel-agents lintel-infrastructure lintel-workflows lintel"
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

# Include both committed changes since BASE_REF and uncommitted working tree changes
committed=$(git diff --name-only "$BASE_REF"...HEAD 2>/dev/null || git diff --name-only "$BASE_REF" HEAD 2>/dev/null || true)
uncommitted=$(git diff --name-only HEAD 2>/dev/null || true)
untracked=$(git ls-files --others --exclude-standard 2>/dev/null || true)
changed_files=$(printf '%s\n%s\n%s' "$committed" "$uncommitted" "$untracked" | sort -u)

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

# Root files that genuinely affect all packages (dependency/config changes)
ROOT_ALL_PATTERNS="^(pyproject\.toml|uv\.lock|conftest\.py)$|^\.github/"

# Root files/dirs that affect specific packages via integration/e2e tests
# tests/integration/ and tests/e2e/ run against the app package
ROOT_APP_PATTERNS="^tests/"

# Root files that are safe to ignore (docs, scripts, tooling, migrations)
# Makefile, scripts/, docs/, migrations/, *.md, .claude/, todos/, etc.

if echo "$changed_files" | grep -qvE "^packages/"; then
  # Check if any root change requires full rebuild
  if echo "$changed_files" | grep -qE "$ROOT_ALL_PATTERNS"; then
    for pkg in "${PKG_MAP[@]}"; do
      affected+=("$pkg")
    done
  # Check if integration/e2e tests changed — only affects app package
  elif echo "$changed_files" | grep -qE "$ROOT_APP_PATTERNS"; then
    affected+=("lintel")
  fi
  # All other root changes (Makefile, scripts/, docs/, migrations/, etc.)
  # are ignored — they don't affect package test outcomes
fi

# Deduplicate and output
printf '%s\n' "${affected[@]}" | sort -u | tr '\n' ' '
echo
