# helpers/generar_quiz.py
import os
import logging
from typing import Optional

logger = logging.getLogger("generar_quiz")

# lectura de env (se conservan por trazabilidad, pero el wrapper valida la API key)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_raw_model = os.getenv("OPENAI_MODEL", "").strip()
if not _raw_model or len(_raw_model) < 3:
    OPENAI_MODEL = "gpt-4o-mini"
    logger.warning("OPENAI_MODEL inválido o ausente ('%s'), usando fallback '%s'", _raw_model, OPENAI_MODEL)
else:
    OPENAI_MODEL = _raw_model

# intentamos importar el wrapper centralizado (helpers/openai_client.py)
try:
    from helpers.openai_client import chat_completion
except Exception as e:
    chat_completion = None
    logger.warning("helpers.openai_client.chat_completion no disponible: %s", e)

QUIZ_PROMPT_TEMPLATE = """
Eres un generador de preguntas de examen estilo EUNACOM (alta dificultad).
Recibe el siguiente texto (marcado entre <<< >>>). Para ese texto,
genera exactamente 7 preguntas de opción múltiple (A-E), con UNA respuesta correcta cada una.
Formato:
1) Pregunta
A) ...
B) ...
C) ...
D) ...
E) ...

Al final, después de 10 líneas en blanco, incluye el solucionario con la letra correcta y JUSTIFICACIÓN breve (1-2 líneas).
Texto:
<<<
{content}
>>>
Responde SOLO con las preguntas y el solucionario.
"""

def generar_quiz_from_text(content: str, order_id: Optional[str]=None, block_index: Optional[int]=None, model: Optional[str]=None) -> str:
    """
    Genera un quiz (7 preguntas) usando la función central chat_completion.
    - content: texto a partir del cual generar las preguntas.
    - order_id/block_index: opcionales, para guardar un artifact en /tmp.
    - model: opcional para sobreescribir OPENAI_MODEL.
    Devuelve el texto (preguntas + solucionario).
    """
    model_to_use = model or OPENAI_MODEL

    if chat_completion is None:
        raise RuntimeError(
            "helpers.openai_client.chat_completion no disponible. "
            "Por favor crea helpers/openai_client.py o revisa la instalación del cliente OpenAI."
        )
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno.")

    prompt = QUIZ_PROMPT_TEMPLATE.format(content=content)
    logger.info("Generando quiz (order=%s block=%s model=%s)", order_id, block_index, model_to_use)

    try:
        messages = [
            {"role": "system", "content": "Generador de preguntas EUNACOM."},
            {"role": "user", "content": prompt}
        ]
        text = chat_completion(messages, model=model_to_use, temperature=0.0, max_tokens=1500)
        text = text.strip() if isinstance(text, str) else str(text)

        # guardar artifact si tenemos order_id y block_index
        if order_id and block_index is not None:
            try:
                filename = f"/tmp/{order_id}_block_{block_index}_quiz.txt"
                with open(filename, "w", encoding="utf-8") as fh:
                    fh.write(text)
                logger.info("Quiz guardado en %s", filename)
            except Exception:
                logger.exception("Fallo al guardar el artifact del quiz en /tmp")

        return text

    except Exception as e:
        logger.exception("Error generando quiz: %s", e)
        # En caso de fallo, devolver un mensaje claro en vez de None
        fallback = "ERROR: fallo al generar quiz automáticamente. Revisa logs."
        # intentar guardar fallback si es posible
        if order_id and block_index is not None:
            try:
                filename = f"/tmp/{order_id}_block_{block_index}_quiz_error.txt"
                with open(filename, "w", encoding="utf-8") as fh:
                    fh.write(fallback + "\n\n" + str(e))
                logger.info("Artifact de error guardado en %s", filename)
            except Exception:
                logger.exception("No se pudo guardar artifact de error")
        return fallback
