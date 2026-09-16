FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY staging_bundle /tmp/staging_bundle
COPY staging_persistence_canary.py /app/staging_persistence_canary.py
COPY staging_remote_e2e_v2_1.py /app/staging_remote_e2e_v2_1.py
COPY staging_rc_validation_v2_3.py /app/staging_rc_validation_v2_3.py
COPY apply_rc_v2_3_patch.py /app/apply_rc_v2_3_patch.py
COPY production_hardening_patch_v2_4.py /app/production_hardening_patch_v2_4.py
COPY production_backup_worker_v2_5.py /app/production_backup_worker_v2_5.py
COPY production_google_drive_backup_worker_v2_7.py /app/production_google_drive_backup_worker_v2_7.py
COPY production_google_drive_backup_smoke_v2_7.py /app/production_google_drive_backup_smoke_v2_7.py
COPY production_google_oidc_probe_v2_7.py /app/production_google_oidc_probe_v2_7.py
COPY production_entrypoint_v2_4.py /app/production_entrypoint_v2_4.py
COPY production_public_web_v3_0.py /app/production_public_web_v3_0.py
COPY production_public_web_v3_0_2.py /app/production_public_web_v3_0_2.py
COPY public_web_v3_0 /app/public_web_v3_0
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
 && python /app/apply_rc_v2_3_patch.py \
 && python /app/production_hardening_patch_v2_4.py \
 && python -m py_compile /app/production_entrypoint_v2_4.py /app/production_public_web_v3_0.py /app/production_public_web_v3_0_2.py /app/production_backup_worker_v2_5.py /app/production_google_drive_backup_worker_v2_7.py /app/production_google_drive_backup_smoke_v2_7.py /app/production_google_oidc_probe_v2_7.py \
 && python -c "import json,pathlib; root=json.loads(pathlib.Path('/app/public_web_v3_0/flavor-details.json').read_text()); parts=[json.loads(pathlib.Path('/app/public_web_v3_0', pathlib.Path(url).name).read_text()) for url in root['shards']]; assert root['v']==1 and sum(len(p['f']) for p in parts)==200" \
 && python -c "import google.oauth2.credentials, googleapiclient.discovery, production_google_drive_backup_worker_v2_7 as m; assert m.DRIVE_FILE_SCOPE == 'https://www.googleapis.com/auth/drive.file'" \
 && python /app/production_google_drive_backup_smoke_v2_7.py \
 && rm -rf /tmp/staging_bundle /tmp/staging_source_bundle.b64 \
 && useradd --uid 10001 --create-home shisha \
 && mkdir -p /data/shisha \
 && chown -R shisha:shisha /app /data
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/production_entrypoint_v2_4.py"]
