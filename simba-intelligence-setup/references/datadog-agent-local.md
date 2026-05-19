# Ship local kind cluster logs to Datadog

Mirror the hosted SI observability surface in `simba-intel-lab` by
running the Datadog Agent as a DaemonSet. Once installed, every container
in the `simba-intel` namespace ships logs to your Datadog org, indexed
by the same `service` and `kube_cluster_name` facets as the hosted
clusters.

Useful when:
- You're reproducing a hosted bug locally and want the same logging
  ergonomics
- You're prepping a demo and want Datadog-side visualisation
- You're testing new SI versions and want to compare behaviour against
  hosted before rolling out

Not useful when:
- You just need a quick `kubectl logs` (don't add Datadog noise for
  that)
- You're working air-gapped (no outbound connectivity)
- You're on metered bandwidth (the Agent is chatty)

---

## Prerequisites

Local cluster details (from your CLAUDE.md):
- Kind cluster: `simba-intel-lab`
- Namespace: `simba-intel`
- Helm release: `si`

You need:
- A Datadog API key (not Application key). See `datadog-logs.md` §
  Programmatic access for how to get one. For local-only Agent traffic
  you can reuse an existing key from another project; the key is just
  a submission token.
- `helm` installed
- ~500 MiB free in the cluster (Agent DaemonSet plus the cluster-check
  pod)

Decide on a cluster identifier. Recommendation: `simba-intel-lab` so it
matches your local kind cluster name and shows up as a distinct
`kube_cluster_name` facet in Datadog.

---

## One-shot install

Pick a US1 site (`datadoghq.com`) since that's where `Isw-Nonprod`
lives. Adjust `DD_API_KEY` and the cluster name as needed.

```bash
helm repo add datadog https://helm.datadoghq.com
helm repo update

kubectl create namespace datadog 2>/dev/null || true

helm upgrade --install datadog-agent \
  --namespace datadog \
  --set datadog.apiKey=$DD_API_KEY \
  --set datadog.site=datadoghq.com \
  --set datadog.clusterName=simba-intel-lab \
  --set datadog.logs.enabled=true \
  --set datadog.logs.containerCollectAll=true \
  --set datadog.kubelet.tlsVerify=false \
  --set clusterAgent.enabled=true \
  --set clusterAgent.metricsProvider.enabled=false \
  datadog/datadog
```

What each flag does:

- `datadog.logs.enabled=true` turns the log shipper on. Off by default.
- `datadog.logs.containerCollectAll=true` auto-discovers every container
  in every namespace. Without this you'd have to annotate each pod
  individually.
- `datadog.kubelet.tlsVerify=false` is required for kind specifically.
  Kind's kubelet cert isn't trusted by the Agent's default chain. On
  EKS / AKS / GKE you'd leave this on.
- `clusterAgent.enabled=true` adds the cluster-level Agent for K8s
  metadata enrichment (deployment/replica-set tags, etc.). Without it
  your logs would have container names but not nicer kube tags.
- `clusterAgent.metricsProvider.enabled=false` disables the External
  Metrics Provider feature. You don't need it locally and it requires
  a TLS cert dance.

Wait for the Agent pods to come up:

```bash
kubectl -n datadog get pods -w
```

Expect one `datadog-agent-<id>` DaemonSet pod per node (just one on
kind by default) plus a `datadog-cluster-agent-<id>` pod.

---

## Verify logs are flowing

In Datadog Log Explorer:

```
kube_cluster_name:simba-intel-lab
```

Within ~30 seconds you should see entries. Filter by your SI service:

```
kube_cluster_name:simba-intel-lab service:simba-intelligence
```

If nothing arrives:

1. Check the Agent itself is healthy:
   ```
   kubectl -n datadog logs -l app.kubernetes.io/component=agent --tail=50
   ```
   Look for `Successfully posted payload to "https://agent.logs.datadoghq.com/api/v2/logs"`.
2. Check the kubelet cert flag took effect. Errors mentioning `tls:
   failed to verify certificate` mean `tlsVerify=false` didn't apply.
3. Confirm the API key is right. The Agent logs an `Error: API key is
   invalid` line clearly if it isn't.

---

## Mirroring the hosted facet names

For the saved Log Explorer queries from `datadog-logs.md` to work
locally without modification, the local logs need the same `service`
tags as the hosted ones (`simba-intelligence`, `zoomdata-query-engine`,
etc.). By default the Agent uses the container name as the service tag,
which won't match.

Two ways to fix this. Pick one:

### Option A: pod annotations (precise, more work)

Annotate the SI pods so the Agent uses the same service names hosted
uses. Add to your Helm `values.yaml`:

```yaml
si-simba-intelligence-chart:
  podAnnotations:
    ad.datadoghq.com/simbaintelligence.logs: |
      [{
        "source": "simba-intelligence",
        "service": "simba-intelligence"
      }]

si-discovery-query-engine:
  podAnnotations:
    ad.datadoghq.com/zoomdata-query-engine.logs: |
      [{
        "source": "zoomdata-query-engine",
        "service": "zoomdata-query-engine"
      }]
```

Repeat for each service you care about. Annotation key format:
`ad.datadoghq.com/<container-name>.logs`.

Then re-apply your SI Helm release.

### Option B: filename-based mapping (broad, less precise)

Skip the per-pod annotation and rely on the Agent's auto-tagging from
container names. Acceptable if you're only ever filtering by
`kube_cluster_name:simba-intel-lab` and don't care that the `service`
facet shows `simbaintelligence` instead of `simba-intelligence`.

---

## Reducing noise

The default `containerCollectAll=true` ships logs from every container,
including system pods. To exclude noisy ones:

```bash
helm upgrade datadog-agent \
  --namespace datadog \
  --reuse-values \
  --set datadog.containerExclude="kube_namespace:kube-system kube_namespace:datadog name:coredns"
```

Excludes:
- Everything in `kube-system` (kubelet, coredns, kube-proxy)
- The Datadog Agent itself (avoids recursive log ingestion)
- CoreDNS by container name

---

## Cost awareness

Even on a local lab cluster the Agent will happily ship gigabytes of
logs per day if you let it. Two safeguards:

- **Use a personal key with a sampling pipeline.** In Datadog, set up a
  log processing pipeline that drops anything with `kube_cluster_name:simba-intel-lab`
  and `status:info` beyond, say, 10% sampling.
- **Set log retention to 1 day** for the local cluster. Configure under
  Logs → Configuration → Indexes → exclusion filter on
  `kube_cluster_name:simba-intel-lab` with retention override.

If you're on a team-owned key, ask the key owner before turning this
on.

---

## Teardown

When you're done:

```bash
helm uninstall datadog-agent -n datadog
kubectl delete namespace datadog
```

To stop shipping logs without removing the Agent (e.g. you're going
air-gapped):

```bash
helm upgrade datadog-agent -n datadog --reuse-values \
  --set datadog.logs.enabled=false
```

---

## Known gotchas

- **kind kubelet TLS**: the `kubelet.tlsVerify=false` flag is required.
  Without it the Agent silently can't enumerate pods.
- **Docker Desktop Kubernetes on macOS**: similar issue, plus the Agent
  needs `criSocketPath: /var/run/cri-dockerd.sock` if you're on a
  recent Docker Desktop. Add via
  `--set datadog.criSocketPath=/var/run/cri-dockerd.sock`.
- **ARM Macs**: the Agent image is multi-arch, no special handling
  needed.
- **Air-gapped clusters**: the Agent has an enterprise on-prem variant
  (Observability Pipelines Worker). Out of scope for this guide;
  consult Datadog directly.
