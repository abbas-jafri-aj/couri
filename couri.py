#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.6"
# ///

"""couri - simple script/module for sending SMTP mail"""

import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate
from smtplib import SMTP, SMTPConnectError, SMTPAuthenticationError, SMTPSenderRefused, SMTPRecipientsRefused, SMTPDataError, SMTPException
from pathlib import Path
from typing import List
import ssl

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
    parser.add_argument('--verify-tls', action='store_true', help='Verify SMTP TLS certificate')

    return parser.parse_args()

def get_piped_input() -> str:
    """If not body as an argument to the script, look for text on the standard input i.e. assume user has piped it"""
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ''

def build_mime_message(sender: str, to: List[str], cc: List[str], bcc: List[str],
                       subject: str, body: str, mimetype: str, attachments: List[str]) -> MIMEMultipart:
    """Build a MIME message with optional attachments"""
    msg_type = 'mixed' if attachments else 'alternative'
    msg = MIMEMultipart(msg_type)

    msg['Date'] = formatdate(localtime=True)
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    if cc:
        msg['Cc'] = ', '.join(cc)
    if subject:
        msg['Subject'] = subject

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
              verbose: bool = False, verify_tls: bool = False) -> None:
    recipients = [r.strip() for r in mime_message['To'].split(',')]
    if mime_message.get('Cc'):
        recipients += [r.strip() for r in mime_message['Cc'].split(',')]
    recipients += bcc
    recipients = list(set(r for r in recipients if r))  # deduplicate

    try:
        context = ssl.create_default_context() if verify_tls else None
        with SMTP(host, port) as smtp:
            smtp.ehlo()
            if context:
                smtp.starttls(context=context)
                smtp.ehlo()
            elif verify_tls:
                smtp.starttls()
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
              message, args.bcc, verbose=args.verbose, verify_tls=args.verify_tls)
