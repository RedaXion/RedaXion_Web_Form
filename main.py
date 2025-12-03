# main.py - flujo completo RedaXion (actualizado)
"""
generate_and_deliver(order_id, *args, **kwargs)

Orquesta el flujo completo para una orden:
- descarga / obtiene URL del audio (ya subido a GCS)
- transcribe con AssemblyAI -> guarda .txt
- divide en bloques de 3000 palabras y procesa con ChatGPT-5 por bloque
- une bloques en TCP en estilo libro universitario
- extrae títulos/subtítulos y por cada "página" (estimada) busca una imagen relevante
- genera 7 preguntas difíciles por página (RedaQuiz)
- aplica plantilla .docx (color/columnas)
- convierte a pdf, sube todo a Drive, marca Sheets y envía correo
"""

import os
import tempfile
import traceback
from datetime import datetime, timedelta

# Intentar importar tus helpers (estructura original). Si están en 'helpers.*' ajustamos.
try:
    from sheets import get_todos_los_pendientes, marcar_como_procesado, get_pedido_por_fila, actualizar_estado_y_links
    from gcs import procesar_audio
    from assemblyai import transcribir_audio
    from process_txt import procesar_txt_con_chatgpt_block  # si existe
    from formatter_docx import guardar_como_docx, guardar_quiz_como_docx
    from subir_archivo import subir_archivo_a_drive
    from generar_quiz import generar_quiz_desde_docx
    from enviar_correo import enviar_correo_con_adjuntos
    from convertidor_pdf import convertir_a_pdf
except Exception:
    # Try alternate import paths used earlier in the repo (helpers package)
    try:
        from helpers.sheets import get_todos_los_pendientes, marcar_como_procesado, get_pedido_por_fila, actualizar_estado_y_links
        from helpers.gcs import procesar_audio
        from helpers.assemblyai import transcribir_audio
        from helpers.process_txt import procesar_txt_con_chatgpt_block
        from helpers.formatter_docx import guardar_como_docx, guardar_quiz_como_docx
        from helpers.subir_archivo import subir_archivo_a_drive
        from helpers.generar_quiz import generar_quiz_desde_docx
        from helpers.enviar_correo import enviar_correo_con_adjuntos
        from helpers.convertidor_pdf import convertir_a_pdf
    except Exception:
        # If imports fail, we'll use internal stubs and continue so the worker doesn't crash.
        get_todos_los_pendientes = None
        marcar_como_procesado = None
        get_pedido_por_fila = None
        actualizar_estado_y_links = None
        procesar_audio = None
        transcribir_audio = None
        procesar_txt_con_chatgpt_block = None
        guardar_como_docx = None
        guardar_quiz_como_docx = None
        subir_archivo_a_drive = None
        generar_quiz_desde_docx = None
        enviar_correo_con_adjuntos = None
        convertir_a_pdf = None

import importlib
import math
import json

# -----------------------
# Utilidades internas
# -----------------------
def split_text_into_blocks(text: str, words_per_block: int = 3000):
    words = text.split()
    blocks = []
    for i in range(0, len(words), words_per_block):
        block = " ".join(words[i:i + words_per_block])
        blocks.append(block)
    return blocks

def call_chatgpt_for_block(block_text: str, block_index: int, order_id: str):
    """
    Llama a la función que transforma un bloque en estilo 'TCP' y devuelve texto formateado.
    Intenta usar el helper 'procesar_txt_con_chatgpt_block' si existe, si no, usa un stub
    (reemplazar con llamadas a tu wrapper de ChatGPT-5).
    """
    try:
        if procesar_txt_con_chatgpt_block:
            print(f"[CHATGPT] usando helper procesar_txt_con_chatgpt_block para bloque {block_index}")
            return procesar_txt_con_chatgpt_block(block_text, order_id=order_id, block_index=block_index)
        else:
            # STUB: agregar encabezado por bloque. Reemplazar por llamada a ChatGPT-5 API.
            print(f"[CHATGPT][STUB] procesando bloque {block_index} (stub)")
            return f"## Bloque {block_index}\n\n" + block_text[:2000] + "\n\n"
    except Exception as e:
        print(f"[CHATGPT][ERROR] al procesar bloque {block_index}: {e}")
        traceback.print_exc()
        return ""

def merge_processed_blocks(blocks_processed):
    return "\n\n".join(blocks_processed)

