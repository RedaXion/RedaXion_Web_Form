# main.py - wrapper robusto para RQ/worker
import importlib
import traceback

def generate_and_deliver(order_id, *args, **kwargs):
    """
    Wrapper que RQ puede importar y ejecutar.
    - Acepta kwargs extras (enqueue_timeout, timeout, etc.) y los ignora
      si la implementación real no los requiere.
    - Intenta detectar e invocar una implementación "real" en varios módulos
      comunes. Si no encuentra nada, actúa como stub y termina limpiamente.
    """
    try:
        print(f"[main.generate_and_deliver] llamado con order_id={order_id}")
        if args:
            print(f"[main] args recibidos: {args}")
        if kwargs:
            print(f"[main] kwargs recibidos: {kwargs}")

        # Lista de candidatos (modulo, función) donde intentar encontrar la implementación real
        candidatos = [
            ("main_real", "ejecutar_flujo_redaxion"),
            ("main_flow", "ejecutar_flujo_redaxion"),
            ("reda_main", "ejecutar_flujo_redaxion"),
            ("main", "ejecutar_flujo_redaxion"),        # por si tu archivo principal tiene ese nombre
            ("pipeline", "generate_and_deliver"),
            ("tasks", "generate_and_deliver"),
            ("worker_impl", "generate_and_deliver"),
            ("processor", "generate_and_deliver"),
        ]

        for modname, funcname in candidatos:
            try:
                mod = importlib.import_module(modname)
            except Exception as e:
                # módulo no existe -> seguir con el siguiente candidato
                # print reducido para no llenar logs, pero útil si debugging
                print(f"[main] no se pudo importar módulo {modname}: {e}")
                continue

            func = getattr(mod, funcname, None)
            if callable(func):
                print(f"[main] usando implementación real: {modname}.{funcname}")
                try:
                    # Primero intenta llamar solo con order_id (API esperada)
                    return func(order_id)
                except TypeError:
                    # Si la función espera otros argumentos, intenta pasar todo
                    return func(order_id, *args, **kwargs)

        # Si llegamos aquí, no encontramos implementación real: comportamiento de stub
        print(f"[main] No se encontró implementación real para processar la orden {order_id}. Ejecutando stub mínimo.")
        # Aquí puedes poner un procesamiento mínimo, logging adicional, o dejarlo así.
        print(f"[main] stub finalizado para order {order_id}")
        return None

    except Exception as err:
        print(f"[main][ERROR] Excepción inesperada en generate_and_deliver: {err}")
        traceback.print_exc()
        # Re-lanzar para que RQ registre el fallo (opcional)
        raise
