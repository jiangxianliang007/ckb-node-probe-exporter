# ckb-node-probe-exporter

Prometheus exporter for CKB Node Probe. It queries **both** mainnet and testnet using the same API endpoint and labels network metrics with `network="main"` and `network="test"`.

## Run

Build locally:

```bash
docker build -t ckb-node-probe-exporter:network-labels .
docker run -d --name ckb-node-probe-exporter -p 3000:3000 \
  -e node_probe_api=https://api-nodes.ckb.dev/ \
  ckb-node-probe-exporter:network-labels
curl -s http://127.0.0.1:3000/metrics/probe
```

Optionally set `NODE_PROBE_API_TIMEOUT` (seconds, default 10) and `PORT` (default 3000). The API URL defaults to `https://api-nodes.ckb.dev/`.

## Metrics

- `get_node_online_totality{network="main|test",node_probe_api="..."}`: count of peers returned by the API, or -1 when the request fails.
- `ckb_node_probe_version_known{network="main|test"}`: peers with a non-empty version.
- `ckb_node_probe_version_unknown{network="main|test"}`: peers whose version is empty.
- `ckb_node_probe_scrape_success{network="main|test"}`: 1 for successful API requests, 0 otherwise.
- `get_api_last_update{node_probe_health_api="..."}`: last update from `/health` (or -1 on failure).

The existing metric names `get_node_online_totality` and `get_api_last_update` are retained. `get_node_online_totality` now has an additional `network` label, so update Prometheus/Grafana queries if necessary.

**Upstream caveat:** The `ckb-discovery/exposed` API implementation currently shares a single 30-second process cache between networks. This exporter queries `network=main` and `network=test` separately, but it cannot correct cross-network results caused by the API server. Fix the upstream cache to use a network-specific key before relying on both metrics for alerts.
