#!/usr/bin/env bash
set -euo pipefail

# Cổng kiểm artifact trước khi phát hành extension cho người dùng.
artifact_dir="${1:-.output/chrome-mv3}"
build_mode="${2:-production}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Nếu có node, ưu tiên dùng verify-build-artifact.mjs để kiểm tra toàn diện
if command -v node >/dev/null 2>&1; then
  node "$script_dir/verify-build-artifact.mjs" "$artifact_dir" "$build_mode"
  exit $?
fi

# Fallback kiểm tra thuần bash nếu không có node
if [[ ! -d "$artifact_dir" ]]; then
  echo "khong tim thay thu muc artifact: $artifact_dir" >&2
  exit 1
fi

manifest_file="$artifact_dir/manifest.json"
if [[ ! -f "$manifest_file" ]]; then
  echo "khong tim thay manifest.json: $manifest_file" >&2
  exit 1
fi

if grep -rEn --include='*.html' '<link[^>]+rel="modulepreload"' "$artifact_dir"; then
  echo "modulepreload tags found in extension HTML" >&2
  exit 1
fi

echo "extension HTML has no cross-world modulepreload tags"

if [[ "$build_mode" == "production" ]]; then
  if grep -rEn --include='*.html' --include='*.js' --include='manifest.json' \
    'https?://(localhost|127\.0\.0\.1)(:[0-9]+)?' "$artifact_dir"; then
    echo "local endpoint found in production extension artifact" >&2
    exit 1
  fi

  for expected_endpoint in \
    "${WXT_API_BASE_URL:-https://p004-api.duckdns.org}" \
    "${WXT_WEB_APP_URL:-https://www.c3-app-004.io.vn}"; do
    if ! grep -rqF --include='*.js' --include='manifest.json' \
      "$expected_endpoint" "$artifact_dir"; then
      echo "missing production endpoint in extension artifact: $expected_endpoint" >&2
      exit 1
    fi
  done

  echo "extension artifact targets production API and web app"
fi
