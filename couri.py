#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.6"
# ///

"""couri - simple script/module for sending SMTP mail"""

import sys
import ssl
from argparse import Namespace, ArgumentParser, RawTextHelpFormatter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate
from smtplib import SMTP, SMTPConnectError, SMTPAuthenticationError, SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError, SMTPException
from pathlib import Path
from typing import List

def get_args() -> Namespace:
    """Set arguments and options for CLI use"""

    parser = ArgumentParser(
        description="couri: send SMTP mail easily (Python 3.6+)",
        formatter_class=RawTextHelpFormatter
    )

    parser.add_argument('-H', '--host', type=str, required=True, help='SMTP server hostname or IP')
    parser.add_argument('-p', '--port', type=int, default=25, help='SMTP port (default: 25)')
    parser.add_argument('-u', '--username', type=str, default='', help='SMTP username (optional)')
    parser.add_argument('-w', '--password', type=str, default='', help='SMTP password (optional)')
    parser.add_argument('-s', '--sender', type=str, required=True, help="Sender's email address")
    parser.add_argument('-t', '--to', type=str, required=True, nargs='+', help="Recipient email(s)")
    parser.add_argument('-c', '--cc', type=str, nargs='*', default=[], help='CC recipient(s)')
    parser.add_argument('-k', '--bcc', type=str, nargs='*', default=[], help='BCC recipient(s)')
    parser.add_argument('-j', '--subject', type=str, default='', help='Email subject')
    parser.add_argument('-b', '--body', type=str, default='', help='Email body (omit to read from pipe)')
    parser.add_argument('-m', '--mimetype', type=str, default='plain', choices=['plain', 'html'], help='Mime type for body (plain or html)')
    parser.add_argument('-a', '--attachment', type=str, nargs='*', default=[], help='Attachment file(s)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--tls', action='store_true', help='Enable STARTTLS (required for port 587)')
    parser.add_argument('--verify-tls', action='store_true', help='Enable STARTTLS and verify server certificate')

    return parser.parse_args()

def get_piped_input() -> str:
    """
    if stdin is not a terminal i.e. text is being piped in
    for example: echo "hello" | python couri.py
    return that text to be set as body of the message
    """
    
    # isatty returns True if the script’s standard input is connected to a terminal (interactive use),
    # and False if it’s connected to a pipe or a file.
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ''

def build_mime_message(sender: str, to: List[str], cc: List[str], bcc: List[str],
                       subject: str, body: str, mimetype: str, attachments: List[str]) -> MIMEMultipart:
    """Build a MIME message with optional attachments."""

    # MIME multipart type matters for how mail clients render the message:
    # - 'mixed': body + attachments as separate parts (attachments shown as downloadable files)
    # - 'alternative': multiple representations of the same content (e.g. plain + html)
    # When there are no attachments, 'alternative' is the safer default because some
    # mail clients misrender 'mixed' messages that only contain a text body.
    msg_type = 'mixed' if attachments else 'alternative'
    msg = MIMEMultipart(msg_type)

    msg['Date'] = formatdate(localtime=True)
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    if cc:
        msg['Cc'] = ', '.join(cc)
    if subject:
        msg['Subject'] = subject

    # If email body has not been passed as an argument to the script,
    # look for text on the standard input i.e. assume user has piped it
    if not body:
        body = get_piped_input()
    if body:
        msg.attach(MIMEText(body, mimetype))

    for filepath in attachments:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: attachment '{filepath}' does not exist and will be skipped.")
            continue
        with path.open('rb') as f:
            part = MIMEApplication(f.read(), Name=path.name)
            part['Content-Disposition'] = f'attachment; filename="{path.name}"'
            msg.attach(part)

    return msg

def send_mail(host: str, port: int, username: str, password: str,
              mime_message: MIMEMultipart, bcc: List[str],
              verbose: bool = False, tls: bool = False, verify_tls: bool = False) -> None:
    """Connect to SMTP server, optionally upgrade to TLS, authenticate, and send.

    Args:
        host: SMTP server hostname or IP.
        port: SMTP port (25 for plain, 587 for STARTTLS, 465 for implicit SSL).
        username: SMTP username. Empty string to skip authentication.
        password: SMTP password. Empty string to skip authentication.
        mime_message: Pre-built MIME message from build_mime_message().
        bcc: BCC recipients (not in MIME headers, but included in SMTP envelope).
        verbose: Print success message after sending.
        tls: Issue STARTTLS to upgrade the connection to TLS.
        verify_tls: Verify the server's TLS certificate. Implies tls=True.
    """

    # Build the full recipient list from To, Cc, and Bcc fields.
    # SMTP envelope (sendmail) needs all recipients, but Bcc must NOT appear
    # in the MIME headers -- that's why Bcc is passed separately.
    recipients = [r.strip() for r in mime_message['To'].split(',')]
    if mime_message.get('Cc'):
        recipients += [r.strip() for r in mime_message['Cc'].split(',')]
    recipients += bcc
    # Deduplicate: a recipient might appear in both To and Cc, or Cc and Bcc.
    # Sending to the same address twice is harmless but wasteful.
    recipients = list(set(r for r in recipients if r))

    # Each SMTP exception is caught separately so the error message is specific
    # and actionable. We exit with code 1 on any failure rather than raising,
    # because couri is designed for pipelines where a non-zero exit code signals
    # failure to the calling process.
    try:
        # STARTTLS and certificate verification are independent concerns:
        # - tls=True: upgrade the connection to TLS (required by port 587 servers)
        # - verify_tls=True: also verify the server's certificate (implies tls)
        # verify_tls implies tls -- you can't verify a cert without upgrading.
        use_tls = tls or verify_tls
        context = ssl.create_default_context() if verify_tls else None

        with SMTP(host, port) as smtp:
            # EHLO identifies us to the server and discovers supported extensions.
            # Must be called before STARTTLS so the server advertises TLS support.
            smtp.ehlo()
            if use_tls:
                # STARTTLS upgrades the existing plaintext connection to TLS.
                # If verify_tls is set, we pass a context that checks the cert
                # against the system's CA bundle. Without it, the connection is
                # encrypted but the server's identity is not verified (acceptable
                # for internal/trusted servers).
                smtp.starttls(context=context)
                # Second EHLO is required by RFC 3207: after STARTTLS, the server
                # resets its knowledge of client capabilities, so we re-identify.
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(mime_message['From'], recipients, mime_message.as_string())
        if verbose:
            print(f"Email successfully sent to: {', '.join(recipients)}")
    except SMTPConnectError as e:
        print(f"Error connecting to SMTP server: {e}")
        sys.exit(1)
    except SMTPAuthenticationError as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
    except SMTPSenderRefused as e:
        print(f"Sender address refused: {e}")
        sys.exit(1)
    except SMTPRecipientsRefused as e:
        print(f"Recipient(s) refused: {e.recipients}")
        sys.exit(1)
    except SMTPDataError as e:
        print(f"SMTP data error: {e}")
        sys.exit(1)
    except SMTPException as e:
        print(f"SMTP error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.version_info < (3, 6):
        print("Python 3.6 or higher is required")
        sys.exit(1)

    args = get_args()
    message = build_mime_message(
        sender=args.sender,
        to=args.to,
        cc=args.cc,
        bcc=args.bcc,
        subject=args.subject,
        body=args.body,
        mimetype=args.mimetype,
        attachments=args.attachment
    )

    send_mail(args.host, args.port, args.username, args.password,
              message, args.bcc, verbose=args.verbose, tls=args.tls,
              verify_tls=args.verify_tls)
