#!/usr/bin/env bash
# Single entry-point for the full migration pipeline.
# Two manual pause points (Remnawave first-admin registration + API token paste)
# are inevitable architectural constraints. All other steps are automated.
set -euo pipefail

NEW_HOST="${NEW_HOST:-212.74.231.217}"
OLD_HOST="${OLD_HOST:-194.87.83.31}"
LOCAL_BASE="$(cd "$(dirname "$0")/.." && pwd)"

confirm() {
    local prompt="$1"
    read -r -p "${prompt} [y/N] " resp
    [[ "${resp}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
}

echo "===================================================="
echo "  Cyber Berezka — full migration pipeline"
echo "  New (coordinator): ${NEW_HOST}"
echo "  Old (node-only):   ${OLD_HOST}"
echo "===================================================="

echo "===> [1/9] Sanity-check SSH access"
ssh -o BatchMode=yes -o ConnectTimeout=5 "root@${NEW_HOST}" 'echo OK' >/dev/null
ssh -o BatchMode=yes -o ConnectTimeout=5 "root@${OLD_HOST}" 'echo OK' >/dev/null
echo "    SSH OK on both servers"

echo "===> [2/9] Sync repo to NEW server"
bash "${LOCAL_BASE}/scripts/sync_repo_to_server.sh" "${NEW_HOST}"

echo "===> [3/9] Provision NEW server"
ssh "root@${NEW_HOST}" 'bash /root/cyber-berezka/scripts/provision_new_server.sh'

echo "===> [4/9] MANUAL PAUSE — first admin registration"
echo "    Open https://admin.212-74-231-217.nip.io in a browser."
echo "    Register the admin user (username: z1kurat or as you prefer)."
echo "    NOTE: TLS certificate may take ~60s to issue via Let's Encrypt."
confirm "Done?"

echo "===> [5/9] MANUAL PAUSE — paste Remnawave API token"
echo "    In Remnawave UI, go to Settings -> API tokens -> Generate."
echo "    Copy the token, then paste it below."
ssh -t "root@${NEW_HOST}" 'python3 /root/cyber-berezka/infra/remnawave/bootstrap_token.py'

echo "===> [6/9] Sync repo to OLD server"
bash "${LOCAL_BASE}/scripts/sync_repo_to_server.sh" "${OLD_HOST}"

echo "===> [7/9] Teardown old coordinator stack"
ssh "root@${OLD_HOST}" 'bash /root/cyber-berezka/scripts/teardown_old_server.sh'

echo "===> [8/9] Reconfigure OLD as remote node"
echo "    NOTE: NODE_SECRET_KEY in ${OLD_HOST}:/root/cyber-berezka/infra/.env"
echo "    must match what Remnawave panel issued for this node."
confirm "NODE_SECRET_KEY set in old server's .env?"
ssh "root@${OLD_HOST}" 'bash /root/cyber-berezka/scripts/reconfigure_old_as_node.sh'

echo "===> [9/9] Final status"
ssh "root@${NEW_HOST}" 'cd /root/cyber-berezka/infra/remnawave && python3 apply.py status' || true

echo "===================================================="
echo "  Migration complete."
echo "  Next steps:"
echo "    - Rotate Reality keys: ssh root@${NEW_HOST} 'cd /root/cyber-berezka/infra/remnawave && python3 apply.py rotate-reality-key'"
echo "    - Write verification suite (spec task #48)"
echo "===================================================="
