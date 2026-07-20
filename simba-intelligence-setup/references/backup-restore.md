# Backup and restore: the identity-carry pattern

Proven route for moving or reviving an SI instance with its licence, users, API
keys, LLM config, connections and sources intact (used gren→mcpdemo→azuretest,
and for the 2026 webinar rig revivals). Capture: pg_dump the six databases
(simbaintelligence, zoomdata, zoomdata-upload, zoomdata-keyset,
zoomdata-user-auditing, zoomdata-qe) plus host artefacts (pg password, Caddyfile,
port-forward list, k8s secrets). Restore: fresh chart install, restore dumps,
re-run the dbm job, scale up.

## The paid-for lessons, in order of discovery

1. **discovery-web must be up before the dbm re-run.** Its init container waits
   on `http://si-discovery-web:9050/discovery/actuator/health/liveness`.
2. **Consul must stay up during the restore.** Scale only DEPLOYS plus the
   discovery statefulsets down before dropping databases; discovery-web's init
   also waits on consul. Scaling every statefulset to zero deadlocks the restore.
3. **Drop with force.** `dropdb --force` avoids hangs on lingering connections.
4. **Resync sequences after pg_restore, before the first write** (2026-07-20).
   pg_restore can leave sequences behind their tables; the instance READS fine
   and fails only on the first INSERT (for us: `duplicate key value violates
   unique constraint "acl_entry_pkey"` on the first visual created via API).
   Fix, per database:

   ```sql
   -- generates one setval per owned sequence; run the generated statements
   SELECT 'SELECT setval(' || quote_literal(quote_ident(ns.nspname)||'.'||quote_ident(s.relname))
     || ', COALESCE((SELECT MAX('||quote_ident(a.attname)||') FROM '
     || quote_ident(tns.nspname)||'.'||quote_ident(t.relname)||'), 0)+1, false);'
   FROM pg_class s
   JOIN pg_namespace ns ON ns.oid=s.relnamespace
   JOIN pg_depend d ON d.objid=s.oid AND d.deptype='a'
   JOIN pg_class t ON t.oid=d.refobjid
   JOIN pg_namespace tns ON tns.oid=t.relnamespace
   JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid
   WHERE s.relkind='S';
   ```

   Verification that costs nothing: after any restore, CREATE one throwaway
   object through the API (a visual, a tag) before declaring the restore done.
5. **The licence carries in the DBs**, and licence keys are instance-token-bound
   unless minted with the instance_id restriction disabled. A key with
   `instance_id: enabled=false` is portable across instances.
6. **DISABLE_BI_FEATURES in the licence silently hides Composer dashboards.**
   If the restored instance needs the BI/visuals surface, check
   `GET /discovery/api/license` (basic auth admin) and look for
   `DISABLE_BI_FEATURES` in features; apply a viz-enabled key via
   `POST /discovery/api/license` with `Content-Type: application/vnd.composer.v3+json`
   and body `{"licenseKey": "<key>"}`. Back up the old key first (same GET).
