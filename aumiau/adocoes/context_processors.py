from django.db.models import F, Q

from .chat_service import usuario_disponivel
from .models import MensagemAdocao


def mensagens_chat(request):
    if not usuario_disponivel(request.user):
        return {'mensagens_chat_nao_lidas': 0}
    mensagens = MensagemAdocao.objects.filter(conversa__solicitacao__status='aprovada').filter(
        Q(conversa__solicitacao__usuario=request.user, pk__gt=F('conversa__ultimo_lido_adotante_id'))
        | Q(conversa__anunciante=request.user, pk__gt=F('conversa__ultimo_lido_anunciante_id'))
    ).exclude(autor=request.user)
    return {'mensagens_chat_nao_lidas': mensagens.count()}