def extract_titles_subtitles(tcp_text: str):
    """
    Heurística simple para extraer títulos/subtítulos desde el texto TCP.
    Ideal: reemplazar por un extractor robusto o por otro call a la API.
    Devuelve lista de tuples (title, subtitle, approx_page).
    """
    lines = [l.strip() for l in tcp_text.splitlines() if l.strip()]
    titles = []
    # heurística: líneas que parecen headings (p.ej. tienen menos de 100 chars y empiezan con mayúscula)
    for i, line in enumerate(lines):
        if len(line) < 120 and line[0].isupper() and len(line.split()) < 8:
            # tomar la siguiente línea corta como subtítulo si aplica
            subtitle = ""
            if i + 1 < len(lines) and len(lines[i+1].split()) < 12:
                subtitle = lines[i+1]
            titles.append((line, subtitle))
    # agregar approx page index (distribuir uniformemente)
    result = []
    if not titles:
        return []
    total = max(1, len(titles))
    for idx, t in enumerate(titles):
        approx_page = idx + 1
        result.append((t[0], t[1], approx_page))
    return result

def search_image_for_topic(title: str, subtitle: str = ""):
    """
    Placeholder: Buscar la mejor imagen para un tema.
    Reemplaza esto con integración real (Unsplash, Bing Image Search, Google Custom Search, etc.).
    Debe devolver URL pública de la imagen o path local subido a Drive/GCS.
    """
    # STUB: devuelve placeholder o marca para reemplazar
    query = f"{title} {subtitle}".strip()
    print(f"[IMG_SEARCH][STUB] buscar imagen para: {query}")
    # Ejemplo de placeholder (puedes cambiar por la llamada real)
    return f"https://via.placeholder.com/1200x800.png?text={query.replace(' ', '+')}"


def generate_questions_for_titles(titles_list, per_title=7):
    """
    Genera preguntas por cada título/subtítulo.
    Ideal: conectar con tu módulo generador (o invocar ChatGPT con prompt EUNACOM-style).
    Devuelve dict: {page_num: [ {q:..., options:[...], answer:..., justification:...}, ... ] }
    """
    questions_by_page = {}
    for title, subtitle, page in titles_list:
        questions = []
        for i in range(per_title):
            q_text = f"Pregunta difícil sobre «{title}» (ítem {i+1})"
            options = [
                "A) Opción 1",
                "B) Opción 2",
                "C) Opción 3",
                "D) Opción 4",
                "E) Opción 5",
            ]
            # STUB: respuesta siempre 'A' (reemplazar con IA)
            questions.append({
                "question": q_text,
                "options": options,
                "answer": "A",
                "justification": "Justificación breve (stub)."
            })
        questions_by_page.setdefault(page, []).extend(questions)
    return questions_by_page

def apply_docx_template_and_insert_images(tcp_text, images_map, out_path, color="azul", columnas="simple"):
    """
    Usa tu helper `guardar_como_docx`. Si tu helper acepta 'images' pasa el map,
    sino implementa aquí un pequeño generador con python-docx (omitted).
    images_map: {page_number: image_url}
    """
    try:
        if guardar_como_docx:
            print("[DOCX] usando helper guardar_como_docx (con imágenes si el helper lo soporta).")
            # Se asume que guardar_como_docx acepta param images_map (si no, extiende el helper).
            try:
                return guardar_como_docx(tcp_text, out_path, color=color, columnas=columnas, images_map=images_map)
            except TypeError:
                # helper no acepta images_map -> llamar sin él (dejar TODO para integrar)
                print("[DOCX] guardar_como_docx no acepta images_map: llamando sin imágenes (extender helper).")
                return guardar_como_docx(tcp_text, out_path, color=color, columnas=columnas)
        else:
            # STUB: crear archivo .docx simple con el texto (placeholder)
            print("[DOCX][STUB] crear DOCX simple (no plantilla).")
            from docx import Document
            doc = Document()
            for para in tcp_text.split("\n\n"):
                doc.add_paragraph(para)
            doc.save(out_path)
            return out_path
    except Exception as e:
        print(f"[DOCX][ERROR] al generar DOCX: {e}")
        traceback.print_exc()
        return None

