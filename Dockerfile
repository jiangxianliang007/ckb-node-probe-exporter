FROM python:3.9

WORKDIR /config
COPY ./ckb-node-probe.py ./requirements.txt /config/
RUN pip3 install -r requirements.txt
ENV PORT=3000

CMD "python3" "ckb-node-probe.py" "$node_probe_api" 
