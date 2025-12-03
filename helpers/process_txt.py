# helpers/process_txt.py
import os
import time
import typing
import openai
import backoff  # opcional: añade a requirements.txt si no está
import logging

logger = logging.getLogger("process_txt")
logger.setLevel(logging.INFO)

# Prompt maestro (usa exactamente el que diste)
PROMPT_MAESTRO = """Eres un asistente experto en redacción académica y edición técnica. Tu tarea es transformar una transcripción de clase universitaria en un texto con estilo de libro profesional, manteniendo de forma exhaustiva todo el contenido relevante del original, sin resumir ni omitir detalles.

INSTRUCCIONES CLAVE (ESTRATEGIA RIGUROSA):

NO RESUMAS. NO REDUZCAS. NO AGRUPES ideas que estaban separadas.

Reescribe todo el contenido con mejor redacción, pero sin acortar ni eliminar nada útil.

Asegúrate de que todas las explicaciones, ejemplos, aclaraciones, datos técnicos, descripciones y frases relevantes del docente se conserven.

No introduzcas interpretaciones personales ni agregues información externa.

Si aparecen fórmulas (matemáticas, físicas, químicas o biomédicas), escríbelas siempre en formato de texto editable y compatible con Word/Docs (MathType, Unicode para subíndices/superíndices). Nunca como imágenes.

OBJETIVO:
La reescritura debe mantener la extensión y densidad de contenido del original, con redacción mejorada, sin recortes ni simplificaciones. Aunque un fragmento parezca redundante o largo, si contiene contenido valioso, debe conservarse.

SI ENCUENTRAS:

Reiteraciones similares pero con palabras distintas → conserva ambas.

Aclaraciones repetidas pero útiles → mantenlas.

Explicaciones largas → divídelas en párrafos claros, sin omitir ninguna oración.

Listas de ítems, mecanismos, efectos, características → conviértelas en listas con viñetas o numeración, sin eliminar elementos.

ESTILO Y FORMATO:

Redacta en tercera persona, con lenguaje técnico, fluido y formal.

Usa títulos temáticos jerárquicos:

para secciones principales.
para subtemas dentro de cada sección.

Redacta como si fuera un capítulo completo de libro universitario de medicina, derecho, biología u otra carrera técnica.

Si un párrafo es muy largo, sepáralo por lógica temática o discursiva, sin omitir ninguna oración.

ÉNFASIS EN EL TEXTO:

En cada párrafo, identifica y resalta en negritas las partes más importantes del contenido.

En las listas, coloca en negritas la categoría o palabra previa a los dos puntos.
Ejemplo:

Causas de diarrea:

Infecciones

Enfermedad inflamatoria intestinal (EII)

CONTEXTO:
Este fragmento forma parte de un documento mayor, por lo tanto:

No incluyas introducciones, conclusiones ni frases de cierre.

Mantén la continuidad textual como si el lector ya viniera leyendo desde una sección anterior.

NOTA FINAL:
Debes transformar la redacción, no el contenido. Mejora la estructura, claridad y estilo, sin reducir la extensión informativa.

FORMATO DE ENCABEZADOS (ESTRICTO):

Usa únicamente ## para secciones principales del contenido.

Usa ### para subtemas o divisiones dentro de una sección.

No utilices #### ni niveles inferiores.

Si deseas incluir un ejemplo, escribe “Ejemplo:” como parte del cuerpo del párrafo, o destácalo en cursiva si corresponde, pero no lo marques como encabezado.
"""

# Config de OpenAI: usa env var OPENAI_API_KEY y OPENAI_MODEL (por ejemplo "gpt-5" o "gpt-4o-mini").
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")  # ajusta en Railway si quieres otro modelo

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

