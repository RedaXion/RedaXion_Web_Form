# helpers/assemblyai.py
import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger("assemblyai")
logger.setLevel(logging.INFO)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
BASE = "https://api.assemblyai.com/v2"
HEADERS = {"authorization": ASSEMBLYAI_API_KEY} if ASSEMBLYAI_API_KEY else {}

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))


def _upload_file_local(path):
    logger.info("Uploading local file to AssemblyAI: %s", path)
    upload_url = f"{BASE}/upload"
    with open(path, "rb") as f:
        resp = session.post(upload_url, headers=HEADERS, data=f, timeout=120)
    resp.raise_for_status()
    return resp.json().get("upload_url")


def transcribir_audio(audio_source, order_id=None, poll_interval=5, timeout=600):
    if not ASSEMBLYAI_API_KEY:
        raise RuntimeError("ASSEMBLYAI_API_KEY not configured")

    if not str(audio_source).startswith(("http://", "https://")):
        audio_url = _upload_file_local(audio_source)
    else:
        audio_url = audio_source

    payload = {"audio_url": audio_url}
    resp = session.post(f"{BASE}/transcript", headers={**HEADERS, "content-type": "application/json"}, json=payload, timeout=30)
    resp.raise_for_status()
    tid = resp.json()["id"]

    start = time.time()
    while True:
        r = session.get(f"{BASE}/transcript/{tid}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
        status = j.get("status")
        if status == "completed":
            text = j.get("text", "")
            p = f"/tmp/{order_id}_transcript.txt" if order_id else f"/tmp/assemblyai_{tid}_transcript.txt"
            try:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text or "")
                logger.info("Saved transcript artifact: %s (chars=%s)", p, len(text or ""))
            except Exception:
                logger.exception("Could not save transcript to disk")
            return {"transcript_id": tid, "text": text, "raw": j}
        if status in ("queued", "processing"):
            if time.time() - start > timeout:
                raise TimeoutError(f"Transcription timed out after {timeout}s (status={status})")
            time.sleep(poll_interval)
            continue
        if status == "error":
            raise RuntimeError(f"AssemblyAI error: {j.get('error')}")
        time.sleep(poll_interval)
