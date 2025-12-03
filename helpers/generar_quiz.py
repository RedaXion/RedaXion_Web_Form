# helpers/generar_quiz.py
import os
import logging
import openai

logger = logging.getLogger("generar_quiz")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

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

def generar_quiz_from_text(content, order_id=None, block_index=None):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    prompt = QUIZ_PROMPT_TEMPLATE.format(content=content)
    logger.info("Generando quiz (order=%s block=%s)", order_id, block_index)
    resp = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[{"role":"system","content":"Generador de preguntas EUNACOM."},
                  {"role":"user","content":prompt}],
        temperature=0.0,
        max_tokens=1500,
    )
    text = resp.choices[0].message["content"].strip()
    # save artifact
    if order_id:
        try:
            with open(f"/tmp/{order_id}_block_{block_index}_quiz.txt", "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception:
            logger.exception("Failed saving quiz artifact")
    return text
