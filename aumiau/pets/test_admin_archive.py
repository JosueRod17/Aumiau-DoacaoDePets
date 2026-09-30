from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from supervisores.models import RegistroAtividade

from .models import Pet


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ArquivamentoAdminPetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin-arquivo', 'admin@example.com', 'teste')
        cls.pet = Pet.objects.create(
            nome='Amora', especie=Pet.Especie.GATO, cidade='Recife', estado='PE',
            status=Pet.Status.PUBLICADO, publicado_em=timezone.now() - timedelta(days=1),
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse('admin:pets_pet_arquivar', args=[self.pet.pk])

    def test_arquiva_cadastro_antigo_sem_exigir_os_campos_novos(self):
        anterior = self.pet.atualizado_em
        publicado_em = self.pet.publicado_em
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('admin:pets_pet_change', args=[self.pet.pk]))
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.ARQUIVADO)
        self.assertEqual(self.pet.moderado_por, self.admin)
        self.assertIsNotNone(self.pet.moderado_em)
        self.assertGreater(self.pet.atualizado_em, anterior)
        self.assertEqual(self.pet.publicado_em, publicado_em)
        self.assertEqual(self.pet.porte, Pet.Porte.NAO_INFORMADO)
        self.assertIsNone(self.pet.data_nascimento)
        self.assertIsNone(self.pet.responsavel)
        self.assertFalse(Pet.objects.publicos().filter(pk=self.pet.pk).exists())
        self.assertEqual(LogEntry.objects.filter(object_id=str(self.pet.pk)).count(), 1)
        registro = RegistroAtividade.objects.get(objeto_id=self.pet.pk, entidade='pet')
        self.assertEqual(registro.acao, RegistroAtividade.Acao.ARQUIVOU)
        self.assertEqual(registro.supervisor, self.admin)

    def test_acao_visivel_somente_para_pet_ainda_nao_arquivado(self):
        url = reverse('admin:pets_pet_change', args=[self.pet.pk])
        self.assertContains(self.client.get(url), f'action="{self.url}"')
        self.assertContains(self.client.get(url), 'Arquivar anúncio')
        self.client.post(self.url)
        self.assertNotContains(self.client.get(url), f'action="{self.url}"')

    def test_repetir_arquivamento_preserva_historico_e_datas(self):
        self.client.post(self.url)
        self.pet.refresh_from_db()
        moderado_em = self.pet.moderado_em
        atualizado_em = self.pet.atualizado_em
        self.client.post(self.url)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.moderado_em, moderado_em)
        self.assertEqual(self.pet.atualizado_em, atualizado_em)
        self.assertEqual(LogEntry.objects.filter(object_id=str(self.pet.pk)).count(), 1)
        self.assertEqual(RegistroAtividade.objects.filter(objeto_id=self.pet.pk, entidade='pet').count(), 1)

    def test_aprovar_anuncio_antigo_sem_validar_formulario_inteiro(self):
        self.pet.status = Pet.Status.PENDENTE
        self.pet.save()
        url = reverse('admin:pets_pet_publicar', args=[self.pet.pk])
        self.assertContains(self.client.get(reverse('admin:pets_pet_change', args=[self.pet.pk])), 'Aprovar e publicar')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.PUBLICADO)
        self.assertIsNotNone(self.pet.publicado_em)
        self.assertEqual(self.pet.moderado_por, self.admin)
        self.assertEqual(RegistroAtividade.objects.get(entidade='pet', objeto_id=self.pet.pk).acao,
                         RegistroAtividade.Acao.APROVOU)

    def test_aprovacao_nao_republica_adotados_ou_ongs_nao_aprovadas(self):
        from ongs.models import Ong
        ong = Ong.objects.create(nome='ONG em análise', cidade='Recife', estado='PE', status='pendente')
        self.pet.status = Pet.Status.PENDENTE
        self.pet.ong = ong
        self.pet.save()
        url = reverse('admin:pets_pet_publicar', args=[self.pet.pk])
        self.client.post(url)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.PENDENTE)
        self.pet.ong = None
        self.pet.status = Pet.Status.ADOTADO
        self.pet.save()
        self.client.post(url)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.ADOTADO)

    def test_arquivamento_em_lote_registra_historico_e_preserva_adocao(self):
        adotado_em = timezone.now() - timedelta(hours=1)
        adotado = Pet.objects.create(
            nome='Luna', especie=Pet.Especie.GATO, cidade='Recife', estado='PE',
            status=Pet.Status.ADOTADO, adotado_em=adotado_em,
        )
        response = self.client.post(reverse('admin:pets_pet_changelist'), {
            'action': 'arquivar_selecionados', '_selected_action': [self.pet.pk, adotado.pk],
            'index': '0', 'select_across': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.pet.refresh_from_db()
        adotado.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.ARQUIVADO)
        self.assertEqual(adotado.status, Pet.Status.ARQUIVADO)
        self.assertEqual(adotado.adotado_em, adotado_em)
        self.assertEqual(LogEntry.objects.count(), 2)
        self.assertEqual(RegistroAtividade.objects.filter(acao=RegistroAtividade.Acao.ARQUIVOU).count(), 2)

    def test_get_nao_arquiva(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.PUBLICADO)

    def test_post_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.PUBLICADO)

    def test_conta_sem_acesso_admin_nao_arquiva(self):
        usuario = get_user_model().objects.create_user('equipe-arquivo', password='teste', is_staff=True)
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.PUBLICADO)

    def test_pet_inexistente_retorna_404(self):
        self.assertEqual(self.client.post(reverse('admin:pets_pet_arquivar', args=[999999])).status_code, 404)
