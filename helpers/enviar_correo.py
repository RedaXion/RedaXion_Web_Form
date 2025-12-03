# helpers/enviar_correo.py
import os
import logging
import smtplib
import mimetypes
from email.message import EmailMessage

logger = logging.getLogger("mail")
logger.setLevel(logging.INFO)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 0)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", "admin@redaxiontcp.com")


def _send_via_smtp(to_emails, subject, html_body, attachments=None, from_email=SMTP_FROM):
    attachments = attachments or []
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails) if isinstance(to_emails, (list,tuple)) else to_emails
    msg.set_content("Correo en HTML. Usa cliente que soporte HTML.")
    msg.add_alternative(html_body, subtype="html")

    for path in attachments:
        try:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(path, "rb") as fp:
                data = fp.read()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))
        except Exception:
            logger.exception("Failed to attach file %s", path)

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                s.ehlo()
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        logger.info("Email sent to %s via SMTP", msg["To"])
        return True
    except Exception:
        logger.exception("SMTP send failed")
        raise


def enviar_correo_con_adjuntos(to_emails, subject, html_body, attachments=None, from_email=None):
    if from_email is None:
        from_email = SMTP_FROM
    # Prefer SendGrid if key present (optional)
    if SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
            import base64
            message = Mail(from_email=from_email, to_emails=to_emails, subject=subject, html_content=html_body)
            if attachments:
                for path in attachments:
                    with open(path, "rb") as f:
                        data = base64.b64encode(f.read()).decode()
                    att = Attachment()
                    att.file_content = FileContent(data)
                    att.file_type = FileType(mimetypes.guess_type(path)[0] or "application/octet-stream")
                    att.file_name = FileName(os.path.basename(path))
                    att.disposition = Disposition("attachment")
                    message.add_attachment(att)
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            sg.send(message)
            logger.info("Email sent via SendGrid to %s", to_emails)
            return True
        except Exception:
            logger.exception("SendGrid send failed, falling back to SMTP")

    # fallback SMTP
    if not (SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASS):
        raise RuntimeError("No email backend configured (SENDGRID or SMTP missing).")
    return _send_via_smtp(to_emails, subject, html_body, attachments, from_email)
