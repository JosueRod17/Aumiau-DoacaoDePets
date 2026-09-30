from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pets.models import Pet
from supervisores.models import RegistroAtividade
from .models import SolicitacaoAdocao
from .solicitacao_service import decidir_solicitacao


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SolicitacoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dono = User.objects.create_user('dono', email='dono@example.com')
        cls.interessado = User.objects.create_user('interessado', email='interessado@example.com')
        cls.outro = User.objects.create_user('outro')
        cls.admin = User.objects.create_superuser('admin', 'admin@example.com', 'teste')
        cls.supervisor = User.objects.create_user('supervisor')
        cls.supervisor.groups.add(Group.objects.get(name='Supervisores'))
        cls.pet = Pet.objects.create(nome='Amora', especie='gato', cidade='Recife', estado='PE',
                                     responsavel=cls.dono, status='publicado', destaque=True)

    def pedido(self, usuario=None):
        return SolicitacaoAdocao.objects.create(pet=self.pet, usuario=usuario or self.interessado,
                                               mensagem='Quero oferecer um lar seguro.')

    def test_solicitar_duplicado_e_visibilidade(self):
        url = reverse('solicitar_adocao', args=[self.pet.pk])
        self.assertEqual(self.client.post(url, {'mensagem': 'Meu lar'}).status_code, 302)
        self.assertEqual(SolicitacaoAdocao.objects.count(), 0)
        self.client.force_login(self.interessado)
        self.assertContains(self.client.get(reverse('pets:detalhe', args=[self.pet.pk])), url)
        self.assertContains(self.client.get(url), 'Enviar pedido de adoção')
        self.client.post(url, {'mensagem': 'Meu lar'})
        self.client.post(url, {'mensagem': 'Reenvio'})
        self.assertEqual(SolicitacaoAdocao.objects.count(), 1)
        pedido = SolicitacaoAdocao.objects.get()
        self.assertContains(self.client.get(reverse('minhas_adocoes')), 'Amora')
        self.assertContains(self.client.get(reverse('adocao_detalhe', args=[pedido.pk])), 'Meu lar')
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('adocao_detalhe', args=[pedido.pk])).status_code, 404)

    def test_nao_solicita_proprio_pet_ou_pet_indisponivel(self):
        url = reverse('solicitar_adocao', args=[self.pet.pk])
        self.client.force_login(self.dono)
        self.assertEqual(self.client.post(url, {'mensagem': 'Teste'}).status_code, 403)
        self.pet.status = 'arquivado'
        self.pet.save()
        self.client.force_login(self.interessado)
        self.assertEqual(self.client.post(url, {'mensagem': 'Teste'}).status_code, 404)

    def test_aprovacao_finaliza_pet_e_outros_pedidos_com_historico(self):
        pedido, outro = self.pedido(), self.pedido(self.outro)
        decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.supervisor, aprovar=True, resposta='Aprovado!')
        self.pet.refresh_from_db()
        pedido.refresh_from_db()
        outro.refresh_from_db()
        self.assertEqual(pedido.status, 'aprovada')
        self.assertEqual(self.pet.status, 'adotado')
        self.assertFalse(self.pet.destaque)
        self.assertIsNotNone(self.pet.adotado_em)
        self.assertEqual(outro.status, 'recusada')
        self.assertIn('já foi adotado', outro.resposta)
        self.assertEqual(RegistroAtividade.objects.count(), 3)
        with self.assertRaises(ValidationError):
            decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=True)
        self.assertEqual(RegistroAtividade.objects.count(), 3)

    def test_recusa_exige_motivo_e_nao_altera_pet(self):
        pedido = self.pedido()
        with self.assertRaises(ValidationError):
            decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=False)
        decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=False, resposta='Cuidados incompatíveis.')
        pedido.refresh_from_db()
        self.pet.refresh_from_db()
        self.assertEqual(pedido.status, 'recusada')
        self.assertEqual(self.pet.status, 'publicado')

    def test_protecao_de_ator_e_estado(self):
        pedido = self.pedido()
        with self.assertRaises(PermissionDenied):
            decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.interessado, aprovar=True)
        self.pet.status = 'arquivado'
        self.pet.save()
        with self.assertRaises(ValidationError):
            decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=True)
        self.pet.status = 'publicado'
        self.pet.save()
        self.interessado.is_active = False
        self.interessado.save()
        with self.assertRaises(ValidationError):
            decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=True)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'pendente')

    def test_cancelamento_somente_por_post_do_solicitante(self):
        pedido = self.pedido()
        url = reverse('cancelar_adocao', args=[pedido.pk])
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.interessado)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'cancelada')

    def test_paineis_permissoes_e_decisoes(self):
        pedido = self.pedido()
        url = reverse('supervisores:adocao_detalhe', args=[pedido.pk])
        self.client.force_login(self.interessado)
        self.assertEqual(self.client.post(url, {'acao': 'aprovar'}).status_code, 403)
        self.client.force_login(self.supervisor)
        self.assertContains(self.client.get(reverse('supervisores:dashboard')), 'Pedidos de adoção')
        self.assertContains(self.client.get(reverse('supervisores:adocoes_lista')), 'Amora')
        self.assertContains(self.client.get(url), 'Confirmar decisão')
        self.assertContains(self.client.post(url, {'acao': 'recusar'}), 'Explique o motivo')
        self.assertEqual(self.client.post(url, {'acao': 'aprovar', 'resposta': 'Pode adotar!'}).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'aprovada')

    def test_admin_analisa_e_csrf_obrigatorio(self):
        pedido = self.pedido()
        url = reverse('admin:adocoes_solicitacaoadocao_analisar', args=[pedido.pk])
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:index')), 'Pedidos de adoção')
        self.assertContains(self.client.get(reverse('admin:adocoes_solicitacaoadocao_changelist')), 'Analisar pedido')
        self.assertContains(self.client.get(url), 'Confirmar decisão')
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.admin)
        self.assertEqual(seguro.post(url, {'acao': 'aprovar'}).status_code, 403)
        self.assertEqual(self.client.post(url, {'acao': 'aprovar'}).status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'aprovada')
