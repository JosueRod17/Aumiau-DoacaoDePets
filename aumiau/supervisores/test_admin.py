from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from pets.models import Pet


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ApresentacaoAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin-interface', 'admin@example.com', 'teste')
        cls.pet = Pet.objects.create(nome='Amora', especie='gato', cidade='Recife', estado='PE')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_paginas_tem_titulo_favicon_e_navegacao_unicos(self):
        for route, title in (
            ('admin:index', 'Visão geral'),
            ('admin:pets_pet_changelist', 'Pets'),
            ('admin:pets_pet_add', 'Novo anúncio'),
            ('admin:auth_user_changelist', 'Usuários'),
            ('admin:ongs_ong_changelist', 'ONGs parceiras'),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertContains(response, f'<title>{title} | AuMiau Admin</title>')
                self.assertContains(response, '/static/img/favicon.svg')
                self.assertNotContains(response, '<span>Moderação</span>')
                self.assertNotContains(response, '<span>Dashboard</span>')

    def test_contagem_preserva_filtro_e_acao_personalizada_continua_funcional(self):
        url = reverse('admin:pets_pet_changelist')
        response = self.client.get(url, {'status__exact': 'pendente'})
        self.assertContains(response, 'Selecione uma opção')
        self.assertContains(response, 'Em análise')
        self.assertContains(response, 'Mostrar contagem')
        self.assertContains(response, f'<a href="{url}" class="aumiau-nav-link is-active">')
        facet_link = response.context['cl'].add_facet_link
        self.assertIn('status__exact=pendente', facet_link)
        response = self.client.get(url + facet_link)
        self.assertContains(response, 'Ocultar contagem')
        self.assertEqual(response.context['cl'].result_count, 1)

        response = self.client.post(url, {
            'action': 'arquivar_selecionados', '_selected_action': [self.pet.pk],
            'index': '0', 'select_across': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.ARQUIVADO)
