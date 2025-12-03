# main.py - wrapper mínimo para que RQ/worker pueda importar generate_and_deliver
import traceback

def generate_and_deliver(order_id: str):
    # Este stub evita errores. En producción, reemplaza por la función real.
    print(f"[main.generate_and_deliver] llamado con order_id={order_id}")
    # Si tienes la función real (ej: ejecutar_flujo_redaxion en otro módulo), intenta importarla:
    try:
        # ejemplo si tienes main_real.py o otro nombre
        # from main_real import ejecutar_flujo_redaxion
        # ejecutar_flujo_redaxion(order_id)
        pass
    except Exception as e:
        print("No se pudo invocar el flujo real:", e)
        traceback.print_exc()
