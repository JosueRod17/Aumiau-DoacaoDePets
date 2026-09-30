from io import StringIO
from hashlib import sha256

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from ongs.models import Ong
from .models import Pet
from .management.commands.popular_demo import DESCRICOES_ANTERIORES


@override_settings(AUMIAU_DATA_MODE='local')
class CadastrosDemonstracaoTests(TestCase):
    def popular(self):
        call_command('popular_demo', stdout=StringIO())

    def test_cria_fotos_sem_duplicar_ou_sobrescrever_edicoes(self):
        real = Pet.objects.create(nome='Cadastro existente', especie='gato', cidade='Natal', estado='RN')
        self.popular()
        self.assertEqual(Pet.objects.filter(codigo_demonstracao__isnull=False).count(), 12)
        self.assertEqual(Ong.objects.count(), 3)
        nomes_fotos = list(Pet.objects.exclude(pk=real.pk).values_list('foto_principal', flat=True))
        for pet in Pet.objects.exclude(pk=real.pk):
            self.assertTrue(pet.foto_principal.storage.exists(pet.foto_principal.name))
            self.assertFalse(pet.email_contato or pet.telefone_contato)
        for ong in Ong.objects.all():
            self.assertTrue(ong.foto.storage.exists(ong.foto.name))
            self.assertIsNone(ong.cnpj)
            self.assertFalse(ong.email or ong.telefone or ong.cnpj_confirmado_manualmente)
        editado = Pet.objects.get(codigo_demonstracao='demo-pet-01')
        editado.nome = 'Nome ajustado no painel'
        editado.descricao = 'Descrição ajustada no painel.'
        editado.save()
        ong_editada = Ong.objects.get(codigo_demonstracao='demo-ong-sp')
        ong_editada.descricao = 'Descrição da ONG ajustada no painel.'
        ong_editada.save(update_fields=['descricao'])
        self.popular()
        editado.refresh_from_db()
        ong_editada.refresh_from_db()
        real.refresh_from_db()
        self.assertEqual(editado.nome, 'Nome ajustado no painel')
        self.assertEqual(editado.descricao, 'Descrição ajustada no painel.')
        self.assertEqual(ong_editada.descricao, 'Descrição da ONG ajustada no painel.')
        self.assertEqual(real.nome, 'Cadastro existente')
        self.assertEqual(Pet.objects.count(), 13)
        self.assertEqual(nomes_fotos, list(Pet.objects.exclude(pk=real.pk).values_list('foto_principal', flat=True)))

    def test_atualiza_somente_texto_padrao_antigo(self):
        self.popular()
        pet = Pet.objects.get(codigo_demonstracao='demo-pet-01')
        descricao_atual = pet.descricao
        descricao_antiga = (
            'Exemplo fictício: Paçoca é uma companheira tranquila que adora acompanhar a rotina da casa e descansar '
            'depois dos passeios. Ela gosta de conhecer pessoas com calma e de brincadeiras com brinquedos macios. '
            'Sua futura família, nesta história de demonstração, teria tempo para passeios diários e adaptação gradual. '
            'Foto ilustrativa; não há animal disponível neste anúncio.'
        )
        self.assertEqual(
            sha256(descricao_antiga.encode('utf-8')).hexdigest(),
            DESCRICOES_ANTERIORES['demo-pet-01']['descricao'],
        )
        pet.descricao = descricao_antiga
        pet.save(update_fields=['descricao'])
        self.popular()
        pet.refresh_from_db()
        self.assertEqual(pet.descricao, descricao_atual)

    def test_pets_publicados_tem_contato_e_pendentes_continuam_privados(self):
        self.popular()
        pet = Pet.objects.get(codigo_demonstracao='demo-pet-01')
        response = self.client.get(reverse('pets:detalhe', args=[pet.pk]))
        self.assertContains(response, 'id="contato"')
        self.assertNotContains(response, 'Pet fictício de demonstração')
        self.assertNotContains(self.client.get(reverse('ongs:detalhe', args=[pet.ong_id])), 'Perfil fictício de demonstração')
        self.assertNotContains(self.client.get(reverse('ongs:lista')), 'Demonstração')
        pendente = Pet.objects.filter(codigo_demonstracao__isnull=False, status=Pet.Status.PENDENTE).first()
        self.assertEqual(self.client.get(reverse('pets:detalhe', args=[pendente.pk])).status_code, 404)
        self.assertEqual(Pet.objects.publicos().count(), 9)

    @override_settings(AUMIAU_DATA_MODE='shared')
    def test_nao_popula_banco_compartilhado(self):
        with self.assertRaises(CommandError):
            self.popular()
        self.assertFalse(Pet.objects.exists())
