#!/bin/bash
set -u

URL_BASE="https://admin.194-87-83-31.nip.io"

echo "=== Try common OpenAPI spec paths ==="
for p in /docs/json /docs-json /docs/openapi.json /docs/swagger.json /scalar.json /scalar/v1/openapi.json /api-json /api/openapi.json /openapi /openapi.yaml /api/swagger; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "${URL_BASE}${p}")
  ct=$(curl -sk -o /dev/null -w '%{content_type}' "${URL_BASE}${p}")
  echo "  ${p} -> ${code} ${ct}"
done

echo
echo "=== Look inside /docs HTML for JSON URL reference ==="
curl -sk "${URL_BASE}/docs" 2>/dev/null | grep -oE 'url[[:space:]]*[:=][[:space:]]*"[^"]+"' | head -5
echo
echo "=== Look inside /scalar HTML for JSON URL reference ==="
curl -sk "${URL_BASE}/scalar" 2>/dev/null | grep -oE 'url[[:space:]]*[:=][[:space:]]*"[^"]+"' | head -5
echo
echo "=== Check /docs page first 4 KB ==="
curl -sk "${URL_BASE}/docs" 2>/dev/null | head -c 4000
