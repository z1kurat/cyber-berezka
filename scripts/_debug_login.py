#!/usr/bin/env python3
"""Diagnose what Remnawave login returns and what /api/tokens needs."""
import getpass
import json
import sys

import httpx

URL = "https://admin.194-87-83-31.nip.io"
USERNAME = sys.argv[1] if len(sys.argv) > 1 else "z1kurat"
PASSWORD = getpass.getpass(f"Password for {USERNAME}: ")

print("\n=== Step 1: POST /api/auth/login ===")
with httpx.Client(base_url=URL, timeout=15) as c:
    r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    print(f"Status: {r.status_code}")
    print(f"Cookies set: {[(k, v[:20]+'...' if len(v) > 20 else v) for k, v in r.cookies.items()]}")
    print(f"Headers (subset): {dict((k, v) for k, v in r.headers.items() if k.lower() in ('set-cookie','content-type','x-auth'))}")

    body = r.json()
    print(f"Body keys: {list(body.keys())}")
    if "response" in body:
        resp = body["response"]
        print(f"  response keys: {list(resp.keys())}")
        for k, v in resp.items():
            preview = (str(v)[:60] + "...") if isinstance(v, str) and len(str(v)) > 60 else v
            print(f"    {k}: {preview}")

    jwt = body.get("response", {}).get("accessToken") or body.get("response", {}).get("token")
    if not jwt:
        print("\nNo accessToken in response. Aborting.")
        sys.exit(2)

    print(f"\n=== Step 2: GET /api/tokens with same client (cookies + Bearer) ===")
    r2 = c.get("/api/tokens", headers={"Authorization": f"Bearer {jwt}"})
    print(f"Status: {r2.status_code}")
    print(f"Body preview: {r2.text[:300]}")

    print(f"\n=== Step 3: GET /api/system/health with cookies only (no Bearer) ===")
    r3 = c.get("/api/system/health")
    print(f"Status: {r3.status_code}")
    print(f"Body preview: {r3.text[:300]}")

    print(f"\n=== Step 4: POST /api/tokens (cookie + Bearer combined) ===")
    r4 = c.post("/api/tokens", json={"tokenName": "cyber-berezka-debug"},
                headers={"Authorization": f"Bearer {jwt}"})
    print(f"Status: {r4.status_code}")
    print(f"Body preview: {r4.text[:400]}")
