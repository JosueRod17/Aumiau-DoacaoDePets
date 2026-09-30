import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ongs.models import Ong
from pets.models import Pet
from .documentos import assinatura_cpf, normalizar_cpf, validar_cpf_disponivel
from .google import PENDING_KEY, TRANSACTION_KEY, _trocar_codigo
from .models import ContaGoogle, DocumentoBloqueado, Perfil
from .services import alterar_situacao_usuario, excluir_conta


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProtecaoContaTests(TestCase):
    def test_exclusao_anonimiza_conta_legada_sem_perfil_e_foto_ong(self):
        from django.core.files.base import ContentFile
        legado = get_user_model().objects.create_user(username='legado', password='Teste123')
        ong = Ong.objects.create(nome='ONG exemplo', responsavel=legado, cidade='X', estado='SP')
        ong.foto.save('foto-legado.jpg', ContentFile(b'arquivo de teste'))
        storage, nome = ong.foto.storage, ong.foto.name
        with self.captureOnCommitCallbacks(execute=True):
            excluir_conta(legado)
        ong.refresh_from_db()
        self.assertFalse(ong.foto)
        self.assertFalse(storage.exists(nome))
        self.assertEqual(Perfil.objects.get(usuario=legado).situacao, Perfil.Situacao.EXCLUIDA)
        with self.assertRaises(ValueError):
            alterar_situacao_usuario(legado, Perfil.Situacao.ATIVA)

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username='teste@example.com', email='teste@example.com', password='Senha-forte!123')
        self.perfil = Perfil.objects.create(usuario=self.usuario, cpf_hash=assinatura_cpf('11144477735'), cpf_final='7735', telefone='11999991234', cidade='São Paulo', estado='SP', aceitou_termos_em=timezone.now(), versao_termos='1.1')

    def test_cpf_normalizado_verificador_e_unicidade(self):
        self.assertEqual(normalizar_cpf('111.444.777-35'), '11144477735')
        for valor in ('11111111111', '11144477736', '1114447773X', ''):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                normalizar_cpf(valor)
        with self.assertRaises(ValidationError):
            validar_cpf_disponivel('111.444.777-35')
        self.assertNotIn('11144477735', self.perfil.cpf_hash)

    def test_cadastro_exige_cpf(self):
        from .forms import CadastroUsuarioForm
        self.assertTrue(CadastroUsuarioForm().fields['cpf'].required)
        self.assertNotIn('cpf_hash', CadastroUsuarioForm().fields)

    def test_suspensao_invalida_sessao_e_arquiva_publicacoes(self):
        pet = Pet.objects.create(nome='Teste', especie='gato', responsavel=self.usuario, cidade='X', estado='SP', status='publicado')
        ong = Ong.objects.create(nome='Teste ONG', responsavel=self.usuario, cidade='X', estado='SP', status='aprovada')
        self.client.force_login(self.usuario)
        alterar_situacao_usuario(self.usuario, Perfil.Situacao.SUSPENSA)
        pet.refresh_from_db(); ong.refresh_from_db()
        self.assertEqual(pet.status, 'arquivado')
        self.assertEqual(ong.status, 'suspensa')
        self.assertIsNone(authenticate(username=self.usuario.username, password='Senha-forte!123'))
        self.assertEqual(self.client.get(reverse('pets:meus_pets')).status_code, 302)
        # Nem reativar apenas a flag legado pode contornar a moderação.
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=True)
        self.assertIsNone(authenticate(username=self.usuario.username, password='Senha-forte!123'))

    def test_banimento_preserva_bloqueio_apos_exclusao(self):
        alterar_situacao_usuario(self.usuario, Perfil.Situacao.BANIDA)
        excluir_conta(self.usuario)
        self.assertTrue(DocumentoBloqueado.objects.filter(cpf_hash=assinatura_cpf('11144477735')).exists())
        with self.assertRaises(ValidationError):
            validar_cpf_disponivel('11144477735')

    def test_exclusao_exige_senha_confirmacao_e_post(self):
        self.client.force_login(self.usuario)
        url = reverse('usuarios:excluir')
        self.assertEqual(self.client.get(url).status_code, 200)
        for dados in ({'senha': 'errada', 'confirmacao': 'on'}, {'senha': 'Senha-forte!123'}, {'confirmacao': 'on'}):
            self.assertEqual(self.client.post(url, dados).status_code, 200)
            self.usuario.refresh_from_db()
            self.assertTrue(self.usuario.is_active)
        self.client.post(url, {'senha': 'Senha-forte!123', 'confirmacao': 'on'})
        self.usuario.refresh_from_db(); self.perfil.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(self.usuario.has_usable_password())
        self.assertEqual(self.usuario.email, '')
        self.assertIsNone(self.perfil.cpf_hash)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(validar_cpf_disponivel('11144477735'), '11144477735')
        with self.assertRaises(ValueError):
            alterar_situacao_usuario(self.usuario, Perfil.Situacao.ATIVA)

    def test_exclusao_nao_atinge_pet_transferido(self):
        outro = get_user_model().objects.create_user(username='outro')
        pet = Pet.objects.create(nome='Transferido', especie='gato', criado_por=self.usuario, responsavel=outro, cidade='X', estado='SP', status='publicado', email_contato='novo@example.com')
        excluir_conta(self.usuario)
        pet.refresh_from_db()
        self.assertEqual(pet.status, 'publicado')
        self.assertEqual(pet.email_contato, 'novo@example.com')

    def test_exclusao_google_sem_prova_recente_e_bloqueada(self):
        self.usuario.set_unusable_password(); self.usuario.save()
        ContaGoogle.objects.create(usuario=self.usuario, subject='google-test')
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('usuarios:excluir'), {'confirmacao': 'on'})
        self.assertContains(resposta, 'Confirme sua identidade')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_exclusao_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(client.post(reverse('usuarios:excluir'), {'senha': 'Senha-forte!123', 'confirmacao': 'on'}).status_code, 403)

    def test_painel_supervisor_exige_motivo_e_bloqueia_cpf_no_banimento(self):
        from django.contrib.auth.models import Group
        from supervisores.permissions import GRUPO_SUPERVISORES
        supervisor = get_user_model().objects.create_user(username='supervisor')
        supervisor.groups.add(Group.objects.get(name=GRUPO_SUPERVISORES))
        self.client.force_login(supervisor)
        url = reverse('supervisores:alterar_status_usuario', args=[self.usuario.pk, 'banir'])
        self.client.post(url)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.client.post(url, {'motivo': 'Denúncia analisada pela equipe.'})
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.situacao, Perfil.Situacao.BANIDA)
        self.assertTrue(DocumentoBloqueado.objects.exists())

    def test_usuario_comum_nao_pode_banir_outro(self):
        outro = get_user_model().objects.create_user(username='outro')
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(reverse('supervisores:alterar_status_usuario', args=[outro.pk, 'banir']), {'motivo': 'Forjado'}).status_code, 403)
        outro.refresh_from_db()
        self.assertTrue(outro.is_active)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], GOOGLE_CLIENT_ID='teste-client', GOOGLE_CLIENT_SECRET='teste-secret', GOOGLE_REDIRECT_URI='https://example.com/usuarios/google/retorno/')
