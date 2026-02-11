#!/usr/bin/env bash
# Smoke test for webhook-gateway health endpoint
set -euo pipefail

PORT="${1:-8280}"
URL="http://localhost:${PORT}/health"

echo "Smoke testing ${URL}..."
RESP=$(curl -sf --max-time 5 "${URL}" 2>&1) || {
    echo "FAIL: health endpoint unreachable at ${URL}"
    exit 1
}

echo "Response: ${RESP}"

if echo "${RESP}" | grep -q '"ok"'; then
    echo "PASS: health check returned ok"
    exit 0
else
    echo "FAIL: unexpected response"
    exit 1
fi
