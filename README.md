# couri

**couri** is a simple, dependency-free Python script and module for sending SMTP emails. It is designed for automation and pipelines, requiring **only Python 3.6+**.

---

## Features

- Send emails via any SMTP server.
- Supports multiple recipients, CC, and BCC.
- Send plain text or HTML emails.
- Attach multiple files.
- Read email body from stdin (piped input).
- STARTTLS support with optional certificate verification.
- Zero external dependencies.

---

## Requirements

- Python 3.6 or higher.
- SMTP server access.

---

## Installation

No installation needed. Simply download or clone the script.

---

## CLI Usage

```
python couri.py -H <host> -s <sender> -t <recipient> [options]
```

### Send a plain text email

```bash
python couri.py -H smtp.example.com -p 587 --tls \
    -u myuser -w mypassword \
    -s sender@example.com -t recipient@example.com \
    -j "Hello" -b "This is the body" -v
```

### Send an HTML email

```bash
python couri.py -H smtp.example.com -p 587 --tls \
    -u myuser -w mypassword \
    -s sender@example.com -t recipient@example.com \
    -j "Weekly Report" -b "<h1>Report</h1><p>Details here.</p>" -m html
```

### Pipe body from stdin

```bash
echo "Piped message body" | python couri.py -H smtp.example.com -p 587 --tls \
    -u myuser -w mypassword \
    -s sender@example.com -t recipient@example.com \
    -j "Piped email"
```

### Send with attachments

```bash
python couri.py -H smtp.example.com -p 587 --tls \
    -u myuser -w mypassword \
    -s sender@example.com -t recipient@example.com \
    -j "Files attached" -b "See attachments." \
    -a report.pdf data.csv
```

### Multiple recipients with CC and BCC

```bash
python couri.py -H smtp.example.com -p 587 --tls \
    -u myuser -w mypassword \
    -s sender@example.com \
    -t alice@example.com bob@example.com \
    -c manager@example.com \
    -k auditor@example.com \
    -j "Team update" -b "FYI."
```

### TLS options

```bash
# STARTTLS without certificate verification (encrypted, but server identity not checked)
python couri.py -H smtp.example.com -p 587 --tls -s ... -t ...

# STARTTLS with certificate verification (encrypted + server identity verified)
python couri.py -H smtp.example.com -p 587 --verify-tls -s ... -t ...

# No TLS (plain SMTP, port 25)
python couri.py -H smtp.example.com -p 25 -s ... -t ...
```

---

## Module Usage

couri can be imported and used as a Python module:

```python
from couri import build_mime_message, send_mail

message = build_mime_message(
    sender="sender@example.com",
    to=["recipient@example.com"],
    cc=[],
    bcc=[],
    subject="Hello from code",
    body="This is the body.",
    mimetype="plain",
    attachments=[]
)

send_mail(
    host="smtp.example.com",
    port=587,
    username="myuser",
    password="mypassword",
    mime_message=message,
    bcc=[],
    tls=True
)
```

---

## All Options

```
-H, --host         SMTP server hostname or IP (required)
-p, --port         SMTP port (default: 25)
-u, --username     SMTP username
-w, --password     SMTP password
-s, --sender       Sender email address (required)
-t, --to           Recipient email(s) (required, space-separated)
-c, --cc           CC recipient(s)
-k, --bcc          BCC recipient(s)
-j, --subject      Email subject
-b, --body         Email body (omit to read from stdin)
-m, --mimetype     Body MIME type: plain (default) or html
-a, --attachment   File(s) to attach
-v, --verbose      Print success message after sending
--tls              Enable STARTTLS (required for port 587)
--verify-tls       Enable STARTTLS and verify server certificate
```
