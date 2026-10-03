# First custom-built image in this project — every other service uses an
# official upstream chart/image (architecture.md §3: "assemble mature
# components, custom code only for the integration layer"). This *is* the
# integration layer: the phase5/ connectors themselves have nowhere
# upstream to come from.
FROM python:3.13-slim

# tzdata: extraction.py's zoneinfo.ZoneInfo("Europe/Paris") needs the IANA
# database, not present in the slim base image by default.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests

WORKDIR /app
COPY *.py .

ENTRYPOINT ["python3", "cron_runner.py"]
