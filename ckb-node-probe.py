# -*- coding: utf-8 -*-
"""Prometheus exporter with periodic mainnet and testnet polling."""

import logging
import os
import sys
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from flask import Flask, Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest

DEFAULT_API = "https://api-nodes.ckb.dev/"
API_BASE = os.environ.get("node_probe_api") or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_API)
API_TIMEOUT = float(os.environ.get("NODE_PROBE_API_TIMEOUT", "10"))
POLL_INTERVAL = float(os.environ.get("NODE_PROBE_POLL_INTERVAL", "60"))
PORT = int(os.environ.get("PORT", "3000"))
if POLL_INTERVAL <= 0:
    raise ValueError("NODE_PROBE_POLL_INTERVAL must be greater than zero")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
_lock = threading.Lock()
_samples = {
    "main": {"total": -1, "known": -1, "unknown": -1, "success": 0, "last_success": 0},
    "test": {"total": -1, "known": -1, "unknown": -1, "success": 0, "last_success": 0},
}
_health_last_update = -1


def api_url(path, network=None):
    parts = urlsplit(API_BASE.rstrip("/"))
    root_path = parts.path.rstrip("/")
    if root_path.endswith("/peer"):
        root_path = root_path[:-5]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k != "network"]
    if network:
        query.append(("network", network))
    return urlunsplit((parts.scheme, parts.netloc, root_path + "/" + path,
                       urlencode(query), parts.fragment))


def fetch_json(url):
    response = requests.get(
        url, timeout=API_TIMEOUT,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    response.raise_for_status()
    return response.json()


def poll_network(network):
    url = api_url("peer", network)
    try:
        peers = fetch_json(url)
        if not isinstance(peers, list) or not all(isinstance(p, dict) for p in peers):
            raise ValueError("Expected a JSON array of peer objects")
        known = sum(bool(p.get("version")) for p in peers)
        with _lock:
            _samples[network] = {
                "total": len(peers), "known": known, "unknown": len(peers) - known,
                "success": 1, "last_success": time.time(),
            }
        logger.info("Collected %s: total=%d known=%d", network, len(peers), known)
    except (requests.RequestException, ValueError, TypeError) as exc:
        # Preserve last known counts, but report the failed API request.
        with _lock:
            _samples[network]["success"] = 0
        logger.warning("Failed to collect %s: %s", network, exc)


def poll_health():
    global _health_last_update
    try:
        value = float(fetch_json(api_url("health"))["last_update"])
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        logger.warning("Failed to collect health endpoint: %s", exc)
        value = -1
    with _lock:
        _health_last_update = value


def polling_loop():
    # There is no API request in the Prometheus scrape handler.
    # Fetch both networks sequentially once per interval, without a forced gap.
    while True:
        started = time.monotonic()
        poll_health()
        poll_network("main")
        poll_network("test")
        time.sleep(max(0, POLL_INTERVAL - (time.monotonic() - started)))


@app.route("/metrics/probe")
def metrics():
    registry = CollectorRegistry(auto_describe=False)
    total = Gauge("get_node_online_totality", "Number of nodes reported by CKB Node Probe",
                  ["network", "node_probe_api"], registry=registry)
    known = Gauge("ckb_node_probe_version_known", "Nodes with a reported version",
                  ["network"], registry=registry)
    unknown = Gauge("ckb_node_probe_version_unknown", "Nodes with an empty version",
                    ["network"], registry=registry)
    success = Gauge("ckb_node_probe_scrape_success", "Whether the latest API poll succeeded",
                    ["network"], registry=registry)
    last_success = Gauge("ckb_node_probe_last_success_timestamp_seconds",
                         "Unix time of most recent successful network API poll",
                         ["network"], registry=registry)
    last_update = Gauge("get_api_last_update", "Timestamp of last CKB Node Probe update",
                        ["node_probe_health_api"], registry=registry)

    with _lock:
        snapshot = {network: record.copy() for network, record in _samples.items()}
        health_last_update = _health_last_update

    for network, record in snapshot.items():
        total.labels(network=network, node_probe_api=api_url("peer", network)).set(record["total"])
        known.labels(network=network).set(record["known"])
        unknown.labels(network=network).set(record["unknown"])
        success.labels(network=network).set(record["success"])
        last_success.labels(network=network).set(record["last_success"])
    last_update.labels(node_probe_health_api=api_url("health")).set(health_last_update)
    return Response(generate_latest(registry), mimetype="text/plain; version=0.0.4")


if __name__ == "__main__":
    # One polling worker per process; do not enable the Flask reloader.
    threading.Thread(target=polling_loop, name="ckb-node-probe-poller", daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)
