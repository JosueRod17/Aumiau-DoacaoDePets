"""Dígitos verificadores e consulta cadastral de organizações na BrasilAPI."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone


def normalizar_cnpj(valor):
    return re.sub(r'[.\s/\-]', '', str(valor or '')).upper()


def validar_cnpj(valor):
    cnpj = normalizar_cnpj(valor)
    if not re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', cnpj) or len(set(cnpj)) == 1:
        raise ValidationError('Informe um CNPJ válido, com 14 caracteres.')
    base = [ord(caractere) - 48 for caractere in cnpj[:12]]
    for pesos in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        resto = sum(numero * peso for numero, peso in zip(base, pesos)) % 11
        base.append(0 if resto < 2 else 11 - resto)
    if cnpj[-2:] != ''.join(str(digito) for digito in base[-2:]):
        raise ValidationError('Os dígitos do CNPJ não conferem. Confira o número informado.')
    return cnpj


def consultar_cnpj(valor):
    """Retorna só os dados necessários; não retém sócios/endereço da resposta."""
    cnpj = validar_cnpj(valor)
    # A documentação atual da BrasilAPI só admite 14 dígitos numéricos.
    # O formato alfanumérico passa pela conferência documental da supervisão.
    if not cnpj.isdigit():
        return None
    chave = f'cnpj:brasilapi:v1:{cnpj}'
    salvo = cache.get(chave)
    if salvo:
        return salvo
    pedido = Request(f'https://brasilapi.com.br/api/cnpj/v1/{cnpj}', headers={
        'Accept': 'application/json', 'User-Agent': 'AuMiau/1.0 (consulta cadastral de ONG)',
    })
    try:
        with urlopen(pedido, timeout=5) as resposta:
            conteudo = resposta.read(100001)
            if len(conteudo) > 100000:
                raise ValueError
            dados = json.loads(conteudo)
    except HTTPError as erro:
        if erro.code == 404:
            raise ValidationError('CNPJ não encontrado na consulta pública. Confira o número ou fale com o suporte.') from None
        if erro.code == 400:
            raise ValidationError('O serviço de consulta não reconheceu este CNPJ. Confira o número.') from None
        raise ValidationError('A consulta de CNPJ está indisponível. Seus campos foram mantidos; tente novamente em instantes.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ValidationError('Não foi possível consultar o CNPJ agora. Seus campos foram mantidos; tente novamente em instantes.') from None
    if not isinstance(dados, dict) or normalizar_cnpj(dados.get('cnpj')) != cnpj or not dados.get('razao_social'):
        raise ValidationError('O serviço retornou uma resposta incompleta. Tente consultar o CNPJ novamente.')
    if dados.get('situacao_cadastral') != 2:
        raise ValidationError('O CNPJ não consta como ativo na consulta pública. Confira a situação cadastral antes de continuar.')
    resultado = {
        'razao_social': str(dados['razao_social'])[:200],
        'situacao': 'ATIVA',
        'consultado_em': timezone.now(),
    }
    cache.set(chave, resultado, 3600)
    return resultado
