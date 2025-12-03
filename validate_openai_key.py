# validate_openai_key.py
import os, sys
import requests

key = os.getenv("OPENAI_API_KEY", "")
print("=== DIAGNÓSTICO OPENAI KEY (no se imprime la clave) ===")

if not key:
    print("RESULT: MISSING_KEY")
    sys.exit(2)

if key.startswith('"') and key.endswith('"'):
    print("RESULT: SURROUNDING_QUOTES")
    sys.exit(3)

if ("\n" in key) or ("\r" in key):
    print("RESULT: KEY_HAS_NEWLINE")
    sys.exit(4)

if len(key) < 20:
    print("RESULT: KEY_TOO_SHORT")
    sys.exit(5)

if not key.startswith("sk-"):
    print("RESULT: KEY_DOES_NOT_START_WITH_sk- (no fatal, pero revisa)")
else:
    print("RESULT: KEY_FORMAT_OK (starts with sk-)")

# Try a lightweight GET to models endpoint to test connectivity (no sensitive output)
try:
    resp = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    print("HTTP_STATUS:", resp.status_code)
    if resp.status_code == 200:
        print("REQUEST: OK (models list reachable)")
        sys.exit(0)
    elif resp.status_code in (401, 403):
        print("REQUEST: AUTH_ERROR (401/403) - key invalid or no access to models")
        sys.exit(6)
    else:
        print("REQUEST: HTTP_ERROR", resp.status_code)
        # don't print full body; print first 200 chars safely
        body = resp.text or ""
        print("BODY_SNIPPET:", body[:200].replace("\n"," "))
        sys.exit(7)
except Exception as ex:
    print("REQUEST_EXCEPTION:", type(ex).__name__, str(ex))
    # often connection errors with illegal header show here
    sys.exit(8)
