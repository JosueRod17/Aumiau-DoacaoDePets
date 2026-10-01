import importlib
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.http import Http404
from django.test import TestCase, override_settings
from django.utils import timezone

from ongs.models import Ong
from pets.models import Pet
from usuarios.models import Perfil
from usuarios.services import excluir_conta

from .chat_service import criar_conversa, conversas_do_usuario, enviar_mensagem, usuario_disponivel
from .models import ConversaAdocao, MensagemAdocao, SolicitacaoAdocao
from .solicitacao_service import decidir_solicitacao


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ChatServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dono = User.objects.create_user('doador-chat')
        cls.adotante = User.objects.create_user('adotante-chat')
        cls.outro = User.objects.create_user('estranho-chat')
        cls.admin = User.objects.create_superuser('admin-chat', 'admin@example.com', 'teste')
        cls.pet = Pet.objects.create(
            nome='Sol', especie='gato', cidade='Recife', estado='PE',
            status='publicado', responsavel=cls.dono,
        )
        cls.pedido = SolicitacaoAdocao.objects.create(
            pet=cls.pet, usuario=cls.adotante, mensagem='Posso acolher a Sol.', status='aprovada',
        )

    def enviar(self, conversa, usuario=None, texto='Podemos combinar a retirada?', cliente_id=None):
        return enviar_mensagem(
            conversa_id=conversa.pk, usuario=usuario or self.adotante,
            texto=texto, cliente_id=cliente_id or uuid.uuid4(),
        )

    def test_aprovacao_cria_conversa_na_mesma_transacao(self):
        self.pedido.status = 'pendente'
        self.pedido.save()
        decidir_solicitacao(solicitacao_id=self.pedido.pk, ator=self.admin, aprovar=True)
        conversa = ConversaAdocao.objects.get(solicitacao=self.pedido)
        self.assertEqual(conversa.anunciante_id, self.dono.pk)
        self.assertEqual(conversa.ultimo_lido_adotante_id, 0)
        self.assertEqual(conversa.ultimo_lido_anunciante_id, 0)
        self.assertEqual(criar_conversa(self.pedido).pk, conversa.pk)

    def test_falha_ao_finalizar_aprovacao_desfaz_conversa(self):
        self.pedido.status = 'pendente'
        self.pedido.save()
        with patch('adocoes.solicitacao_service.Pet.save', side_effect=RuntimeError('falha simulada')):
            with self.assertRaises(RuntimeError):
                decidir_solicitacao(solicitacao_id=self.pedido.pk, ator=self.admin, aprovar=True)
        self.assertFalse(ConversaAdocao.objects.exists())
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'pendente')

    def test_conversa_restrita_a_participantes_sem_acesso_especial_admin(self):
        conversa = criar_conversa(self.pedido)
        for usuario in [self.dono, self.adotante]:
            self.assertEqual(list(conversas_do_usuario(usuario)), [conversa])
        for usuario in [self.outro, self.admin, AnonymousUser()]:
            self.assertFalse(conversas_do_usuario(usuario).exists())
        for usuario in [self.outro, self.admin]:
            with self.assertRaises(Http404):
                self.enviar(conversa, usuario)
        with self.assertRaises(Http404):
            enviar_mensagem(conversa_id=999999, usuario=self.adotante, texto='Oi', cliente_id=uuid.uuid4())
        self.assertFalse(MensagemAdocao.objects.exists())

    def test_mudanca_do_responsavel_nao_transfere_historico(self):
        conversa = criar_conversa(self.pedido)
        self.enviar(conversa)
        self.pet.responsavel = self.outro
        self.pet.save()
        self.assertEqual(criar_conversa(self.pedido).anunciante_id, self.dono.pk)
        self.assertFalse(conversas_do_usuario(self.outro).exists())
        self.assertTrue(conversas_do_usuario(self.dono).exists())
        with self.assertRaises(Http404):
            self.enviar(conversa, self.outro)

    def test_ong_e_fallback_para_criador(self):
        ong = Ong.objects.create(nome='Lar Seguro', cidade='Recife', estado='PE', responsavel=self.outro)
        self.pet.ong = ong
        self.pet.save()
        self.assertEqual(criar_conversa(self.pedido).anunciante_id, self.outro.pk)
        ConversaAdocao.objects.all().delete()
        self.pet.ong = None
        self.pet.responsavel = None
        self.pet.criado_por = self.dono
        self.pet.save()
        self.assertEqual(criar_conversa(self.pedido).anunciante_id, self.dono.pk)

    def test_nao_cria_sem_responsavel_com_proprio_adotante_ou_sem_aprovacao(self):
        self.pet.responsavel = None
        self.pet.save()
        self.assertIsNone(criar_conversa(self.pedido))
        self.pet.responsavel = self.adotante
        self.pet.save()
        self.assertIsNone(criar_conversa(self.pedido))
        self.pet.responsavel = self.dono
        self.pet.save()
        for status in ['pendente', 'recusada', 'cancelada']:
            self.pedido.status = status
            self.pedido.save()
            self.assertIsNone(criar_conversa(self.pedido))
        self.assertFalse(ConversaAdocao.objects.exists())

    def test_envio_bidirecional_idempotencia_e_texto_preservado(self):
        conversa = criar_conversa(self.pedido)
        identificador = uuid.uuid4()
        mensagem, criada = self.enviar(conversa, texto='  Posso buscar amanhã?  ', cliente_id=identificador)
        self.assertTrue(criada)
        self.assertEqual(mensagem.texto, 'Posso buscar amanhã?')
        repetida, criada = self.enviar(conversa, texto='Posso buscar amanhã?', cliente_id=str(identificador))
        self.assertFalse(criada)
        self.assertEqual(repetida.pk, mensagem.pk)
        with self.assertRaisesMessage(ValidationError, 'outro texto'):
            self.enviar(conversa, texto='Novo texto', cliente_id=identificador)
        resposta, criada = self.enviar(conversa, usuario=self.dono, texto='Sim, vamos combinar.', cliente_id=identificador)
        self.assertTrue(criada)
        self.assertEqual(MensagemAdocao.objects.count(), 2)
        conversa.refresh_from_db()
        self.assertEqual(conversa.ultima_mensagem_em, resposta.criado_em)
        self.assertEqual(list(conversa.mensagens.all()), [mensagem, resposta])

    def test_limitacao_de_frequencia_nao_impede_retry(self):
        conversa = criar_conversa(self.pedido)
        mensagem, _ = self.enviar(conversa)
        with self.assertRaisesMessage(ValidationError, 'dois segundos'):
            self.enviar(conversa, texto='Outra mensagem')
        repetida, criada = self.enviar(conversa, cliente_id=mensagem.cliente_id)
        self.assertEqual(repetida.pk, mensagem.pk)
        self.assertFalse(criada)
        MensagemAdocao.objects.filter(pk=mensagem.pk).update(criado_em=timezone.now() - timedelta(seconds=3))
        self.assertTrue(self.enviar(conversa, texto='Agora pode enviar')[1])

    def test_valida_texto_e_identificador(self):
        conversa = criar_conversa(self.pedido)
        for texto in ['', ' \n\t ', 'a' * 2001, None]:
            with self.assertRaises(ValidationError):
                enviar_mensagem(conversa_id=conversa.pk, usuario=self.adotante, texto=texto, cliente_id=uuid.uuid4())
        for identificador in ['', 'valor-invalido', None, 100]:
            with self.assertRaises(ValidationError):
                enviar_mensagem(conversa_id=conversa.pk, usuario=self.adotante, texto='Oi', cliente_id=identificador)
        self.assertFalse(MensagemAdocao.objects.exists())

    def test_conta_inativa_ou_suspensa_bloqueia_envio_e_leitura_do_ator(self):
        conversa = criar_conversa(self.pedido)
        get_user_model().objects.filter(pk=self.adotante.pk).update(is_active=False)
        self.assertFalse(usuario_disponivel(self.adotante))
        self.assertFalse(conversas_do_usuario(self.adotante).exists())
        with self.assertRaises(PermissionDenied):
            self.enviar(conversa)
        self.assertTrue(conversas_do_usuario(self.dono).exists())
        with self.assertRaises(PermissionDenied):
            self.enviar(conversa, self.dono)
        get_user_model().objects.filter(pk=self.adotante.pk).update(is_active=True)
        Perfil.objects.create(usuario=self.adotante, aceitou_termos_em=timezone.now(), situacao='suspensa')
        self.assertFalse(usuario_disponivel(self.adotante))
        with self.assertRaises(PermissionDenied):
            self.enviar(conversa)

    def test_estado_da_solicitacao_e_anunciante_ausente_bloqueiam_envio(self):
        conversa = criar_conversa(self.pedido)
        self.pedido.status = 'cancelada'
        self.pedido.save()
        self.assertFalse(conversas_do_usuario(self.adotante).exists())
        with self.assertRaises(ValidationError):
            self.enviar(conversa)
        self.pedido.status = 'aprovada'
        self.pedido.save()
        conversa.anunciante = None
        conversa.save()
        self.assertTrue(conversas_do_usuario(self.adotante).exists())
        with self.assertRaises(PermissionDenied):
            self.enviar(conversa)

    def test_exclusao_da_conta_do_anunciante_apaga_conversa_e_mensagens(self):
        conversa = criar_conversa(self.pedido)
        self.enviar(conversa)
        excluir_conta(self.dono)
        self.assertFalse(ConversaAdocao.objects.exists())
        self.assertFalse(MensagemAdocao.objects.exists())
        self.assertTrue(SolicitacaoAdocao.objects.filter(pk=self.pedido.pk).exists())

    def test_exclusao_da_conta_do_adotante_apaga_conversa_e_mensagens(self):
        conversa = criar_conversa(self.pedido)
        self.enviar(conversa)
        excluir_conta(self.adotante)
        self.assertFalse(ConversaAdocao.objects.exists())
        self.assertFalse(MensagemAdocao.objects.exists())

    def test_migracao_inclui_aprovacoes_antigas_sem_duplicar_ou_recriar_participante(self):
        migracao = importlib.import_module('adocoes.migrations.0005_chat_adocao')
        schema_editor = SimpleNamespace(connection=connection)
        migracao.criar_conversas_aprovadas(apps, schema_editor)
        conversa = ConversaAdocao.objects.get()
        self.assertEqual(conversa.anunciante_id, self.dono.pk)
        self.pet.responsavel = self.outro
        self.pet.save()
        migracao.criar_conversas_aprovadas(apps, schema_editor)
        self.assertEqual(ConversaAdocao.objects.count(), 1)
        conversa.refresh_from_db()
        self.assertEqual(conversa.anunciante_id, self.dono.pk)
