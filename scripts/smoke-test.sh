#!/bin/bash
# Smoke test for webhook-gateway
# Checks /health endpoint

URL="http://localhost:8280/health"

echo "Checking $URL..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Health check passed (200 OK)"
    exit 0
else
    echo "❌ Health check failed (HTTP $HTTP_CODE)"
    exit 1
fi
