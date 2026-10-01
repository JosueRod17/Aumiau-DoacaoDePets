"""Contato usado na análise e exibido somente ao solicitante aprovado."""
import re
from urllib.parse import urlencode


def _telefone_brasileiro(valor):
    digitos = re.sub(r'\D', '', valor or '')
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return '', ''
    return f'({digitos[:2]}) {digitos[2:-4]}-{digitos[-4:]}', '55' + digitos


def contato_para_retirada(pet):
    if pet.ong_id:
        responsavel = pet.ong.responsavel
        nome = pet.ong.nome
        telefone = pet.ong.telefone
    else:
        responsavel = pet.responsavel or pet.criado_por
        nome = (responsavel.get_full_name() or responsavel.username) if responsavel else 'a equipe responsável'
        telefone = pet.telefone_contato
    numero, digitos = _telefone_brasileiro(telefone)
    if not numero and responsavel:
        perfil = getattr(responsavel, 'perfil', None)
        numero, digitos = _telefone_brasileiro(perfil.telefone if perfil else '')
    texto = f'Olá! Meu pedido de adoção de {pet.nome} foi aprovado no AuMiau. Podemos combinar o dia, horário e local da retirada?'
    return {
        'nome': nome, 'telefone': numero,
        'telefone_url': f'tel:+{digitos}' if digitos else '',
        'whatsapp_url': f'https://wa.me/{digitos}?' + urlencode({'text': texto}) if digitos else '',
    }


def mensagem_aprovacao(pet):
    contato = contato_para_retirada(pet)
    inicio = f'Seu pedido de adoção de {pet.nome} foi aprovado! '
    if contato['telefone']:
        return (inicio + f"Entre em contato com {contato['nome']} pelo número {contato['telefone']} "
                f'para combinar o dia, horário e local da retirada de {pet.nome}.')
    return (inicio + 'O responsável ainda não possui telefone disponível. '
            'Abra um chamado em Fale conosco para a equipe ajudar a combinar o dia, horário e local da retirada.')
