# run_process_txt.py
from helpers import process_txt
sample = ("Texto de prueba: fisiopatología básica de la hipertensión arterial primaria. "
          "El médico explica causas, diagnóstico y manejo. Include lists, examples.")
try:
    out = process_txt.procesar_txt_con_chatgpt_block(sample, order_id="gh-actions-test", block_index=1, total_blocks=1)
    print("===PROCESS_TXT OUTPUT (inicio)===")
    print(out[:4000])
    print("===PROCESS_TXT OUTPUT (fin)===")
except Exception as e:
    import traceback
    traceback.print_exc()
    raise
