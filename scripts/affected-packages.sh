#!/usr/bin/env bash
# Determine which workspace packages are affected by changes since a given git ref.
# Usage: ./scripts/affected-packages.sh [BASE_REF]
# Default BASE_REF: origin/main
#
# Outputs space-separated package names (e.g., "lintel-contracts lintel-domain lintel")

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
)

# Dependency graph: package -> dependents (transitive closure)
declare -A DEPENDENTS=(
  [lintel-contracts]="lintel-domain lintel-agents lintel-infrastructure lintel-workflows lintel"
  [lintel-domain]="lintel-infrastructure lintel"
  [lintel-agents]="lintel-workflows lintel"
  [lintel-infrastructure]="lintel"
  [lintel-workflows]="lintel"
  [lintel]=""
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
