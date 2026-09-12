#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_REPO="$(mktemp -d)"
trap 'rm -rf "$TMP_REPO"' EXIT

git init -q -b main "$TMP_REPO"
git -C "$TMP_REPO" config user.email test@example.com
git -C "$TMP_REPO" config user.name Test
printf 'clean checkout\n' > "$TMP_REPO/README"
git -C "$TMP_REPO" add README
git -C "$TMP_REPO" commit -qm initial

output="$(cd "$TMP_REPO" && P004_SSH_KEY="$TMP_REPO/deploy-key" \
  bash "$REPO_ROOT/scripts/deploy_vm_local.sh" --dry-run)"

grep -Fq 'git pull --ff-only origin main' <<< "$output"
grep -Fq 'rsync' <<< "$output"
if grep -Fq -- '--delete-delay' <<< "$output"; then
  echo 'deploy script must not delete VM artifacts' >&2
  exit 1
fi
grep -Fq 'production .env, git data and local caches excluded' <<< "$output"
grep -Fq 'Building and rolling out backend services on VM' <<< "$output"
grep -Fq 'curl -fsS https://p004-api.duckdns.org/health' <<< "$output"

echo 'deploy_vm_local.sh dry-run test passed'
