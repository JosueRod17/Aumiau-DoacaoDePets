from io import BytesIO
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ongs.models import Ong
from .models import FotoPet, Pet
from .forms import PetForm


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FluxosPublicosPetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user('protetor', password='teste')
        cls.outro = get_user_model().objects.create_user('outro', password='teste')
        cls.ong = Ong.objects.create(nome='ONG de teste', responsavel=cls.usuario, cidade='Campinas', estado='SP', status=Ong.Status.APROVADA, email='ong@example.com')

    def setUp(self):
        self.arquivos = TemporaryDirectory(prefix='aumiau-test-media-')
        self.addCleanup(self.arquivos.cleanup)
        config = override_settings(MEDIA_ROOT=self.arquivos.name)
        config.enable()
        self.addCleanup(config.disable)
        self.client.force_login(self.usuario)

    def foto(self, formato='PNG'):
        arquivo = BytesIO()
        Image.new('RGB', (30, 30), 'orange').save(arquivo, format=formato)
        return SimpleUploadedFile(f'pet.{formato.lower()}', arquivo.getvalue(), content_type=f'image/{formato.lower()}')

    def dados(self, **alteracoes):
        return {
            'nome': 'Amora', 'especie': 'gato', 'raca': 'Sem raça definida', 'genero': 'femea',
            'porte': 'pequeno', 'idade_anos': '1', 'idade_meses': '4',
            'nascimento_desconhecido': 'on',
            'cidade': 'Campinas', 'estado': 'SP', 'descricao': 'Uma gatinha que gosta de companhia.',
            'email_contato': 'contato@example.com', 'confirmar': 'on', 'acao': 'enviar',
        } | alteracoes

    def pet(self, **alteracoes):
        return Pet.objects.create(**{
            'nome': 'Amora', 'especie': 'gato', 'genero': 'femea', 'porte': 'pequeno',
            'idade_anos': 1, 'cidade': 'Campinas', 'estado': 'SP', 'descricao': 'Muito carinhosa.',
            'responsavel': self.usuario, 'criado_por': self.usuario, 'email_contato': 'contato@example.com',
        } | alteracoes)

    def test_envio_salva_fotos_e_nao_aceita_status_ou_dono_forjados(self):
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(
            foto_principal=self.foto(), galeria=[self.foto(), self.foto()],
            status='publicado', destaque='on', responsavel=self.outro.pk, criado_por=self.outro.pk,
        ))
        self.assertRedirects(resposta, reverse('pets:meus_pets'))
        pet = Pet.objects.get()
        self.assertEqual(pet.responsavel, self.usuario)
        self.assertEqual(pet.criado_por, self.usuario)
        self.assertEqual(pet.status, Pet.Status.PENDENTE)
        self.assertFalse(pet.destaque)
        self.assertEqual(pet.fotos.count(), 2)
        self.assertTrue(pet.foto_principal.storage.exists(pet.foto_principal.name))

    def test_pendente_so_e_visivel_ao_responsavel(self):
        pet = self.pet()
        self.assertEqual(self.client.get(reverse('pets:detalhe', args=[pet.pk])).status_code, 200)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('pets:detalhe', args=[pet.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('pets:lista')), 'Amora')

    def test_anuncio_da_ong_tem_apenas_um_responsavel(self):
        self.client.post(reverse('pets:anunciar'), self.dados(ong=self.ong.pk, foto_principal=self.foto()))
        pet = Pet.objects.get()
        self.assertEqual(pet.ong, self.ong)
        self.assertIsNone(pet.responsavel)
        self.assertEqual(pet.email_contato, '')

    def test_ong_alheia_ou_nao_aprovada_e_bloqueada(self):
        alheia = Ong.objects.create(nome='Outra ONG', responsavel=self.outro, cidade='Campinas', estado='SP', status=Ong.Status.APROVADA)
        pendente = Ong.objects.create(nome='Nova ONG', responsavel=self.usuario, cidade='Campinas', estado='SP')
        for ong in (alheia, pendente):
            resposta = self.client.post(reverse('pets:anunciar'), self.dados(ong=ong.pk, foto_principal=self.foto()))
            self.assertIn('ong', resposta.context['form'].errors)
        self.assertFalse(Pet.objects.exists())

    def test_ong_precisa_de_contato_para_receber_interessados(self):
        self.ong.email = ''
        self.ong.save()
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(ong=self.ong.pk, foto_principal=self.foto()))
        self.assertIn('ong', resposta.context['form'].errors)
        self.assertFalse(Pet.objects.exists())

    def test_upload_invalido_nao_persiste_pet(self):
        for arquivo in (SimpleUploadedFile('fake.png', b'nao sou uma imagem', content_type='image/png'), self.foto('GIF')):
            resposta = self.client.post(reverse('pets:anunciar'), self.dados(foto_principal=arquivo))
            self.assertIn('foto_principal', resposta.context['form'].errors)
        self.assertFalse(Pet.objects.exists())

    def test_imagem_grande_e_galeria_excedente_sao_rejeitadas(self):
        imagem = SimpleUploadedFile('grande.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png')
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(foto_principal=imagem))
        self.assertIn('foto_principal', resposta.context['form'].errors)
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(foto_principal=self.foto(), galeria=[self.foto() for _ in range(7)]))
        self.assertIn('galeria', resposta.context['form'].errors)
        self.assertFalse(Pet.objects.exists())

    def test_rascunho_nao_exige_foto_historia_ou_contato(self):
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(acao='rascunho', descricao='', email_contato='', confirmar=''))
        self.assertRedirects(resposta, reverse('pets:meus_pets'))
        self.assertEqual(Pet.objects.get().status, Pet.Status.RASCUNHO)

    def test_edicao_de_publicado_exige_nova_analise(self):
        pet = self.pet(status=Pet.Status.PUBLICADO, foto_principal=self.foto(), publicado_em=timezone.now(), destaque=True)
        resposta = self.client.post(reverse('pets:editar', args=[pet.pk]), self.dados(nome='Novo nome'))
        self.assertRedirects(resposta, reverse('pets:meus_pets'))
        pet.refresh_from_db()
        self.assertEqual(pet.status, Pet.Status.PENDENTE)
        self.assertIsNone(pet.publicado_em)
        self.assertFalse(pet.destaque)

    def test_edicao_alheia_e_transferencia_de_responsavel(self):
        pet = self.pet(responsavel=self.outro)
        resposta = self.client.post(reverse('pets:editar', args=[pet.pk]), self.dados())
        self.assertEqual(resposta.status_code, 404)
        pet.refresh_from_db()
        self.assertEqual(pet.responsavel, self.outro)

    def test_foto_alheia_nao_pode_ser_removida(self):
        pet = self.pet(foto_principal=self.foto())
        outro_pet = self.pet(responsavel=self.outro)
        foto = FotoPet.objects.create(pet=outro_pet, imagem=self.foto())
        resposta = self.client.post(reverse('pets:editar', args=[pet.pk]), self.dados(remover_fotos=[foto.pk]))
        self.assertIn('remover_fotos', resposta.context['form'].errors)
        self.assertTrue(FotoPet.objects.filter(pk=foto.pk).exists())

    def test_pet_adotado_nao_volta_para_analise_por_edicao(self):
        pet = self.pet(status=Pet.Status.ADOTADO)
        self.client.post(reverse('pets:editar', args=[pet.pk]), self.dados(foto_principal=self.foto()))
        pet.refresh_from_db()
        self.assertEqual(pet.status, Pet.Status.ADOTADO)

    def test_filtros_localizacao_saude_e_paginacao(self):
        for indice in range(11):
            self.pet(nome=f'Gato {indice}', status=Pet.Status.PUBLICADO, microchipado=True)
        self.pet(nome='Fora da busca', estado='RJ', status=Pet.Status.PUBLICADO)
        resposta = self.client.get(reverse('pets:lista'), {'localizacao': 'SP', 'microchipado': '1', 'idade': 'jovem', 'page': '2'})
        self.assertEqual(resposta.context['page_obj'].paginator.count, 11)
        self.assertEqual(len(resposta.context['pets']), 2)
        self.assertIn('localizacao=SP', resposta.context['querystring'])

    def test_ong_suspensa_oculta_pet_publicado(self):
        pet = self.pet(ong=self.ong, responsavel=None, status=Pet.Status.PUBLICADO)
        self.ong.status = Ong.Status.SUSPENSA
        self.ong.save()
        self.client.logout()
        self.assertEqual(self.client.get(reverse('pets:detalhe', args=[pet.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('pets:lista')).context['page_obj'].paginator.count, 0)

    def test_meus_anuncios_preserva_status_na_paginacao(self):
        for indice in range(13):
            self.pet(nome=f'Pet {indice}')
        resposta = self.client.get(reverse('pets:meus_pets'), {'status': 'pendente', 'page': 2})
        self.assertEqual(len(resposta.context['page_obj']), 1)
        self.assertEqual(resposta.context['querystring'], 'status=pendente')

    def test_racas_sao_validadas_por_especie_e_tipo_nao_catalogado_e_preservado(self):
        invalida = self.client.post(reverse('pets:anunciar'), self.dados(raca='Labrador', foto_principal=self.foto()))
        self.assertIn('raca', invalida.context['form'].errors)
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(especie='coelho', raca='__outra__', raca_outra='Raça local', foto_principal=self.foto()))
        self.assertRedirects(resposta, reverse('pets:meus_pets'))
        self.assertEqual(Pet.objects.get().raca, 'Raça local')
        formulario = PetForm(instance=Pet.objects.get(), usuario=self.usuario)
        self.assertEqual(formulario.initial['raca'], '__outra__')
        self.assertEqual(formulario.initial['raca_outra'], 'Raça local')

    def test_data_nascimento_calcula_idade_atual_e_preserva_estimativa_legada(self):
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(
            nascimento_desconhecido='', data_nascimento='2024-03-15', idade_anos='', idade_meses='', foto_principal=self.foto(),
        ))
        self.assertRedirects(resposta, reverse('pets:meus_pets'))
        pet = Pet.objects.get()
        self.assertEqual(pet.data_nascimento, date(2024, 3, 15))
        with patch('pets.models.timezone.localdate', return_value=date(2026, 9, 14)):
            self.assertEqual(pet.idade_formatada, '2 anos e 5 meses')
        legado = self.pet(idade_anos=3, idade_meses=2)
        self.assertEqual(legado.idade_formatada, '3 anos e 2 meses')
        self.assertIsNone(legado.data_nascimento)

    def test_data_futura_ou_ausente_e_estimativa_ausente_sao_rejeitadas(self):
        for nascimento in ('', (timezone.localdate() + timedelta(days=1)).isoformat()):
            resposta = self.client.post(reverse('pets:anunciar'), self.dados(
                nascimento_desconhecido='', data_nascimento=nascimento, foto_principal=self.foto(),
            ))
            self.assertIn('data_nascimento', resposta.context['form'].errors)
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(idade_anos='', idade_meses='', foto_principal=self.foto()))
        self.assertIn('idade_anos', resposta.context['form'].errors)
        self.assertFalse(Pet.objects.exists())

    def test_estimativa_zero_significa_menos_de_um_mes(self):
        self.client.post(reverse('pets:anunciar'), self.dados(idade_anos='0', idade_meses='0', foto_principal=self.foto()))
        self.assertEqual(Pet.objects.get().idade_formatada, 'Menos de 1 mês (aprox.)')

    def test_porte_nao_informado_nao_e_opcao_publica_ou_aceito_no_post(self):
        form = self.client.get(reverse('pets:anunciar')).context['form']
        self.assertNotIn('nao_informado', dict(form.fields['porte'].choices))
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(porte='nao_informado', foto_principal=self.foto()))
        self.assertIn('porte', resposta.context['form'].errors)
        legado = self.pet(porte='nao_informado')
        self.assertEqual(legado.porte, 'nao_informado')

    def test_envio_assincrono_valida_sem_redirect_e_reenvio_salva_fotos(self):
        foto = self.foto()
        galeria = self.foto()
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(nome='', foto_principal=foto, galeria=[galeria]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resposta.status_code, 422)
        self.assertIn('nome', resposta.json()['errors'])
        self.assertNotIn('foto_principal', resposta.json()['errors'])
        self.assertFalse(Pet.objects.exists())
        foto.seek(0)
        galeria.seek(0)
        resposta = self.client.post(reverse('pets:anunciar'), self.dados(foto_principal=foto, galeria=[galeria]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['redirect_url'], reverse('pets:meus_pets'))
        self.assertEqual(Pet.objects.get().fotos.count(), 1)

    def test_email_abre_clientes_com_destinatario_e_assunto_codificados(self):
        pet = self.pet(nome='Amora & Mel', email_contato='pessoa+pet@example.com', status=Pet.Status.PUBLICADO)
        resposta = self.client.get(reverse('pets:detalhe', args=[pet.pk]))
        for campo in ('gmail_url', 'outlook_url'):
            params = parse_qs(urlsplit(resposta.context[campo]).query)
            self.assertEqual(params['to'], ['pessoa+pet@example.com'])
            self.assertIn('Amora & Mel', (params.get('su') or params.get('subject'))[0])
        self.assertContains(resposta, 'Abrir no Gmail')
        self.assertContains(resposta, 'Abrir no Outlook')

    def test_filtro_idade_usa_nascimento_em_vez_de_estimativa_desatualizada(self):
        self.pet(data_nascimento=date(2024, 9, 28), idade_anos=30, status=Pet.Status.PUBLICADO)
        with patch('pets.views.timezone.localdate', return_value=date(2026, 9, 28)):
            self.assertEqual(self.client.get(reverse('pets:lista'), {'idade': 'jovem'}).context['page_obj'].paginator.count, 1)
            self.assertEqual(self.client.get(reverse('pets:lista'), {'idade': 'idoso'}).context['page_obj'].paginator.count, 0)

    def test_status_publico_mostra_em_analise_sem_alterar_valor_persistido(self):
        self.pet()
        resposta = self.client.get(reverse('pets:meus_pets'))
        self.assertContains(resposta, 'Em análise')
        self.assertNotContains(resposta, '>Pendente<')

    def test_filtro_outros_inclui_especies_especificas_e_nao_cachorro(self):
        coelho = self.pet(especie='coelho', status=Pet.Status.PUBLICADO)
        self.pet(especie='cachorro', status=Pet.Status.PUBLICADO)
        resposta = self.client.get(reverse('pets:lista'), {'especie': 'outros'})
        self.assertEqual(list(resposta.context['pets']), [coelho])
