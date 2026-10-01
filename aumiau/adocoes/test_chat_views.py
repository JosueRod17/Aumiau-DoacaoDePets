import uuid
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from pets.models import Pet
from usuarios.models import Perfil
from usuarios.services import excluir_conta

from .chat_service import criar_conversa
from .context_processors import mensagens_chat
from .models import ConversaAdocao, MensagemAdocao, SolicitacaoAdocao


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ChatViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dono = User.objects.create_user('doador-conversa', first_name='Ana')
        cls.adotante = User.objects.create_user('adotante-conversa', first_name='Bia')
        cls.outro = User.objects.create_user('outro-conversa')
        cls.admin = User.objects.create_superuser('admin-conversa', 'admin@example.com', 'teste')
        cls.pet = Pet.objects.create(
            nome='Estrela', especie='gato', cidade='Recife', estado='PE',
            status='adotado', responsavel=cls.dono,
        )
        cls.pedido = SolicitacaoAdocao.objects.create(
            pet=cls.pet, usuario=cls.adotante, mensagem='Desejo adotar.', status='aprovada',
        )
        cls.conversa = criar_conversa(cls.pedido)

    def url(self, nome='conversa_adocao', conversa=None):
        if nome == 'minhas_conversas':
            return reverse(nome)
        return reverse(nome, args=[(conversa or self.conversa).pk])

    def mensagem(self, texto='Vamos combinar para amanhã?', autor=None, conversa=None):
        return MensagemAdocao.objects.create(
            conversa=conversa or self.conversa, autor=autor or self.dono,
            texto=texto, cliente_id=uuid.uuid4(),
        )

    def enviar(self, texto='Posso buscar às 10h?', identificador=None, **kwargs):
        return self.client.post(self.url('conversa_mensagens'), {
            'texto': texto, 'cliente_id': str(identificador or uuid.uuid4()),
        }, **kwargs)

    def nao_lidas(self, usuario):
        return mensagens_chat(SimpleNamespace(user=usuario))['mensagens_chat_nao_lidas']

    def outra_conversa(self):
        pedido = SolicitacaoAdocao.objects.create(
            pet=self.pet, usuario=self.outro, mensagem='Outro pedido', status='aprovada',
        )
        return criar_conversa(pedido)

    def test_participantes_podem_ver_lista_pagina_e_api(self):
        mensagem = self.mensagem()
        for usuario in [self.dono, self.adotante]:
            self.client.force_login(usuario)
            lista = self.client.get(self.url('minhas_conversas'))
            self.assertContains(lista, 'Estrela')
            self.assertEqual(lista.context['pagina'].paginator.count, 1)
            detalhe = self.client.get(self.url())
            self.assertContains(detalhe, mensagem.texto)
            self.assertEqual(detalhe.context['conversa'].pk, self.conversa.pk)
            api = self.client.get(self.url('conversa_mensagens')).json()
            self.assertEqual(api['mensagens'][0]['texto'], mensagem.texto)
            self.assertEqual(api['mensagens'][0]['minha'], usuario == self.dono)

    def test_terceiro_e_admin_nao_participante_nao_acessam_historico_ou_envio(self):
        mensagem = self.mensagem('Informação particular da conversa.')
        for usuario in [self.outro, self.admin]:
            self.client.force_login(usuario)
            lista = self.client.get(self.url('minhas_conversas'))
            self.assertEqual(lista.context['pagina'].paginator.count, 0)
            self.assertNotContains(lista, mensagem.texto)
            self.assertEqual(self.client.get(self.url()).status_code, 404)
            self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 404)
            self.assertEqual(self.enviar(HTTP_ACCEPT='application/json').status_code, 404)
            resposta = self.client.post(self.url('conversa_lidas'), {'ultimo_id': mensagem.pk})
            self.assertEqual(resposta.status_code, 404)
            self.assertEqual(self.nao_lidas(usuario), 0)
        self.assertEqual(MensagemAdocao.objects.count(), 1)

    def test_anonimo_redirecionado_em_paginas_e_401_em_apis(self):
        for nome in ['minhas_conversas', 'conversa_adocao']:
            self.assertEqual(self.client.get(self.url(nome)).status_code, 302)
        self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 401)
        self.assertEqual(self.enviar(HTTP_ACCEPT='application/json').status_code, 401)
        self.assertEqual(self.client.post(self.url('conversa_lidas'), {'ultimo_id': 0}).status_code, 401)
        self.assertEqual(self.nao_lidas(AnonymousUser()), 0)

    def test_pedido_nao_aprovado_oculta_conversa_existente_e_bloqueia_apis(self):
        mensagem = self.mensagem()
        self.client.force_login(self.adotante)
        for status in ['pendente', 'recusada', 'cancelada']:
            SolicitacaoAdocao.objects.filter(pk=self.pedido.pk).update(status=status)
            self.assertEqual(self.client.get(self.url('minhas_conversas')).context['pagina'].paginator.count, 0)
            self.assertEqual(self.client.get(self.url()).status_code, 404)
            self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 404)
            self.assertEqual(self.enviar(HTTP_ACCEPT='application/json').status_code, 404)
            self.assertEqual(self.client.post(self.url('conversa_lidas'), {'ultimo_id': mensagem.pk}).status_code, 404)
            self.assertEqual(self.nao_lidas(self.adotante), 0)

    def test_trocar_responsavel_nao_transfere_acesso_ao_historico(self):
        self.mensagem()
        Pet.objects.filter(pk=self.pet.pk).update(responsavel=self.outro)
        self.client.force_login(self.dono)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 404)

    def test_texto_e_nomes_renderizados_escapados(self):
        texto = '<script>alert("chat")</script><img src=x onerror=alert(1)>'
        self.mensagem(texto)
        get_user_model().objects.filter(pk=self.dono.pk).update(first_name='<b>Ana</b>')
        self.client.force_login(self.adotante)
        pagina = self.client.get(self.url())
        self.assertNotContains(pagina, texto)
        self.assertContains(pagina, '&lt;script&gt;alert(&quot;chat&quot;)&lt;/script&gt;')
        self.assertContains(pagina, '&lt;b&gt;Ana&lt;/b&gt;')
        lista = self.client.get(self.url('minhas_conversas'))
        self.assertNotContains(lista, '<script>alert')
        api = self.client.get(self.url('conversa_mensagens'))
        self.assertEqual(api['Content-Type'], 'application/json')
        self.assertEqual(api.json()['mensagens'][0]['texto'], texto)

    def test_post_exige_csrf_para_envio_e_leitura(self):
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.adotante)
        mensagem = self.mensagem()
        self.assertEqual(seguro.post(self.url('conversa_mensagens'), {
            'texto': 'Olá', 'cliente_id': str(uuid.uuid4()),
        }).status_code, 403)
        self.assertEqual(seguro.post(self.url('conversa_lidas'), {'ultimo_id': mensagem.pk}).status_code, 403)
        seguro.get(self.url())
        token = seguro.cookies['csrftoken'].value
        enviado = seguro.post(self.url('conversa_mensagens'), {
            'texto': 'Olá', 'cliente_id': str(uuid.uuid4()),
        }, HTTP_X_CSRFTOKEN=token, HTTP_ACCEPT='application/json')
        self.assertEqual(enviado.status_code, 201)
        lida = seguro.post(self.url('conversa_lidas'), {'ultimo_id': mensagem.pk},
                           HTTP_X_CSRFTOKEN=token, HTTP_ACCEPT='application/json')
        self.assertEqual(lida.status_code, 200)

    def test_polling_paginas_de_50_e_cursor_sem_repeticao(self):
        mensagens = [self.mensagem(f'Mensagem {numero}') for numero in range(57)]
        self.client.force_login(self.adotante)
        primeiro = self.client.get(self.url('conversa_mensagens'), {'apos': 0}).json()
        self.assertEqual(len(primeiro['mensagens']), 50)
        self.assertTrue(primeiro['tem_mais'])
        self.assertEqual(primeiro['proxima'], mensagens[49].pk)
        segundo = self.client.get(self.url('conversa_mensagens'), {'apos': primeiro['proxima']}).json()
        self.assertEqual(len(segundo['mensagens']), 7)
        self.assertFalse(segundo['tem_mais'])
        self.assertEqual(segundo['proxima'], mensagens[-1].pk)
        self.assertEqual([m['id'] for m in primeiro['mensagens'] + segundo['mensagens']], [m.pk for m in mensagens])
        vazio = self.client.get(self.url('conversa_mensagens'), {'apos': segundo['proxima']}).json()
        self.assertEqual(vazio['mensagens'], [])
        self.assertEqual(vazio['proxima'], segundo['proxima'])

    def test_cursores_invalidos_nao_causam_erro_de_servidor(self):
        self.mensagem()
        self.client.force_login(self.adotante)
        for cursor in ['-1', 'abc', '9' * 100, '１']:
            self.assertEqual(self.client.get(self.url('conversa_mensagens'), {'apos': cursor}).status_code, 200)

    def test_get_nao_marca_leitura_e_post_marca_apenas_ids_da_conversa(self):
        mensagens = [self.mensagem(f'Mensagem {numero}') for numero in range(3)]
        externa = self.mensagem(conversa=self.outra_conversa())
        self.client.force_login(self.adotante)
        self.client.get(self.url())
        self.client.get(self.url('conversa_mensagens'))
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.ultimo_lido_adotante_id, 0)
        marcada = self.client.post(self.url('conversa_lidas'), {'ultimo_id': mensagens[1].pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(marcada.status_code, 200)
        self.client.post(self.url('conversa_lidas'), {'ultimo_id': mensagens[0].pk}, HTTP_ACCEPT='application/json')
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.ultimo_lido_adotante_id, mensagens[1].pk)
        self.assertEqual(self.conversa.ultimo_lido_anunciante_id, 0)
        rejeitada = self.client.post(self.url('conversa_lidas'), {'ultimo_id': externa.pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(rejeitada.status_code, 400)
        self.conversa.refresh_from_db()
        self.assertEqual(self.conversa.ultimo_lido_adotante_id, mensagens[1].pk)
        self.assertEqual(self.client.get(self.url('conversa_lidas')).status_code, 405)

    def test_badge_e_caixa_contam_somente_mensagens_recebidas_nao_lidas(self):
        primeira = self.mensagem('Mensagem do doador')
        self.mensagem('Minha resposta', autor=self.adotante)
        segunda = self.mensagem('Outra mensagem do doador')
        outra = self.outra_conversa()
        self.mensagem('Mensagem de outra conversa', conversa=outra, autor=self.outro)
        self.assertEqual(self.nao_lidas(self.adotante), 2)
        self.assertEqual(self.nao_lidas(self.dono), 2)
        self.client.force_login(self.adotante)
        lista = self.client.get(self.url('minhas_conversas'))
        self.assertEqual(lista.context['pagina'].object_list[0]['nao_lidas'], 2)
        self.client.post(self.url('conversa_lidas'), {'ultimo_id': primeira.pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(self.nao_lidas(self.adotante), 1)
        self.client.post(self.url('conversa_lidas'), {'ultimo_id': segunda.pk}, HTTP_ACCEPT='application/json')
        self.assertEqual(self.nao_lidas(self.adotante), 0)
        self.assertEqual(self.nao_lidas(self.dono), 2)
        self.assertEqual(self.client.get(self.url('minhas_conversas')).context['pagina'].object_list[0]['nao_lidas'], 0)

    def test_historico_paginado_preserva_ordem_e_nao_polling_pagina_antiga(self):
        mensagens = [self.mensagem(f'Mensagem {numero}') for numero in range(57)]
        self.client.force_login(self.adotante)
        recente = self.client.get(self.url())
        self.assertEqual([m.pk for m in recente.context['mensagens']], [m.pk for m in mensagens[7:]])
        self.assertTrue(recente.context['atualizar_chat'])
        antiga = self.client.get(self.url(), {'pagina': 2})
        self.assertEqual([m.pk for m in antiga.context['mensagens']], [m.pk for m in mensagens[:7]])
        self.assertFalse(antiga.context['atualizar_chat'])
        self.assertNotContains(antiga, 'data-chat-form')

    def test_envio_html_redireciona_e_preserva_mensagens(self):
        self.client.force_login(self.adotante)
        resposta = self.enviar(texto='Posso buscar no sábado?')
        self.assertRedirects(resposta, self.url())
        self.assertEqual(MensagemAdocao.objects.get().texto, 'Posso buscar no sábado?')

    def test_envio_ajax_idempotente_e_uuid_reutilizado_com_texto_diferente(self):
        self.client.force_login(self.adotante)
        identificador = uuid.uuid4()
        primeira = self.enviar(identificador=identificador, HTTP_ACCEPT='application/json')
        self.assertEqual(primeira.status_code, 201)
        self.assertTrue(primeira.json()['criada'])
        repetida = self.enviar(identificador=identificador, HTTP_ACCEPT='application/json')
        self.assertEqual(repetida.status_code, 200)
        self.assertFalse(repetida.json()['criada'])
        self.assertEqual(primeira.json()['mensagem']['id'], repetida.json()['mensagem']['id'])
        conflito = self.enviar(texto='Texto alterado', identificador=identificador, HTTP_ACCEPT='application/json')
        self.assertEqual(conflito.status_code, 400)
        self.assertIn('outro texto', conflito.json()['erro'])
        self.assertEqual(MensagemAdocao.objects.count(), 1)

    def test_uuid_ausente_ou_invalido_rejeitado_e_rascunho_html_preservado(self):
        self.client.force_login(self.adotante)
        for dados in [{'texto': 'Rascunho importante'}, {'texto': 'Rascunho importante', 'cliente_id': 'invalido'}]:
            resposta = self.client.post(self.url('conversa_mensagens'), dados, HTTP_ACCEPT='application/json')
            self.assertEqual(resposta.status_code, 400)
            self.assertTrue(resposta.json()['erro'])
        html = self.client.post(self.url('conversa_mensagens'), {'texto': 'Rascunho importante', 'cliente_id': 'invalido'})
        self.assertEqual(html.status_code, 400)
        self.assertEqual(html.context['form']['texto'].value(), 'Rascunho importante')
        self.assertContains(html, 'Rascunho importante', status_code=400)
        self.assertFalse(MensagemAdocao.objects.exists())

    def test_erro_de_frequencia_preserva_rascunho_e_uuid(self):
        self.client.force_login(self.adotante)
        self.enviar()
        identificador = uuid.uuid4()
        rejeitada = self.enviar(texto='Segundo envio ainda não recebido', identificador=identificador)
        self.assertEqual(rejeitada.status_code, 400)
        self.assertContains(rejeitada, 'Segundo envio ainda não recebido', status_code=400)
        self.assertEqual(str(rejeitada.context['form']['cliente_id'].value()), str(identificador))
        self.assertEqual(MensagemAdocao.objects.count(), 1)

    def test_outro_participante_suspenso_permite_historico_mas_nao_envio(self):
        self.mensagem('Histórico existente')
        Perfil.objects.create(usuario=self.dono, aceitou_termos_em=timezone.now(), situacao='suspensa')
        self.client.force_login(self.adotante)
        pagina = self.client.get(self.url())
        self.assertContains(pagina, 'Histórico existente')
        self.assertFalse(pagina.context['pode_enviar'])
        self.assertFalse(self.client.get(self.url('conversa_mensagens')).json()['pode_enviar'])
        self.assertEqual(self.enviar(HTTP_ACCEPT='application/json').status_code, 403)
        self.client.force_login(self.dono)
        # O backend de autenticação também recusa contas suspensas.
        self.assertRedirects(self.client.get(self.url()), reverse('usuarios:login') + '?next=' + self.url())
        self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 401)
        self.assertEqual(self.nao_lidas(self.dono), 0)

    def test_lista_paginada_utiliza_parametro_dos_links(self):
        for numero in range(21):
            pedido = SolicitacaoAdocao.objects.create(
                pet=self.pet, usuario=self.adotante, mensagem=f'Pedido {numero}', status='aprovada',
            )
            criar_conversa(pedido)
        self.client.force_login(self.adotante)
        primeira = self.client.get(self.url('minhas_conversas'))
        segunda = self.client.get(self.url('minhas_conversas'), {'page': 2})
        self.assertContains(primeira, '?page=2')
        self.assertEqual(segunda.context['pagina'].number, 2)
        ids_primeira = {item['conversa'].pk for item in primeira.context['pagina']}
        ids_segunda = {item['conversa'].pk for item in segunda.context['pagina']}
        self.assertEqual(len(ids_primeira), 20)
        self.assertEqual(len(ids_segunda), 2)
        self.assertFalse(ids_primeira & ids_segunda)

    def test_exclusao_de_conta_remove_historico_e_acesso(self):
        self.mensagem('Histórico removido na exclusão')
        excluir_conta(self.dono)
        self.client.force_login(self.adotante)
        self.assertFalse(ConversaAdocao.objects.exists())
        self.assertFalse(MensagemAdocao.objects.exists())
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.get(self.url('conversa_mensagens')).status_code, 404)
        self.assertEqual(self.client.get(self.url('minhas_conversas')).context['pagina'].paginator.count, 0)
        self.assertEqual(self.nao_lidas(self.adotante), 0)
