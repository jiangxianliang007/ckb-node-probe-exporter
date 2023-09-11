#encoding: utf-8

import requests
import prometheus_client
from prometheus_client import Gauge
from prometheus_client.core import CollectorRegistry
from flask import Response, Flask, request, current_app
import os
import sys


CKB_NODE_PROBE_API = sys.argv[1]
CKB_NODE_PROBE_HEALTH_API = CKB_NODE_PROBE_API + "health"

NodeFlask = Flask(__name__)

def get_ckb_node_online(api):
    try:
        response = requests.get(api)
        data = response.json()
        node_online = len(data)
        return {
            "node_online": node_online,
        }
    except:
        return {
            "node_online": "-1",
        }

def get_api_last_update(api):
    try:
        response = requests.get(api)
        data = response.json()
        last_update_time = data.get('last_update')
        return {
            "last_update": last_update_time,
        }
    except:
        return {
            "last_update": "-1",
        }

@NodeFlask.route("/metrics/probe")
def rpc_get():
    CKB_NODE_PROBE = CollectorRegistry(auto_describe=False)
    Get_api_last_update = Gauge("get_api_last_update",
                                   "Get NODE PROBE API LAST UPDATE TIME",
                                   ["node_probe_health_api"],
                                   registry=CKB_NODE_PROBE)

    Get_node_online = Gauge("get_node_online_totality",
                                   "Get CKB FULLNODE ONLINE TOTALITY",
                                   ["node_probe_api"],
                                   registry=CKB_NODE_PROBE)

    probe_health_info = get_api_last_update(CKB_NODE_PROBE_HEALTH_API)
    Get_api_last_update.labels(
        node_probe_health_api = CKB_NODE_PROBE_HEALTH_API
    ).set(probe_health_info["last_update"])


    probe_node_online_info = get_ckb_node_online(CKB_NODE_PROBE_API)
    Get_node_online.labels(
        node_probe_api = CKB_NODE_PROBE_API
    ).set(probe_node_online_info["node_online"])    

    return Response(prometheus_client.generate_latest(CKB_NODE_PROBE), mimetype="text/plain")

if __name__ == "__main__":
    NodeFlask.run(host="0.0.0.0",port=3000)
