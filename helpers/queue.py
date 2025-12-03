# helpers/queue.py
import os
import threading

def enqueue_generate_and_deliver(order_id: str):
    """
    Si REDIS_URL existe, intenta encolar con RQ.
    Si no, lanza en background thread importando main.generate_and_deliver.
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            from redis import Redis
            from rq import Queue
            conn = Redis.from_url(redis_url)
            q = Queue("reda", connection=conn)
            job = q.enqueue("main.generate_and_deliver", order_id, enqueue_timeout=3600, timeout=3600)
            return {"job_id": job.id}
        except Exception as e:
            print("RQ enqueue falló:", e)

    # Fallback: background thread
    def worker():
        try:
            import main
            if hasattr(main, "generate_and_deliver"):
                main.generate_and_deliver(order_id)
            elif hasattr(main, "ejecutar_flujo_redaxion"):
                # Si no existe función por orden, intenta ejecutar flujo completo (menos ideal)
                main.ejecutar_flujo_redaxion()
            else:
                print("No se encontró función de procesamiento en main.py")
        except Exception as e:
            print("Error en worker:", e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return {"background": True}
