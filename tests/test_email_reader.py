import types

import jarvis.skills.email_reader as email_reader


class FakeIMAP:
    def __init__(self, *args, **kwargs):
        self.mailbox = None
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, pwd):
        self.logged_in = True

    def select(self, mailbox):
        self.mailbox = mailbox

    def search(self, charset, criteria):
        if criteria == "UNSEEN":
            return "OK", [b"1 2"]
        return "OK", [b"1 2"]

    def fetch(self, msg_id, what):
        if what.startswith("(BODY[HEADER"):
            if msg_id == b"1":
                header = b"From: Alice\r\nSubject: Hello\r\n\r\n"
            else:
                header = b"From: Bob\r\nSubject: Update\r\n\r\n"
            return "OK", [(b"data", header)]
        else:
            body = b"From: Bob\r\nSubject: Update\r\n\r\nThe body"
            return "OK", [(b"data", body)]


class FakeSMTP:
    def __init__(self, *args, **kwargs):
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, pwd):
        self.user = user

    def sendmail(self, from_addr, to_addr, msg):
        self.sent.append((from_addr, to_addr, msg))


class DummyConfig:
    def get(self, *keys, **kwargs):
        mapping = {
            ("email", "imap_server"): "imap.example.com",
            ("email", "imap_port"): 993,
            ("email", "smtp_server"): "smtp.example.com",
            ("email", "smtp_port"): 587,
            ("email", "username"): "user@example.com",
            ("email", "password"): "secret",
        }
        return mapping.get(keys)


def test_can_handle():
    assert email_reader.can_handle("read_email")
    assert email_reader.can_handle("send_email")
    assert email_reader.can_handle("list_unread")
    assert not email_reader.can_handle("other")


def test_list_unread(monkeypatch):
    monkeypatch.setattr(email_reader, "imaplib", types.SimpleNamespace(IMAP4_SSL=FakeIMAP))
    monkeypatch.setattr(email_reader, "Config", lambda: DummyConfig())
    resp = email_reader.handle({"intent": "list_unread", "entities": {}, "context": {}})
    assert "Unread emails" in resp["text"]
    assert "Alice - Hello" in resp["text"]


def test_send_email(monkeypatch):
    smtp = FakeSMTP()
    monkeypatch.setattr(email_reader, "smtplib", types.SimpleNamespace(SMTP=lambda *a, **k: smtp))
    monkeypatch.setattr(email_reader, "Config", lambda: DummyConfig())
    resp = email_reader.handle({"intent": "send_email", "entities": {"to": "a@b.com", "subject": "Hi", "body": "Test"}, "context": {}})
    assert resp["text"] == "Email sent."
    assert smtp.sent


def test_read_email(monkeypatch):
    monkeypatch.setattr(email_reader, "imaplib", types.SimpleNamespace(IMAP4_SSL=FakeIMAP))
    monkeypatch.setattr(email_reader, "Config", lambda: DummyConfig())
    resp = email_reader.handle({"intent": "read_email", "entities": {"index": 0}, "context": {}})
    assert "subject 'Update'" in resp["text"]
