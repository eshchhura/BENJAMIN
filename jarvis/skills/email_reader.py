import logging
import email
from email import message
import imaplib
import smtplib
import ssl

from jarvis.config import Config

logger = logging.getLogger(__name__)


def can_handle(intent: str) -> bool:
    """Return True if this module can handle the intent."""
    return intent in {"read_email", "send_email", "list_unread"}


def _get_credentials():
    cfg = Config()
    return {
        "imap_server": cfg.get("email", "imap_server"),
        "imap_port": cfg.get("email", "imap_port", default=993),
        "smtp_server": cfg.get("email", "smtp_server"),
        "smtp_port": cfg.get("email", "smtp_port", default=587),
        "username": cfg.get("email", "username"),
        "password": cfg.get("email", "password"),
    }


def _read_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(errors="ignore")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(errors="ignore")


def handle(request: dict) -> dict:
    intent = request.get("intent", "")
    params = request.get("entities", {})
    creds = _get_credentials()

    try:
        if intent == "list_unread":
            with imaplib.IMAP4_SSL(creds["imap_server"], creds["imap_port"]) as imap:
                imap.login(creds["username"], creds["password"])
                imap.select("INBOX")
                typ, data = imap.search(None, "UNSEEN")
                ids = data[0].split() if data and data[0] else []
                if not ids:
                    return {"text": "No unread emails."}
                subjects = []
                for msg_id in ids[:5]:
                    typ, msg_data = imap.fetch(msg_id, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
                    header = msg_data[0][1]
                    msg = email.message_from_bytes(header)
                    subjects.append(f"{msg.get('From')} - {msg.get('Subject')}")
                return {"text": "Unread emails:\n" + "\n".join(subjects)}

        elif intent == "read_email":
            index = int(params.get("index", 0))
            with imaplib.IMAP4_SSL(creds["imap_server"], creds["imap_port"]) as imap:
                imap.login(creds["username"], creds["password"])
                imap.select("INBOX")
                typ, data = imap.search(None, "ALL")
                ids = data[0].split() if data and data[0] else []
                if not ids or index >= len(ids):
                    return {"text": "No such email."}
                msg_id = ids[-(index + 1)]
                typ, msg_data = imap.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                body = _read_body(msg)
                snippet = body.strip().splitlines()[0] if body else ""
                return {"text": f"Email from {msg.get('From')} subject '{msg.get('Subject')}': {snippet}"}

        elif intent == "send_email":
            to_addr = params.get("to")
            subject = params.get("subject", "")
            body = params.get("body", "")
            if not to_addr:
                return {"text": "Please provide a recipient."}
            msg = f"From: {creds['username']}\r\nTo: {to_addr}\r\nSubject: {subject}\r\n\r\n{body}"
            context = ssl.create_default_context()
            with smtplib.SMTP(creds["smtp_server"], creds["smtp_port"]) as smtp:
                smtp.starttls(context=context)
                smtp.login(creds["username"], creds["password"])
                smtp.sendmail(creds["username"], to_addr, msg.encode("utf-8"))
            return {"text": "Email sent."}

        else:
            return {"text": "Email skill received an unknown intent."}

    except Exception as exc:
        logger.exception("Email skill error: %s", exc)
        return {"text": "Error handling email request."}
