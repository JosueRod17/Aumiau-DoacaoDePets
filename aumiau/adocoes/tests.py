from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from ongs.models import Ong
from pets.models import Pet

from .models import ChamadoAjuda
from .ajuda import PERGUNTAS


class HomeCardsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ong = Ong.objects.create(nome='Patas do Centro', cidade='São Paulo', estado='SP', status=Ong.Status.APROVADA)
        cls.ong_pendente = Ong.objects.create(nome='Aguardando análise', cidade='São Paulo', estado='SP')
        for indice in range(6):
            Pet.objects.create(
                nome=f'Pet {indice}', especie=Pet.Especie.CACHORRO,
                cidade='São Paulo', estado='SP', ong=cls.ong,
                status=Pet.Status.PUBLICADO,
                codigo_demonstracao='demo-home' if indice == 0 else None,
            )
        Pet.objects.create(
            nome='Pet privado', especie=Pet.Especie.GATO,
            cidade='São Paulo', estado='SP', ong=cls.ong_pendente,
            status=Pet.Status.PUBLICADO,
        )

    def test_carrossel_mostra_todos_os_pets_publicos_e_cards_com_acao(self):
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context['pets']), 6)
        self.assertContains(resposta, 'data-carousel-track')
        self.assertContains(resposta, 'data-carousel-prev')
        self.assertContains(resposta, 'data-carousel-next')
        self.assertContains(resposta, 'class="pet-card"', count=6)
        self.assertContains(resposta, 'Quero adotar', count=6)
        self.assertContains(resposta, reverse('pets:detalhe', args=[Pet.objects.get(nome='Pet 0').pk]))
        self.assertNotContains(resposta, 'Pet privado')
        self.assertNotContains(resposta, '>Demonstração<')
        self.assertContains(resposta, 'Patas do Centro')
        self.assertContains(resposta, 'class="home-ong-card"', count=1)
        self.assertContains(resposta, reverse('ongs:detalhe', args=[self.ong.pk]))
        self.assertNotContains(resposta, 'Aguardando análise')

    def test_busca_local_e_estado_vazio(self):
        resposta = self.client.get(reverse('home'), {'localizacao': 'Rio de Janeiro'})
        self.assertEqual(len(resposta.context['pets']), 0)
        self.assertContains(resposta, 'Nenhum pet disponível por enquanto')
        self.assertNotContains(resposta, 'data-carousel-track')


class CentralAjudaTests(TestCase):
    def test_perguntas_publicas_e_filtro_por_categoria(self):
        resposta = self.client.get(reverse('ajuda'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context['perguntas']), 5)
        self.assertContains(resposta, 'Como podemos ajudar?')
        resposta = self.client.get(reverse('ajuda'), {'categoria': 'ongs'})
        self.assertTrue(resposta.context['perguntas'])
        self.assertTrue(all(item['categoria'] == 'ongs' for item in resposta.context['perguntas']))
        self.assertContains(resposta, 'Como cadastrar uma ONG')

    def test_busca_ignora_acentos_e_mostra_estado_vazio(self):
        resposta = self.client.get(reverse('ajuda'), {'q': 'doacoes'})
        self.assertTrue(resposta.context['perguntas'])
        self.assertContains(resposta, 'O AuMiau cobra alguma taxa?')
        resposta = self.client.get(reverse('ajuda'), {'q': 'zzzzzz'})
        self.assertEqual(resposta.context['perguntas'], [])
        self.assertContains(resposta, 'Nenhuma resposta encontrada')

    def test_filtro_invalido_retorna_perguntas_em_destaque(self):
        resposta = self.client.get(reverse('ajuda'), {'categoria': 'inexistente'})
        self.assertEqual(resposta.context['categoria_ativa'], '')
        self.assertEqual(len(resposta.context['perguntas']), 5)

    def test_paginas_informativas_publicas(self):
        for nome in ['termos', 'privacidade']:
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)


class ChamadoAjudaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username='solicitante', password='teste-2026')
        cls.outro = get_user_model().objects.create_user(username='outro', password='teste-2026')
        cls.chamado = ChamadoAjuda.objects.create(
            usuario=cls.usuario,
            categoria=ChamadoAjuda.Categoria.ADOCAO,
            assunto='Dúvida particular sobre adoção',
            mensagem='Preciso saber mais sobre um anúncio.',
        )

    def test_rotas_exigem_login(self):
        for url in [reverse('chamado_novo'), reverse('meus_chamados'), reverse('chamado_detalhe', args=[self.chamado.pk])]:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 302)
                self.assertIn(reverse('usuarios:login'), resposta.url)

    def test_envio_salva_mensagem_do_usuario_sem_campos_administrativos(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('chamado_novo'), {
            'categoria': 'sugestao',
            'assunto': ' Melhorias na busca ',
            'mensagem': ' Gostaria de encontrar pets pelo porte. ',
            'usuario': self.outro.pk,
            'status': 'respondido',
            'resposta': 'Resposta forjada',
        })
        chamado = ChamadoAjuda.objects.exclude(pk=self.chamado.pk).get()
        self.assertRedirects(resposta, reverse('chamado_detalhe', args=[chamado.pk]))
        self.assertEqual(chamado.usuario, self.usuario)
        self.assertEqual(chamado.status, ChamadoAjuda.Status.ABERTO)
        self.assertEqual(chamado.resposta, '')
        self.assertEqual(chamado.assunto, 'Melhorias na busca')
        self.assertEqual(chamado.mensagem, 'Gostaria de encontrar pets pelo porte.')

    def test_erro_preserva_campos_e_nao_salva_chamado(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('chamado_novo'), {
            'categoria': 'nao_existe', 'assunto': 'Uma sugestão', 'mensagem': '   ',
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(ChamadoAjuda.objects.count(), 1)
        self.assertContains(resposta, 'Uma sugestão')
        self.assertIn('categoria', resposta.context['form'].errors)
        self.assertIn('mensagem', resposta.context['form'].errors)

    def test_dono_ve_resposta_e_outro_usuario_nao_ve_chamado(self):
        self.chamado.resposta = 'O responsável poderá confirmar os requisitos.'
        self.chamado.status = ChamadoAjuda.Status.RESPONDIDO
        self.chamado.save()
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('chamado_detalhe', args=[self.chamado.pk]))
        self.assertContains(resposta, self.chamado.resposta)
        self.assertContains(resposta, 'Respondido')
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(reverse('chamado_detalhe', args=[self.chamado.pk])).status_code, 404)
        resposta = self.client.get(reverse('meus_chamados'))
        self.assertNotContains(resposta, self.chamado.assunto)
        self.assertContains(resposta, 'Você ainda não enviou mensagens')

    def test_texto_do_chamado_e_resposta_sao_escapados(self):
        self.chamado.mensagem = '<script>alert("mensagem")</script>'
        self.chamado.resposta = '<script>alert("resposta")</script>'
        self.chamado.save()
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('chamado_detalhe', args=[self.chamado.pk]))
        self.assertNotContains(resposta, '<script>alert(')
        self.assertContains(resposta, '&lt;script&gt;')

    def test_post_sem_csrf_nao_cria_chamado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        resposta = cliente.post(reverse('chamado_novo'), {
            'categoria': 'adocao', 'assunto': 'Dúvida', 'mensagem': 'Quero ajuda.',
        })
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(ChamadoAjuda.objects.count(), 1)

    def test_administracao_pode_responder_no_painel(self):
        admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'teste-2026')
        self.client.force_login(admin)
        resposta = self.client.post(reverse('admin:adocoes_chamadoajuda_change', args=[self.chamado.pk]), {
            'status': 'respondido', 'resposta': 'Recebemos sua sugestão.', '_save': 'Salvar',
        })
        self.assertEqual(resposta.status_code, 302)
        self.chamado.refresh_from_db()
        self.assertEqual(self.chamado.resposta, 'Recebemos sua sugestão.')
        self.assertEqual(self.chamado.status, ChamadoAjuda.Status.RESPONDIDO)


class InteresseAdocaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username='interessado', password='teste-2026')
        cls.pet = Pet.objects.create(
            nome='Lua', especie=Pet.Especie.GATO, cidade='Campinas', estado='SP',
            status=Pet.Status.PUBLICADO, codigo_demonstracao='lua-exemplo',
        )
        cls.privado = Pet.objects.create(
            nome='Não publicado', especie=Pet.Especie.CACHORRO, cidade='Campinas', estado='SP',
            status=Pet.Status.PENDENTE,
        )

    def url_interesse(self):
        return reverse('chamado_novo') + f'?pet={self.pet.pk}'

    def test_anuncio_publico_com_dados_demo_tem_acao_de_adocao(self):
        resposta = self.client.get(reverse('pets:detalhe', args=[self.pet.pk]))
        self.assertContains(resposta, 'id="contato"')
        self.assertContains(resposta, self.url_interesse())
        self.assertNotContains(resposta, 'Pet fictício de demonstração')
        self.assertContains(self.client.get(reverse('pets:lista')), 'Quero adotar')

    def test_interesse_exige_login_e_preserva_pet_no_destino(self):
        resposta = self.client.get(self.url_interesse())
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('pet%3D', resposta.url)
        self.assertEqual(ChamadoAjuda.objects.count(), 0)

    def test_envio_vincula_pet_publico_e_ignora_categoria_ou_pet_forjados(self):
        self.client.force_login(self.usuario)
        formulario = self.client.get(self.url_interesse())
        self.assertEqual(formulario.context['form'].initial['categoria'], ChamadoAjuda.Categoria.ADOCAO)
        self.assertTrue(formulario.context['form'].fields['categoria'].disabled)
        self.assertContains(formulario, 'Interesse em adotar Lua')
        resposta = self.client.post(self.url_interesse(), {
            'categoria': 'sugestao', 'assunto': 'Quero conhecer a Lua',
            'mensagem': 'Quando posso conhecê-la?', 'pet': self.privado.pk,
        })
        chamado = ChamadoAjuda.objects.get()
        self.assertRedirects(resposta, reverse('chamado_detalhe', args=[chamado.pk]))
        self.assertEqual(chamado.pet, self.pet)
        self.assertEqual(chamado.usuario, self.usuario)
        self.assertEqual(chamado.categoria, ChamadoAjuda.Categoria.ADOCAO)
        self.assertContains(self.client.get(resposta.url), 'Lua')

    def test_anuncio_nao_publico_ou_id_invalido_nao_gera_interesse(self):
        self.client.force_login(self.usuario)
        for pet_id in (self.privado.pk, 'invalido', '0'):
            with self.subTest(pet_id=pet_id):
                url = reverse('chamado_novo') + f'?pet={pet_id}'
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {
                    'categoria': 'adocao', 'assunto': 'Olá', 'mensagem': 'Tenho interesse.',
                }).status_code, 404)
        self.assertFalse(ChamadoAjuda.objects.exists())


class PluttuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username='pluttu-usuario', password='teste-2026')
        cls.outro = get_user_model().objects.create_user(username='pluttu-outro', password='teste-2026')

    def perguntar(self, pergunta, cliente=None):
        return (cliente or self.client).post(
            reverse('pluttu'), {'mensagem': pergunta}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def preparar_encaminhamento(self):
        self.client.force_login(self.usuario)
        self.perguntar('Minha dúvida ainda não foi resolvida.')
        resposta = self.client.get(reverse('chamado_novo'), {'pluttu': '1'})
        self.assertEqual(resposta.context['form'].initial['mensagem'], 'Minha dúvida ainda não foi resolvida.')
        return resposta.context['form'].initial['conversa_pluttu']

    def dados_chamado(self, token, incluir=True):
        dados = {
            'categoria': 'sugestao', 'assunto': 'Preciso da equipe',
            'mensagem': 'Por favor, confiram minha dúvida.', 'conversa_pluttu': token,
        }
        if incluir:
            dados['incluir_conversa'] = 'on'
        return dados

    def test_perguntas_da_faq_reutilizam_resposta_e_rotas_reais(self):
        for pergunta in PERGUNTAS:
            with self.subTest(pergunta=pergunta['id']):
                resposta = self.perguntar(pergunta['pergunta'])
                self.assertEqual(resposta.status_code, 200)
                mensagem = resposta.json()['historico'][-1]['resposta']
                self.assertEqual(mensagem['texto'], pergunta['resposta'])
                self.assertFalse(mensagem['encaminhar'])
                self.assertTrue(mensagem['url'].startswith(reverse(pergunta['rota'])))

    def test_reconhece_intencoes_em_portugues_sem_acentos(self):
        for mensagem, rota in [
            ('Quero publicar um cachorro', 'pets:anunciar'),
            ('Como criar uma ong?', 'ongs:cadastrar'),
            ('Meu pet nao aparece', 'pets:meus_pets'),
            ('Quero denunciar um golpe', 'chamado_novo'),
        ]:
            with self.subTest(mensagem=mensagem):
                resposta = self.perguntar(mensagem).json()['historico'][-1]['resposta']
                self.assertTrue(resposta['url'].startswith(reverse(rota)))

    def test_duvida_desconhecida_e_pedido_de_humano_oferecem_chamado(self):
        for mensagem in ['Meu animal precisa de um remédio.', 'Quero falar com uma pessoa']:
            resposta = self.perguntar(mensagem).json()['historico'][-1]['resposta']
            self.assertTrue(resposta['encaminhar'])
            self.assertIn('Meus chamados', resposta['texto'])
        self.assertEqual(ChamadoAjuda.objects.count(), 0)
        self.assertContains(self.client.get(reverse('ajuda')), 'Encaminhar para a equipe')

    def test_historico_limitado_isolado_e_limpeza_exige_post(self):
        for indice in range(8):
            self.perguntar(f'Pergunta particular {indice}')
        historico = self.client.session['pluttu_historico']
        self.assertEqual(len(historico), 6)
        self.assertEqual(historico[0]['mensagem'], 'Pergunta particular 2')
        self.assertNotContains(Client().get(reverse('ajuda')), 'Pergunta particular')
        resposta = self.client.get(reverse('ajuda'))
        self.assertIn('no-store', resposta.headers['Cache-Control'])
        self.client.get(reverse('pluttu'), {'acao': 'limpar'})
        self.assertEqual(len(self.client.session['pluttu_historico']), 6)
        self.client.post(reverse('pluttu'), {'acao': 'limpar'})
        self.assertNotIn('pluttu_historico', self.client.session)

    def test_entrada_invalida_preserva_historico_e_mostra_erro_portugues(self):
        for mensagem in ['', 'x' * 501]:
            resposta = self.perguntar(mensagem)
            self.assertEqual(resposta.status_code, 400)
            self.assertIn('erro', resposta.json())
        self.assertNotIn('pluttu_historico', self.client.session)
        resposta = self.client.post(reverse('pluttu'), {'mensagem': ''})
        self.assertContains(resposta, 'Digite sua dúvida', status_code=400)

    def test_sem_javascript_e_html_recebido_sao_seguros(self):
        resposta = self.client.post(reverse('pluttu'), {'mensagem': '<script>alert("teste")</script>'})
        self.assertRedirects(resposta, reverse('ajuda') + '#pluttu')
        resposta = self.client.get(reverse('ajuda'))
        self.assertContains(resposta, '&lt;script&gt;')
        self.assertNotContains(resposta, '<script>alert(')

    def test_csrf_obrigatorio_antes_de_mudar_historico(self):
        cliente = Client(enforce_csrf_checks=True)
        resposta = self.perguntar('Como adotar?', cliente)
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn('pluttu_historico', cliente.session)

    def test_encaminhamento_exige_login_preservando_destino(self):
        self.perguntar('Preciso de ajuda de uma pessoa')
        resposta = self.client.get(reverse('chamado_novo'), {'pluttu': '1'})
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('pluttu%3D1', resposta.url)
        self.assertEqual(ChamadoAjuda.objects.count(), 0)

    def test_conversa_revisada_so_e_anexada_com_consentimento(self):
        token = self.preparar_encaminhamento()
        resposta = self.client.post(reverse('chamado_novo'), self.dados_chamado(token))
        chamado = ChamadoAjuda.objects.get()
        self.assertRedirects(resposta, reverse('chamado_detalhe', args=[chamado.pk]))
        self.assertEqual(chamado.usuario, self.usuario)
        self.assertIn('Você: Minha dúvida ainda não foi resolvida.', chamado.contexto_pluttu)
        self.assertIn('Pluttu:', chamado.contexto_pluttu)
        self.assertContains(self.client.get(resposta.url), 'Conversa encaminhada do Pluttu')
        self.client.post(reverse('chamado_novo'), self.dados_chamado(token, incluir=False))
        sem_conversa = ChamadoAjuda.objects.exclude(pk=chamado.pk).get()
        self.assertEqual(sem_conversa.contexto_pluttu, '')

    def test_snapshot_revisado_nao_muda_apos_nova_pergunta(self):
        token = self.preparar_encaminhamento()
        self.perguntar('Outra mensagem que ainda não revisei')
        self.client.post(reverse('chamado_novo'), self.dados_chamado(token))
        self.assertNotIn('Outra mensagem', ChamadoAjuda.objects.get().contexto_pluttu)

    def test_token_alterado_e_de_outra_conta_nao_sao_aceitos(self):
        token = self.preparar_encaminhamento()
        resposta = self.client.post(reverse('chamado_novo'), self.dados_chamado(token + 'invalido'))
        self.assertContains(resposta, 'A conversa expirou ou não pôde ser confirmada')
        self.client.force_login(self.outro)
        resposta = self.client.post(reverse('chamado_novo'), self.dados_chamado(token))
        self.assertContains(resposta, 'A conversa expirou ou não pôde ser confirmada')
        self.assertFalse(ChamadoAjuda.objects.exists())

    def test_categoria_tem_opcao_inicial_em_portugues(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('chamado_novo'))
        self.assertContains(resposta, 'Selecione uma opção')
        self.assertNotContains(resposta, '---------')
        self.assertEqual(resposta.context['form'].fields['categoria'].choices[0], ('', 'Selecione uma opção'))
