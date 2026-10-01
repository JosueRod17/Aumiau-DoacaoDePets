"""Conversas particulares entre os participantes de uma adoção aprovada."""
from datetime import timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from usuarios.models import Perfil

from .models import ConversaAdocao, MensagemAdocao, SolicitacaoAdocao


def conta_disponivel(usuario_id):
    return bool(usuario_id) and get_user_model().objects.filter(
        pk=usuario_id, is_active=True,
    ).exists() and not Perfil.objects.filter(usuario_id=usuario_id).exclude(
        situacao=Perfil.Situacao.ATIVA,
    ).exists()


def usuario_disponivel(usuario):
    return bool(usuario and usuario.is_authenticated and conta_disponivel(usuario.pk))


@transaction.atomic
def criar_conversa(solicitacao):
    """Congela o anunciante ao aprovar; pedidos sem responsável usam o suporte."""
    solicitacao = SolicitacaoAdocao.objects.select_for_update().get(pk=solicitacao.pk)
    if solicitacao.status != SolicitacaoAdocao.Status.APROVADA:
        return None
    existente = ConversaAdocao.objects.filter(solicitacao=solicitacao).first()
    if existente:
        return existente
    pet = solicitacao.pet
    anunciante_id = (
        pet.ong.responsavel_id if pet.ong_id and pet.ong.responsavel_id else
        pet.responsavel_id or pet.criado_por_id
    )
    if not anunciante_id or anunciante_id == solicitacao.usuario_id:
        return None
    conversa, _ = ConversaAdocao.objects.get_or_create(
        solicitacao=solicitacao, defaults={'anunciante_id': anunciante_id},
    )
    return conversa


def conversas_do_usuario(usuario):
    conversas = ConversaAdocao.objects.select_related(
        'solicitacao__pet', 'solicitacao__usuario', 'anunciante',
    )
    if not usuario.is_authenticated or not conta_disponivel(usuario.pk):
        return conversas.none()
    return conversas.filter(solicitacao__status=SolicitacaoAdocao.Status.APROVADA).filter(
        Q(solicitacao__usuario_id=usuario.pk) | Q(anunciante_id=usuario.pk),
    )


@transaction.atomic
def enviar_mensagem(*, conversa_id, usuario, texto, cliente_id):
    """Retorna (mensagem, criada); repetir o identificador não duplica o envio."""
    if not usuario.is_authenticated or not conta_disponivel(usuario.pk):
        raise PermissionDenied('Sua conta precisa estar ativa para enviar mensagens.')
    # A trava da conversa serializa envios e torna a limitação de frequência e
    # a chave de idempotência consistentes também em múltiplos processos.
    try:
        conversa = ConversaAdocao.objects.select_for_update().get(pk=conversa_id)
    except ConversaAdocao.DoesNotExist as exc:
        raise Http404('Conversa não encontrada.') from exc
    solicitacao = conversa.solicitacao
    if usuario.pk not in {solicitacao.usuario_id, conversa.anunciante_id}:
        raise Http404('Conversa não encontrada.')
    if solicitacao.status != SolicitacaoAdocao.Status.APROVADA:
        raise ValidationError('O chat está disponível somente após a aprovação da adoção.')
    outro_id = (
        conversa.anunciante_id if usuario.pk == solicitacao.usuario_id
        else solicitacao.usuario_id
    )
    if not conta_disponivel(outro_id):
        raise PermissionDenied('O outro participante está indisponível. Entre em contato com o suporte.')
    try:
        identificador = UUID(str(cliente_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('Identificador de envio inválido. Atualize a página e tente novamente.') from exc
    existente = MensagemAdocao.objects.filter(
        conversa=conversa, autor_id=usuario.pk, cliente_id=identificador,
    ).first()
    if existente:
        if not isinstance(texto, str) or existente.texto != texto.strip():
            raise ValidationError('Este envio já foi recebido com outro texto. Atualize a página antes de enviar uma nova mensagem.')
        return existente, False
    if not isinstance(texto, str) or not texto.strip():
        raise ValidationError('Escreva uma mensagem antes de enviar.')
    texto = texto.strip()
    if len(texto) > 2000:
        raise ValidationError('A mensagem deve ter no máximo 2000 caracteres.')
    agora = timezone.now()
    if MensagemAdocao.objects.filter(
        conversa=conversa, autor_id=usuario.pk, criado_em__gt=agora - timedelta(seconds=2),
    ).exists():
        raise ValidationError('Aguarde dois segundos antes de enviar outra mensagem.')
    mensagem = MensagemAdocao.objects.create(
        conversa=conversa, autor_id=usuario.pk, texto=texto, cliente_id=identificador,
    )
    conversa.ultima_mensagem_em = mensagem.criado_em
    conversa.save(update_fields=['ultima_mensagem_em'])
    return mensagem, True
