#!/bin/bash
# Reorder routing rules so IPv6 destinations are matched before IPv4.
# Without this, domains with both A/AAAA records get routed to v4-fallback
# (because Xray sees A first in resolution order). With the swap, IPv6
# rule wins for dual-stack domains -> v6-pool balancer kicks in.

set -uo pipefail

cat > /tmp/swap_rules.py <<'PY'
import json, sys
config = json.load(sys.stdin)

# Find and remove the catch-all rules, keep block + domain rules.
v4_catch_all = None
v6_default_network = None
preserved = []
for rule in config["routing"]["rules"]:
    if rule.get("ip") == ["0.0.0.0/0"]:
        v4_catch_all = rule
    elif rule.get("network") == "tcp,udp" and rule.get("balancerTag") == "v6-pool":
        v6_default_network = rule
    else:
        preserved.append(rule)

# Build new rule order: block -> domain rules -> IPv6 catch-all -> IPv4 catch-all
# IPv6 catch-all = "any IPv6 destination" -> v6-pool balancer
# IPv4 catch-all = "any IPv4 destination" -> v4-fallback
new_rules = preserved + [
    {"type": "field", "ip": ["::/0"], "balancerTag": "v6-pool"},
    {"type": "field", "ip": ["0.0.0.0/0"], "outboundTag": "v4-fallback"},
]
config["routing"]["rules"] = new_rules
json.dump(config, sys.stdout, ensure_ascii=False)
PY

docker exec remnawave-db psql -U remnawave -d remnawave -t -A \
    -c "SELECT config FROM config_profiles WHERE uuid = '00000000-0000-0000-0000-000000000000';" \
    > /tmp/old_config.json

python3 /tmp/swap_rules.py < /tmp/old_config.json > /tmp/new_config.json

echo "=== New rule order ==="
python3 -c "import json; r=json.load(open('/tmp/new_config.json'))['routing']; print('domainStrategy:', r['domainStrategy']); [print(' ', i, json.dumps(rule)) for i, rule in enumerate(r['rules'])]"

echo
echo "=== UPDATE DB ==="
{
  echo "BEGIN;"
  echo "UPDATE config_profiles SET config = \$json\$"
  cat /tmp/new_config.json
  echo "\$json\$::jsonb, updated_at = now() WHERE uuid = '00000000-0000-0000-0000-000000000000';"
  echo "SELECT jsonb_array_length(config -> 'routing' -> 'rules') AS rules_count;"
  echo "COMMIT;"
} | docker exec -i remnawave-db psql -U remnawave -d remnawave

echo
echo "=== Restart node ==="
docker compose -f /root/cyber-berezka/infra/docker-compose.node.yml restart 2>&1 | tail -3
sleep 12

echo
echo "=== Node logs ==="
docker logs remnanode --tail 5 2>&1
