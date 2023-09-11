# ckb-node-probe-exporter

run 
```
docker run -d -it -p 3000:3000 -e node_probe_api=https://api-nodes.ckb.dev/  jiangxianliang/ckb-node-probe-exporter:20230911

curl http://127.0.0.1:3000/metrics/probe
```
