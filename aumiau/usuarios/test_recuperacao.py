import json
import re
from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .email import BrevoEmailBackend


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_RECOVERY_AVAILABLE=True,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RecuperacaoSenhaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user('maria', 'maria@example.com', 'antiga123')

    def setUp(self):
        cache.clear()
        self.url = reverse('usuarios:recuperar')

    def test_login_tem_link_e_fluxo_completo_envia_token_de_uso_unico(self):
        self.assertContains(self.client.get(reverse('usuarios:login')), self.url)
        self.assertContains(self.client.get(self.url), 'Enviar link de recuperação')
        response = self.client.post(self.url, {'email': self.usuario.email})
        self.assertRedirects(response, reverse('usuarios:recuperar_enviado'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])
        link = re.search(r'https?://[^\s]+', mail.outbox[0].body).group(0)
        pagina = self.client.get(link, follow=True)
        self.assertContains(pagina, 'Salvar nova senha')
        destino = pagina.redirect_chain[-1][0]
        response = self.client.post(destino, {'new_password1': 'Outra-senha-forte-921!',
                                               'new_password2': 'Outra-senha-forte-921!'})
        self.assertRedirects(response, reverse('usuarios:recuperar_concluido'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Outra-senha-forte-921!'))
        self.assertContains(self.client.get(link, follow=True), 'Este link é inválido')

    def test_email_inexistente_inativo_e_sem_senha_nao_enviam(self):
        usuarios = get_user_model().objects
        usuarios.create_user('inativo', 'inativo@example.com', 'teste', is_active=False)
        usuarios.create_user('google', 'google@example.com')
        for email in ['ausente@example.com', 'inativo@example.com', 'google@example.com']:
            self.assertRedirects(self.client.post(self.url, {'email': email}), reverse('usuarios:recuperar_enviado'))
        self.assertEqual(len(mail.outbox), 0)

    def test_sem_configuracao_informa_indisponibilidade_sem_consultar_conta(self):
        with override_settings(EMAIL_RECOVERY_AVAILABLE=False), patch('usuarios.recuperacao.RecuperarSenhaForm.get_users') as buscar:
            self.assertContains(self.client.get(self.url), 'temporariamente indisponível')
            self.assertContains(self.client.post(self.url, {'email': self.usuario.email}), 'temporariamente indisponível')
            buscar.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_limita_pedidos_repetidos(self):
        for _ in range(4):
            self.client.post(self.url, {'email': self.usuario.email})
        self.assertEqual(len(mail.outbox), 3)

    def test_token_expirado_e_usuario_desativado(self):
        with patch.object(default_token_generator, '_now', return_value=default_token_generator._now() - timedelta(hours=2)):
            token = default_token_generator.make_token(self.usuario)
        url = reverse('usuarios:recuperar_confirmar', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(self.usuario.pk)), 'token': token,
        })
        self.assertContains(self.client.get(url), 'Este link é inválido')
        token = default_token_generator.make_token(self.usuario)
        self.usuario.is_active = False
        self.usuario.save()
        url = reverse('usuarios:recuperar_confirmar', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(self.usuario.pk)), 'token': token,
        })
        self.assertContains(self.client.get(url), 'Este link é inválido')


@override_settings(BREVO_API_KEY='chave-ficticia-teste', DEFAULT_FROM_EMAIL='AuMiau <contato@example.com>',
                   EMAIL_FROM_NAME='AuMiau')
class EmailBackendTests(SimpleTestCase):
    @patch('usuarios.email.urlopen')
    def test_envia_por_https_com_remetente_e_conteudo(self, abrir):
        abrir.return_value.__enter__.return_value.status = 201
        mensagem = EmailMessage('Recuperar senha', 'Link fictício', to=['usuario@example.com'])
        self.assertEqual(BrevoEmailBackend().send_messages([mensagem]), 1)
        request = abrir.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.get_method(), 'POST')
        payload = json.loads(request.data)
        self.assertEqual(payload['sender']['email'], 'contato@example.com')
        self.assertEqual(payload['to'], [{'email': 'usuario@example.com'}])
        self.assertEqual(payload['textContent'], 'Link fictício')

    @patch('usuarios.email.urlopen')
    def test_falha_nao_expoe_chave_ou_link(self, abrir):
        abrir.side_effect = HTTPError('https://api.brevo.com', 401, 'chave-secreta', {}, None)
        mensagem = EmailMessage('Recuperar senha', 'link-secreto', to=['usuario@example.com'])
        with self.assertRaisesRegex(RuntimeError, 'HTTP 401') as erro:
            BrevoEmailBackend().send_messages([mensagem])
        self.assertNotIn('secreta', str(erro.exception))
        self.assertEqual(BrevoEmailBackend(fail_silently=True).send_messages([mensagem]), 0)
