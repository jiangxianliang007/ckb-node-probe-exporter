# -*- coding: utf-8 -*-
"""Prometheus exporter for CKB Node Probe mainnet and testnet."""

import os
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from flask import Flask, Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest

DEFAULT_API = "https://api-nodes.ckb.dev/"
API_BASE = os.environ.get("node_probe_api") or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_API)
API_TIMEOUT = float(os.environ.get("NODE_PROBE_API_TIMEOUT", "10"))
PORT = int(os.environ.get("PORT", "3000"))

app = Flask(__name__)


def api_url(path, network=None):
    """Build a URL without inheriting an accidentally pinned network parameter."""
    base = API_BASE.rstrip("/")
    parts = urlsplit(base)
    root_path = parts.path.rstrip("/")
    if root_path.endswith("/peer"):
        root_path = root_path[:-5]
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key != "network"]
    if network:
        query.append(("network", network))
    # Preserve existing timeout parameters when configured by the caller.
    return urlunsplit((parts.scheme, parts.netloc, root_path + "/" + path,
                       urlencode(query), parts.fragment))


def fetch_json(url):
    response = requests.get(url, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


@app.route("/metrics/probe")
def metrics():
    registry = CollectorRegistry(auto_describe=False)
    total = Gauge("get_node_online_totality", "Number of nodes reported by CKB Node Probe",
                  ["network", "node_probe_api"], registry=registry)
    known = Gauge("ckb_node_probe_version_known", "Nodes with a reported version",
                  ["network"], registry=registry)
    unknown = Gauge("ckb_node_probe_version_unknown", "Nodes with an empty version",
                    ["network"], registry=registry)
    success = Gauge("ckb_node_probe_scrape_success", "Whether the network API request succeeded",
                    ["network"], registry=registry)
    last_update = Gauge("get_api_last_update", "Timestamp of last CKB Node Probe update",
                        ["node_probe_health_api"], registry=registry)

    health_url = api_url("health")
    try:
        health = fetch_json(health_url)
        last_update.labels(node_probe_health_api=health_url).set(float(health["last_update"]))
    except (requests.RequestException, ValueError, TypeError, KeyError):
        last_update.labels(node_probe_health_api=health_url).set(-1)

    for network in ("main", "test"):
        peer_url = api_url("peer", network)
        try:
            peers = fetch_json(peer_url)
            if not isinstance(peers, list):
                raise ValueError("Expected a JSON array from /peer")
            count_known = sum(1 for node in peers if isinstance(node, dict) and node.get("version"))
            total.labels(network=network, node_probe_api=peer_url).set(len(peers))
            known.labels(network=network).set(count_known)
            unknown.labels(network=network).set(len(peers) - count_known)
            success.labels(network=network).set(1)
        except (requests.RequestException, ValueError, TypeError):
            total.labels(network=network, node_probe_api=peer_url).set(-1)
            known.labels(network=network).set(-1)
            unknown.labels(network=network).set(-1)
            success.labels(network=network).set(0)

    return Response(generate_latest(registry), mimetype="text/plain; version=0.0.4")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