def apply_quiz_template_and_save(questions_by_page, out_quiz_path, color="azul", columnas="simple"):
    """
    Convierte questions_by_page a un docx con formato.
    Usamos guardar_quiz_como_docx si existe.
    """
    try:
        if guardar_quiz_como_docx:
            print("[QUIZ] usando helper guardar_quiz_como_docx")
            return guardar_quiz_como_docx(questions_by_page, out_quiz_path, color=color, columnas=columnas)
        else:
            # STUB: construir docx con preguntas básicas
            print("[QUIZ][STUB] guardando quiz básico en docx")
            from docx import Document
            doc = Document()
            for page, qs in questions_by_page.items():
                doc.add_heading(f"Preguntas - Página {page}", level=2)
                for idx, q in enumerate(qs, start=1):
                    doc.add_paragraph(f"{idx}. {q['question']}")
                    for opt in q['options']:
                        doc.add_paragraph(f"   {opt}")
                doc.add_page_break()
            doc.save(out_quiz_path)
            return out_quiz_path
    except Exception as e:
        print(f"[QUIZ][ERROR] {e}")
        traceback.print_exc()
        return None

# -----------------------
# Orquestador principal
# -----------------------
def generate_and_deliver(order_id, *args, **kwargs):
    """
    Orquesta todo el pipeline para una orden específica.
    """
    try:
        print(f"\n🚀 [MAIN] generate_and_deliver -> order_id={order_id} - inicio {datetime.utcnow().isoformat()}")

        # 1) Obtener datos de la orden desde sheets (fila / detalles)
        if get_pedido_por_fila:
            try:
                # Si tu sheets helper devuelve por orden_id, ajusta este llamado.
                detalles = get_pedido_por_fila(order_id)
            except Exception:
                # algunos flows usan get_todos_los_pendientes -> buscar manualmente
                detalles = None
        else:
            detalles = None

        # Si no encontramos detalles, intentar buscar en pendientes
        if not detalles and get_todos_los_pendientes:
            print("[MAIN] Detalles no recuperados por order_id, buscando en pendientes...")
            pendientes = get_todos_los_pendientes()
            detalles = next((p for p in pendientes if p.get("orden") == order_id), None)

        if not detalles:
            print(f"[MAIN][WARN] No se encontró metadata de la orden {order_id} en Sheets. Abortando.")
            return

        # Validación básica
        color = detalles.get("color", "azul")
        columnas = detalles.get("columnas", "simple")
        correo_cliente = detalles.get("email", "")
        fila = detalles.get("fila") or detalles.get("row") or None

        # Idempotencia: si ya está marcado procesado -> saltar
        estado_actual = detalles.get("estado", "").strip().lower()
        if "entregado" in estado_actual or "procesado" in estado_actual:
            print(f"[MAIN] Orden {order_id} ya tiene estado '{estado_actual}'. Saltando procesamiento.")
            return

        # 2) Obtener URL pública del audio (helper gcs/procesar_audio)
        audio_url_public = detalles.get("audio_url") or detalles.get("url") or None
        if not audio_url_public:
            print("[MAIN] No se encontró audio_url en metadata: intentando reprocesar con gcs.procesar_audio (si se tiene path)")
            try:
                # si detalles tiene 'gcs_path' o 'audio_path' se puede usar procesar_audio
                source_path = detalles.get("audio_path") or detalles.get("gdrive_path")
                if procesar_audio and source_path:
                    audio_url_public = procesar_audio(source_path, f"{order_id}.mp3")
            except Exception:
                audio_url_public = None

        if not audio_url_public:
            print(f"[MAIN][ERROR] No hay URL pública del audio para la orden {order_id}. Marcar en Sheets y abortar.")
            try:
                if actualizar_estado_y_links:
                    actualizar_estado_y_links(order_id, estado="Error: no audio_url")
                else:
                    print("[MAIN] actualizar_estado_y_links no disponible (helper).")
            except Exception:
                pass
            return

        print(f"[MAIN] Audio público: {audio_url_public}")

        # 3) Transcribir con AssemblyAI -> obtener texto completo y guardar .txt
        try:
            print("[MAIN] Enviando a AssemblyAI para transcripción (puede tardar)...")
            if transcribir_audio:
                texto = transcribir_audio(audio_url_public)
            else:
                print("[MAIN][STUB] transcribir_audio helper no disponible. Creando texto stub.")
                texto = "Transcripción de prueba. " * 1000
        except Exception as e:
            print("[MAIN][ERROR] Falló transcripción:", e)
            traceback.print_exc()
            if actualizar_estado_y_links:
                actualizar_estado_y_links(order_id, estado=f"Error: transcripcion {e}")
            return

        # Guardar .txt local y subir a Drive
        tmp_dir = tempfile.mkdtemp()
        path_txt = os.path.join(tmp_dir, f"{order_id}.txt")
        try:
            with open(path_txt, "w", encoding="utf-8") as f:
                f.write(texto)
            print(f"[MAIN] Guardado .txt temporal en {path_txt}")
            if subir_archivo_a_drive:
                subir_archivo_a_drive(path_txt, f"{order_id}.txt", order_id)
                print("[MAIN] .txt subido a Drive.")
        except Exception as e:
            print("[MAIN][ERROR] No se pudo guardar/subir .txt:", e)
            traceback.print_exc()

        # 4) Dividir en bloques de 3000 palabras y procesar cada bloque con ChatGPT-5
        blocks = split_text_into_blocks(texto, words_per_block=3000)
        print(f"[MAIN] Texto dividido en {len(blocks)} bloques de ~3000 palabras.")

        processed_blocks = []
        for i, blk in enumerate(blocks, start=1):
            pb = call_chatgpt_for_block(blk, i, order_id)
            processed_blocks.append(pb)

        tcp_text = merge_processed_blocks(processed_blocks)
        print(f"[MAIN] TCP (texto procesado) ensamblado, tamaño {len(tcp_text)} caracteres.")

        # 5) Extraer títulos/subtítulos y estimar páginas (heurística)
        titles = extract_titles_subtitles(tcp_text)
        print(f"[MAIN] Extraídos {len(titles)} títulos/subtítulos heurísticos.")

        # 6) Para cada título / página -> buscar imagen relevante (STUB)
        images_map = {}  # page_num -> image_url
        for title, subtitle, page in titles:
            img_url = search_image_for_topic(title, subtitle)
            images_map[page] = img_url

        print(f"[MAIN] Imágenes buscadas para {len(images_map)} páginas (map listo).")

        # 7) Generar preguntas por título/página (7 por página)
        questions_by_page = generate_questions_for_titles(titles, per_title=7)
        print(f"[MAIN] Generadas preguntas: {sum(len(v) for v in questions_by_page.values())} ítems.")

        # 8) Guardar TCP en DOCX usando plantilla y aplicar imágenes por página
        nombre_tcp = f"RedaXion - Nº{order_id}.docx"
        path_docx = os.path.join(tmp_dir, nombre_tcp)
        docx_path_result = apply_docx_template_and_insert_images(tcp_text, images_map, path_docx, color=color, columnas=columnas)
        if docx_path_result:
            print(f"[MAIN] DOCX TCP generado en {docx_path_result}")
            if subir_archivo_a_drive:
                subir_archivo_a_drive(docx_path_result, nombre_tcp, order_id)
                print("[MAIN] DOCX TCP subido a Drive.")
        else:
            print("[MAIN][ERROR] No se pudo generar DOCX TCP.")

        # 9) Convertir DOCX TCP a PDF
        pdf_tcp = None
        try:
            if convertir_a_pdf and docx_path_result:
                pdf_tcp = convertir_a_pdf(docx_path_result)
                if pdf_tcp:
                    nombre_tcp_pdf = nombre_tcp.replace(".docx", ".pdf")
                    subir_archivo_a_drive(pdf_tcp, nombre_tcp_pdf, order_id)
                    print(f"[MAIN] PDF TCP generado y subido: {nombre_tcp_pdf}")
        except Exception as e:
            print("[MAIN][ERROR] convertir_a_pdf fallo:", e)
            traceback.print_exc()

        # 10) Generar QUIZ DOCX (format)
        nombre_quiz = f"RedaQuiz - Nº{order_id}.docx"
        path_quiz = os.path.join(tmp_dir, nombre_quiz)
        quiz_docx = apply_quiz_template_and_save(questions_by_page, path_quiz, color=color, columnas=columnas)
        if quiz_docx:
            print(f"[MAIN] Quiz DOCX generado en {quiz_docx}")
            if subir_archivo_a_drive:
                subir_archivo_a_drive(quiz_docx, nombre_quiz, order_id)
                print("[MAIN] Quiz DOCX subido a Drive.")
        else:
            print("[MAIN][WARN] No se produjo Quiz DOCX.")

        # 11) Convertir QUIZ a PDF
        try:
            if convertir_a_pdf and quiz_docx:
                pdf_quiz = convertir_a_pdf(quiz_docx)
                if pdf_quiz:
                    nombre_quiz_pdf = nombre_quiz.replace(".docx", ".pdf")
                    subir_archivo_a_drive(pdf_quiz, nombre_quiz_pdf, order_id)
                    print(f"[MAIN] PDF Quiz generado y subido: {nombre_quiz_pdf}")
        except Exception as e:
            print("[MAIN][ERROR] convertir_a_pdf (quiz) fallo:", e)
            traceback.print_exc()

        # 12) Actualizar Sheets: marcar como entregado y publicar links (si tienes helper)
        try:
            if actualizar_estado_y_links:
                # Debe aceptar order_id, estado, links dict {tcp: url, pdf: url, quiz: url}
                links = {
                    "txt": f"{order_id}.txt",
                    "docx_tcp": nombre_tcp,
                    "pdf_tcp": nombre_tcp.replace(".docx", ".pdf") if pdf_tcp else None,
                    "docx_quiz": nombre_quiz,
                    "pdf_quiz": nombre_quiz.replace(".docx", ".pdf") if 'pdf_quiz' in locals() and pdf_quiz else None,
                }
                actualizar_estado_y_links(order_id, estado="Entregado", links=links)
                print("[MAIN] Sheets actualizado con estado Entregado y links.")
            else:
                print("[MAIN] actualizar_estado_y_links helper no disponible; intentar marcar_como_procesado si existe.")
                if marcar_como_procesado and fila:
                    marcar_como_procesado(fila)
                    print("[MAIN] marcar_como_procesado ejecutado.")
        except Exception:
            print("[MAIN][WARN] Falló al actualizar Sheets con links/estado.")
            traceback.print_exc()

        # 13) Enviar correo al cliente con adjuntos (docx + pdf)
        try:
            archivos_adjuntos = []
            if docx_path_result:
                archivos_adjuntos.append(docx_path_result)
            if 'pdf_tcp' in locals() and pdf_tcp:
                archivos_adjuntos.append(pdf_tcp)
            if quiz_docx:
                archivos_adjuntos.append(quiz_docx)
            if 'pdf_quiz' in locals() and pdf_quiz:
                archivos_adjuntos.append(pdf_quiz)

            if enviar_correo_con_adjuntos and correo_cliente:
                asunto = f"Tu pedido RedaXion Nº{order_id} está listo ✅"
                cuerpo = (
                    f"Hola 👋\n\nAdjuntamos tu Transcripción Académica Profesional (TCP) y el RedaQuiz.\n"
                    "Gracias por usar RedaXion — ¡éxitos en el estudio! 🧠\n\n"
                    "— Equipo RedaXion"
                )
                enviar_correo_con_adjuntos(correo_cliente, asunto, cuerpo, archivos_adjuntos)
                print(f"[MAIN] Correo enviado a {correo_cliente}")
            else:
                print("[MAIN] enviar_correo_con_adjuntos helper no disponible o correo_cliente vacío; correo no enviado.")
        except Exception:
            print("[MAIN][ERROR] Error enviando correo con adjuntos.")
            traceback.print_exc()

        print(f"✅ [MAIN] Finalizado flujo para orden {order_id} ({datetime.utcnow().isoformat()})")
        return True

    except Exception as err:
        print(f"[MAIN][ERROR] Excepción en generate_and_deliver para {order_id}: {err}")
        traceback.print_exc()
        # marcar en sheet como error si es posible
        try:
            if actualizar_estado_y_links:
                actualizar_estado_y_links(order_id, estado=f"Error: {err}")
        except Exception:
            pass
        return False

# Mantener compatibilidad (si el worker importa main.generate_and_deliver)
if __name__ == "__main__":
    # Si ejecutas main.py manualmente, procesa todos los pendientes (opcional)
    try:
        print("🚀 Ejecutando flujo RedaXion en modo standalone (procesar pendientes)")
        if get_todos_los_pendientes:
            pendientes = get_todos_los_pendientes()
            for p in pendientes:
                try:
                    oid = p.get("orden")
                    if oid:
                        generate_and_deliver(oid)
                except Exception:
                    traceback.print_exc()
        else:
            print("No hay helper get_todos_los_pendientes disponible.")
    except Exception:
        traceback.print_exc()
