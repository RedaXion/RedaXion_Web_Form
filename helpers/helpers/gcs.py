# helpers/gcs.py
import os
import json
from google.cloud import storage
from google.oauth2 import service_account
from datetime import timedelta

def _get_client():
    creds_json = os.getenv("GCS_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GCS_CREDENTIALS_JSON no configurada")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info)
    return storage.Client(credentials=creds, project=info.get("project_id"))

def upload_to_gcs(local_path: str, filename: str) -> str:
    """
    Sube local_path al bucket y retorna una URL firmada (v4) válida 7 días.
    """
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET no configurado")

    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_filename(local_path, content_type="audio/mpeg")

    # Generar URL firmada (7 días)
    url = blob.generate_signed_url(version="v4", expiration=timedelta(days=7), method="GET")
    return url
