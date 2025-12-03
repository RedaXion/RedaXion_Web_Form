# helpers/openai_client.py
import os
import logging
import backoff
import openai

logger = logging.getLogger("openai_client")
logger.setLevel(logging.INFO)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

def _backoff_handler(details):
    logger.warning("Retrying OpenAI request: %s (tries=%s)", details.get("exception"), details.get("tries"))

@backoff.on_exception(backoff.expo, (Exception,), max_tries=5, on_backoff=_backoff_handler)
def chat_completion(messages, model=None, temperature=0.0, max_tokens=1500):
    """
    Unified chat completion wrapper that tries:
      1) new OpenAI client (openai>=1.0): OpenAI().chat.completions.create(...)
      2) fallback to legacy client (openai<1.0): openai.ChatCompletion.create(...)
    Returns: the string content of the assistant reply (first choice).
    Raises: RuntimeError with a clear message if OPENAI_API_KEY missing or both attempts fail.
    """
    model = model or OPENAI_MODEL
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno.")

    # Try new client (openai>=1.0)
    try:
        try:
            # Prefer explicit import to avoid surprising AttributeErrors at import-time
            from openai import OpenAI as OpenAIClient
        except Exception:
            # Sometimes OpenAI class can be available under openai.OpenAI
            import openai as _openai_mod
            OpenAIClient = getattr(_openai_mod, "OpenAI", None)

        if OpenAIClient:
            client = OpenAIClient(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            # robust extraction
            try:
                return resp.choices[0].message.content
            except Exception:
                pass
            try:
                return resp["choices"][0]["message"]["content"]
            except Exception:
                pass
            return str(resp)
    except Exception as e_new:
        logger.info("New OpenAI client failed: %s", e_new)

    # Fallback to legacy SDK (openai<1.0)
    try:
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # legacy extraction (several shapes)
        try:
            return resp.choices[0].message["content"]
        except Exception:
            try:
                return resp["choices"][0]["message"]["content"]
            except Exception:
                try:
                    return resp.choices[0].text
                except Exception:
                    return str(resp)
    except Exception as e_old:
        logger.exception("Both new and legacy OpenAI calls failed: %s", e_old)
        raise RuntimeError(
            "Error llamando OpenAI (v1+ y legacy fallaron). Revisa OPENAI_API_KEY, la versión del paquete 'openai' y los permisos del modelo."
        ) from e_old
