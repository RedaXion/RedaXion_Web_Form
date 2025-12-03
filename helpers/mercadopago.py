# helpers/mercadopago.py
import os
import requests

MP_BASE = "https://api.mercadopago.com"

def _mp_headers():
    token = os.getenv("MP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("MP_ACCESS_TOKEN no configurado")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_mercadopago_preference(order_id: str, amount: int, callback_url: str):
    """
    Crea una preferencia para Checkout Pro y devuelve el JSON resultante (incluye init_point).
    - order_id -> external_reference
    - amount -> valor en CLP
    - callback_url -> notification_url que MP usará para notificar pagos
    """
    url = f"{MP_BASE}/checkout/preferences"
    headers = _mp_headers()

    payload = {
        "external_reference": str(order_id),
        "items": [
            {
                "id": str(order_id),
                "title": f"Transcripción RedaXion {order_id}",
                "description": "Transcripción académica y RedaQuiz",
                "picture_url": None,
                "quantity": 1,
                "unit_price": float(amount),
                "currency_id": "CLP"
            }
        ],
        # Webhook/Notifications
        "notification_url": callback_url,
        # Redirecciones (opcional, el front-end puede usar init_point)
        "back_urls": {
            "success": callback_url,
            "failure": callback_url,
            "pending": callback_url
        },
        # Auto return al usuario cuando pago aprobado
        "auto_return": "approved",
        # Opciones de método de pago (personalizable)
        # "payment_methods": {
        #     "excluded_payment_types": [{"id":"atm"}],
        #     "installments": 1
        # },
        "payer": {
            # se puede enviar info del pagador si la tienes (opcional)
            # "name": "Nombre",
            # "email": "correo@ejemplo.cl"
        }
    }

    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

def verify_mp_payment(payment_id: str):
    """
    Verifica el pago consultando /v1/payments/{payment_id}
    Retorna el JSON completo; revisa 'status' y 'external_reference' para validar.
    """
    token = os.getenv("MP_ACCESS_TOKEN")
    url = f"{MP_BASE}/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()
