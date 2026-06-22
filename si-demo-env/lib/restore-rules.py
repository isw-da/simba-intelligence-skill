# Apply SI NLQ tenant rules from a rules.json (list) on stdin. Idempotent upsert keyed on
# (name, tenant_id). Runs INSIDE the chart pod; reads the DB password from pod env only.
#
# IDs are install-specific. tenant_id / user_id resolve in this order:
#   1. the rule's own field (if the snapshot carried it)
#   2. env TENANT_ID / USER_ID (set these in the demo's config.sh)
#   3. auto-discover the single tenant/admin user from an existing rule
# If none resolve, it stops with a clear message — this is the fresh-install ID-remap gap.
import os, sys, json, psycopg2

rows = json.load(sys.stdin)
c = psycopg2.connect(
    host=os.environ.get("PG_HOST", "si-logi-symphony-postgresql"), port=5432,
    user=os.environ.get("POSTGRES_USER", "simbaintelligenceuser"),
    password=os.environ["POSTGRES_PASSWORD"],
    dbname=os.environ.get("POSTGRES_DATABASE", "simbaintelligence"),
    connect_timeout=8)
cur = c.cursor()

env_tenant = os.environ.get("TENANT_ID") or None
env_user = os.environ.get("USER_ID") or None
disc_tenant = disc_user = None
try:
    cur.execute("SELECT tenant_id, user_id FROM rules ORDER BY id LIMIT 1")
    r = cur.fetchone()
    if r:
        disc_tenant, disc_user = r
except Exception:
    pass

def resolve(rule, key, env_v, disc_v):
    # env (the discovered tenant on a fresh install) wins, then the rule's own, then auto-discovered
    return env_v or rule.get(key) or disc_v

ins = upd = skip = 0
for r in rows:
    tenant = resolve(r, "tenant_id", env_tenant, disc_tenant)
    user = resolve(r, "user_id", env_user, disc_user)
    if not tenant or not user:
        print(f"  ! cannot resolve tenant_id/user_id for rule '{r['name']}' "
              f"(set TENANT_ID/USER_ID in config.sh) — skipped")
        skip += 1
        continue
    dsid = r.get("data_source_id")
    tw = r.get("is_tenant_wide", True)
    en = r.get("enabled", True)
    cur.execute("SELECT id FROM rules WHERE name=%s AND tenant_id=%s", (r["name"], tenant))
    ex = cur.fetchone()
    if ex:
        cur.execute("UPDATE rules SET content=%s, enabled=%s, user_id=%s, is_tenant_wide=%s, "
                    "data_source_id=%s, updated_at=now() WHERE id=%s",
                    (r["content"], en, user, tw, dsid, ex[0]))
        upd += 1
    else:
        cur.execute("INSERT INTO rules (user_id, tenant_id, is_tenant_wide, name, content, enabled, "
                    "data_source_id, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s, now(), now())",
                    (user, tenant, tw, r["name"], r["content"], en, dsid))
        ins += 1
c.commit()
cur.execute("SELECT count(*) FROM rules")
print(f"  rules: {ins} inserted, {upd} updated, {skip} skipped; total now {cur.fetchone()[0]}")
c.close()