class GoogleLoginTests(TestCase):
    def iniciar(self, **dados):
        resposta = self.client.post(reverse('usuarios:google_iniciar'), dados)
        return parse_qs(urlsplit(resposta.url).query)

    def callback(self, state):
        return self.client.get(reverse('usuarios:google_retorno'), {'state': state, 'code': 'codigo-teste'})

    def test_inicio_post_csrf_e_state_pkce_destino_seguro(self):
        self.assertEqual(self.client.get(reverse('usuarios:google_iniciar')).status_code, 405)
        params = self.iniciar(next='https://externo.example/')
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertTrue(params['nonce'][0])
        self.assertEqual(self.client.session[TRANSACTION_KEY]['next'], '/')
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('usuarios:google_iniciar')).status_code, 403)

    @patch('usuarios.google._trocar_codigo')
    def test_state_errado_ou_expirado_nao_consulta_google(self, trocar):
        self.iniciar(); self.callback('forjado')
        self.iniciar()
        session = self.client.session
        transaction = session[TRANSACTION_KEY]
        transaction['em'] = time.time() - 700
        session[TRANSACTION_KEY] = transaction; session.save()
        self.callback(transaction['state'])
        trocar.assert_not_called()
        self.assertNotIn('_auth_user_id', self.client.session)

    @patch('usuarios.google._trocar_codigo', return_value={'sub': 'google-teste', 'email': 'google@example.com', 'name': 'Pessoa Google'})
    def test_google_novo_exige_cadastro_com_cpf_e_termos(self, trocar):
        params = self.iniciar(next='/pets/anunciar/')
        resposta = self.callback(params['state'][0])
        self.assertRedirects(resposta, reverse('usuarios:google_completar'))
        self.assertNotIn('_auth_user_id', self.client.session)
        dados = {'nome_completo': 'Pessoa Google', 'email': 'forjado@example.com', 'cpf': '11144477735', 'telefone': '11999991234', 'estado': 'SP', 'cidade': 'São Paulo'}
        resposta = self.client.post(reverse('usuarios:google_completar'), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())
        resposta = self.client.post(reverse('usuarios:google_completar'), dados | {'aceite_termos': 'on'})
        self.assertRedirects(resposta, '/pets/anunciar/')
        usuario = get_user_model().objects.get()
        self.assertEqual(usuario.email, 'google@example.com')
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(usuario.perfil.cpf_hash)
        self.assertEqual(usuario.conta_google.subject, 'google-teste')

    @patch('usuarios.google._trocar_codigo', return_value={'sub': 'google-teste', 'email': 'google@example.com', 'name': 'Pessoa Google'})
    def test_email_existente_nao_e_vinculado_automaticamente(self, trocar):
        get_user_model().objects.create_user(username='google@example.com', email='google@example.com')
        params = self.iniciar(); self.callback(params['state'][0])
        self.assertFalse(ContaGoogle.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn(PENDING_KEY, self.client.session)

    @patch('usuarios.google._trocar_codigo', return_value={'sub': 'google-teste', 'email': 'google@example.com', 'name': 'Pessoa Google'})
    def test_conta_banida_nao_entra_pelo_google(self, trocar):
        usuario = get_user_model().objects.create_user(username='google@example.com')
        ContaGoogle.objects.create(usuario=usuario, subject='google-teste')
        alterar_situacao_usuario(usuario, Perfil.Situacao.BANIDA)
        get_user_model().objects.filter(pk=usuario.pk).update(is_active=True)
        params = self.iniciar(); self.callback(params['state'][0])
        self.assertNotIn('_auth_user_id', self.client.session)

    @patch('google.oauth2.id_token.verify_oauth2_token')
    @patch('requests.post')
    def test_token_google_precisa_de_nonce_email_verificado_e_audiencia(self, post, verificar):
        post.return_value.json.return_value = {'id_token': 'token-teste'}
        valido = {'sub': 'google-teste', 'email': 'google@example.com', 'email_verified': True, 'nonce': 'correto'}
        for invalido in ({'nonce': 'errado'}, {'email_verified': False}, {'azp': 'outro-client'}):
            verificar.return_value = valido | invalido
            with self.assertRaises(ValueError):
                _trocar_codigo('codigo', {'nonce': 'correto', 'verifier': 'verificador'})
        verificar.return_value = valido
        self.assertEqual(_trocar_codigo('codigo', {'nonce': 'correto', 'verifier': 'verificador'})['sub'], 'google-teste')
        self.assertEqual(verificar.call_args.args[2], 'teste-client')
        self.assertEqual(post.call_args.kwargs['data']['code_verifier'], 'verificador')