def _build_messages_for_block(block_text: str, order_id: typing.Optional[str], block_index: int, total_blocks: typing.Optional[int]=None):
    """
    Construye el array 'messages' para la API chat/completions.
    """
    # system message: prompt maestro completo
    system_msg = PROMPT_MAESTRO

    # user message: instrucciones específicas para este bloque
    info = f"Procesa el BLOQUE {block_index}"
    if total_blocks:
        info += f" de {total_blocks}"
    if order_id:
        info += f" — order_id: {order_id}"
    info += "."

    # Pedimos salida en Markdown con encabezados ## y ### exclusivamente,
    # sin introducción ni conclusión, y solo el texto transformado.
    user_instruction = (
        info + "\n\n"
        "INSTRUCCIONES DE SALIDA:\n"
        "- Devuelve **solo** el texto transformado en **Markdown**.\n"
        "- Usa **##** para secciones principales y **###** para subtemas exclusivamente.\n"
        "- Resalta partes clave en **negritas** (ésta será la señal para el DOCX).\n"
        "- No incluyas títulos adicionales (p. ej. 'Introducción' o 'Conclusión').\n"
        "- Conserva la extensión informativa: NO RESUMAS, NO OMITEs.\n"
        "- Formato de fórmulas: deja en texto (Unicode, subíndices con _ , superíndices con ^) — no imágenes.\n"
        "- Si el bloque incluye listas o enumeraciones, conviértelas en listas con viñetas o numeradas.\n\n"
        "Texto original a procesar (delimitado por <<< >>>):\n\n"
        f"<<<\n{block_text}\n>>>\n\n"
        "RESPONDE con el texto procesado en Markdown, nada más."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_instruction}
    ]
    return messages

# backoff strategy for transient errors
def backoff_handler(details):
    logger.warning(f"Retrying after error: {details['exception']}, attempt {details['tries']}")

@backoff.on_exception(backoff.expo, (openai.error.RateLimitError, openai.error.APIError, openai.error.Timeout), max_tries=5, on_backoff=backoff_handler)
def call_openai_chat(messages, model=OPENAI_MODEL, temperature=0.1, max_tokens=16000):
    """
    Llama a la API de OpenAI (ChatCompletion). Usa reintentos para RateLimit y transient errors.
    Ajusta "max_tokens" si tu modelo lo permite. Si usas 'gpt-5' con mayor contexto, sube el max.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY no configurada en variables de entorno.")

    # Intentar la llamada (sincrónica)
    logger.info(f"[OPENAI] Llamando modelo={model} con temperature={temperature}")
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # tomar el primer choice
    text = response.choices[0].message["content"]
    return text

def procesar_txt_con_chatgpt_block(block_text: str, order_id: typing.Optional[str]=None, block_index: int=1, total_blocks: typing.Optional[int]=None, model: typing.Optional[str]=None):
    """
    Función pública que procesa un bloque de texto y devuelve el texto transformado por ChatGPT.
    - block_text: texto (string) del bloque (aprox 3000 palabras).
    - order_id: id de orden para logs/seguimiento.
    - block_index: índice del bloque (1-based).
    - total_blocks: opcional: número total de bloques.
    - model: opcional: nombre del modelo; si no se pasa, usa OPENAI_MODEL env var.
    """
    model_to_use = model or OPENAI_MODEL or "gpt-5"

    logger.info(f"[PROCESS_TXT] Procesando bloque {block_index} order_id={order_id} (modelo={model_to_use})")
    try:
        messages = _build_messages_for_block(block_text, order_id, block_index, total_blocks)
        # elegir max_tokens prudente; si el bloque es grande la respuesta puede ser grande también.
        # Ajusta este valor según el modelo y límites:
        max_tokens = 16000  # ajustar según modelo / limits
        result = call_openai_chat(messages, model=model_to_use, temperature=0.12, max_tokens=max_tokens)

        # limpiar/normalizar resultado (por ejemplo, eliminar espacios al inicio)
        processed = result.strip()
        logger.info(f"[PROCESS_TXT] Bloque {block_index} procesado, longitud {len(processed)} chars")
        return processed

    except Exception as e:
        logger.error(f"[PROCESS_TXT][ERROR] al procesar bloque {block_index}: {e}")
        logger.exception(e)
        # En caso de error, devolver un fallback que preserve el texto original (con marca de error)
        fallback = (
            f"## ERROR: fallo en el procesamiento automático del bloque {block_index}\n\n"
            "El contenido original se incluye a continuación sin cambios.\n\n"
            f"{block_text[:10000]}\n\n"  # limitar tamaño
        )
        return fallback
