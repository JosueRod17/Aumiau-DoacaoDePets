import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .cnpj import consultar_cnpj, validar_cnpj


class ConsultaCnpjTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def resposta(self, **dados):
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = json.dumps({
            'cnpj': '19131243000197', 'razao_social': 'Associação exemplo',
            'situacao_cadastral': 2, 'qsa': [{'nome_socio': 'Não reter'}], **dados,
        }).encode()
        return resposta

    def test_digitos_numericos_e_alfanumericos_da_receita(self):
        self.assertEqual(validar_cnpj('19.131.243/0001-97'), '19131243000197')
        self.assertEqual(validar_cnpj('00.000.000/e08g-12'), '00000000E08G12')
        for cnpj in ('11111111111111', '19131243000198', '19$131243000197', '00000000E08G13'):
            with self.subTest(cnpj=cnpj), self.assertRaises(ValidationError):
                validar_cnpj(cnpj)

    @patch('ongs.cnpj.urlopen')
    def test_consulta_ativa_cache_e_minimizacao_de_dados(self, abrir):
        abrir.return_value = self.resposta()
        dados = consultar_cnpj('19131243000197')
        self.assertEqual(dados['situacao'], 'ATIVA')
        self.assertEqual(set(dados), {'situacao', 'razao_social', 'consultado_em'})
        self.assertEqual(consultar_cnpj('19131243000197'), dados)
        abrir.assert_called_once()
        self.assertEqual(abrir.call_args.kwargs['timeout'], 5)

    @patch('ongs.cnpj.urlopen')
    def test_api_invalida_nao_expoe_dados_nem_da_falso_positivo(self, abrir):
        for dados in ({'situacao_cadastral': 8}, {'cnpj': '00000000000191'}, {'razao_social': ''}):
            with self.subTest(dados=dados):
                abrir.return_value = self.resposta(**dados)
                with self.assertRaises(ValidationError):
                    consultar_cnpj('19131243000197')

    @patch('ongs.cnpj.urlopen')
    def test_timeout_limite_e_nao_encontrado(self, abrir):
        for erro in (TimeoutError(), URLError('offline'), HTTPError('url', 404, '', {}, None), HTTPError('url', 429, '', {}, None)):
            with self.subTest(erro=type(erro).__name__):
                abrir.side_effect = erro
                with self.assertRaises(ValidationError):
                    consultar_cnpj('19131243000197')

    @patch('ongs.cnpj.urlopen')
    def test_alfanumerico_nao_e_enviado_para_api_que_so_aceita_numerico(self, abrir):
        self.assertIsNone(consultar_cnpj('00000000E08G12'))
        abrir.assert_not_called()
