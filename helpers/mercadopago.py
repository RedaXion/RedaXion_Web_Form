# helpers/mercadopago.py
import os
import requests

MP_BASE = "https://api.mercadopago.com"

def create_mercadopago_preference(order_id: str, amount: int, callback_url: str):
    token = os.getenv("MP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("MP_ACCESS_TOKEN no configurado")
    url = f"{MP_BASE}/checkout/preferences"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "external_reference": order_id,
        "items": [
            {"title": f"Transcripción RedaXion {order_id}", "quantity": 1, "unit_price": float(amount), "currency_id": "CLP"}
        ],
        "notification_url": callback_url,  # MP envía notificaciones aqui
        "back_urls": {"success": callback_url, "failure": callback_url, "pending": callback_url},
        "auto_return": "approved"
    }
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

def verify_mp_payment(payment_id: str):
    token = os.getenv("MP_ACCESS_TOKEN")
    url = f"{MP_BASE}/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()
