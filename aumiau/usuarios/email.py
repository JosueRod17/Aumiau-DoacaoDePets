"""Envio transacional por HTTPS para funcionar no plano gratuito do Render."""

import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


class BrevoEmailBackend(BaseEmailBackend):
    """Adaptador mínimo de EmailMessage para a API transacional da Brevo."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except (HTTPError, URLError, OSError, ValueError) as exc:
                if self.fail_silently:
                    continue
                status = getattr(exc, 'code', None)
                if status is not None:
                    raise RuntimeError(f'Envio de e-mail recusado pela Brevo (HTTP {status}).') from None
                raise RuntimeError('Não foi possível enviar o e-mail pela Brevo.') from None
            else:
                sent += 1
        return sent

    def _send(self, message):
        if message.attachments or getattr(message, 'alternatives', None):
            raise ValueError('O backend de e-mail transacional aceita apenas texto simples sem anexos.')
        sender_name, sender_email = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        recipients = [address for address in message.to if address]
        if not sender_email or not recipients or not settings.BREVO_API_KEY:
            raise ValueError('Remetente, destinatário ou chave de e-mail ausente.')
        payload = {
            'sender': {'email': sender_email, 'name': sender_name or settings.EMAIL_FROM_NAME},
            'to': [{'email': address} for address in recipients],
            'subject': message.subject,
            'textContent': message.body,
        }
        if message.cc:
            payload['cc'] = [{'email': address} for address in message.cc]
        if message.bcc:
            payload['bcc'] = [{'email': address} for address in message.bcc]
        if message.reply_to:
            payload['replyTo'] = {'email': message.reply_to[0]}
        request = Request(
            BREVO_URL,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={
                'api-key': settings.BREVO_API_KEY,
                'accept': 'application/json',
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urlopen(request, timeout=10) as response:
            if response.status not in (200, 201, 202):
                raise ValueError('A Brevo não confirmou o envio do e-mail.')
