from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ongs.models import Ong
from pets.models import Pet
from .models import Perfil


class FluxosPublicosTests(TestCase):
    def dados_cadastro(self, **alteracoes):
        dados = {
            'nome_completo': 'Pessoa de Teste', 'email': 'pessoa@example.com',
            'telefone': '(11) 99999-1234', 'estado': 'SP', 'cidade': 'São Paulo',
            'cpf': '111.444.777-35',
            'password1': 'Senha-de-teste!8472', 'password2': 'Senha-de-teste!8472',
            'aceite_termos': 'on',
        }
        return dados | alteracoes

    def test_cadastro_preserva_destino_e_cria_perfil(self):
        destino = reverse('ongs:cadastrar')
        resposta = self.client.get(reverse('usuarios:cadastro'), {'next': destino})
        self.assertContains(resposta, f'value="{destino}"')
        resposta = self.client.post(reverse('usuarios:cadastro'), self.dados_cadastro(next=destino))
        self.assertRedirects(resposta, destino)
        perfil = Perfil.objects.get(usuario__email='pessoa@example.com')
        self.assertEqual(perfil.telefone, '11999991234')
        self.assertEqual(int(self.client.session['_auth_user_id']), perfil.usuario_id)

    def test_cadastro_nao_redireciona_para_site_externo(self):
        resposta = self.client.post(reverse('usuarios:cadastro'), self.dados_cadastro(next='https://externo.example/'))
        self.assertRedirects(resposta, reverse('home'))

    def test_cadastro_invalido_preserva_destino_e_valores(self):
        destino = reverse('pets:anunciar')
        resposta = self.client.post(reverse('usuarios:cadastro'), self.dados_cadastro(next=destino, password2='outra'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['next'], destino)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_login_oferece_cadastro_com_destino(self):
        resposta = self.client.get(reverse('usuarios:login'), {'next': reverse('ongs:cadastrar')})
        self.assertContains(resposta, '?next=/ongs/cadastrar/')

    def test_rotas_de_gestao_exigem_login(self):
        for nome in ('ongs:cadastrar', 'ongs:painel', 'pets:anunciar', 'pets:meus_pets', 'meus_chamados'):
            with self.subTest(nome=nome):
                destino = reverse(nome)
                self.assertRedirects(self.client.get(destino), f"{reverse('usuarios:login')}?next={destino}")

    def test_home_so_exibe_pets_publicos_de_ongs_aprovadas(self):
        ong = Ong.objects.create(nome='ONG em análise', cidade='São Paulo', estado='SP')
        Pet.objects.create(nome='Pet oculto', especie='gato', cidade='São Paulo', estado='SP', ong=ong, status=Pet.Status.PUBLICADO)
        pet = Pet.objects.create(nome='Pet disponível', especie='gato', cidade='São Paulo', estado='SP', status=Pet.Status.PUBLICADO)
        resposta = self.client.get(reverse('home'))
        self.assertEqual(list(resposta.context['pets']), [pet])
        self.assertEqual(resposta.context['total_pets'], 1)
        self.assertContains(resposta, reverse('pets:detalhe', args=[pet.pk]))
        self.assertNotContains(resposta, 'Pet oculto')

    def test_paginas_publicas_e_navegacao_renderizam(self):
        for nome in ('home', 'pets:lista', 'ongs:lista', 'ajuda', 'termos', 'privacidade'):
            with self.subTest(nome=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200)
                for destino in ('pets:lista', 'ongs:lista', 'ajuda', 'ongs:cadastrar'):
                    self.assertContains(resposta, reverse(destino))

    def test_conta_sem_perfil_pode_acessar_gestao(self):
        usuario = get_user_model().objects.create_user(username='sem-perfil')
        self.client.force_login(usuario)
        for nome in ('home', 'ongs:cadastrar', 'pets:anunciar', 'pets:meus_pets', 'ongs:painel'):
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)
