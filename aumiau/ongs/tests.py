from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from pets.models import Pet

from .forms import CadastroOngForm
from .models import Ong


class FluxosPublicosOngTests(TestCase):
    def setUp(self):
        consulta = patch('ongs.forms.consultar_cnpj', return_value={
            'razao_social': 'Organização de teste', 'situacao': 'ATIVA', 'consultado_em': timezone.now(),
        })
        self.consulta = consulta.start()
        self.addCleanup(consulta.stop)
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username='protetora', password='SenhaSegura123!', email='pessoal@example.com')
        cls.outro = get_user_model().objects.create_user(username='outro', password='SenhaSegura123!')

    def dados(self, **alteracoes):
        dados = {'nome': 'Patinhas Felizes', 'cnpj': '19.131.243/0001-97', 'estado': 'SP', 'cidade': 'Campinas', 'descricao': 'Cuidamos de animais resgatados.', 'email': 'CONTATO@example.com', 'telefone': '(19) 99999-1234'}
        dados.update(alteracoes)
        return dados

    def criar_ong(self, **alteracoes):
        dados = {'nome': 'Lar Amigo', 'estado': 'SP', 'cidade': 'Campinas', 'responsavel': self.usuario}
        dados.update(alteracoes)
        return Ong.objects.create(**dados)

    def criar_pet(self, ong, **alteracoes):
        dados = {'nome': 'Amora', 'especie': Pet.Especie.GATO, 'ong': ong, 'cidade': 'Campinas', 'estado': 'SP'}
        dados.update(alteracoes)
        return Pet.objects.create(**dados)

    def test_visitante_precisa_entrar_para_cadastrar_e_acessar_painel(self):
        for rota in ('ongs:cadastrar', 'ongs:painel'):
            with self.subTest(rota=rota):
                url = reverse(rota)
                self.assertRedirects(self.client.get(url), f"{reverse('usuarios:login')}?next={url}")

    def test_cadastro_pertence_ao_usuario_e_nao_aceita_aprovacao_forjada(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('ongs:cadastrar'), self.dados(
            responsavel=self.outro.pk, status=Ong.Status.APROVADA, aprovada='on', moderado_por=self.outro.pk,
        ))
        self.assertRedirects(resposta, reverse('ongs:painel'))
        ong = Ong.objects.get(nome='Patinhas Felizes')
        self.assertEqual(ong.responsavel, self.usuario)
        self.assertEqual(ong.status, Ong.Status.PENDENTE)
        self.assertFalse(ong.aprovada)
        self.assertIsNone(ong.moderado_por)
        self.assertEqual(ong.email, 'contato@example.com')
        self.assertEqual(ong.telefone, '19999991234')

    def test_contatos_opcionais_nao_copiam_dados_privados_da_conta(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse('ongs:cadastrar'), self.dados(email='', telefone=''))
        ong = Ong.objects.get()
        self.assertEqual(ong.email, '')
        self.assertEqual(ong.telefone, '')

    def test_formulario_invalido_preserva_valores_sem_cadastrar(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('ongs:cadastrar'), self.dados(email='invalido', telefone='abc', estado='XX'))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Ong.objects.exists())
        self.assertContains(resposta, 'Patinhas Felizes')
        self.assertEqual(set(resposta.context['form'].errors), {'email', 'telefone', 'estado'})

    def test_listagem_busca_filtro_e_contadores_usam_apenas_registros_publicos(self):
        ong = self.criar_ong(nome='Lar Amigo Campinas', status=Ong.Status.APROVADA)
        oculta = self.criar_ong(nome='ONG em análise')
        self.criar_ong(nome='ONG do Rio', cidade='Rio de Janeiro', estado='RJ', status=Ong.Status.APROVADA)
        self.criar_pet(ong, status=Pet.Status.PUBLICADO)
        self.criar_pet(ong, status=Pet.Status.ADOTADO)
        self.criar_pet(ong, status=Pet.Status.REJEITADO)
        self.criar_pet(oculta, status=Pet.Status.PUBLICADO)
        resposta = self.client.get(reverse('ongs:lista'), {'q': 'Campinas', 'regiao': 'SP'})
        self.assertContains(resposta, 'Lar Amigo Campinas')
        self.assertNotContains(resposta, 'ONG em análise')
        self.assertNotContains(resposta, 'ONG do Rio')
        self.assertEqual(resposta.context['total_ongs'], 2)
        self.assertEqual(resposta.context['total_pets'], 2)
        self.assertEqual(resposta.context['total_adocoes'], 1)
        self.assertEqual(resposta.context['ongs'][0].pets_disponiveis, 1)

    def test_paginacao_preserva_busca_e_regiao(self):
        for numero in range(9):
            self.criar_ong(nome=f'Rede Amiga {numero}', status=Ong.Status.APROVADA)
        resposta = self.client.get(reverse('ongs:lista'), {'q': 'Rede', 'regiao': 'SP'})
        self.assertEqual(len(resposta.context['ongs']), 8)
        self.assertContains(resposta, 'pagina=2&amp;q=Rede&amp;regiao=SP')
        segunda = self.client.get(reverse('ongs:lista'), {'q': 'Rede', 'regiao': 'SP', 'pagina': 2})
        self.assertEqual(len(segunda.context['ongs']), 1)

    def test_detalhe_pendente_e_restrito_ao_responsavel(self):
        ong = self.criar_ong()
        url = reverse('ongs:detalhe', args=[ong.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(url), 'Este perfil ainda não está público.')

    def test_detalhe_aprovado_so_mostra_pets_publicados(self):
        ong = self.criar_ong(status=Ong.Status.APROVADA, email='contato@example.com', telefone='11999991234')
        self.criar_pet(ong, nome='Amora disponível', status=Pet.Status.PUBLICADO)
        self.criar_pet(ong, nome='Pet ainda em análise')
        resposta = self.client.get(reverse('ongs:detalhe', args=[ong.pk]))
        self.assertContains(resposta, 'Amora disponível')
        self.assertNotContains(resposta, 'Pet ainda em análise')
        self.assertContains(resposta, 'mailto:contato@example.com')
        self.assertContains(resposta, 'tel:+5511999991234')

    def test_edicao_alheia_nao_altera_a_ong(self):
        ong = self.criar_ong()
        self.client.force_login(self.outro)
        url = reverse('ongs:editar', args=[ong.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.dados()).status_code, 404)
        ong.refresh_from_db()
        self.assertEqual(ong.nome, 'Lar Amigo')

    def test_edicao_reenvia_para_analise_e_oculta_perfil_e_pets(self):
        ong = self.criar_ong(status=Ong.Status.APROVADA, moderado_por=self.outro, moderado_em=timezone.now())
        pet = self.criar_pet(ong, status=Pet.Status.PUBLICADO)
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('ongs:editar', args=[ong.pk]), self.dados())
        self.assertRedirects(resposta, reverse('ongs:painel'))
        ong.refresh_from_db()
        self.assertEqual(ong.status, Ong.Status.PENDENTE)
        self.assertFalse(ong.aprovada)
        self.assertIsNone(ong.moderado_por)
        self.assertIsNone(ong.moderado_em)
        perfil = self.client.get(reverse('ongs:detalhe', args=[ong.pk]))
        self.assertQuerySetEqual(perfil.context['pets'], [])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('ongs:detalhe', args=[ong.pk])).status_code, 404)
        self.assertNotIn(pet, Pet.objects.publicos())

    def test_painel_exibe_somente_ongs_do_responsavel_e_seus_pets(self):
        minha = self.criar_ong(nome='Minha organização', status=Ong.Status.APROVADA)
        self.criar_pet(minha, nome='Pet da minha ONG')
        self.criar_ong(nome='Organização alheia', responsavel=self.outro)
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('ongs:painel'))
        self.assertContains(resposta, 'Minha organização')
        self.assertContains(resposta, 'Pet da minha ONG')
        self.assertNotContains(resposta, 'Organização alheia')
        self.assertContains(resposta, f"{reverse('pets:anunciar')}?ong={minha.pk}")

    def test_formulario_nao_expoe_campos_de_moderacao_ou_proprietario(self):
        self.assertEqual(set(CadastroOngForm().fields), {'nome', 'cnpj', 'foto', 'estado', 'cidade', 'descricao', 'email', 'telefone'})

    def test_upload_de_foto_publica_e_recusa_de_arquivo_invalido(self):
        self.client.force_login(self.usuario)
        imagem = BytesIO()
        Image.new('RGB', (24, 24), 'purple').save(imagem, format='JPEG')
        foto = SimpleUploadedFile('ong.jpg', imagem.getvalue(), content_type='image/jpeg')
        resposta = self.client.post(reverse('ongs:cadastrar'), self.dados(foto=foto))
        self.assertEqual(resposta.status_code, 302)
        ong = Ong.objects.get()
        self.assertTrue(ong.foto.storage.exists(ong.foto.name))
        nome_foto = ong.foto.name
        invalido = SimpleUploadedFile('falso.jpg', b'isto nao e uma imagem', content_type='image/jpeg')
        resposta = self.client.post(reverse('ongs:editar', args=[ong.pk]), self.dados(foto=invalido))
        self.assertIn('foto', resposta.context['form'].errors)
        ong.refresh_from_db()
        self.assertEqual(ong.foto.name, nome_foto)

    def test_ong_demo_editavel_sem_consultar_documento_real(self):
        ong = self.criar_ong(codigo_demonstracao='demo-ong-teste')
        form = CadastroOngForm(self.dados(cnpj=''), instance=ong)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().cnpj)
        self.consulta.assert_not_called()
        form = CadastroOngForm(self.dados(), instance=ong)
        self.assertFalse(form.is_valid())
        self.assertIn('cnpj', form.errors)

    def test_cnpj_obrigatorio_e_unico_e_nao_aceita_digito_invalido(self):
        self.criar_ong(cnpj='19131243000197')
        for cnpj in ('', '19.131.243/0001-97', '19131243000198', '00000000000000'):
            with self.subTest(cnpj=cnpj):
                form = CadastroOngForm(self.dados(cnpj=cnpj))
                self.assertFalse(form.is_valid())
                self.assertIn('cnpj', form.errors)
        self.consulta.assert_not_called()

    def test_consulta_indisponivel_nao_salva_nem_declara_verificado(self):
        from django.core.exceptions import ValidationError
        self.consulta.side_effect = ValidationError('Consulta indisponível.')
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('ongs:cadastrar'), self.dados())
        self.assertContains(resposta, 'Consulta indisponível.')
        self.assertContains(resposta, 'Patinhas Felizes')
        self.assertFalse(Ong.objects.exists())

    def test_metadados_da_validacao_vem_da_consulta_nao_do_post(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse('ongs:cadastrar'), self.dados(
            razao_social='Forjada', cnpj_confirmado_manualmente='on', cnpj_situacao='Forjada',
        ))
        ong = Ong.objects.get()
        self.assertEqual(ong.cnpj, '19131243000197')
        self.assertEqual(ong.razao_social, 'Organização de teste')
        self.assertEqual(ong.cnpj_situacao, 'ATIVA')
        self.assertFalse(ong.cnpj_confirmado_manualmente)
        self.assertIsNotNone(ong.cnpj_consultado_em)

    def test_cnpj_alfanumerico_fica_pendente_de_conferencia_documental(self):
        self.consulta.return_value = None
        self.client.force_login(self.usuario)
        self.client.post(reverse('ongs:cadastrar'), self.dados(cnpj='00.000.000/E08G-12'))
        ong = Ong.objects.get()
        self.assertEqual(ong.status, Ong.Status.PENDENTE)
        self.assertTrue(ong.cnpj_requer_conferencia)
        self.assertIsNone(ong.cnpj_consultado_em)

    def test_supervisor_precisa_confirmar_conferencia_cnpj_alfanumerico(self):
        from django.contrib.auth.models import Group
        from supervisores.permissions import GRUPO_SUPERVISORES
        grupo = Group.objects.get(name=GRUPO_SUPERVISORES)
        self.outro.groups.add(grupo)
        ong = self.criar_ong(cnpj='00000000E08G12')
        self.client.force_login(self.outro)
        url = reverse('supervisores:moderar_ong', args=[ong.pk, 'aprovar'])
        self.client.post(url)
        ong.refresh_from_db()
        self.assertEqual(ong.status, Ong.Status.PENDENTE)
        self.assertFalse(ong.cnpj_confirmado_manualmente)
        self.client.post(url, {'confirmar_cnpj': '1'})
        ong.refresh_from_db()
        self.assertEqual(ong.status, Ong.Status.APROVADA)
        self.assertTrue(ong.cnpj_confirmado_manualmente)
        self.assertIsNone(ong.cnpj_consultado_em)
