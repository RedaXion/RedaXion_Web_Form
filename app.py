# app.py
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse
import uuid, os, shutil, tempfile

# Helpers (implementaremos en helpers/*.py)
from helpers.gcs import upload_to_gcs  # debe devolver URL pública firmada
from helpers.sheets import add_row_to_sheets, mark_order_paid_in_sheets
from helpers.mercadopago import create_mercadopago_preference, verify_mp_payment
from helpers.queue import enqueue_generate_and_deliver

app = FastAPI()

@app.post("/create-order")
async def create_order(
    name: str = Form(...),
    email: str = Form(...),
    columnas: str = Form(...),
    color: str = Form(...),
    audio: UploadFile = File(...)
):
    order_id = str(uuid.uuid4())[:10]
    tmp_dir = tempfile.mkdtemp()
    filename = f"{order_id}_{audio.filename}"
    tmp_path = os.path.join(tmp_dir, filename)

    # Guardar audio temporalmente
    with open(tmp_path, "wb") as f:
        f.write(await audio.read())

    # Subir a GCS (helper) -> debe devolver URL pública (signed url)
    public_url = upload_to_gcs(tmp_path, filename)

    # Registrar en Google Sheets (helper)
    row = {
        "orden": order_id,
        "fecha": "",  # opcional: let the helper set timestamp
        "nombre": name,
        "email": email,
        "audio_url": public_url,
        "columnas": columnas,
        "color": color,
        "estado": "Pendiente"
    }
    add_row_to_sheets(row)

    # Crear preferencia Mercado Pago y devolver init_point
    amount = int(os.getenv("DEFAULT_PRICE_CLP", "4000"))  # configurable en env
    callback_url = os.getenv("MP_WEBHOOK_URL", "")  # debe apuntar a /mp-webhook pública
    pref = create_mercadopago_preference(order_id, amount, callback_url)

    # limpiar tmp
    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass

    return JSONResponse({"order_id": order_id, "init_point": pref.get("init_point")})

@app.post("/mp-webhook")
async def mp_webhook(req: Request):
    """
    Endpoint público que recibe notificaciones de Mercado Pago.
    Validamos el payment_id con la API de MP y solo si está 'approved' marcamos la orden y encolamos.
    """
    payload = await req.json()
    # Mercado Pago puede enviar distintos eventos; aquí asumimos que se envía payment id en data.id
    payment_id = None
    try:
        # ejemplos: {"type":"payment","data":{"id":1234567890}}
        if "data" in payload and isinstance(payload["data"], dict):
            payment_id = payload["data"].get("id")
    except Exception:
        payment_id = None

    if not payment_id:
        return JSONResponse({"ok": False, "reason": "no payment id"})

    payment = verify_mp_payment(payment_id)
    if not payment:
        return JSONResponse({"ok": False, "reason": "mp verify failed"})

    status = payment.get("status")
    external_ref = payment.get("external_reference")  # debe ser order_id
    if status == "approved" and external_ref:
        mark_order_paid_in_sheets(external_ref, payment_id)
        enqueue_generate_and_deliver(external_ref)
        return JSONResponse({"ok": True, "processed": True})

    return JSONResponse({"ok": True, "processed": False, "status": status})
