from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from adocoes.models import ChamadoAjuda
from pets.models import Pet

from .models import RegistroAtividade
from .permissions import GRUPO_SUPERVISORES


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AtendimentoChamadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model().objects
        cls.autor = usuarios.create_user('autor-chamado', email='autor@example.com')
        cls.outro = usuarios.create_user('outro-usuario')
        cls.supervisor = usuarios.create_user('supervisor-chamado')
        cls.grupo = Group.objects.get(name=GRUPO_SUPERVISORES)
        cls.supervisor.groups.add(cls.grupo)
        cls.admin = usuarios.create_superuser('admin-chamado', 'admin@example.com', 'teste')
        cls.pet = Pet.objects.create(nome='Amora', especie='gato', cidade='Recife', estado='PE')
        cls.chamado = ChamadoAjuda.objects.create(
            usuario=cls.autor, pet=cls.pet, categoria='cadastro',
            assunto='Não consigo atualizar meu anúncio', mensagem='Preciso de ajuda com a Amora.',
            contexto_pluttu='Usuário: Como editar meu pet?\nPluttu: Abra Meus anúncios.',
        )

    def setUp(self):
        self.client.force_login(self.supervisor)
        self.lista_url = reverse('supervisores:chamados_lista')
        self.detalhe_url = reverse('supervisores:chamado_detalhe', args=[self.chamado.pk])

    def test_grupo_recebe_permissoes_de_atendimento(self):
        self.assertTrue(self.supervisor.has_perms([
            'adocoes.view_chamadoajuda', 'adocoes.change_chamadoajuda',
        ]))
        self.assertFalse(self.supervisor.has_perm('adocoes.delete_chamadoajuda'))

    def test_supervisor_encontra_chamado_menu_e_dashboard(self):
        response = self.client.get(reverse('supervisores:dashboard'))
        self.assertContains(response, f'href="{self.lista_url}"')
        self.assertContains(response, f'href="{self.lista_url}?status=pendentes"')
        self.assertEqual(response.context['chamados_pendentes'], 1)
        response = self.client.get(self.lista_url)
        self.assertContains(response, self.chamado.assunto)
        response = self.client.get(self.detalhe_url)
        self.assertContains(response, 'Conversa encaminhada do Pluttu')
        self.assertContains(response, 'Como editar meu pet?')
        self.assertContains(response, 'Salvar atendimento')
        self.assertContains(response, reverse('supervisores:pet_detalhe', args=[self.pet.pk]))

    def test_resposta_fica_disponivel_apenas_para_autor_e_equipe(self):
        texto = 'Abra Meus anúncios e selecione Editar no cadastro da Amora.'
        response = self.client.post(self.detalhe_url, {'status': 'aberto', 'resposta': texto})
        self.assertRedirects(response, self.detalhe_url)
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.resposta, texto)
        self.assertEqual(self.chamado.status, ChamadoAjuda.Status.RESPONDIDO)
        self.assertTrue(RegistroAtividade.objects.filter(
            entidade='chamado', objeto_id=self.chamado.pk, supervisor=self.supervisor,
        ).exists())
        self.client.force_login(self.autor)
        url = reverse('chamado_detalhe', args=[self.chamado.pk])
        self.assertContains(self.client.get(url), texto)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_situacao_respondido_exige_resposta(self):
        response = self.client.post(self.detalhe_url, {'status': 'respondido', 'resposta': ' '})
        self.assertContains(response, 'Escreva a resposta antes de marcar')
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.status, ChamadoAjuda.Status.ABERTO)
        self.assertEqual(self.chamado.resposta, '')

    def test_pode_analisar_encerrar_e_reabrir(self):
        for status in ('em_analise', 'encerrado', 'aberto'):
            with self.subTest(status=status):
                response = self.client.post(self.detalhe_url, {'status': status, 'resposta': ''})
                self.assertRedirects(response, self.detalhe_url)
                self.chamado.refresh_from_db()
                self.assertEqual(self.chamado.status, status)

    def test_visitante_e_usuario_comum_nao_acessam_atendimento(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.lista_url).status_code, 302)
        self.client.force_login(self.autor)
        self.assertEqual(self.client.get(self.lista_url).status_code, 403)
        self.assertEqual(self.client.get(self.detalhe_url).status_code, 403)
        self.assertEqual(self.client.post(self.detalhe_url, {
            'status': 'respondido', 'resposta': 'Tentativa não autorizada',
        }).status_code, 403)
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.resposta, '')

    def test_permissao_so_de_leitura_nao_permite_resposta(self):
        self.grupo.permissions.remove(Permission.objects.get(
            content_type__app_label='adocoes', codename='change_chamadoajuda',
        ))
        response = self.client.get(self.detalhe_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Salvar atendimento')
        self.assertEqual(self.client.post(self.detalhe_url, {
            'status': 'respondido', 'resposta': 'Tentativa não autorizada',
        }).status_code, 403)
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.resposta, '')

    def test_sem_permissao_de_visualizar_oculta_menu_e_bloqueia_acesso(self):
        self.grupo.permissions.remove(Permission.objects.get(
            content_type__app_label='adocoes', codename='view_chamadoajuda',
        ))
        self.assertEqual(self.client.get(self.lista_url).status_code, 403)
        self.assertEqual(self.client.get(self.detalhe_url).status_code, 403)
        response = self.client.get(reverse('supervisores:dashboard'))
        self.assertNotContains(response, f'href="{self.lista_url}"')
        self.assertFalse(response.context['pode_ver_chamados'])

    def test_busca_filtro_e_paginacao(self):
        ChamadoAjuda.objects.bulk_create([
            ChamadoAjuda(usuario=self.autor, categoria='cadastro', assunto=f'Atualizar anúncio {i}',
                         mensagem='Ajuda', status='em_analise')
            for i in range(13)
        ])
        ChamadoAjuda.objects.create(usuario=self.autor, categoria='cadastro', assunto='Resolvido',
                                    mensagem='Tudo certo', resposta='Resolvido', status='respondido')
        response = self.client.get(self.lista_url, {'status': 'pendentes', 'busca': 'anúncio'})
        self.assertEqual(response.context['total_resultados'], 14)
        self.assertEqual(len(response.context['chamados']), 12)
        self.assertContains(response, 'busca=an%C3%BAncio&amp;status=pendentes')
        response = self.client.get(self.lista_url, {'status': 'pendentes', 'busca': 'anúncio', 'pagina': 2})
        self.assertEqual(len(response.context['chamados']), 2)
        # A busca também encontra o número nos assuntos; deve incluir o ID exato.
        response = self.client.get(self.lista_url, {'busca': str(self.chamado.pk)})
        self.assertIn(self.chamado.pk, [chamado.pk for chamado in response.context['chamados']])

    def test_admin_menu_dashboard_filtro_e_resposta(self):
        self.client.force_login(self.admin)
        admin_lista = reverse('admin:adocoes_chamadoajuda_changelist')
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, f'href="{admin_lista}"')
        self.assertEqual(response.context['chamados_pendentes'], 1)
        response = self.client.get(admin_lista, {'status__in': 'aberto,em_analise'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cl'].result_count, 1)
        admin_detalhe = reverse('admin:adocoes_chamadoajuda_change', args=[self.chamado.pk])
        response = self.client.post(admin_detalhe, {'status': 'aberto', 'resposta': 'Resposta pelo admin.', '_save': 'Salvar'})
        self.assertRedirects(response, admin_lista)
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.status, ChamadoAjuda.Status.RESPONDIDO)
        self.assertEqual(self.chamado.resposta, 'Resposta pelo admin.')
        self.client.force_login(self.autor)
        self.assertContains(self.client.get(reverse('chamado_detalhe', args=[self.chamado.pk])), 'Resposta pelo admin.')

    def test_admin_tambem_valida_resposta_vazia(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:adocoes_chamadoajuda_change', args=[self.chamado.pk]), {
            'status': 'respondido', 'resposta': '', '_save': 'Salvar',
        })
        self.assertContains(response, 'Escreva a resposta antes de marcar')
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.status, ChamadoAjuda.Status.ABERTO)
