"""Validação matemática do CPF; não consulta nem comprova identidade na Receita."""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.crypto import salted_hmac


def normalizar_cpf(valor):
    valor = str(valor or '').strip()
    if not re.fullmatch(r'[0-9.\-\s]+', valor):
        raise ValidationError('Informe um CPF válido com 11 dígitos.')
    cpf = re.sub(r'\D', '', valor)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValidationError('Informe um CPF válido com 11 dígitos.')
    for quantidade in (9, 10):
        soma = sum(int(cpf[i]) * (quantidade + 1 - i) for i in range(quantidade))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[quantidade]):
            raise ValidationError('Os dígitos verificadores do CPF são inválidos.')
    return cpf


def assinatura_cpf(valor):
    cpf = normalizar_cpf(valor)
    chave = getattr(settings, 'DOCUMENT_HASH_KEY', '') or settings.SECRET_KEY
    return salted_hmac('aumiau.cpf.v1', cpf, secret=chave, algorithm='sha256').hexdigest()


def validar_cpf_disponivel(valor):
    from .models import DocumentoBloqueado, Perfil
    cpf = normalizar_cpf(valor)
    assinatura = assinatura_cpf(cpf)
    if (Perfil.objects.filter(cpf_hash=assinatura).exists()
            or DocumentoBloqueado.objects.filter(cpf_hash=assinatura).exists()):
        raise ValidationError('Não é possível cadastrar este CPF. Entre em contato com o suporte.')
    return cpf
