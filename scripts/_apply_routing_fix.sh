#!/bin/bash
# Apply IPv4-routing fix to Remnawave profile config and restart node.
set -uo pipefail

DB="docker exec -i remnawave-db psql -U remnawave -d remnawave"

cat > /tmp/fix_routing.py <<'PY'
import json, sys
config = json.load(sys.stdin)
new_rules = []
for rule in config["routing"]["rules"]:
    new_rules.append(rule)
    if rule.get("outboundTag") == "v4-fallback" and "domain" in rule:
        new_rules.append({
            "type": "field",
            "ip": ["0.0.0.0/0"],
            "outboundTag": "v4-fallback",
        })
config["routing"]["rules"] = new_rules
config["routing"]["domainStrategy"] = "IPOnDemand"
json.dump(config, sys.stdout, ensure_ascii=False)
PY

echo "=== Read current config ==="
docker exec remnawave-db psql -U remnawave -d remnawave -t -A \
    -c "SELECT config FROM config_profiles WHERE uuid = '00000000-0000-0000-0000-000000000000';" \
    > /tmp/old_config.json
wc -c /tmp/old_config.json

echo
echo "=== Transform ==="
python3 /tmp/fix_routing.py < /tmp/old_config.json > /tmp/new_config.json
wc -c /tmp/new_config.json

echo
echo "=== Build UPDATE SQL with JSONB literal in dollar-quotes ==="
{
  echo "BEGIN;"
  echo "UPDATE config_profiles SET config = \$json\$"
  cat /tmp/new_config.json
  echo "\$json\$::jsonb,"
  echo "updated_at = now() WHERE uuid = '00000000-0000-0000-0000-000000000000';"
  echo "SELECT jsonb_array_length(config -> 'routing' -> 'rules') AS rules_count,"
  echo "       config -> 'routing' -> 'domainStrategy' AS strategy"
  echo "FROM config_profiles WHERE uuid = '00000000-0000-0000-0000-000000000000';"
  echo "COMMIT;"
} > /tmp/update.sql
wc -l /tmp/update.sql

echo
echo "=== Execute UPDATE ==="
$DB < /tmp/update.sql

echo
echo "=== Verify DB state ==="
docker exec remnawave-db psql -U remnawave -d remnawave -t -A \
    -c "SELECT jsonb_array_length(config -> 'routing' -> 'rules'), config -> 'routing' -> 'domainStrategy' FROM config_profiles WHERE uuid = '00000000-0000-0000-0000-000000000000';"

echo
echo "=== Restart node ==="
docker compose -f /root/cyber-berezka/infra/docker-compose.node.yml restart 2>&1 | tail -3
sleep 12

echo
echo "=== Node logs ==="
docker logs remnanode --tail 6 2>&1
