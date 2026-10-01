from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ongs.models import Ong
from pets.models import Pet
from supervisores.adocoes import DecisaoAdocaoForm
from usuarios.models import Perfil

from .contato_adocao import contato_para_retirada, mensagem_aprovacao
from .models import SolicitacaoAdocao
from .solicitacao_service import decidir_solicitacao


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FeedbackAdocaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.dono = User.objects.create_user('responsavel', first_name='Ana', last_name='Silva')
        cls.interessado = User.objects.create_user('interessado-feedback')
        cls.outro = User.objects.create_user('outro-feedback')
        cls.admin = User.objects.create_superuser('admin-feedback', 'admin@example.com', 'teste')
        cls.supervisor = User.objects.create_user('supervisor-feedback')
        cls.supervisor.groups.add(Group.objects.get(name='Supervisores'))
        for usuario, telefone in ((cls.dono, '81987654321'), (cls.admin, '11911112222')):
            Perfil.objects.create(
                usuario=usuario, telefone=telefone, cidade='Recife', estado='PE',
                aceitou_termos_em=timezone.now(), versao_termos='1',
            )
        cls.pet = Pet.objects.create(
            nome='Amora', especie='gato', cidade='Recife', estado='PE',
            responsavel=cls.dono, criado_por=cls.admin, status=Pet.Status.PUBLICADO,
            telefone_contato='(81) 98888-7777',
        )

    def pedido(self, **campos):
        return SolicitacaoAdocao.objects.create(
            pet=self.pet, usuario=self.interessado, mensagem='Quero oferecer um lar seguro.', **campos,
        )

    def detalhe(self, pedido):
        self.client.force_login(self.interessado)
        return self.client.get(reverse('adocao_detalhe', args=[pedido.pk]))

    def test_contato_do_anuncio_tem_preferencia_e_links_com_ddd_e_pais(self):
        contato = contato_para_retirada(self.pet)
        self.assertEqual(contato['nome'], 'Ana Silva')
        self.assertEqual(contato['telefone'], '(81) 98888-7777')
        self.assertEqual(contato['telefone_url'], 'tel:+5581988887777')
        whatsapp = urlsplit(contato['whatsapp_url'])
        self.assertEqual((whatsapp.scheme, whatsapp.netloc, whatsapp.path),
                         ('https', 'wa.me', '/5581988887777'))
        mensagem = parse_qs(whatsapp.query)['text'][0]
        self.assertIn('Amora', mensagem)
        self.assertIn('dia, horário e local', mensagem)

    def test_telefone_fixo_e_prefixo_internacional_sao_formatados(self):
        for numero, formatado, link in (
            ('+55 (81) 98888-7777', '(81) 98888-7777', 'tel:+5581988887777'),
            ('8132224444', '(81) 3222-4444', 'tel:+558132224444'),
            ('+55 81 3222-4444', '(81) 3222-4444', 'tel:+558132224444'),
        ):
            with self.subTest(numero=numero):
                self.pet.telefone_contato = numero
                contato = contato_para_retirada(self.pet)
                self.assertEqual(contato['telefone'], formatado)
                self.assertEqual(contato['telefone_url'], link)

    def test_contato_invalido_usa_perfil_do_responsavel_e_nao_criador_admin(self):
        for numero in ('', 'não informado', '1234'):
            with self.subTest(numero=numero):
                self.pet.telefone_contato = numero
                contato = contato_para_retirada(self.pet)
                self.assertEqual(contato['nome'], 'Ana Silva')
                self.assertEqual(contato['telefone_url'], 'tel:+5581987654321')
                self.assertNotIn('11911112222', contato['telefone_url'])

    def test_ong_usa_contato_publico_e_fallback_do_responsavel_da_ong(self):
        self.pet.ong = Ong.objects.create(
            nome='Lar Amigo', responsavel=self.dono, telefone='8133334444',
            cidade='Recife', estado='PE', status=Ong.Status.APROVADA,
        )
        self.pet.responsavel = self.admin
        contato = contato_para_retirada(self.pet)
        self.assertEqual(contato['nome'], 'Lar Amigo')
        self.assertEqual(contato['telefone_url'], 'tel:+558133334444')
        self.pet.ong.telefone = ''
        contato = contato_para_retirada(self.pet)
        self.assertEqual(contato['telefone_url'], 'tel:+5581987654321')

    def test_anuncio_sem_responsavel_usa_criador(self):
        self.pet.responsavel = None
        self.pet.telefone_contato = ''
        contato = contato_para_retirada(self.pet)
        self.assertEqual(contato['nome'], 'admin-feedback')
        self.assertEqual(contato['telefone_url'], 'tel:+5511911112222')

    def test_sem_numero_valido_nao_gera_link_quebrado_e_orienta_suporte(self):
        self.pet.responsavel = self.outro
        self.pet.telefone_contato = ''
        contato = contato_para_retirada(self.pet)
        self.assertEqual(contato['telefone'], '')
        self.assertEqual(contato['telefone_url'], '')
        self.assertEqual(contato['whatsapp_url'], '')
        self.assertIn('Abra um chamado', mensagem_aprovacao(self.pet))
        self.pet.save(update_fields=['responsavel', 'telefone_contato'])
        pedido = self.pedido(status=SolicitacaoAdocao.Status.APROVADA)
        resposta = self.detalhe(pedido)
        self.assertContains(resposta, 'Pedir ajuda para combinar a retirada')
        self.assertNotContains(resposta, 'https://wa.me/')

    def test_aprovar_sem_resposta_persiste_feedback_e_orientacao_de_retirada(self):
        pedido = self.pedido()
        decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.admin, aprovar=True, resposta='   ')
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, SolicitacaoAdocao.Status.APROVADA)
        self.assertIn('foi aprovado', pedido.resposta)
        self.assertIn('Ana Silva', pedido.resposta)
        self.assertIn('(81) 98888-7777', pedido.resposta)
        self.assertIn('dia, horário e local', pedido.resposta)
        resposta = self.detalhe(pedido)
        self.assertContains(resposta, 'Sua adoção foi aprovada!')
        self.assertContains(resposta, pedido.resposta)
        self.assertContains(resposta, 'href="tel:+5581988887777"')
        self.assertContains(resposta, 'Combinar pelo WhatsApp')

    def test_resposta_personalizada_e_preservada_com_contato_separado(self):
        pedido = self.pedido()
        texto = 'A entrevista foi concluída. Prepare a caixa de transporte.'
        decidir_solicitacao(solicitacao_id=pedido.pk, ator=self.supervisor, aprovar=True, resposta=texto)
        pedido.refresh_from_db()
        self.assertEqual(pedido.resposta, texto)
        resposta = self.detalhe(pedido)
        self.assertContains(resposta, texto)
        self.assertContains(resposta, 'Combine a retirada de Amora')
        self.assertContains(resposta, '(81) 98888-7777')
        self.assertContains(resposta, 'Ligar para o responsável')

    def test_aprovacao_antiga_sem_resposta_exibe_orientacao_sem_mutar_registro(self):
        pedido = self.pedido(status=SolicitacaoAdocao.Status.APROVADA)
        atualizado = pedido.atualizado_em
        resposta = self.detalhe(pedido)
        self.assertContains(resposta, 'Seu pedido de adoção de Amora foi aprovado!')
        self.assertContains(resposta, '(81) 98888-7777')
        pedido.refresh_from_db()
        self.assertEqual(pedido.resposta, '')
        self.assertEqual(pedido.atualizado_em, atualizado)

    def test_equipe_visualiza_orientacao_de_aprovacao_antiga_sem_mutar_registro(self):
        pedido = self.pedido(status=SolicitacaoAdocao.Status.APROVADA)
        atualizado = pedido.atualizado_em
        for usuario, rota in (
            (self.admin, 'admin:adocoes_solicitacaoadocao_analisar'),
            (self.supervisor, 'supervisores:adocao_detalhe'),
        ):
            with self.subTest(rota=rota):
                self.client.force_login(usuario)
                resposta = self.client.get(reverse(rota, args=[pedido.pk]))
                self.assertContains(resposta, 'Seu pedido de adoção de Amora foi aprovado!')
                self.assertContains(resposta, '(81) 98888-7777')
        pedido.refresh_from_db()
        self.assertEqual(pedido.resposta, '')
        self.assertEqual(pedido.atualizado_em, atualizado)

    def test_pedido_nao_aprovado_nao_expoe_telefone_privado_do_perfil(self):
        self.pet.telefone_contato = ''
        self.pet.save(update_fields=['telefone_contato'])
        pedido = self.pedido()
        for status in (SolicitacaoAdocao.Status.PENDENTE, SolicitacaoAdocao.Status.RECUSADA,
                       SolicitacaoAdocao.Status.CANCELADA):
            with self.subTest(status=status):
                pedido.status = status
                pedido.save(update_fields=['status'])
                resposta = self.detalhe(pedido)
                self.assertIsNone(resposta.context['contato_retirada'])
                self.assertNotContains(resposta, '(81) 98765-4321')
                self.assertNotContains(resposta, '5581987654321')
                self.assertNotContains(resposta, 'Combinar pelo WhatsApp')

    def test_contato_aprovado_nao_fica_acessivel_a_outro_usuario(self):
        pedido = self.pedido(status=SolicitacaoAdocao.Status.APROVADA)
        self.client.force_login(self.outro)
        resposta = self.client.get(reverse('adocao_detalhe', args=[pedido.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertNotContains(resposta, '(81) 98888-7777', status_code=404)

    def test_formulario_sugere_numero_na_aprovacao_e_motivo_na_recusa(self):
        form = DecisaoAdocaoForm(pet=self.pet)
        attrs = form.fields['resposta'].widget.attrs
        self.assertIn('(81) 98888-7777', attrs['placeholder'])
        self.assertIn('dia, horário e local', attrs['placeholder'])
        self.assertEqual(attrs['placeholder'], attrs['data-placeholder-aprovacao'])
        self.assertEqual(list(form.fields), ['acao', 'resposta'])
        recusa = DecisaoAdocaoForm({'acao': 'recusar', 'resposta': ''}, pet=self.pet)
        self.assertFalse(recusa.is_valid())
        self.assertIn('resposta', recusa.errors)
        self.assertNotIn('(81) 98888-7777', recusa.fields['resposta'].widget.attrs['placeholder'])
        self.assertIn('Explique', recusa.fields['resposta'].widget.attrs['placeholder'])
        aprovar = DecisaoAdocaoForm({'acao': 'aprovar', 'resposta': ''}, pet=self.pet)
        self.assertTrue(aprovar.is_valid())

    def test_admin_confirma_aprovacao_com_feedback_visivel(self):
        pedido = self.pedido()
        self.client.force_login(self.admin)
        resposta = self.client.post(
            reverse('admin:adocoes_solicitacaoadocao_analisar', args=[pedido.pk]),
            {'acao': 'aprovar', 'resposta': ''}, follow=True,
        )
        self.assertContains(resposta, 'Adoção de Amora aprovada!')
        self.assertContains(resposta, 'Minhas adoções do interessado')
        pedido.refresh_from_db()
        self.assertIn('(81) 98888-7777', pedido.resposta)

    def test_supervisor_confirma_aprovacao_com_feedback_visivel(self):
        pedido = self.pedido()
        self.client.force_login(self.supervisor)
        resposta = self.client.post(
            reverse('supervisores:adocao_detalhe', args=[pedido.pk]),
            {'acao': 'aprovar', 'resposta': ''}, follow=True,
        )
        self.assertContains(resposta, 'Adoção de Amora aprovada!')
        self.assertContains(resposta, 'Minhas adoções do interessado')
        pedido.refresh_from_db()
        self.assertIn('(81) 98888-7777', pedido.resposta)
