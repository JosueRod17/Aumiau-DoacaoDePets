from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from pets.models import Pet
from ongs.models import Ong

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
            reverse('supervisores:ongs_lista'),
        )
        self.assertTrue(ong.aprovada)
