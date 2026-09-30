from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from pets.models import Pet
from ongs.models import Ong

from .forms import FotoPetSupervisorFormSet, PetSupervisorForm
from .models import RegistroAtividade
from .permissions import GRUPO_SUPERVISORES


class AcessoSupervisorTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.usuario = Usuario.objects.create_user(
            username='usuario@example.com',
            email='usuario@example.com',
            password='senha-segura-123',
        )

    def test_visitante_e_redirecionado_para_login(self):
        resposta = self.client.get(
            reverse('supervisores:dashboard'),
        )

        self.assertRedirects(
            resposta,
            f"{reverse('home')}?next=%2Fsupervisor%2F",
            fetch_redirect_response=False,
        )

    def test_usuario_comum_recebe_403(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse('supervisores:dashboard'),
        )

        self.assertEqual(resposta.status_code, 403)

    def test_integrante_do_grupo_acessa_dashboard(self):
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.usuario.groups.add(grupo)
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse('supervisores:dashboard'),
        )

        self.assertEqual(resposta.status_code, 200)

    def test_supervisor_nao_acessa_django_admin(self):
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.usuario.groups.add(grupo)
        self.usuario.is_staff = True
        self.usuario.save(update_fields=['is_staff'])
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse('admin:index'))

        self.assertRedirects(
            resposta,
            f"{reverse('admin:login')}?next=%2Fadmin%2F",
            fetch_redirect_response=False,
        )

    def test_superuser_acessa_os_dois_paineis(self):
        Usuario = get_user_model()
        superusuario = Usuario.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='senha-segura-123',
        )
        self.client.force_login(superusuario)

        resposta_supervisor = self.client.get(
            reverse('supervisores:dashboard'),
        )
        resposta_admin = self.client.get(reverse('admin:index'))

        self.assertEqual(resposta_supervisor.status_code, 200)
        self.assertEqual(resposta_admin.status_code, 200)

    def test_supervisor_pode_publicar_pet(self):
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.usuario.groups.add(grupo)
        self.client.force_login(self.usuario)

        pet = Pet.objects.create(
            nome='Bolinha',
            especie=Pet.Especie.CACHORRO,
            cidade='São Paulo',
            estado='SP',
            responsavel=self.usuario,
            criado_por=self.usuario,
        )

        detalhe = self.client.get(
            reverse(
                'supervisores:pet_detalhe',
                args=[pet.pk],
            )
        )

        resposta = self.client.post(
            reverse(
                'supervisores:moderar_pet',
                args=[pet.pk, 'publicar'],
            )
        )

        pet.refresh_from_db()

        self.assertEqual(detalhe.status_code, 200)
        self.assertRedirects(
            resposta,
            reverse(
                'supervisores:pet_detalhe',
                args=[pet.pk],
            ),
        )
        self.assertEqual(pet.status, Pet.Status.PUBLICADO)
        self.assertEqual(pet.moderado_por, self.usuario)
        self.assertIsNotNone(pet.publicado_em)

    def test_login_supervisor_redireciona_para_painel(self):
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.usuario.groups.add(grupo)

        resposta = self.client.post(
            reverse('usuarios:login'),
            {
                'username': self.usuario.username,
                'password': 'senha-segura-123',
            },
        )

        self.assertRedirects(
            resposta,
            reverse('supervisores:dashboard'),
            fetch_redirect_response=False,
        )

    def test_supervisor_pode_aprovar_ong(self):
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.usuario.groups.add(grupo)
        self.client.force_login(self.usuario)

        ong = Ong.objects.create(
            nome='Amigos dos Animais',
            cidade='São Paulo',
            estado='SP',
        )

        resposta = self.client.post(
            reverse(
                'supervisores:moderar_ong',
                args=[ong.pk, 'aprovar'],
            )
        )

        ong.refresh_from_db()

        self.assertRedirects(
            resposta,
            reverse(
                'supervisores:ong_detalhe',
                args=[ong.pk],
            ),
        )
        self.assertTrue(ong.aprovada)
        self.assertEqual(ong.status, Ong.Status.APROVADA)


class FluxosSupervisorTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.supervisor = Usuario.objects.create_user(
            username='supervisor@example.com',
            email='supervisor@example.com',
            password='senha-segura-123',
        )
        self.usuario = Usuario.objects.create_user(
            username='tutor@example.com',
            email='tutor@example.com',
            password='senha-segura-123',
        )
        grupo, _ = Group.objects.get_or_create(
            name=GRUPO_SUPERVISORES,
        )
        self.supervisor.groups.add(grupo)
        self.client.force_login(self.supervisor)

    def criar_pet(self, **dados):
        padrao = {
            'nome': 'Paçoca',
            'especie': Pet.Especie.CACHORRO,
            'cidade': 'Recife',
            'estado': 'PE',
            'responsavel': self.usuario,
            'criado_por': self.usuario,
        }
        padrao.update(dados)
        return Pet.objects.create(**padrao)

    def test_telas_novas_do_supervisor_abrem(self):
        pet = self.criar_pet()
        ong = Ong.objects.create(
            nome='Patinhas Felizes',
            cidade='Recife',
            estado='PE',
        )

        urls = (
            reverse('supervisores:pet_criar'),
            reverse('supervisores:pet_editar', args=[pet.pk]),
            reverse('supervisores:ong_criar'),
            reverse('supervisores:ong_editar', args=[ong.pk]),
            reverse('supervisores:ong_detalhe', args=[ong.pk]),
            reverse(
                'supervisores:usuario_detalhe',
                args=[self.usuario.pk],
            ),
            reverse('supervisores:atividades_lista'),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_transicao_invalida_de_pet_e_bloqueada(self):
        pet = self.criar_pet()

        resposta = self.client.post(
            reverse(
                'supervisores:moderar_pet',
                args=[pet.pk, 'adotar'],
            )
        )
        pet.refresh_from_db()

        self.assertRedirects(
            resposta,
            reverse('supervisores:pet_detalhe', args=[pet.pk]),
        )
        self.assertEqual(pet.status, Pet.Status.PENDENTE)

    def test_rejeicao_de_pet_exige_motivo(self):
        pet = self.criar_pet()

        self.client.post(
            reverse(
                'supervisores:moderar_pet',
                args=[pet.pk, 'rejeitar'],
            )
        )
        pet.refresh_from_db()

        self.assertEqual(pet.status, Pet.Status.PENDENTE)
        self.assertEqual(pet.motivo_rejeicao, '')

    def test_pet_de_ong_pendente_nao_pode_ser_publicado(self):
        ong = Ong.objects.create(
            nome='ONG em análise',
            cidade='Recife',
            estado='PE',
        )
        pet = self.criar_pet(responsavel=None, ong=ong)

        self.client.post(
            reverse(
                'supervisores:moderar_pet',
                args=[pet.pk, 'publicar'],
            )
        )
        pet.refresh_from_db()

        self.assertEqual(pet.status, Pet.Status.PENDENTE)

    def test_suspender_ong_arquiva_anuncios_publicados(self):
        ong = Ong.objects.create(
            nome='ONG aprovada',
            cidade='Recife',
            estado='PE',
            status=Ong.Status.APROVADA,
        )
        pet = self.criar_pet(
            responsavel=None,
            ong=ong,
            status=Pet.Status.PUBLICADO,
        )

        self.client.post(
            reverse(
                'supervisores:moderar_ong',
                args=[ong.pk, 'suspender'],
            ),
            {'motivo': 'Documentação vencida.'},
        )
        ong.refresh_from_db()
        pet.refresh_from_db()

        self.assertEqual(ong.status, Ong.Status.SUSPENSA)
        self.assertFalse(ong.aprovada)
        self.assertEqual(pet.status, Pet.Status.ARQUIVADO)

    def test_alterar_status_de_usuario_exige_motivo(self):
        url = reverse(
            'supervisores:alterar_status_usuario',
            args=[self.usuario.pk, 'inativar'],
        )

        self.client.post(url)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

        self.client.post(url, {'motivo': 'Solicitação confirmada.'})
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    def test_supervisor_comum_nao_gerencia_equipe(self):
        resposta = self.client.get(
            reverse('supervisores:equipe_lista')
        )
        self.assertEqual(resposta.status_code, 403)

    def test_superuser_pode_promover_supervisor(self):
        Usuario = get_user_model()
        admin = Usuario.objects.create_superuser(
            username='admin-fluxo',
            email='admin-fluxo@example.com',
            password='senha-segura-123',
        )
        candidato = Usuario.objects.create_user(
            username='novo-supervisor',
            password='senha-segura-123',
        )
        self.client.force_login(admin)

        resposta = self.client.post(
            reverse(
                'supervisores:alterar_supervisor',
                args=[candidato.pk, 'promover'],
            )
        )

        self.assertRedirects(
            resposta,
            reverse('supervisores:equipe_lista'),
        )
        self.assertTrue(
            candidato.groups.filter(
                name=GRUPO_SUPERVISORES,
            ).exists()
        )

    def test_supervisor_cadastra_pet_e_registra_atividade(self):
        resposta = self.client.post(
            reverse('supervisores:pet_criar'),
            {
                'nome': 'Nina',
                'especie': Pet.Especie.GATO,
                'raca': 'Sem raça definida',
                'genero': Pet.Genero.FEMEA,
                'porte': Pet.Porte.PEQUENO,
                'idade_anos': 2,
                'nascimento_desconhecido': 'on',
                'idade_meses': 3,
                'responsavel': self.usuario.pk,
                'ong': '',
                'estado': 'PE',
                'cidade': 'Recife',
                'descricao': 'Gata dócil e saudável.',
                'fotos-TOTAL_FORMS': 6,
                'fotos-INITIAL_FORMS': 0,
                'fotos-MIN_NUM_FORMS': 0,
                'fotos-MAX_NUM_FORMS': 6,
                **{
                    f'fotos-{indice}-ordem': 0
                    for indice in range(6)
                },
            },
        )

        erros = ''
        if resposta.context:
            erros = (
                f"form={resposta.context['form'].errors}; "
                f"fotos={resposta.context['fotos_formset'].errors}; "
                f"fotos_non={resposta.context['fotos_formset'].non_form_errors()}"
            )
        self.assertEqual(resposta.status_code, 302, erros)

        pet = Pet.objects.get(nome='Nina')
        self.assertRedirects(
            resposta,
            reverse('supervisores:pet_detalhe', args=[pet.pk]),
        )
        self.assertEqual(pet.status, Pet.Status.PENDENTE)
        self.assertEqual(pet.criado_por, self.supervisor)
        self.assertTrue(
            RegistroAtividade.objects.filter(
                acao=RegistroAtividade.Acao.CADASTROU,
                entidade='pet',
                objeto_id=pet.pk,
            ).exists()
        )

    @patch('ongs.forms.consultar_cnpj')
    def test_supervisor_cadastra_ong_e_registra_atividade(self, consulta):
        consulta.return_value = {'razao_social': 'ONG de teste', 'situacao': 'ATIVA', 'consultado_em': timezone.now()}
        resposta = self.client.post(
            reverse('supervisores:ong_criar'),
            {
                'nome': 'Amor Animal',
                'cnpj': '19131243000197',
                'estado': 'PE',
                'cidade': 'Recife',
                'descricao': 'Proteção e adoção responsável.',
            },
        )

        ong = Ong.objects.get(nome='Amor Animal')
        self.assertRedirects(
            resposta,
            reverse('supervisores:ong_detalhe', args=[ong.pk]),
        )
        self.assertEqual(ong.status, Ong.Status.PENDENTE)
        self.assertFalse(ong.aprovada)
        self.assertTrue(
            RegistroAtividade.objects.filter(
                acao=RegistroAtividade.Acao.CADASTROU,
                entidade='ong',
                objeto_id=ong.pk,
            ).exists()
        )

    def test_edicao_preserva_responsavel_que_virou_supervisor(self):
        pet = self.criar_pet()
        grupo = Group.objects.get(name=GRUPO_SUPERVISORES)
        self.usuario.groups.add(grupo)
        self.usuario.is_active = False
        self.usuario.save(update_fields=['is_active'])

        form = PetSupervisorForm(instance=pet)

        self.assertIn(
            self.usuario,
            form.fields['responsavel'].queryset,
        )

    def test_cadastro_oferece_seis_fotos_adicionais(self):
        formset = FotoPetSupervisorFormSet(instance=Pet())
        self.assertEqual(formset.total_form_count(), 6)

    def test_motivo_longo_e_truncado_no_historico(self):
        resposta = self.client.post(
            reverse(
                'supervisores:alterar_status_usuario',
                args=[self.usuario.pk, 'inativar'],
            ),
            {'motivo': 'x' * 500},
        )

        self.assertRedirects(
            resposta,
            reverse(
                'supervisores:usuario_detalhe',
                args=[self.usuario.pk],
            ),
        )
        atividade = RegistroAtividade.objects.get(
            objeto_id=self.usuario.pk,
            entidade='usuario',
        )
        self.assertLessEqual(len(atividade.descricao), 255)
        self.assertTrue(atividade.descricao.endswith('...'))

    @patch('ongs.forms.consultar_cnpj')
    def test_supervisor_edita_pet_e_ong(self, consulta):
        consulta.return_value = {'razao_social': 'ONG de teste', 'situacao': 'ATIVA', 'consultado_em': timezone.now()}
        pet = self.criar_pet()
        ong = Ong.objects.create(
            nome='Nome antigo',
            cidade='Recife',
            estado='PE',
        )

        resposta_pet = self.client.post(
            reverse('supervisores:pet_editar', args=[pet.pk]),
            {
                'nome': 'Paçoca atualizado',
                'especie': Pet.Especie.CACHORRO,
                'raca': 'Sem raça definida',
                'genero': Pet.Genero.MACHO,
                'porte': Pet.Porte.MEDIO,
                'idade_anos': 4,
                'nascimento_desconhecido': 'on',
                'idade_meses': 0,
                'responsavel': self.usuario.pk,
                'ong': '',
                'estado': 'PE',
                'cidade': 'Olinda',
                'descricao': 'Descrição atualizada.',
                'fotos-TOTAL_FORMS': 6,
                'fotos-INITIAL_FORMS': 0,
                'fotos-MIN_NUM_FORMS': 0,
                'fotos-MAX_NUM_FORMS': 6,
                **{
                    f'fotos-{indice}-ordem': 0
                    for indice in range(6)
                },
            },
        )
        resposta_ong = self.client.post(
            reverse('supervisores:ong_editar', args=[ong.pk]),
            {
                'nome': 'Nome atualizado',
                'cnpj': '19131243000197',
                'estado': 'PE',
                'cidade': 'Olinda',
                'descricao': 'Descrição atualizada.',
            },
        )

        pet.refresh_from_db()
        ong.refresh_from_db()
        self.assertRedirects(
            resposta_pet,
            reverse('supervisores:pet_detalhe', args=[pet.pk]),
        )
        self.assertRedirects(
            resposta_ong,
            reverse('supervisores:ong_detalhe', args=[ong.pk]),
        )
        self.assertEqual(pet.nome, 'Paçoca atualizado')
        self.assertEqual(pet.cidade, 'Olinda')
        self.assertEqual(ong.nome, 'Nome atualizado')
        self.assertEqual(
            RegistroAtividade.objects.filter(
                acao=RegistroAtividade.Acao.EDITOU,
            ).count(),
            2,
        )

    def test_status_da_ong_mantem_booleano_legado_sincronizado(self):
        ong = Ong.objects.create(
            nome='Sincronizada',
            cidade='Recife',
            estado='PE',
        )
        ong.status = Ong.Status.APROVADA
        ong.save(update_fields=['status'])
        ong.refresh_from_db()

        self.assertTrue(ong.aprovada)
