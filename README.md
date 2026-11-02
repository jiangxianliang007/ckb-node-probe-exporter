# ckb-node-probe-exporter

CKB Node Probe Prometheus exporter that **separately polls Mainnet and Testnet in the background**. Prometheus scrapes are served from an in-process snapshot and do not contact the upstream API.

## Run

```bash
docker build -t ckb-node-probe-exporter:periodic .
docker run -d --name ckb-node-probe-exporter -p 3000:3000 \
  -e node_probe_api=https://api-nodes.ckb.dev/ \
  ckb-node-probe-exporter:periodic
curl -s http://127.0.0.1:3000/metrics/probe
```

Config: `node_probe_api` (default `https://api-nodes.ckb.dev/`), `NODE_PROBE_API_TIMEOUT` (default 10 seconds), `NODE_PROBE_POLL_INTERVAL` (default 60 seconds, must be >0), `PORT` (default 3000).

The poller requests mainnet and testnet sequentially without a forced gap, once every 60 seconds (measured from the start of each cycle). Health is polled before the network requests. This assumes the upstream API has already fixed network-specific cache isolation.

**Startup:** metrics are immediately available, but network counts start at `-1` and success at `0` until each first successful poll (testnet is polled immediately after mainnet). After an API failure, last known counts are retained; use success and last-success time to detect stale data.

## Metrics

- `get_node_online_totality{network="main|test",node_probe_api="..."}`: last successfully fetched node count; -1 before first success.
- `ckb_node_probe_version_known{network="main|test"}`: last successfully fetched count with version.
- `ckb_node_probe_version_unknown{network="main|test"}`: last successfully fetched count without version.
- `ckb_node_probe_scrape_success{network="main|test"}`: 1 if latest background poll succeeded; otherwise 0.
- `ckb_node_probe_last_success_timestamp_seconds{network="main|test"}`: Unix timestamp of last successful poll; 0 before the first success.
- `get_api_last_update{node_probe_health_api="..."}`: last update from `/health`, or -1 on health failure.

Use a single exporter process per container so that only one background polling thread is started. Do not use Flask's reloader or multi-worker web servers with this in-process poller. Protect alerts from stale results, e.g. by combining count checks with `ckb_node_probe_scrape_success == 1` and a maximum `time() - ckb_node_probe_last_success_timestamp_seconds`.

**Upstream prerequisite:** Deploy the network-specific cache fix in `ckb-discovery/exposed` before switching to this version. Without it, back-to-back queries may still return cross-network cached data.
