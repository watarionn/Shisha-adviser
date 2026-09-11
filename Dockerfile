FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY staging_bundle /tmp/staging_bundle
COPY staging_persistence_canary.py /app/staging_persistence_canary.py
COPY staging_entrypoint.py /app/staging_entrypoint.py
RUN cat \
 /tmp/staging_bundle/00a.b64 /tmp/staging_bundle/00b.b64 \
 /tmp/staging_bundle/01a1.b64 /tmp/staging_bundle/01a2.b64 /tmp/staging_bundle/01b1.b64 /tmp/staging_bundle/01b2.b64 \
 /tmp/staging_bundle/02a1.b64 /tmp/staging_bundle/02a2.b64 \
 /tmp/staging_bundle/02x0.b64 /tmp/staging_bundle/02x1.b64 /tmp/staging_bundle/02x2.b64 /tmp/staging_bundle/02x3.b64 \
 /tmp/staging_bundle/03.b64 /tmp/staging_bundle/04.b64 \
 /tmp/staging_bundle/05a.b64 /tmp/staging_bundle/05b.b64 \
 /tmp/staging_bundle/06a.b64 /tmp/staging_bundle/06b.b64 /tmp/staging_bundle/06c.b64 /tmp/staging_bundle/06d.b64 \
 /tmp/staging_bundle/07a.b64 /tmp/staging_bundle/07b.b64 /tmp/staging_bundle/07c.b64 \
 > /tmp/staging_source_bundle.b64 \
 && python -c "import base64,hashlib,io,pathlib,zipfile; txt=pathlib.Path('/tmp/staging_source_bundle.b64').read_text(); raw=base64.b64decode(txt,validate=True); actual=hashlib.sha256(raw).hexdigest(); expected='8795b3b80a147e3107e0844fbcab777fbd7308ab4f06cf7f54e2d21148c6e4a2'; assert actual==expected,(actual,expected); z=zipfile.ZipFile(io.BytesIO(raw)); assert z.testzip() is None; z.extractall('/app')" \
 && rm -rf /tmp/staging_bundle /tmp/staging_source_bundle.b64 \
 && useradd --uid 10001 --create-home shisha \
 && mkdir -p /tmp/shisha \
 && chown -R shisha:shisha /app
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/staging_entrypoint.py"]
