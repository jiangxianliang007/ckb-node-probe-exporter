# ckb-node-probe-exporter

CKB Node Probe Prometheus exporter that **separately polls Mainnet and Testnet in the background**. Prometheus scrapes are served from an in-process snapshot and do not contact the upstream API.

## Run

```bash
docker build -t ckb-node-probe-exporter:staggered .
docker run -d --name ckb-node-probe-exporter -p 3000:3000 \
  -e node_probe_api=https://api-nodes.ckb.dev/ \
  ckb-node-probe-exporter:staggered
curl -s http://127.0.0.1:3000/metrics/probe
```

Config: `node_probe_api` (default `https://api-nodes.ckb.dev/`), `NODE_PROBE_API_TIMEOUT` (default 10 seconds), `NODE_PROBE_POLL_GAP` (default 35 seconds, must be >30), `PORT` (default 3000).

The poller requests mainnet, waits 35 seconds, requests testnet, waits 35 seconds, then repeats. Health is polled before mainnet. This avoids fetching both networks within the upstream API's 30-second shared in-memory cache window *when the exporter is the only client refreshing that cache*. Other clients, replicas, or proxies may still populate the upstream cache; the actual fix is network-specific caching in `ckb-discovery/exposed`.

**Startup:** metrics are immediately available, but network counts start at `-1` and success at `0` until each first successful poll (testnet is first polled after about 35 seconds). After an API failure, last known counts are retained; use success and last-success time to detect stale data.

## Metrics

- `get_node_online_totality{network="main|test",node_probe_api="..."}`: last successfully fetched node count; -1 before first success.
- `ckb_node_probe_version_known{network="main|test"}`: last successfully fetched count with version.
- `ckb_node_probe_version_unknown{network="main|test"}`: last successfully fetched count without version.
- `ckb_node_probe_scrape_success{network="main|test"}`: 1 if latest background poll succeeded; otherwise 0.
- `ckb_node_probe_last_success_timestamp_seconds{network="main|test"}`: Unix timestamp of last successful poll; 0 before the first success.
- `get_api_last_update{node_probe_health_api="..."}`: last update from `/health`, or -1 on health failure.

Run exactly **one exporter process/replica** for this workaround; multiple instances can refresh the upstream cache at different times and collide. Do not use Flask's reloader or multi-worker web servers with this in-process poller. Protect alerts from stale results, e.g. by combining count checks with `ckb_node_probe_scrape_success == 1` and a maximum `time() - ckb_node_probe_last_success_timestamp_seconds`.

**Upstream caveat:** This is a best-effort operational workaround, not a guarantee: the API's 30-second cache is global to its instance, and another consumer can refresh it between our staggered requests. Fix the cache key in `ckb-discovery/exposed` for definitive network separation.
