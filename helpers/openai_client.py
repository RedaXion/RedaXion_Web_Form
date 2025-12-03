# helpers/openai_client.py
import os
import logging
import backoff
import openai
import traceback

logger = logging.getLogger("openai_client")
logger.setLevel(logging.INFO)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _backoff_handler(details):
    logger.warning("Retrying OpenAI request: %s (tries=%s)", details.get("exception"), details.get("tries"))

def _get_openai_version():
    ver = getattr(openai, "__version__", None)
    if ver is None:
        return None
    # Try to normalize "1.2.3" -> 1.2
    try:
        parts = ver.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor, ver)
    except Exception:
        return (None, None, ver)

def _extract_text_from_response(resp):
    """
    Robustly extract assistant text from various response shapes.
    """
    try:
        # New-style: resp.choices[0].message.content
        return resp.choices[0].message.content
    except Exception:
        pass
    try:
        # Dict-like new-style
        return resp["choices"][0]["message"]["content"]
    except Exception:
        pass
    try:
        # Some older shapes: resp.choices[0].message["content"]
        return resp.choices[0].message["content"]
    except Exception:
        pass
    try:
        # Legacy text field
        return resp.choices[0].text
    except Exception:
        pass
    try:
        # dict-like legacy
        return resp["choices"][0]["text"]
    except Exception:
        pass
    # fallback to string
    return str(resp)


@backoff.on_exception(backoff.expo, (Exception,), max_tries=5, on_backoff=_backoff_handler)
def chat_completion(messages, model=None, temperature=0.0, max_tokens=1500):
    """
    Unified chat completion wrapper:
      - Prefer the new OpenAI client (openai>=1.0): OpenAI().chat.completions.create(...)
      - Only attempt legacy openai.ChatCompletion.create if installed openai version < 1.0
    Returns the assistant reply string (first choice) or raises RuntimeError with actionable advice.
    """
    model = model or OPENAI_MODEL
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno.")

    # Log a compact diagnostic (no secrets)
    openai_ver = _get_openai_version()
    logger.info("OpenAI chat_completion called (model=%s) messages=%d openai_version=%s", model, len(messages), openai_ver)

    # If we can detect version >= 1.0, prefer new API and do NOT call legacy shim (which raises APIRemovedInV1).
    try:
        major, minor, ver_str = (openai_ver if isinstance(openai_ver, tuple) else (None, None, openai_ver))
    except Exception:
        major = minor = ver_str = None

    # Try new API when available / recommended
    tried_new = False
    tried_legacy = False
    if major is not None and major >= 1:
        # Expect new-style client available
        try:
            tried_new = True
            # Prefer explicit import to avoid attribute lookup surprises
            try:
                from openai import OpenAI as OpenAIClient
            except Exception:
                # fallback to attribute on module
                OpenAIClient = getattr(openai, "OpenAI", None)

            if OpenAIClient is None:
                raise ImportError("Clase OpenAI no encontrada en el paquete 'openai' instalado.")

            client = OpenAIClient(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = _extract_text_from_response(resp)
            logger.info("OpenAI (v1+) response length=%d", len(text) if text else 0)
            return text
        except Exception as e_new:
            logger.warning("Error usando OpenAI v1+ client: %s", e_new)
            logger.debug("Traceback new-api:\n%s", traceback.format_exc())
            # If v1 exists but failed, fail clearly (avoid attempting legacy which will raise APIRemovedInV1)
            raise RuntimeError(
                "Fallo al usar la API nueva de OpenAI (openai>=1.0). "
                "Revisa que la versión del paquete 'openai' instalada y la configuración del entorno sean compatibles con OpenAI v1+. "
                "En CI, asegúrate de instalar 'openai>=1.0.0' e incluir OPENAI_API_KEY en los secrets."
            ) from e_new

    # If we reach here, either version not detected or version <1 → try legacy:
    try:
        tried_legacy = True
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = _extract_text_from_response(resp)
        logger.info("OpenAI legacy response length=%d", len(text) if text else 0)
        return text
    except Exception as e_legacy:
        logger.warning("Legacy ChatCompletion failed: %s", e_legacy)
        logger.debug("Traceback legacy-api:\n%s", traceback.format_exc())

    # If both attempts failed, raise clear actionable error
    msg_lines = [
        "Error llamando OpenAI (v1+ y legacy fallaron).",
        "Diagnóstico:",
        f"  - openai.__version__ = {openai_ver}",
        "Recomendaciones:",
        "  - En GitHub Actions / CI: asegúrate de instalar la versión moderna del SDK: `pip install \"openai>=1.0.0\"`",
        "  - Si no puedes actualizar ahora, alternativa temporal: pinnear `openai==0.28.0` (legacy) en el CI, pero esto es temporal.",
        "  - Verifica que OPENAI_API_KEY esté correctamente seteada en los secrets/envars.",
        "  - Revisa OPENAI_MODEL: usa un modelo válido disponible para tu API key (ej. gpt-4o-mini, gpt-5 si tienes acceso)."
    ]
    logger.error("\n".join(msg_lines))
    raise RuntimeError("\n".join(msg_lines))
