FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY staging_source_bundle.zip /tmp/staging_source_bundle.b64
RUN python -c "import base64, pathlib, zipfile; b64=pathlib.Path('/tmp/staging_source_bundle.b64').read_bytes(); raw=base64.b64decode(b64); pathlib.Path('/tmp/staging_source_bundle.zip').write_bytes(raw); zipfile.ZipFile('/tmp/staging_source_bundle.zip').extractall('/app')" \
 && rm /tmp/staging_source_bundle.b64 /tmp/staging_source_bundle.zip \
 && useradd --uid 10001 --create-home shisha \
 && mkdir -p /tmp/shisha \
 && chown -R shisha:shisha /tmp/shisha /app
USER 10001
ENV PYTHONUNBUFFERED=1
CMD ["sh","-c","python shisha_hardened_service_v1_7.py --base-dir /app --db /tmp/shisha/shisha_advisor.db --auth-mode local-bearer --rate-limit 60 --rate-window-seconds 60 --log-path /tmp/shisha/service.jsonl --host 0.0.0.0 --port ${PORT:-8789}"]
