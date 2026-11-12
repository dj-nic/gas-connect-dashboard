FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends mosquitto mosquitto-clients tini && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
RUN mkdir /data
VOLUME /data
EXPOSE 8080 1883
HEALTHCHECK --interval=30s --start-period=20s CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8080/health')); assert d['mqtt']"
ENTRYPOINT ["/usr/bin/tini","--","python","-m","app.entrypoint"]
