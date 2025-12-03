# helpers/sheets.py
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def _get_client():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS_JSON no configurada")
    info = json.loads(creds_json)
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
    return gspread.authorize(creds)

def add_row_to_sheets(row: dict):
    """
    row: dict con keys como orden, fecha, nombre, email, audio_url, columnas, color, estado
    Agrega al final del sheet. Asume que la primera fila tiene encabezados.
    """
    client = _get_client()
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        raise RuntimeError("SHEET_ID no configurado")
    ss = client.open_by_key(sheet_id)
    ws = ss.sheet1

    # Obtener encabezados para ordenar campos
    headers = ws.row_values(1)
    # Si hoja vacía, crea encabezados basicos
    if not headers:
        headers = ["orden","fecha","nombre","email","audio_url","columnas","color","estado","payment_id","comentarios"]
        ws.insert_row(headers, index=1)

    # Prepare row in header order
    fecha = row.get("fecha") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    values = []
    for h in headers:
        if h == "fecha":
            values.append(fecha)
        else:
            values.append(row.get(h, ""))
    ws.append_row(values)
    return True

def mark_order_paid_in_sheets(order_id: str, payment_id: str):
    client = _get_client()
    sheet_id = os.getenv("SHEET_ID")
    ss = client.open_by_key(sheet_id)
    ws = ss.sheet1

    # Buscar la celda donde orden == order_id
    try:
        cell = ws.find(order_id, in_column=1)  # asume 'orden' en columna 1
    except Exception:
        # fallback: buscar en todo el sheet
        all_vals = ws.get_all_records()
        for idx, r in enumerate(all_vals, start=2):
            if str(r.get("orden", "")) == str(order_id):
                cell = ws.cell(idx, 1)
                break
        else:
            cell = None

    if not cell:
        # no encontrado
        return False

    row_index = cell.row
    # encontrar índice de la columna payment_id y estado
    headers = ws.row_values(1)
    try:
        status_col = headers.index("estado") + 1
    except ValueError:
        # si no existe, añadir en última col+1
        status_col = len(headers) + 1
        ws.update_cell(1, status_col, "estado")

    try:
        pay_col = headers.index("payment_id") + 1
    except ValueError:
        pay_col = len(headers) + 1
        ws.update_cell(1, pay_col, "payment_id")

    ws.update_cell(row_index, status_col, "Paid")
    ws.update_cell(row_index, pay_col, payment_id)
    return True
