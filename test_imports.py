# test_imports.py
import sys
sys.path.append('.')
from helpers import process_txt, assemblyai, enviar_correo, gcs, queue, sheets, generar_quiz, locks, utils
print("IMPORTS OK")
print("process_txt:", hasattr(process_txt, 'procesar_txt_con_chatgpt_block'))
print("assemblyai:", hasattr(assemblyai, 'transcribir_audio'))
print("mail:", hasattr(enviar_correo, 'enviar_correo_con_adjuntos'))
print("generar_quiz:", hasattr(generar_quiz, 'generar_quiz_from_text'))
print("locks:", hasattr(locks, 'acquire_lock'))
print("utils:", hasattr(utils, 'retry'))
