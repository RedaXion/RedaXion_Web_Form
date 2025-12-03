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
    try:
        parts = ver.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor, ver)
    except Exception:
        return (None, None, ver)

def _extract_text_from_response(resp):
    try:
        return resp.choices[0].message.content
    except Exception:
        pass
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        pass
    try:
        return resp.choices[0].message["content"]
    except Exception:
        pass
    try:
        return resp.choices[0].text
    except Exception:
        pass
    try:
        return resp["choices"][0]["text"]
    except Exception:
        pass
    return str(resp)

def _is_badrequest_exc(e):
    # Try to detect new-style BadRequest-like messages
    try:
        msg = ""
        # openai exceptions sometimes have .args[0] as dict or string
        if hasattr(e, "args") and e.args:
            msg = str(e.args[0])
        else:
            msg = str(e)
        return "Unsupported" in msg or "unsupported" in msg or "invalid_request_error" in msg or "unsupported_parameter" in msg or "unsupported_value" in msg
    except Exception:
        return False

@backoff.on_exception(backoff.expo, (Exception,), max_tries=5, on_backoff=_backoff_handler)
def chat_completion(messages, model=None, temperature=None, max_tokens=None):
    """
    Robust wrapper for OpenAI chat completions:
    - Prefer API v1 (OpenAI().chat.completions.create)
    - Map max_tokens -> max_completion_tokens for v1
    - If v1 returns unsupported-parameter or unsupported-value errors, retry:
        1) remove/rename offending params (max_completion_tokens / temperature)
        2) finally call with only model+messages
    - If v1 is not available or all retries fail, attempt legacy openai.ChatCompletion.create.
    """
    model = model or OPENAI_MODEL
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno.")

    openai_ver = _get_openai_version()
    logger.info("OpenAI chat_completion called (model=%s) messages=%d openai_version=%s", model, len(messages), openai_ver)

    # Detect major version
    try:
        major, minor, ver_str = (openai_ver if isinstance(openai_ver, tuple) else (None, None, openai_ver))
    except Exception:
        major = minor = ver_str = None

    # Helper to attempt new API call with a kwargs dict and sensible logging
    def _try_new_api_call(kwargs):
        try:
            try:
                from openai import OpenAI as OpenAIClient
            except Exception:
                OpenAIClient = getattr(openai, "OpenAI", None)
            if OpenAIClient is None:
                raise ImportError("Clase OpenAI no encontrada en el paquete 'openai' instalado.")
            client = OpenAIClient(api_key=OPENAI_API_KEY)
            logger.debug("Calling OpenAI v1+ with keys: %s", list(kwargs.keys()))
            resp = client.chat.completions.create(**kwargs)
            text = _extract_text_from_response(resp)
            logger.info("OpenAI (v1+) response length=%d", len(text) if text else 0)
            return text
        except Exception as e:
            # re-raise for outer handling
            raise e

    # Try new API when version >= 1
    if major is not None and major >= 1:
        # Build initial kwargs (map max_tokens -> max_completion_tokens)
        kwargs = {"model": model, "messages": messages}
        if temperature is not None:
            # pass temperature only if provided (we may remove it on retry)
            kwargs["temperature"] = float(temperature)
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = int(max_tokens)

        # First attempt: try with full kwargs
        try:
            return _try_new_api_call(kwargs)
        except Exception as e_new:
            logger.warning("Error usando OpenAI v1+ client (first attempt): %s", e_new)
            logger.debug("Traceback new-api first:\n%s", traceback.format_exc())

            # If it's a BadRequest about unsupported param/value, try relaxed retries:
            if _is_badrequest_exc(e_new):
                msg = str(e_new)
                # Retry 1: if message mentions 'max_tokens' or 'max_completion_tokens' or 'unsupported_parameter'
                if "max_tokens" in msg or "max_completion_tokens" in msg or "unsupported_parameter" in msg:
                    logger.info("Retrying without max_completion_tokens due to unsupported param.")
                    kwargs2 = {k: v for k, v in kwargs.items() if k != "max_completion_tokens"}
                    try:
                        return _try_new_api_call(kwargs2)
                    except Exception as e2:
                        logger.warning("Retry without max_completion_tokens failed: %s", e2)
                        logger.debug("Traceback retry1:\n%s", traceback.format_exc())
                        # continue to next retry

                # Retry 2: if message mentions 'temperature' or 'unsupported_value' for temperature
                if "temperature" in msg or "unsupported_value" in msg:
                    logger.info("Retrying without temperature due to unsupported value.")
                    kwargs3 = {k: v for k, v in kwargs.items() if k != "temperature"}
                    # also remove max_completion_tokens if still present (safe)
                    kwargs3.pop("max_completion_tokens", None)
                    try:
                        return _try_new_api_call(kwargs3)
                    except Exception as e3:
                        logger.warning("Retry without temperature failed: %s", e3)
                        logger.debug("Traceback retry2:\n%s", traceback.format_exc())
                        # continue to final minimal attempt

                # Final retry: minimal call (only model + messages)
                logger.info("Final retry: calling v1 API with minimal kwargs (model + messages) due to repeated unsupported params.")
                kwargs_min = {"model": model, "messages": messages}
                try:
                    return _try_new_api_call(kwargs_min)
                except Exception as e_min:
                    logger.warning("Final minimal retry on v1 failed: %s", e_min)
                    logger.debug("Traceback minimal retry:\n%s", traceback.format_exc())
                    # fall through to legacy fallback
            # If not a BadRequest-like error or retries failed, raise a clear error
            logger.error("Fallo al usar la API nueva de OpenAI (openai>=1.0). Mensaje interno: %s", e_new)
            raise RuntimeError(
                "Fallo al usar la API nueva de OpenAI (openai>=1.0). Revisa la versión del paquete 'openai', la conectividad y que OPENAI_API_KEY esté correcta. Mensaje interno: "
                + str(e_new)
            ) from e_new

    # Legacy fallback (version < 1 or if v1 attempts ultimately failed)
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=(temperature if temperature is not None else 0.0),
            max_tokens=(max_tokens if max_tokens is not None else 1500),
        )
        text = _extract_text_from_response(resp)
        logger.info("OpenAI legacy response length=%d", len(text) if text else 0)
        return text
    except Exception as e_legacy:
        logger.warning("Legacy ChatCompletion failed: %s", e_legacy)
        logger.debug("Traceback legacy-api:\n%s", traceback.format_exc())

    msg_lines = [
        "Error llamando OpenAI (v1+ y legacy fallaron).",
        f"  - openai.__version__ = {openai_ver}",
        "Recomendaciones:",
        "  - En CI: instala 'openai>=1.0.0' (`pip install \"openai>=1.0.0\"`).",
        "  - Si no puedes actualizar ahora, alternativa temporal: pinnear 'openai==0.28.0' (legacy), pero no recomendado a largo plazo.",
        "  - Verifica OPENAI_API_KEY en secrets/envs y que el modelo declarado exista y sea accesible.",
    ]
    logger.error("\n".join(msg_lines))
    raise RuntimeError("\n".join(msg_lines))
